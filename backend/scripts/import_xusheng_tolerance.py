# -*- coding: utf-8 -*-
"""依旭生「尺寸公差對照表」的區間規則，批次建立旭生的廠商公差主檔。

背景：旭生給的是區間式公差（外徑範圍 / 壁厚範圍各一組 ±），而本系統的公差主檔
是「一筆規格對應一組公差」。九家廠商的公差表中只有旭生是區間式，為此改動
公差明細的資料結構（該組欄位被出貨、巡檢、SPC、機械性質共用）不划算，
因此改為把區間規則「展開」成各規格的公差——展開結果與人工查表完全一致。

分組方式：以（材質 + 規格前兩段）建一筆主檔，例如 6061-O / 38.1*1.8。
公差比對的開頭匹配（bucket 2）會讓它涵蓋該外徑*厚度的所有長度，
未來同外徑同壁厚的新長度不必再建檔。

刻意不做的事：
  * 不建外徑-only 的主檔（如規格只填 38.1）。那樣筆數更少、也能涵蓋未來的新壁厚，
    但跨壁厚區間時會套到錯的 ±，而且可能偏鬆而漏判——寧可查不到（不判定並進缺口
    清單），也不能誤放。
  * 不建旭生表沒給的項目（內徑、長度、真圓度、同心度、硬度）。建了就會被判定。
  * 有專用圖面的規格不由本腳本建檔，見 DRAWING_EXEMPT_PREFIXES。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.import_xusheng_tolerance          # dry-run
    .\\venv\\Scripts\\python.exe -m backend.scripts.import_xusheng_tolerance --apply  # 實際寫入
"""
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import ShippingData, Vendor, VendorToleranceMain, VendorToleranceDetail
from ..services.tolerance_service import ToleranceService
from ..utils import parse_spec_nominals, normalize_spec_for_match

VENDOR_NAME = '旭生'
NOTE = '依旭生尺寸公差對照表區間換算'

# 外徑區間 → ±公差。旭生表為 ≦20 / 20<OD≦50 / 50<OD≦100 / >100，上界為含。
OD_BANDS = [(20, 0.10), (50, 0.15), (100, 0.20), (float('inf'), 0.30)]

# 有專用圖面、公差以圖面為準的規格（以正規化後的規格前兩段為鍵）。
# 42*33.7（五通）已依圖面 C-01-0000231 建檔：外徑 Ø42±0.1、內徑 Ø33.7 +0.1/-0，
# 圖面未要求厚度故不判定厚度。本腳本一律略過，不得以通用區間表覆蓋。
DRAWING_EXEMPT_PREFIXES = {'42*33.7'}


def band_value(value, bands):
    """取 value 落在哪一段的 ± 公差；bands 為 [(上界, 公差), ...] 由小到大，上界為含。"""
    for upper, tol in bands:
        if value <= upper:
            return tol
    return bands[-1][1]


def wall_tolerance(wall):
    """壁厚 ± 公差。旭生表寫的是 <1.5 / 1.5~3.0 / >3.0，
    邊界 1.5 屬中間段（1.5 不小於 1.5），不可寫成 wall <= 1.5。"""
    if wall < 1.5:
        return 0.10
    if wall <= 3.0:
        return 0.15
    return 0.20


def spec_prefix(spec):
    """規格正規化後取前兩段，作為主檔規格（開頭匹配的鍵）。"""
    segments = normalize_spec_for_match(spec).split('*')
    return '*'.join(segments[:2])


def collect_groups(vendor_id):
    """掃出貨檢驗數據，彙整成 {(材質, 規格前兩段): [原始規格, ...]}。"""
    rows = (
        db.session.query(ShippingData.material, ShippingData.spec)
        .filter(ShippingData.vendor_id == vendor_id)
        .distinct()
        .all()
    )
    groups = {}
    skipped = []
    for material, spec in rows:
        nominals = parse_spec_nominals(spec)
        od, wall = nominals.get('外徑'), nominals.get('厚度')
        if not material or od is None or wall is None:
            skipped.append((material, spec, '規格無法解析出外徑/厚度'))
            continue
        key = (material.strip(), spec_prefix(spec))
        groups.setdefault(key, {'specs': [], 'od': od, 'wall': wall})
        groups[key]['specs'].append(spec)
    return groups, skipped


