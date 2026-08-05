# -*- coding: utf-8 -*-
"""稽核既有機械性質紀錄的材質是否與廠商公差主檔一致。

背景：機械性質來源 Excel 沒有材質欄位，早期匯入是整批套用使用者自訂的單一材質；
但同一廠商不同規格常是不同材質，因此歷史資料可能存在材質誤標
（例如安泰 78*66 實為 6061-T851 卻被標為 6061-T651）。

匯入流程已改為逐產品尺寸反查公差主檔自動填入（resolve_material_by_spec），
但既有紀錄不會自動更正；本腳本以同一套反查邏輯掃出不一致者供人工確認。

分類：
  不一致  反查到唯一材質但與現存不同 → 更正候選（再細分 精確／相近 兩種比對層級）
  查無    公差主檔沒有對應規格       → 建議補建公差主檔，不動資料
  多材質  同規格對應多個材質         → 無法自動判定，須人工釐清

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_mechanical_material
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_mechanical_material --apply
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_mechanical_material --apply --exact-only
    .\\venv\\Scripts\\python.exe -m backend.scripts.audit_mechanical_material --csv out.csv

--apply 預設只更正「精確」比對層級的不一致；加 --include-fuzzy 才一併更正
「相近（前兩段相同）」層級，後者比對較寬鬆、誤更正風險較高，請先人工確認清單。
"""
import csv
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import MechanicalTest, Vendor
from ..services.mechanical_service import _judgement_status
from ..services.mechanical_spec import (
    compute_measurement_ng,
    lookup_limits,
    resolve_material_by_spec,
)


def _recompute_judgement(test: MechanicalTest, material: str) -> None:
    """材質變更後重算量測明細的界限與超規旗標。

    上下限與 is_ng 是存檔當下凍結在明細列上的（見 _apply_measurements），
    只改材質不重算會讓 NG 判定沿用舊材質的規格而失真。
    """
    limits = lookup_limits(material, test.product_size, test.vendor_id)
    for measurement in test.measurements:
        # EC值 或查無規格 → 兩邊皆 None
        lower, upper = limits.get(measurement.item, (None, None))
        measurement.lower_limit = lower
        measurement.upper_limit = upper
        measurement.is_ng = compute_measurement_ng(
            float(measurement.value) if measurement.value is not None else None,
            float(lower) if lower is not None else None,
            float(upper) if upper is not None else None,
        )


def _scan():
    """回傳 (分組結果, 掃描筆數)。分組鍵為 (廠商, 尺寸, 現存材質, 反查結果, 比對層級)。"""
    vendors = {v.id: v.name for v in Vendor.query.all()}
    tests = MechanicalTest.query.order_by(MechanicalTest.id).all()

    # 同一 (廠商, 尺寸) 只反查一次；歷史資料量大，避免重複查詢公差主檔
    cache: dict[tuple, dict] = {}
    groups: dict[tuple, list[MechanicalTest]] = defaultdict(list)

    for test in tests:
        size = (test.product_size or '').strip()
        stored = (test.material or '').strip()
        key = (test.vendor_id, size)
        if key not in cache:
            cache[key] = resolve_material_by_spec(size, test.vendor_id)
        result = cache[key]

        if result['status'] == 'resolved':
            if stored and result['material'].lower() == stored.lower():
                continue  # 一致，不需列出
            category = '不一致'
            resolved = result['material']
        elif result['status'] == 'ambiguous':
            category = '多材質'
            resolved = '、'.join(result['candidates'])
        else:
            category = '查無'
            resolved = ''

        groups[(
            vendors.get(test.vendor_id) or '(未指定)', size, stored,
            resolved, result['match'] or '—', category,
        )].append(test)

    return groups, len(tests)


def main(apply: bool, include_fuzzy: bool, csv_path: str | None):
    with app.app_context():
        groups, scanned = _scan()

        order = {'不一致': 0, '多材質': 1, '查無': 2}
        rows = sorted(
            groups.items(),
            key=lambda item: (order[item[0][5]], item[0][0], item[0][1]),
        )

        affected = sum(len(tests) for _key, tests in rows)
        print('=' * 78)
        print(f'  總紀錄數：{scanned}　需檢視筆數：{affected}　群組數：{len(rows)}')
        print('=' * 78)

        counts: dict[str, int] = defaultdict(int)
        for (vendor, size, stored, resolved, match, category), tests in rows:
            counts[category] += len(tests)

        for category, label in (
            ('不一致', '材質與公差主檔不一致（更正候選）'),
            ('多材質', '同規格對應多材質（須人工釐清）'),
            ('查無', '公差主檔查無此規格（建議補建）'),
        ):
            subset = [item for item in rows if item[0][5] == category]
            if not subset:
                continue
            print(f'\n■ {label}　共 {counts[category]} 筆 / {len(subset)} 組')
            for (vendor, size, stored, resolved, match, _cat), tests in subset:
                level = {'exact': '精確', 'fuzzy': '相近'}.get(match, match)
                head = f'  {vendor}　{size:<14}現存 {stored:<12}'
                if category == '不一致':
                    print(f'{head}→ 公差檔 {resolved:<12}（{level}比對，{len(tests)} 筆）')
                    # 材質換了會連帶改變規格下限，先預告判定狀態的變化
                    for test in tests:
                        before = _judgement_status(test)
                        _recompute_judgement(test, resolved)
                        after = _judgement_status(test)
                        if before != after:
                            print(f'      ⚠ id {test.id} 判定將由 {before} 變為 {after}')
                    db.session.rollback()  # 預告用，立即還原
                elif category == '多材質':
                    print(f'{head}　候選 {resolved}（{len(tests)} 筆）')
                else:
                    print(f'{head}　（{len(tests)} 筆）')
                ids = [str(t.id) for t in tests]
                preview = '、'.join(ids[:12]) + ('…' if len(ids) > 12 else '')
                print(f'      id: {preview}')

        if csv_path:
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    '分類', '廠商', '產品尺寸', '現存材質', '公差檔材質',
                    '比對層級', '筆數', 'id清單',
                ])
                for (vendor, size, stored, resolved, match, category), tests in rows:
                    writer.writerow([
                        category, vendor, size, stored, resolved, match,
                        len(tests), ' '.join(str(t.id) for t in tests),
                    ])
            print(f'\n  已輸出 CSV：{csv_path}')

        if not apply:
            print('\n  ℹ️  唯讀稽核，未變更任何資料。')
            print('     確認清單無誤後，可加 --apply 更正「不一致」的紀錄')
            print('     （預設僅精確比對層級；--include-fuzzy 才含相近比對）。')
            return

        # --apply：只更正「不一致」；查無與多材質一律不動（無可靠依據）
        updated = 0
        for (vendor, size, stored, resolved, match, category), tests in rows:
            if category != '不一致':
                continue
            if match == 'fuzzy' and not include_fuzzy:
                continue
            for test in tests:
                test.material = resolved
                # 材質變更會改變適用的規格下限，必須同步重算凍結的 NG 判定
                _recompute_judgement(test, resolved)
                updated += 1
        db.session.commit()
        print(f'\n  ✅ 已更正 {updated} 筆材質，並同步重算下限與 NG 判定。')


if __name__ == '__main__':
    csv_arg = None
    if '--csv' in sys.argv:
        index = sys.argv.index('--csv')
        if index + 1 < len(sys.argv):
            csv_arg = sys.argv[index + 1]
    main(
        apply='--apply' in sys.argv,
        include_fuzzy='--include-fuzzy' in sys.argv,
        csv_path=csv_arg,
    )
