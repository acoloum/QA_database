# -*- coding: utf-8 -*-
"""重算既有機械性質量測明細的規格下限與超規旗標。

背景：明細列的「下限」與 is_ng 是存檔當下依當時的廠商公差凍結的，
`_judgement_status()` 是讀這些凍結值來決定 OK／NG／無規格。因此在存檔之後
才補建或修改廠商公差時，既有紀錄不會自動跟上——最典型的症狀是公差已補建，
紀錄卻仍顯示「無規格」。

本腳本以現行公差重算下限與 is_ng，並回報判定狀態的變化。材質本身是否正確
不在此處理，請先用 audit_mechanical_material 稽核。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_mechanical_judgement
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_mechanical_judgement --apply
"""
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
from ..services.mechanical_spec import compute_measurement_ng, lookup_lower_limits


def main(apply: bool):
    with app.app_context():
        vendors = {v.id: v.name for v in Vendor.query.all()}
        tests = MechanicalTest.query.order_by(MechanicalTest.id).all()

        # 同一 (材質, 尺寸, 廠商) 只查一次公差
        limit_cache: dict[tuple, dict] = {}
        stale: list[tuple] = []
        transitions: dict[str, int] = defaultdict(int)

        for test in tests:
            key = (test.material, test.product_size, test.vendor_id)
            if key not in limit_cache:
                limit_cache[key] = lookup_lower_limits(
                    test.material, test.product_size, test.vendor_id
                )
            limits = limit_cache[key]

            before = _judgement_status(test)
            changes = []
            for measurement in test.measurements:
                lower = limits.get(measurement.item)  # EC值 或查無規格 → None
                new_ng = compute_measurement_ng(
                    float(measurement.value) if measurement.value is not None else None,
                    float(lower) if lower is not None else None,
                )
                old_lower = (
                    float(measurement.lower_limit)
                    if measurement.lower_limit is not None else None
                )
                new_lower = float(lower) if lower is not None else None
                if old_lower != new_lower or bool(measurement.is_ng) != new_ng:
                    changes.append((measurement, new_lower, new_ng))

            if not changes:
                continue

            for measurement, new_lower, new_ng in changes:
                measurement.lower_limit = new_lower
                measurement.is_ng = new_ng
            after = _judgement_status(test)
            stale.append((test, before, after, len(changes)))
            transitions[f'{before} → {after}'] += 1

        print('=' * 74)
        print(f'  總紀錄數：{len(tests)}　凍結值已過期：{len(stale)} 筆')
        print('=' * 74)

        if transitions:
            print('\n判定狀態變化統計：')
            for label, count in sorted(transitions.items(), key=lambda x: -x[1]):
                mark = '  ⚠ 新增不合格' if label.endswith('NG') and 'NG →' not in label else ''
                print(f'  {label:28}{count:5} 筆{mark}')

        for test, before, after, count in stale:
            flag = '  ⚠' if after == 'NG' and before != 'NG' else ''
            print(
                f'  id {test.id:<6}{vendors.get(test.vendor_id) or "(未指定)":<6}'
                f'{test.product_size:<14}{test.material:<12}'
                f'{before} → {after}（{count} 項明細）{flag}'
            )

        if apply:
            db.session.commit()
            print(f'\n  ✅ 已重算 {len(stale)} 筆的下限與 NG 判定。')
        else:
            db.session.rollback()
            print('\n  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際更新。')


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
