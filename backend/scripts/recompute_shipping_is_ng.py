# -*- coding: utf-8 -*-
"""重算既有出貨檢驗紀錄的「是否超差」旗標。

背景：記錄層級的 is_ng（是否超差）是存檔當下依規格推算的公差視窗計算並凍結的。
規格解析 parse_spec_nominals 修正四段式（外徑*內徑*厚度*長度）誤把明列厚度幾何回推
之後，這些四段式紀錄的 is_ng 仍是舊值，可能出現假性超差（或反之）。

範圍：本腳本「僅」重算受四段式解析修正影響的紀錄（規格含 ≥4 個數值段）。
三段式紀錄的解析邏輯未變動，不在此重算——即使其已存旗標與重算結果不一致，
那屬於獨立的資料問題（例如公差設定於存檔後才變更），不應由本次修正一併翻動。
若要全面重算，請改用 --all 參數（謹慎使用）。

另可用 --vendor=<廠商名> 把重算範圍限縮到單一廠商。新建或修改某家廠商的公差後，
只該廠商的紀錄需要重算；不加此參數會連帶翻動其他廠商既有的判定落差
（那些落差另有原因，應獨立查明，不該搭便車一起改）。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_shipping_is_ng          # dry-run，只列差異
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_shipping_is_ng --apply  # 實際寫入(僅四段式)
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_shipping_is_ng --all    # dry-run，含三段式
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_shipping_is_ng --all --vendor=旭生 --apply
"""
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import ShippingData, Vendor
from ..services.tolerance_service import ToleranceService


def _numeric_segment_count(spec) -> int:
    """規格字串中可解析為數值的段數（與 parse_spec_nominals 一致的正規化）。"""
    if not spec:
        return 0
    s = str(spec).strip().replace('×', '*').replace('x', '*').replace('X', '*')
    while '**' in s:
        s = s.replace('**', '*')
    count = 0
    for p in s.split('*'):
        p = p.strip()
        if not p:
            continue
        try:
            float(p)
            count += 1
        except (ValueError, TypeError):
            pass
    return count


def main(apply: bool, all_records: bool = False, vendor_name: str = None):
    with app.app_context():
        query = ShippingData.query
        vendor_label = "全廠商"
        if vendor_name:
            vendor = Vendor.query.filter(Vendor.name.ilike(f'%{vendor_name}%')).first()
            if not vendor:
                print(f'找不到廠商「{vendor_name}」，中止。')
                return 1
            query = query.filter(ShippingData.vendor_id == vendor.id)
            vendor_label = vendor.name.strip()
        records = query.order_by(ShippingData.id).all()
        tol_cache = {}
        changed = []
        scanned = 0

        for r in records:
            # 預設僅處理四段式（受解析修正影響）；--all 才全面重算
            if not all_records and _numeric_segment_count(r.spec) < 4:
                continue
            scanned += 1

            tol_key = (r.material, r.spec, r.vendor_id)
            if tol_key not in tol_cache:
                tol_cache[tol_key] = ToleranceService.check_tolerance({
                    'material': r.material,
                    'spec': r.spec,
                    'vendor_id': r.vendor_id,
                })
            tol_res = tol_cache[tol_key]

            new_is_ng = (
                r.compute_is_ng(tol_res.get('tolerances', []))
                if tol_res.get('found') else False
            )
            old_is_ng = bool(r.is_ng)

            if new_is_ng != old_is_ng:
                changed.append((r.id, r.material, r.spec, old_is_ng, new_is_ng))
                r.is_ng = new_is_ng

        scope = "全部" if all_records else "四段式(≥4數值段)"
        print("=" * 72)
        print(f"  廠商範圍：{vendor_label}　總紀錄數：{len(records)}")
        print(f"  本次重算範圍：{scope}　掃描筆數：{scanned}")
        print(f"  需更新筆數：{len(changed)}")
        print("=" * 72)
        for rid, material, spec, old, new in changed:
            flip = f"{'超差' if old else '合格'} → {'超差' if new else '合格'}"
            print(f"  #{rid}  {material}  {spec}  ：{flip}")

        if apply:
            db.session.commit()
            print("\n  ✅ 已寫入資料庫。")
        else:
            db.session.rollback()
            print("\n  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際更新。")
        return 0


def _arg_value(prefix: str):
    for a in sys.argv[1:]:
        if a.startswith(prefix):
            return a[len(prefix):].strip() or None
    return None


if __name__ == "__main__":
    sys.exit(main(
        apply="--apply" in sys.argv,
        all_records="--all" in sys.argv,
        vendor_name=_arg_value("--vendor="),
    ) or 0)
