# -*- coding: utf-8 -*-
"""稽核廠商公差中「硬度」項目的命名，找出應正名為洛氏／韋伯硬度者。

背景：機械性質模組以 MECH_ITEM_TO_TOLERANCE 把量測項目「硬度」對應到廠商公差的
「洛氏硬度」。但公差主檔中有大量明細把項目登錄為未指明標度的「硬度」，這些條目
在機械性質判定時讀不到下限，紀錄會顯示「無規格」而非真正的 OK／NG。

不能單純把「硬度」也視為洛氏硬度：主檔中「硬度」同時被用於兩種標度
（洛氏 HRB 約 50~90、韋伯 Webster 約 3~20），一律當洛氏會拿韋伯下限
（如 7）去比對洛氏量測值（如 65）而永遠合格，反而製造假合格。

判定依據優先序：
  1. unit 欄位（最可靠）：HRB／HRC／洛氏 → 洛氏；HW／韋伯／韋氏 → 韋伯
  2. 同一主檔內其他硬度項目的標度
  3. 下限值區間（>= 30 視為洛氏，< 30 視為韋伯）— 僅供參考，標為低信心

本腳本唯讀，只輸出建議清單供人工逐筆確認，不修改任何資料。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_hardness_item_naming
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_hardness_item_naming --csv out.csv
"""
import csv
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..models import MechanicalTest, Vendor, VendorToleranceDetail, VendorToleranceMain

ROCKWELL_UNITS = ('hrb', 'hrc', 'hra', 'hr', '洛氏')
WEBSTER_UNITS = ('hw', '韋伯', '韋氏', 'w')
ROCKWELL_MIN = 30  # 洛氏下限普遍 >= 50；韋伯普遍 <= 20，取 30 為分界


def _scale_from_unit(unit):
    text = (unit or '').strip().lower()
    if not text:
        return None
    if any(token in text for token in ROCKWELL_UNITS):
        return '洛氏硬度'
    if any(token in text for token in WEBSTER_UNITS):
        return '韋伯氏硬度'
    return None


def _scale_from_value(lower):
    if lower is None:
        return None
    return '洛氏硬度' if float(lower) >= ROCKWELL_MIN else '韋伯氏硬度'


def _classify(unit, lower, sibling_scale):
    """回傳 (建議標度, 依據, 信心)。

    單位最可靠，但仍有登錄錯誤（例如單位填 HW 卻給洛氏量級的下限 70）；
    單位與下限量級互相矛盾時不逕自採信單位，標為「衝突」要求人工判讀。
    """
    by_unit = _scale_from_unit(unit)
    by_value = _scale_from_value(lower)

    if by_unit and by_value and by_unit != by_value:
        return by_unit, f'單位={unit} 但下限={float(lower)} 量級不符', '衝突'
    if by_unit:
        return by_unit, f'單位={unit}', '高'
    if sibling_scale:
        return sibling_scale, '同主檔其他硬度項目', '中'
    if by_value is None:
        return None, '無單位、無下限', '無法判斷'
    return by_value, f'下限={float(lower)}（僅依量級推測）', '低'


def main(csv_path: str | None):
    with app.app_context():
        vendors = {v.id: v.name for v in Vendor.query.all()}
        mains = {m.id: m for m in VendorToleranceMain.query.all()}

        # 同一主檔內若已有明確標度的硬度項目，可作為未指明者的判定依據
        sibling: dict[int, str] = {}
        for detail in VendorToleranceDetail.query.all():
            if detail.item == '洛氏硬度':
                sibling.setdefault(detail.main_id, '洛氏硬度')
            elif detail.item in ('韋伯氏硬度', '韋伯硬度'):
                sibling.setdefault(detail.main_id, '韋伯氏硬度')

        # 哪些 (廠商, 材質, 規格) 實際有機械性質紀錄 → 優先處理
        in_use = set()
        for test in MechanicalTest.query.all():
            in_use.add((test.vendor_id, (test.material or '').strip().lower()))

        rows = []
        for detail in VendorToleranceDetail.query.filter(
            VendorToleranceDetail.item == '硬度'
        ).order_by(VendorToleranceDetail.id).all():
            main = mains.get(detail.main_id)
            if main is None:
                continue
            lower = detail.dim_min if detail.dim_min is not None else detail.tolerance_min
            suggested, basis, confidence = _classify(
                detail.unit, lower, sibling.get(detail.main_id)
            )
            used = (main.vendor_id, (main.material or '').strip().lower()) in in_use
            rows.append({
                'detail_id': detail.id,
                'vendor': vendors.get(main.vendor_id) or '(未指定)',
                'material': main.material or '',
                'spec': main.spec or '',
                'unit': detail.unit or '',
                'lower': float(lower) if lower is not None else None,
                'suggested': suggested or '(無法判斷)',
                'basis': basis,
                'confidence': confidence,
                'in_use': used,
            })

        print('=' * 96)
        print(f'  項目名為「硬度」的公差明細：{len(rows)} 筆（唯讀稽核，未修改任何資料）')
        print('=' * 96)

        by_conf: dict[str, list] = defaultdict(list)
        for row in rows:
            by_conf[row['confidence']].append(row)

        print('\n判定信心分布：')
        for confidence in ('衝突', '高', '中', '低', '無法判斷'):
            group = by_conf.get(confidence)
            if group:
                rockwell = sum(1 for r in group if r['suggested'] == '洛氏硬度')
                webster = sum(1 for r in group if r['suggested'] == '韋伯氏硬度')
                print(f'  {confidence:5}{len(group):4} 筆　（洛氏 {rockwell} / 韋伯 {webster}）')

        used_rows = [r for r in rows if r['in_use']]
        print(f'\n其中該廠商+材質已有機械性質紀錄者：{len(used_rows)} 筆（優先處理）')
        for row in used_rows:
            print(
                f"  detail {row['detail_id']:<6}{row['vendor']:<7}{row['material']:<12}"
                f"{row['spec']:<18}單位={row['unit'] or '—':<6}下限="
                f"{row['lower'] if row['lower'] is not None else '—':<8}"
                f"→ {row['suggested']}（{row['basis']}，信心{row['confidence']}）"
            )

        print('\n全部清單（依信心排序）：')
        rank = {'衝突': 0, '低': 1, '無法判斷': 2, '中': 3, '高': 4}
        for row in sorted(rows, key=lambda r: (rank[r['confidence']], r['vendor'], r['spec'])):
            mark = '  ★已用' if row['in_use'] else ''
            print(
                f"  [{row['confidence']:4}] detail {row['detail_id']:<6}{row['vendor']:<7}"
                f"{row['material']:<12}{row['spec']:<18}單位={row['unit'] or '—':<6}"
                f"下限={row['lower'] if row['lower'] is not None else '—':<8}"
                f"→ {row['suggested']}{mark}"
            )

        if csv_path:
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            print(f'\n  已輸出 CSV：{csv_path}')

        print('\n  ℹ️  唯讀稽核，未變更任何資料。')
        print('     「洛氏硬度」才會被機械性質判定採用；「韋伯氏硬度」目前不納入判定。')
        print('     請逐筆確認後於公差建檔頁面修正項目名稱（信心「低」者務必人工核對）。')


if __name__ == '__main__':
    path = None
    if '--csv' in sys.argv:
        index = sys.argv.index('--csv')
        if index + 1 < len(sys.argv):
            path = sys.argv[index + 1]
    main(csv_path=path)
