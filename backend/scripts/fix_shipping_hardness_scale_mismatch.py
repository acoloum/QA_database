# -*- coding: utf-8 -*-
"""更正硬度量級與材質所屬標度矛盾的出貨紀錄。

背景：材質決定硬度以哪種標度管制（洛氏 HRB 約 50~90／韋伯 HW 約 3~20）。
若材質填錯成同系列的另一種回火狀態，硬度值會與該材質的標度明顯不符——
例如久鼎 #4148 填 7075-O（韋伯 ≥9）卻量到 87.3~88.6，而同廠商同尺寸的
7075-T651 正是洛氏 ≥85，顯示材質誤填。

僅在證據充分時提出更正，四項條件須同時成立：
  1. 現材質的硬度公差標度與實際量測值量級不符
  2. 同廠商存在另一材質，其硬度公差標度與量測值量級相符
  3. 該替代材質在相同規格下查得到公差（尺寸確實對得上）
  4. 替代材質與現材質屬**同一合金編號**，僅回火狀態不同
唯一符合者才列為可更正；多個候選一律列出供人工判斷。

第 4 項是關鍵的安全界線：合金編號是材質身分（6061 與 6066、7075 與 7005
是不同合金），誤植的通常是回火代號（7075-O ↔ 7075-T651）。跨合金「更正」
等同竄改檢驗紀錄，故一律排除。

更正材質時會一併把硬度量測改回對應的項目鍵（洛氏→「硬度」、韋伯→
「韋伯氏硬度」），否則改了材質卻配不上公差，等於靜默不判定。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.fix_shipping_hardness_scale_mismatch
    .\\venv\\Scripts\\python.exe -m backend.scripts.fix_shipping_hardness_scale_mismatch --apply
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

ROCKWELL_MIN = 30            # 洛氏下限普遍 >= 50、韋伯 <= 20，取 30 為分界
ROCKWELL_ITEM = '洛氏硬度'
WEBSTER_ITEM = '韋伯氏硬度'
# 公差硬度項目 → (標度, 該標度對應的量測項目鍵)
SCALE_OF_ITEM = {
    ROCKWELL_ITEM: ('洛氏', '硬度'),
    WEBSTER_ITEM: ('韋伯', WEBSTER_ITEM),
}


def _alloy_number(material: str) -> str:
    """取合金編號（連字號前的部分，如 7075-T651 → 7075；無連字號則取全部）。"""
    return (material or '').strip().upper().split('-')[0]


def _hardness_scale(material, spec, vendor_id):
    """回傳該（材質,規格）硬度公差的標度與量測項目鍵；查無則 (None, None)。"""
    result = ToleranceService.check_tolerance(
        {'material': material, 'spec': spec, 'vendor_id': vendor_id})
    if not result.get('found'):
        return None, None
    for item in (result.get('tolerances') or []):
        scale = SCALE_OF_ITEM.get(item.get('項目'))
        if scale:
            return scale
    return None, None


def main(apply: bool):
    with app.app_context():
        vendors = {v.id: v.name for v in Vendor.query.all()}
        materials_by_vendor = defaultdict(set)
        for main_row in VendorToleranceMain.query.all():
            if main_row.material and main_row.material.strip():
                materials_by_vendor[main_row.vendor_id].add(main_row.material.strip())

        scale_cache: dict[tuple, tuple] = {}
        fixable, ambiguous = [], []
        for shipping in ShippingData.query.order_by(ShippingData.id).all():
            values = [
                float(m.value_single) for m in shipping.measurements
                if '硬度' in m.item and m.value_single is not None and float(m.value_single) > 0
            ]
            if not values:
                continue
            average = sum(values) / len(values)
            observed = '洛氏' if average >= ROCKWELL_MIN else '韋伯'

            key = (shipping.material, shipping.spec, shipping.vendor_id)
            if key not in scale_cache:
                scale_cache[key] = _hardness_scale(*key)
            current_scale, _current_item = scale_cache[key]
            if current_scale is None or current_scale == observed:
                continue  # 查無硬度公差或標度相符，非本腳本範圍

            # 同廠商、同合金編號中，標度與量測值相符且同規格查得到公差的替代材質
            alloy = _alloy_number(shipping.material)
            options = []
            for candidate in sorted(materials_by_vendor.get(shipping.vendor_id, set())):
                if candidate == shipping.material or _alloy_number(candidate) != alloy:
                    continue
                candidate_key = (candidate, shipping.spec, shipping.vendor_id)
                if candidate_key not in scale_cache:
                    scale_cache[candidate_key] = _hardness_scale(*candidate_key)
                candidate_scale, candidate_item = scale_cache[candidate_key]
                if candidate_scale == observed:
                    options.append((candidate, candidate_item))
            row = (shipping, observed, current_scale, average, options)
            if len(options) == 1:
                fixable.append(row)
            elif options:
                ambiguous.append(row)

        print('=' * 86)
        print(f'  硬度量級與材質標度矛盾：{len(fixable) + len(ambiguous)} 筆')
        print('=' * 86)

        print(f'\n■ 唯一替代材質（可更正）：{len(fixable)} 筆')
        for shipping, observed, current_scale, average, options in fixable:
            candidate, candidate_item = options[0]
            print(f'  #{shipping.id:<6}{vendors.get(shipping.vendor_id) or "(未指定)":<6}'
                  f'{shipping.material:<12}→ {candidate:<12}規格={shipping.spec}')
            print(f'         硬度均值={average:.1f}（{observed}量級）'
                  f'，現材質為{current_scale}標度；量測項目改為「{candidate_item}」')

        if ambiguous:
            print(f'\n■ 多個替代材質（須人工判斷）：{len(ambiguous)} 筆')
            for shipping, observed, _cur, average, options in ambiguous:
                names = '、'.join(name for name, _ in options)
                print(f'  #{shipping.id:<6}{vendors.get(shipping.vendor_id) or "(未指定)":<6}'
                      f'{shipping.material:<12}硬度均值={average:.1f}（{observed}）→ {names}')

        if not apply:
            print('\n  ℹ️  唯讀，未變更任何資料。確認後加 --apply 更正唯一候選者；')
            print('     更正後請執行 recompute_shipping_is_ng --all 重算判定。')
            return

        for shipping, _observed, _cur, _avg, options in fixable:
            candidate, candidate_item = options[0]
            shipping.material = candidate
            for measurement in shipping.measurements:
                if '硬度' in measurement.item:
                    measurement.item = candidate_item
        db.session.commit()
        print(f'\n  ✅ 已更正 {len(fixable)} 筆材質並同步調整硬度量測項目。')
        print('     請執行 recompute_shipping_is_ng --all 重算判定。')


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
