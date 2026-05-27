"""
將 ShippingData 舊平鋪量測欄位資料遷移至 ShippingMeasurement 子表。

執行方式（在 repo 根目錄執行）：
    cd C:\\QC_Database
    .\\backend\\venv\\Scripts\\python.exe -m backend.migration.migrate_shipping_measurements

欄位對應表：
    od{n}_min / od{n}_max  → item='外徑',   value_min / value_max
    id{n}_min / id{n}_max  → item='內徑',   value_min / value_max
    th{n}_min / th{n}_max  → item='厚度',   value_min / value_max
    concentricity{n}       → item='同心度', value_single
    length{n}              → item='長度',   value_single
    hardness{n}            → item='硬度',   value_single
    vickers{n}             → item='韋伯氏硬度', value_single
    straightness{n}        → item='真直度', value_single
    roundness{n}           → item='真圓度', value_single
"""
import sys
import os

# 讓 Python 找得到 backend 套件
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.app import app
from backend.extensions import db
from backend.models import ShippingData, ShippingMeasurement
from decimal import Decimal, InvalidOperation


# ── 量測項目定義 ─────────────────────────────────────────────
# (attr_prefix, 中文名, is_minmax)
MEASUREMENT_ITEMS = [
    ('od',            '外徑',       True),
    ('id',            '內徑',       True),
    ('th',            '厚度',       True),
    ('concentricity', '同心度',     False),
    ('length',        '長度',       False),
    ('hardness',      '硬度',       False),
    ('vickers',       '韋伯氏硬度', False),
    ('straightness',  '真直度',     False),
    ('roundness',     '真圓度',     False),
]

MAX_GROUPS = 10  # ShippingData 最多 10 組


def safe_decimal(v):
    """將字串安全地轉換為 Decimal，無效值回傳 None"""
    try:
        if v is None or str(v).strip() in ('', 'None', '-'):
            return None
        return Decimal(str(v).strip())
    except InvalidOperation:
        return None


def build_measurements(rec: ShippingData) -> list[ShippingMeasurement]:
    """由一筆 ShippingData 產生對應的 ShippingMeasurement 列表"""
    gc = int(rec.group_count or MAX_GROUPS)
    results = []

    for g in range(1, gc + 1):
        for attr_prefix, item_name, is_minmax in MEASUREMENT_ITEMS:
            if is_minmax:
                v_min = safe_decimal(getattr(rec, f'{attr_prefix}{g}_min', None))
                v_max = safe_decimal(getattr(rec, f'{attr_prefix}{g}_max', None))
                # 兩值都為 None → 該組沒有填此項目，跳過
                if v_min is None and v_max is None:
                    continue
                results.append(ShippingMeasurement(
                    shipping_id=rec.id,
                    group_num=g,
                    item=item_name,
                    value_min=v_min,
                    value_max=v_max,
                ))
            else:
                v_single = safe_decimal(getattr(rec, f'{attr_prefix}{g}', None))
                if v_single is None:
                    continue
                results.append(ShippingMeasurement(
                    shipping_id=rec.id,
                    group_num=g,
                    item=item_name,
                    value_single=v_single,
                ))

    return results


def migrate():
    with app.app_context():
        # ── 防重複執行保護 ──────────────────────────────────────
        existing = db.session.query(ShippingMeasurement).count()
        if existing > 0:
            print(f'⚠ 子表已有 {existing} 筆資料，跳過遷移。'
                  '如需重新遷移，請先清空「出貨巡檢量測明細」表。')
            return

        records = ShippingData.query.all()
        total = len(records)
        print(f'共 {total} 筆出貨巡檢記錄待遷移...')

        if total == 0:
            print('出貨檢驗數據表為空，遷移腳本已成功執行（無資料需搬移）。')
            return

        migrated = 0
        inserted = 0

        for rec in records:
            meas_list = build_measurements(rec)
            for m in meas_list:
                db.session.add(m)
                inserted += 1
            migrated += 1

            # 每 50 筆 flush 一次，避免記憶體堆積
            if migrated % 50 == 0:
                db.session.flush()
                print(f'  已處理 {migrated}/{total} 筆...')

        db.session.commit()
        print(f'遷移完成，共處理 {migrated} 筆記錄，新增 {inserted} 筆量測明細。')


if __name__ == '__main__':
    migrate()