def main(apply_changes: bool):
    with app.app_context():
        vendor = Vendor.query.filter(Vendor.name.ilike(f'%{VENDOR_NAME}%')).first()
        if not vendor:
            print(f'找不到廠商「{VENDOR_NAME}」，中止。')
            return 1

        groups, skipped = collect_groups(vendor.id)
        to_create, exempt, already = [], [], []

        for (material, prefix), info in sorted(groups.items()):
            if prefix in DRAWING_EXEMPT_PREFIXES:
                exempt.append((material, prefix, info['specs']))
                continue

            # 以真正的比對邏輯確認是否已有「同廠商」的公差可用（優先權 1~4），
            # 避免建出互相搶匹配的重複主檔。他廠/無廠商的通用檔(5~8)不算數。
            probe = ToleranceService.check_tolerance({
                'material': material,
                'spec': info['specs'][0],
                'vendor_id': vendor.id,
            })
            if probe.get('found') and probe.get('matched_priority') in (1, 2, 3, 4):
                already.append((material, prefix, probe.get('tolerance_id'),
                                probe.get('priority_name')))
                continue

            to_create.append({
                'material': material,
                'spec': prefix,
                'od_tol': band_value(info['od'], OD_BANDS),
                'wall_tol': wall_tolerance(info['wall']),
                'od': info['od'],
                'wall': info['wall'],
                'specs': sorted(info['specs']),
            })

        print('=' * 78)
        print(f'  廠商：{vendor.name.strip()}（識別碼 {vendor.id}）')
        print(f'  出貨規格分組：{len(groups)}　'
              f'待建立：{len(to_create)}　'
              f'依圖面略過：{len(exempt)}　已有公差：{len(already)}')
        print('=' * 78)

        for item in to_create:
            print(f"  + {item['material']:<9}規格={item['spec']:<12}"
                  f"外徑{item['od']:g}→±{item['od_tol']:g}　"
                  f"厚度{item['wall']:g}→±{item['wall_tol']:g}")
            print(f"      涵蓋：{' / '.join(item['specs'])}")

        for material, prefix, specs in exempt:
            print(f"  = {material:<9}規格={prefix:<12}依專用圖面，略過（{' / '.join(sorted(specs))}）")

        for material, prefix, tol_id, priority in already:
            print(f"  = {material:<9}規格={prefix:<12}已有公差 #{tol_id}（{priority}），略過")

        for material, spec, reason in skipped:
            print(f"  ! {material}  {spec}  ：{reason}")

        if not to_create:
            print('\n  沒有需要新增的主檔。')
            return 0

        created_at = datetime.now()
        for item in to_create:
            m = VendorToleranceMain(
                vendor_id=vendor.id,
                material=item['material'],
                spec=item['spec'],
                note=NOTE,
                created_at=created_at,
            )
            db.session.add(m)
            db.session.flush()
            for name, tol in (('外徑', item['od_tol']), ('厚度', item['wall_tol'])):
                db.session.add(VendorToleranceDetail(
                    main_id=m.id,
                    item=name,
                    position='',
                    tolerance_min=-tol,
                    tolerance_max=tol,
                    unit='mm',
                    characteristic_class='其他',
                    note=NOTE,
                ))

        if apply_changes:
            db.session.commit()
            print(f'\n  ✅ 已寫入 {len(to_create)} 筆主檔、{len(to_create) * 2} 筆明細。')
            print('     歷史紀錄的「是否超差」不會自動更新，'
                  '需另跑 recompute_shipping_is_ng。')
        else:
            db.session.rollback()
            print('\n  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際建立。')
        return 0


if __name__ == '__main__':
    sys.exit(main(apply_changes='--apply' in sys.argv))
