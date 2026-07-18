r"""
SPC 統計回歸比對工具

用途：驗證 SPC 2026 保存版本可重現的方法版本、資料雜湊、圖表選型、逐點界限、
兩圖穩定性、時間模型、分布與能力／績效門檻。無參數執行時使用內建固定資料，
不連線或修改正式資料庫；save/compare 模式保留供既有資料庫快照比對。

執行方式（repo 根目錄）：
    # 1. 內建確效（CI 與部署前預設）
    .\venv\Scripts\python.exe backend\scripts\spc_regression.py

    # 2. 另存現有資料庫案例
    .\\venv\\Scripts\\python.exe -m backend.scripts.spc_regression save

    # 3. 比對資料庫案例
    .\\venv\\Scripts\\python.exe -m backend.scripts.spc_regression compare

可選參數：
    --max-combos N    最多取樣的 (廠商,材質,規格) 組合數（預設 80，依筆數由多到少）
    --min-records N   組合至少需有幾筆記錄才納入（預設 1）
    --baseline PATH   基準檔路徑（預設 backend/scripts/spc_baseline.json）
    --abs-tol F       數值絕對容差（預設 1e-6）
    --rel-tol F       數值相對容差（預設 1e-9）
    --field NAME      只測單一量測項目（預設全部）

說明：
    - 每次執行都會先清空 SPC快取，強制 get_stats 重新計算，避免比到舊快取。
    - 比對採遞迴：數值用容差比較，字串/None/布林須完全相等，串列須等長且逐項比對。
"""
import sys
import os
import json
import math
import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.app import app
from backend.extensions import db
from backend.models import ShippingData, Vendor, SPCCache
from backend.services.shipping_service import ShippingService
from backend.services.spc_analysis_service import calculate_process_capability
from backend.services.spc_chart_engine import calculate_chart_set
from backend.services.spc_contracts import SpcSubgroup
from backend.services.spc_distribution import assess_distribution
from backend.services.spc_stability import evaluate_study_stability
from backend.services.spc_study_service import SPC_CODE_VERSION, SPC_METHOD_VERSION
from backend.services.spc_time_model import classify_time_model

# get_stats 支援的量測項目（field_map 的鍵）
ALL_FIELDS = ['外徑', '內徑', '厚度', '同心度', '長度', '硬度', '韋伯氏硬度', '真直度', '真圓度']

DEFAULT_BASELINE = os.path.join(os.path.dirname(__file__), 'spc_baseline.json')


def _validation_groups():
    """固定且具時間順序的 X̄-S 子組，供無資料庫回歸驗證。"""
    patterns = (
        (9.86, 10.01, 10.15), (9.91, 10.07, 10.18),
        (9.83, 9.98, 10.12), (9.90, 10.05, 10.20),
        (9.85, 10.02, 10.17), (9.92, 10.06, 10.16),
        (9.84, 9.99, 10.13), (9.89, 10.04, 10.19),
        (9.87, 10.00, 10.14), (9.93, 10.08, 10.21),
    )
    return tuple(
        SpcSubgroup(
            key=f"validation:{index + 1}",
            timestamp=date(2026, 7, 1) + timedelta(days=index),
            values=values,
            record_ids=(index + 1,),
            measurement_ids=(index * 3 + 1, index * 3 + 2, index * 3 + 3),
        )
        for index, values in enumerate(patterns)
    )


