"""
SPC 統計回歸比對工具

用途：在把 ShippingService.get_stats 從「扁平欄位」改讀「子表」之前，
先用目前版本產生一份基準快照；改寫後再跑一次比對，確保 Cp/Cpk、X-R 圖、
PPM、分佈統計等數字逐筆一致。

執行方式（repo 根目錄）：
    # 1. 改寫前：用現行（扁平）版本建立基準
    .\\venv\\Scripts\\python.exe -m backend.scripts.spc_regression save

    # 2. 改寫後：比對新版（子表）與基準
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
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.app import app
from backend.extensions import db
from backend.models import ShippingData, Vendor, SPCCache
from backend.services.shipping_service import ShippingService

# get_stats 支援的量測項目（field_map 的鍵）
ALL_FIELDS = ['外徑', '內徑', '厚度', '同心度', '長度', '硬度', '韋伯氏硬度', '真直度', '真圓度']

DEFAULT_BASELINE = os.path.join(os.path.dirname(__file__), 'spc_baseline.json')


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
        if not math.isclose(float(a), float(b), abs_tol=abs_tol, rel_tol=rel_tol):
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
            'generated_at': datetime.utcnow().isoformat(),
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
    parser.add_argument('mode', choices=['save', 'compare'])
    parser.add_argument('--max-combos', type=int, default=80)
    parser.add_argument('--min-records', type=int, default=1)
    parser.add_argument('--baseline', default=DEFAULT_BASELINE)
    parser.add_argument('--abs-tol', type=float, default=1e-6)
    parser.add_argument('--rel-tol', type=float, default=1e-9)
    parser.add_argument('--field', default=None, choices=ALL_FIELDS)
    args = parser.parse_args()

    if args.mode == 'save':
        cmd_save(args)
    else:
        cmd_compare(args)


if __name__ == '__main__':
    main()
