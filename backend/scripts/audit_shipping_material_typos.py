# -*- coding: utf-8 -*-
"""稽核出貨檢驗的材質欄輸入錯誤（查不到公差者）。

背景：材質是自由輸入，實際存在缺連字號（7075T651）、字元混淆（2014-0 的零與
O）、漏字（204-O、601-PT、707-T651）等錯誤。材質錯就查不到廠商公差，該筆的
所有項目都不會判定，等同靜默放行。

比對方式：只處理「寫法本身不是系統中任何合法材質」者——例如 7075T651（缺
連字號）、2014-0（零非回火代號）、204-O／601-PT／707-T651（漏字）。
從該廠商公差主檔登錄過的材質中找候選，依序嘗試
  1. 正規化後相同（去連字號、大寫、O/0 視為同形）
  2. 編輯距離 1（單一字元增刪改）
唯一候選才視為可自動更正；多個或無候選一律列出供人工判斷。

【重要】材質本身是合法值（如 6061-T6、7075-O）卻查不到公差時**一律不更正**：
6061 與 6066、7075 與 7005 是不同合金，F/O/H 是不同回火狀態，逕自「更正」
等同竄改檢驗紀錄。那類情形屬公差主檔未建該材質，應補建公差而非改紀錄。

本腳本預設唯讀；--apply 只更正「唯一候選」者。材質變更會改變適用公差，
更正後請執行 recompute_shipping_is_ng --all 重算判定。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_shipping_material_typos
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_shipping_material_typos --apply
"""
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import ShippingData, Vendor, VendorToleranceMain
from ..services.tolerance_service import ToleranceService


def _normalize(material: str) -> str:
    """去連字號與空白、轉大寫，並把數字 0 視為字母 O（回火代號常見混淆）。"""
    text = (material or '').strip().upper().replace('-', '').replace(' ', '')
    return text.replace('0', 'O')


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    """判斷兩字串是否僅差一次字元增／刪／改。"""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    i = j = 0
    skipped = False
    while i < len(shorter) and j < len(longer):
        if shorter[i] == longer[j]:
            i += 1
            j += 1
            continue
        if skipped:
            return False
        skipped = True
        j += 1
    return True


def _candidates(material: str, known: set[str]) -> list[str]:
    """回傳可能的正確材質；正規化相同者優先，無則退到編輯距離 1。"""
    target = _normalize(material)
    exact = sorted({k for k in known if _normalize(k) == target and k != material})
    if exact:
        return exact
    return sorted({
        k for k in known
        if k != material and _edit_distance_at_most_one(_normalize(k), target)
    })


def main(apply: bool):
    with app.app_context():
        vendors = {v.id: v.name for v in Vendor.query.all()}

        # 各廠商公差主檔登錄過的材質，作為候選來源；
        # 全系統合法材質集合則用來判斷「寫法本身是否為合法材質」。
        known_by_vendor: dict[int, set[str]] = defaultdict(set)
        all_known: set[str] = set()
        for main_row in VendorToleranceMain.query.all():
            if main_row.material and main_row.material.strip():
                known_by_vendor[main_row.vendor_id].add(main_row.material.strip())
                all_known.add(main_row.material.strip())

        cache: dict[tuple, bool] = {}
        unique_fix, ambiguous, no_candidate, legitimate = [], [], [], []
        for shipping in ShippingData.query.order_by(ShippingData.id).all():
            material = (shipping.material or '').strip()
            key = (material, shipping.spec, shipping.vendor_id)
            if key not in cache:
                result = ToleranceService.check_tolerance({
                    'material': material, 'spec': shipping.spec,
                    'vendor_id': shipping.vendor_id})
                cache[key] = bool(result.get('found'))
            if cache[key]:
                continue  # 查得到公差，材質無誤
            # 材質本身是系統中的合法值 → 屬公差主檔未建該材質，不得逕自更改紀錄
            if material and material in all_known:
                legitimate.append((shipping, material, []))
                continue
            known = known_by_vendor.get(shipping.vendor_id, set())
            options = _candidates(material, known) if material else []
            row = (shipping, material, options)
            if len(options) == 1:
                unique_fix.append(row)
            elif options:
                ambiguous.append(row)
            else:
                no_candidate.append(row)

        print('=' * 84)
        print(f'  查不到公差的紀錄：'
              f'{len(unique_fix) + len(ambiguous) + len(no_candidate) + len(legitimate)} 筆')
        print(f'  其中材質寫法本身即非合法值（疑似輸入錯誤）：'
              f'{len(unique_fix) + len(ambiguous) + len(no_candidate)} 筆')
        print('=' * 84)

        print(f'\n■ 唯一候選（可自動更正）：{len(unique_fix)} 筆')
        for shipping, material, options in unique_fix:
            print(f'  #{shipping.id:<6}{vendors.get(shipping.vendor_id) or "(未指定)":<6}'
                  f'{material or "(空白)":<14}→ {options[0]:<14}規格={shipping.spec}')

        if ambiguous:
            print(f'\n■ 多個候選（須人工判斷）：{len(ambiguous)} 筆')
            for shipping, material, options in ambiguous:
                print(f'  #{shipping.id:<6}{vendors.get(shipping.vendor_id) or "(未指定)":<6}'
                      f'{material or "(空白)":<14}→ {"、".join(options)}　規格={shipping.spec}')

        if no_candidate:
            print(f'\n■ 無候選（公差主檔可能未建該材質）：{len(no_candidate)} 筆')
            for shipping, material, _ in no_candidate:
                print(f'  #{shipping.id:<6}{vendors.get(shipping.vendor_id) or "(未指定)":<6}'
                      f'{material or "(空白)":<14}規格={shipping.spec}')

        if legitimate:
            combos = sorted({
                (vendors.get(s.vendor_id) or '(未指定)', m) for s, m, _ in legitimate
            })
            print(f'\n■ 材質合法但查無公差：{len(legitimate)} 筆 / {len(combos)} 種組合')
            print('  （屬公差主檔未建該材質，應補建公差而非更改紀錄）')
            for vendor_name, material in combos[:20]:
                count = sum(1 for s, m, _ in legitimate
                            if (vendors.get(s.vendor_id) or '(未指定)') == vendor_name and m == material)
                print(f'  {vendor_name:<8}{material:<14}{count:5} 筆')
            if len(combos) > 20:
                print(f'  …另有 {len(combos) - 20} 種組合')

        if not apply:
            print('\n  ℹ️  唯讀稽核，未變更任何資料。')
            print('     確認後可加 --apply 更正「唯一候選」者；更正後材質適用的公差會改變，')
            print('     請接著執行 recompute_shipping_is_ng --all 重算判定。')
            return

        for shipping, _material, options in unique_fix:
            shipping.material = options[0]
        db.session.commit()
        print(f'\n  ✅ 已更正 {len(unique_fix)} 筆材質。')
        print('     請執行 recompute_shipping_is_ng --all 重算判定。')


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
