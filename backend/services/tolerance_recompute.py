# -*- coding: utf-8 -*-
"""公差異動後，重新判定受影響紀錄的「是否超差」。

背景：出貨與巡檢紀錄的 is_ng 是存檔當下依當時的公差算出來後凍結的，公差之後才
建立或修改都不會回頭補判。實務上曾累積出 41 筆與現行公差不一致的紀錄——絕大多數
是「存檔時查無公差 → is_ng 凍結為 False」，那是未判定而非合格，統計與 SPC 會失真。

因此公差主檔的新增／修改／刪除都要接上本模組。重判在同一個交易內完成，由呼叫端
負責 commit，公差寫入失敗時重判一起回滾。

兩張公差表影響的紀錄不同：
  * 廠商公差（廠商公差主檔）→ 出貨檢驗數據，另外巡檢也會在查不到擠壓公差時
    退回使用廠商公差（見 ExtrusionToleranceService.check 的第二順位），故兩者都要重判。
  * 擠壓公差（擠壓公差主檔）→ 只影響巡檢主檔。
"""
from sqlalchemy import literal
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import ShippingData, PatrolMain
from ..utils import log_audit


def _shipping_in_scope(material, vendor_id):
    """一筆廠商公差主檔可能被哪些出貨紀錄用到。

    比對規則見 ToleranceService.check_tolerance：主檔材質要「包含」紀錄材質
    （SQL 為 主檔材質 ILIKE '%紀錄材質%'）；主檔有綁廠商時只有該廠商的紀錄會用到它
    （桶 1-4），沒綁廠商則對所有廠商生效（桶 5-8）。

    範圍只要涵蓋「可能匹配本主檔」的紀錄即可——不在候選集裡的紀錄，其比對勝出者
    不會因本主檔的異動而改變。
    """
    query = ShippingData.query.options(selectinload(ShippingData.measurements))
    query = query.filter(ShippingData.material.isnot(None), ShippingData.material != '')
    if material:
        # 用 concat()（渲染成 ||）而非 func.concat，後者在 SQLite 測試環境不存在
        pattern = literal('%').concat(ShippingData.material).concat('%')
        query = query.filter(literal(material).ilike(pattern))
    if vendor_id is not None:
        query = query.filter(ShippingData.vendor_id == vendor_id)
    return query


def recompute_shipping(scopes):
    """重判受影響的出貨紀錄，回傳被翻動的識別碼清單。

    scopes 為 [(材質, 廠商ID), ...]。更新公差時必須同時傳入異動前與異動後的組合，
    只傳新的會漏掉「原本吃這筆公差、改完不再吃」的紀錄。
    """
    from .tolerance_service import ToleranceService

    seen, changed, tol_cache = set(), [], {}
    for material, vendor_id in scopes:
        for record in _shipping_in_scope(material, vendor_id).all():
            if record.id in seen:
                continue
            seen.add(record.id)

            key = (record.material, record.spec, record.vendor_id)
            if key not in tol_cache:
                tol_cache[key] = ToleranceService.check_tolerance({
                    'material': record.material,
                    'spec': record.spec,
                    'vendor_id': record.vendor_id,
                })
            result = tol_cache[key]

            new_is_ng = (
                record.compute_is_ng(result.get('tolerances', []))
                if result.get('found') else False
            )
            if bool(record.is_ng) != new_is_ng:
                record.is_ng = new_is_ng
                changed.append(record.id)
    return changed


def recompute_patrol():
    """重判巡檢紀錄，回傳被翻動的識別碼清單。

    刻意全表掃描而不做範圍過濾：巡檢的公差比對有兩條路徑（先擠壓公差，查不到再退回
    廠商公差），兩條的材質比對語意還不一樣（擠壓是雙向包含、廠商公差是單向），
    分別推算範圍容易漏。巡檢僅數百筆且比對結果有快取，全掃的成本遠低於漏判的代價。
    """
    from .extrusion_tolerance_service import ExtrusionToleranceService
    from .patrol_service import PatrolService

    changed, tol_cache = [], {}
    records = PatrolMain.query.options(selectinload(PatrolMain.details)).all()
    for record in records:
        material = record.material or ''
        spec = record.spec or ''
        key = (material, spec, record.customer_id)
        if key not in tol_cache:
            tol_cache[key] = ExtrusionToleranceService.check({
                'material': material, 'spec': spec, 'vendor_id': record.customer_id})
        new_is_ng = PatrolService._compute_is_ng(
            record.details, material, spec, record.customer_id,
            tol_result=tol_cache[key],
        )
        if bool(record.is_ng) != new_is_ng:
            record.is_ng = new_is_ng
            changed.append(record.id)
    return changed


def after_vendor_tolerance_change(scopes, user_id=None, tolerance_id=None):
    """廠商公差異動後的重判。出貨依 scopes 限縮，巡檢全掃。"""
    shipping = recompute_shipping(scopes)
    patrol = recompute_patrol()
    _log(user_id, '廠商公差', tolerance_id, shipping, patrol)
    return {'shipping': shipping, 'patrol': patrol}


def after_extrusion_tolerance_change(user_id=None, tolerance_id=None):
    """擠壓公差異動後的重判。擠壓公差只被巡檢使用，出貨不受影響。"""
    patrol = recompute_patrol()
    _log(user_id, '擠壓公差', tolerance_id, [], patrol)
    return {'shipping': [], 'patrol': patrol}


def _log(user_id, module, tolerance_id, shipping, patrol):
    """只在真的翻動了紀錄時留痕——公差異動本身已有各自的操作紀錄，
    這條稽核是為了讓「歷史判定被改過」這件事可追溯。"""
    if not shipping and not patrol:
        return
    detail = f'出貨 {len(shipping)} 筆、巡檢 {len(patrol)} 筆重新判定'
    if shipping:
        detail += f'；出貨識別碼 {shipping[:50]}' + ('…' if len(shipping) > 50 else '')
    if patrol:
        detail += f'；巡檢識別碼 {patrol[:50]}' + ('…' if len(patrol) > 50 else '')
    log_audit(user_id, '公差異動重判是否超差', module,
              record_id=tolerance_id, new_val=detail)