def _assert_no_nonfinite(value, path="root"):
    if isinstance(value, float) and not math.isfinite(value):
        raise AssertionError(f"{path} 出現非有限數值：{value}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_nonfinite(item, f"{path}[{index}]")


def cmd_validate(_args):
    """以 JSON round-trip 驗證研究快照可保存、可重建且沒有 NaN。"""
    groups = _validation_groups()
    chart = calculate_chart_set(groups)
    stability = evaluate_study_stability(chart)
    values = [value for group in groups for value in group.values]
    distribution = assess_distribution(values, field="外徑")
    time_model = classify_time_model(chart, stability, distribution)
    capability = calculate_process_capability(
        avgs=[float(value) for value in chart.location.values if value is not None],
        all_values=values,
        r_cl=float(chart.variation.cl[0]),
        d2=float(chart.variation.cl[0]) / chart.sigma_within,
        tolerance_limits={"USL": 10.8, "LSL": 9.2},
        stability=stability,
        field="外徑",
        dist=distribution,
        time_model=time_model,
    )
    canonical_input = json.dumps(
        [{"key": group.key, "timestamp": str(group.timestamp), "values": group.values}
         for group in groups],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    snapshot = {
        "dataset_version": "spc-golden-2026.1",
        "method_version": SPC_METHOD_VERSION,
        "code_version": SPC_CODE_VERSION,
        "data_hash": hashlib.sha256(canonical_input.encode("utf-8")).hexdigest(),
        "chart": asdict(chart),
        "stability": stability,
        "distribution": distribution,
        "time_model": time_model,
        "capability": capability,
    }
    _assert_no_nonfinite(snapshot)
    restored = json.loads(json.dumps(snapshot, ensure_ascii=False, allow_nan=False))
    if restored["data_hash"] != snapshot["data_hash"]:
        raise AssertionError("保存版本 JSON round-trip 後資料雜湊改變")
    if not distribution.get("accepted"):
        assert capability.get("available") is False
        assert capability.get("capability_reason") == distribution.get("reason_code")
    if not time_model.get("confirmed"):
        assert capability.get("cpk") is None

    summary = {
        "dataset_version": restored["dataset_version"],
        "method_version": restored["method_version"],
        "code_version": restored["code_version"],
        "data_hash": restored["data_hash"],
        "chart_type": restored["chart"]["chart_type"],
        "subgroup_sizes": restored["chart"]["subgroup_sizes"],
        "location_limits": {
            key: restored["chart"]["location"][key] for key in ("cl", "ucl", "lcl")
        },
        "variation_limits": {
            key: restored["chart"]["variation"][key] for key in ("cl", "ucl", "lcl")
        },
        "location_stable": restored["stability"]["location"]["stable"],
        "variation_stable": restored["stability"]["variation"]["stable"],
        "time_model": restored["time_model"],
        "distribution": {
            "model": restored["distribution"]["model"],
            "accepted": restored["distribution"]["accepted"],
            "reason_code": restored["distribution"]["reason_code"],
        },
        "capability": restored["capability"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    print("\n[PASS] SPC 2026 保存版本回歸驗證通過；無 NaN、無未說明的常態回退。")


def clear_spc_cache():
    """清空 SPC 快取，確保 get_stats 重新計算。"""
    SPCCache.query.delete()
    db.session.commit()


def enumerate_combos(max_combos: int, min_records: int):
    """列出 (廠商名, 材質, 規格) 組合，依記錄筆數由多到少取樣。"""
    rows = (
        db.session.query(
            Vendor.name,
            ShippingData.material,
            ShippingData.spec,
            db.func.count(ShippingData.id).label('cnt'),
        )
        .outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)
        .group_by(Vendor.name, ShippingData.material, ShippingData.spec)
        .having(db.func.count(ShippingData.id) >= min_records)
        .order_by(db.func.count(ShippingData.id).desc())
        .limit(max_combos)
        .all()
    )
    return [
        {'vendor': r[0], 'material': r[1], 'spec': r[2], 'record_count': int(r[3])}
        for r in rows
    ]


def case_key_str(field, combo):
    return f"{field} | {combo.get('vendor') or ''} | {combo.get('material') or ''} | {combo.get('spec') or ''}"


def run_all_cases(combos, fields):
    """對每個組合 × 量測項目呼叫 get_stats，回傳 case 列表。"""
    cases = []
    total = len(combos) * len(fields)
    n = 0
    for combo in combos:
        for field in fields:
            n += 1
            clear_spc_cache()  # 每次都重新計算
            args = {
                'field': field,
                'vendor': combo.get('vendor'),
                'material': combo.get('material'),
                'spec': combo.get('spec'),
            }
            try:
                result = ShippingService.get_stats(args)
                error = None
            except Exception as e:  # noqa: BLE001 — 回歸工具需記錄任何例外
                result = None
                error = f"{type(e).__name__}: {e}"
            cases.append({
                'key': {
                    'field': field,
                    'vendor': combo.get('vendor'),
                    'material': combo.get('material'),
                    'spec': combo.get('spec'),
                },
                'record_count': combo.get('record_count'),
                'result': result,
                'error': error,
            })
            if n % 20 == 0 or n == total:
                print(f"  進度 {n}/{total}", flush=True)
    return cases


# ── 遞迴比對 ──────────────────────────────────────────────────────────

def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def diff_values(a, b, abs_tol, rel_tol, path=""):
    """回傳差異列表，每筆為 (path, 說明)。完全相同則回傳空列表。"""
    diffs = []

    if _is_number(a) and _is_number(b):
        fa, fb = float(a), float(b)
        if not math.isfinite(fa) or not math.isfinite(fb):
            diffs.append((path, f"禁止非有限數值 baseline={a} new={b}"))
            return diffs
        if not math.isclose(fa, fb, abs_tol=abs_tol, rel_tol=rel_tol):
            diffs.append((path, f"數值不符 baseline={a} new={b}"))
        return diffs

    # 型別不同（含 number vs None）
    if type(a) is not type(b) and not (_is_number(a) and _is_number(b)):
        diffs.append((path, f"型別不符 baseline={type(a).__name__}({a!r}) new={type(b).__name__}({b!r})"))
        return diffs

    if isinstance(a, dict):
        a_keys, b_keys = set(a.keys()), set(b.keys())
        for k in a_keys - b_keys:
            diffs.append((f"{path}.{k}", f"new 缺少此鍵 baseline={a[k]!r}"))
        for k in b_keys - a_keys:
            diffs.append((f"{path}.{k}", f"baseline 缺少此鍵 new={b[k]!r}"))
        for k in a_keys & b_keys:
            diffs.extend(diff_values(a[k], b[k], abs_tol, rel_tol, f"{path}.{k}"))
        return diffs

    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append((path, f"串列長度不符 baseline={len(a)} new={len(b)}"))
            return diffs
        for i, (av, bv) in enumerate(zip(a, b)):
            diffs.extend(diff_values(av, bv, abs_tol, rel_tol, f"{path}[{i}]"))
        return diffs

    # 字串 / 布林 / None：須完全相等
    if a != b:
        diffs.append((path, f"值不符 baseline={a!r} new={b!r}"))
    return diffs


def cmd_save(args):
    with app.app_context():
        clear_spc_cache()
        combos = enumerate_combos(args.max_combos, args.min_records)
        fields = [args.field] if args.field else ALL_FIELDS
        print(f"取樣 {len(combos)} 組合 × {len(fields)} 量測項目 = {len(combos) * len(fields)} 案例", flush=True)
        cases = run_all_cases(combos, fields)
        payload = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'abs_tol': args.abs_tol,
            'rel_tol': args.rel_tol,
            'fields': fields,
            'combo_count': len(combos),
            'cases': cases,
        }
        with open(args.baseline, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        clear_spc_cache()  # 不殘留本次（舊版）計算的快取
        non_empty = sum(1 for c in cases if c['result'] and c['result'].get('valid_count'))
        print(f"\n基準已寫入 {args.baseline}")
        print(f"案例總數 {len(cases)}，其中有效（valid_count>0）{non_empty} 筆")


def cmd_compare(args):
    if not os.path.exists(args.baseline):
        print(f"找不到基準檔 {args.baseline}，請先執行 save")
        sys.exit(2)
    with open(args.baseline, encoding='utf-8') as f:
        baseline = json.load(f)

    abs_tol = args.abs_tol if args.abs_tol is not None else baseline.get('abs_tol', 1e-6)
    rel_tol = args.rel_tol if args.rel_tol is not None else baseline.get('rel_tol', 1e-9)

    with app.app_context():
        mismatched_cases = 0
        total_diffs = 0
        for case in baseline['cases']:
            key = case['key']
            clear_spc_cache()
            try:
                new_result = ShippingService.get_stats({
                    'field': key['field'],
                    'vendor': key['vendor'],
                    'material': key['material'],
                    'spec': key['spec'],
                })
                new_error = None
            except Exception as e:  # noqa: BLE001
                new_result = None
                new_error = f"{type(e).__name__}: {e}"

            label = case_key_str(key['field'], key)

            # 例外狀態比對
            if case.get('error') or new_error:
                if case.get('error') != new_error:
                    mismatched_cases += 1
                    total_diffs += 1
                    print(f"\n✗ [{label}] 例外狀態不符")
                    print(f"    baseline error: {case.get('error')}")
                    print(f"    new error:      {new_error}")
                continue

            diffs = diff_values(case['result'], new_result, abs_tol, rel_tol, path="result")
            if diffs:
                mismatched_cases += 1
                total_diffs += len(diffs)
                print(f"\n✗ [{label}]  ({len(diffs)} 處差異)")
                for p, msg in diffs[:15]:
                    print(f"    {p}: {msg}")
                if len(diffs) > 15:
                    print(f"    …還有 {len(diffs) - 15} 處")

        clear_spc_cache()
        total = len(baseline['cases'])
        print("\n" + "=" * 60)
        if mismatched_cases == 0:
            print(f"✓ 全部 {total} 案例一致，無差異（abs_tol={abs_tol}, rel_tol={rel_tol}）")
        else:
            print(f"✗ {mismatched_cases}/{total} 案例有差異，共 {total_diffs} 處")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="SPC 統計回歸比對工具")
    parser.add_argument(
        'mode', nargs='?', default='validate',
        choices=['validate', 'save', 'compare'],
    )
    parser.add_argument('--max-combos', type=int, default=80)
    parser.add_argument('--min-records', type=int, default=1)
    parser.add_argument('--baseline', default=DEFAULT_BASELINE)
    parser.add_argument('--abs-tol', type=float, default=1e-6)
    parser.add_argument('--rel-tol', type=float, default=1e-9)
    parser.add_argument('--field', default=None, choices=ALL_FIELDS)
    args = parser.parse_args()

    if args.mode == 'validate':
        cmd_validate(args)
    elif args.mode == 'save':
        cmd_save(args)
    else:
        cmd_compare(args)


if __name__ == '__main__':
    main()
