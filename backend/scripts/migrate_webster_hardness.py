# -*- coding: utf-8 -*-
"""把韋伯標度的硬度由「硬度」遷移到「韋伯氏硬度」（公差項目 + 出貨量測明細）。

背景：量測項目「硬度」同時被用於兩種標度——安泰等廠商填洛氏(HRB 約50~90)，
品岳等廠商填韋伯(HW 約3~20)。公差主檔同樣混用，因此無法只改其中一邊：
只改公差會使量測配對不到公差而靜默不判定（實測會讓 439 筆由超差變合格）。
本腳本在同一交易內同時遷移兩邊，維持判定連續性。

判定歸屬一律**以公差為準**（規格才是權威），不以量測值量級推測：
  該出貨紀錄查到的硬度公差項目為待遷移的韋伯公差 → 量測明細改為韋伯氏硬度
  查到「洛氏硬度」或查無硬度公差 → 一律不動
久鼎同時存在兩種標度，故必須逐紀錄查公差，不可整廠商套用。

前置條件（缺一不可，否則遷移後會靜默不判定或無欄位可填）：
  1. models.items_to_check 已納入韋伯氏硬度
  2. 出貨表單已能依公差顯示韋伯氏硬度欄

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.migrate_webster_hardness
    .\\venv\\Scripts\\python.exe -m backend.scripts.migrate_webster_hardness --apply
"""
import sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import (ShippingData, ShippingMeasurement, Vendor,
                      VendorToleranceDetail, VendorToleranceMain)
from ..services.tolerance_service import ToleranceService

SOURCE_ITEM = '硬度'
TARGET_ITEM = '韋伯氏硬度'
WEBSTER_UNITS = ('hw', 'w', '韋伯', '韋氏')
ROCKWELL_MAX = 30  # 洛氏下限普遍 >= 50、韋伯 <= 20；用於標記值與公差矛盾者


def _is_webster_detail(detail) -> bool:
    """僅依單位欄位認定韋伯，避免把未標單位者誤遷移。"""
    unit = (detail.unit or '').strip().lower()
    return bool(unit) and any(token in unit for token in WEBSTER_UNITS)


def main(apply: bool):
    with app.app_context():
        vendors = {v.id: v.name for v in Vendor.query.all()}
        mains = {m.id: m for m in VendorToleranceMain.query.all()}

        # 待遷移的公差列：項目仍為「硬度」且單位標明韋伯
        webster_details = [
            d for d in VendorToleranceDetail.query.filter(
                VendorToleranceDetail.item == SOURCE_ITEM).all()
            if _is_webster_detail(d)
        ]
        detail_ids = {d.id for d in webster_details}

        print('=' * 78)
        print(f'  待遷移公差列（項目=硬度 且單位為韋伯）：{len(webster_details)} 筆')
        by_vendor = Counter(
            vendors.get(mains[d.main_id].vendor_id) if d.main_id in mains else '?'
            for d in webster_details)
        for name, count in by_vendor.most_common():
            print(f'     {name or "(未指定)":<8}{count:4} 筆')
        print('=' * 78)

        # 逐出貨紀錄查公差，判斷其硬度量測是否屬韋伯
        cache: dict[tuple, bool] = {}
        migrate_rows: list[ShippingMeasurement] = []
        per_vendor = Counter()
        anomalies = []
        for sd in ShippingData.query.all():
            key = (sd.material, sd.spec, sd.vendor_id)
            if key not in cache:
                result = ToleranceService.check_tolerance({
                    'material': sd.material, 'spec': sd.spec, 'vendor_id': sd.vendor_id})
                is_webster = False
                if result.get('found'):
                    for item in (result.get('tolerances') or []):
                        # check_tolerance 不回傳 detail id，改以（項目、下限、單位）比對
                        if item.get('項目') != SOURCE_ITEM:
                            continue
                        unit = (item.get('單位') or '').strip().lower()
                        if unit and any(token in unit for token in WEBSTER_UNITS):
                            is_webster = True
                cache[key] = is_webster
            if not cache[key]:
                continue
            for measurement in sd.measurements:
                if measurement.item != SOURCE_ITEM:
                    continue
                migrate_rows.append(measurement)
                per_vendor[vendors.get(sd.vendor_id)] += 1
                value = measurement.value_single or measurement.value_max
                if value is not None and float(value) >= ROCKWELL_MAX:
                    anomalies.append((sd.id, vendors.get(sd.vendor_id), sd.material,
                                      sd.spec, float(value)))

        print(f'\n  待遷移量測明細：{len(migrate_rows)} 列')
        for name, count in per_vendor.most_common():
            print(f'     {name or "(未指定)":<8}{count:6} 列')

        # 唯一鍵（紀錄×項目×位置×組別）衝突檢查
        existing = defaultdict(set)
        for m in ShippingMeasurement.query.filter(
                ShippingMeasurement.item == TARGET_ITEM).all():
            existing[m.shipping_id].add((m.group_num, m.position))
        conflicts = [m for m in migrate_rows
                     if (m.group_num, m.position) in existing.get(m.shipping_id, ())]
        print(f'\n  唯一鍵衝突：{len(conflicts)} 列')

        if anomalies:
            print(f'\n  ⚠ 值屬洛氏量級（>= {ROCKWELL_MAX}）卻歸於韋伯公差：{len(anomalies)} 列')
            for row in anomalies[:10]:
                print(f'     出貨 #{row[0]} {row[1]} {row[2]} {row[3]} 值={row[4]}')
            print('     （仍依公差遷移；請另行核對是否為填錯標度）')

        if conflicts:
            print('\n  ❌ 有唯一鍵衝突，中止遷移。請先人工處理上述紀錄。')
            return

        if not apply:
            print('\n  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際遷移。')
            return

        for detail in webster_details:
            detail.item = TARGET_ITEM
        for measurement in migrate_rows:
            measurement.item = TARGET_ITEM
        db.session.commit()
        print(f'\n  ✅ 已遷移公差 {len(detail_ids)} 筆、量測明細 {len(migrate_rows)} 列。')
        print('     請接著執行 recompute_shipping_is_ng --all 驗證判定連續性。')


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
