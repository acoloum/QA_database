"""機械性質疑似異常值偵測。

以「量測項目 + 材質」為一組，用未排除的量測值估計四分位距（IQR），
數值落在 Q1 − 5×IQR ～ Q3 + 5×IQR 之外、或為 0／負值者列為疑似異常值，
供品管人員對照原始報告後更正數值或標示排除統計（AIAG-VDA SPC §6.6）。

5 倍 IQR 刻意比常見的 1.5 倍寬得多：目的在抓輸入錯誤（多打位數、小數點錯位、
填錯欄位），而不是把製程本身的正常波動當成離群值。
"""
from collections import defaultdict
from statistics import quantiles
from typing import Any, Dict, Mapping, Optional

from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import MechanicalMeasurement, MechanicalTest
from ..utils import bounded_int
from .mechanical_service import MechanicalValidationError, _parse_date

# 與 SPC 分析範圍一致的四個判定項目；排列順序也是同爐次內的顯示順序
SUSPECT_ITEMS = ("硬度", "抗拉強度", "降伏強度", "伸長率")
LOCATION_ORDER = ("爐門", "爐頂")
IQR_FENCE = 5
# 組內資料太少時 IQR 不可靠，僅保留 0／負值這類必然錯誤的判定
MIN_GROUP_SIZE = 10
# 判斷「小數點錯位」時，換算後的值需落在一般（1.5 倍 IQR）範圍內才給提示
HINT_FENCE = 1.5
_SCALE_FACTORS = (10, 100, 1000)


def _group_stats(values: list[float]) -> Optional[Dict[str, float]]:
    if len(values) < MIN_GROUP_SIZE:
        return None
    q1, median, q3 = quantiles(values, n=4, method="inclusive")
    iqr = q3 - q1
    return {
        "n": len(values),
        "q1": q1,
        "q3": q3,
        "median": median,
        "lower": q1 - IQR_FENCE * iqr,
        "upper": q3 + IQR_FENCE * iqr,
        "hint_lower": q1 - HINT_FENCE * iqr,
        "hint_upper": q3 + HINT_FENCE * iqr,
    }


def _format_number(value: float) -> str:
    return f"{round(value, 4):g}"


def _hint(value: float, stats: Optional[Dict[str, float]]) -> str:
    if value <= 0:
        return "數值為 0 或負值，可能漏填或誤植"
    if stats is None:
        return ""
    too_high = value > stats["upper"]
    for factor in _SCALE_FACTORS:
        candidate = value / factor if too_high else value * factor
        if stats["hint_lower"] <= candidate <= stats["hint_upper"]:
            return f"疑似小數點位置錯誤，可能應為 {_format_number(candidate)}"
    return "遠離同材質正常範圍，請對照原始報告確認"


def _is_suspect(value: float, stats: Optional[Dict[str, float]]) -> bool:
    if value <= 0:
        return True
    return stats is not None and not stats["lower"] <= value <= stats["upper"]


def _sort_key(row: Dict[str, Any]) -> tuple:
    test_date = row["test_date"]
    return (
        # 新→舊；沒有測試日期的爐次排在最後
        test_date is None,
        -(test_date.toordinal()) if test_date else 0,
        -row["test_id"],
        SUSPECT_ITEMS.index(row["item"]),
        LOCATION_ORDER.index(row["location"]) if row["location"] in LOCATION_ORDER else len(LOCATION_ORDER),
        row["sample_no"],
    )


def find_suspect_measurements(args: Mapping[str, Any]) -> Dict[str, Any]:
    """列出疑似異常的量測值（分頁）。

    統計基準永遠取該（項目, 材質）全部未排除資料；日期、材質等篩選只決定
    要列出哪些疑似值，避免縮小日期範圍後基準樣本不足而漏判。
    """
    item_filter = str(args.get("item") or "").strip()
    if item_filter and item_filter not in SUSPECT_ITEMS:
        raise MechanicalValidationError(f"量測項目必須為：{'、'.join(SUSPECT_ITEMS)}")
    items = (item_filter,) if item_filter else SUSPECT_ITEMS
    material_filter = str(args.get("material") or "").strip().lower()
    date_from = _parse_date(args.get("date_from") or None)
    date_to = _parse_date(args.get("date_to") or None)
    include_excluded = str(args.get("include_excluded", "")).lower() in ("1", "true")
    page = bounded_int(args.get("page"), 1, 1, 1000000)
    page_size = bounded_int(args.get("page_size"), 20, 1, 100)

    rows = [
        {
            "id": row.id, "test_id": row.test_id, "item": row.item,
            "location": row.location, "sample_no": row.sample_no,
            "value": float(row.value), "excluded": bool(row.excluded),
            "material": row.material, "test_date": row.test_date,
        }
        for row in db.session.query(
            MechanicalMeasurement.id,
            MechanicalMeasurement.test_id,
            MechanicalMeasurement.item,
            MechanicalMeasurement.location,
            MechanicalMeasurement.sample_no,
            MechanicalMeasurement.value,
            MechanicalMeasurement.excluded,
            MechanicalTest.material,
            MechanicalTest.test_date,
        )
        .join(MechanicalTest, MechanicalTest.id == MechanicalMeasurement.test_id)
        .filter(
            MechanicalMeasurement.item.in_(items),
            MechanicalMeasurement.value.isnot(None),
        )
        .all()
    ]

    grouped: Dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if not row["excluded"]:
            grouped[(row["item"], row["material"])].append(row["value"])
    stats_by_group = {key: _group_stats(values) for key, values in grouped.items()}

    suspects = []
    for row in rows:
        if row["excluded"] and not include_excluded:
            continue
        if material_filter and material_filter not in (row["material"] or "").lower():
            continue
        if date_from and (row["test_date"] is None or row["test_date"] < date_from):
            continue
        if date_to and (row["test_date"] is None or row["test_date"] > date_to):
            continue
        stats = stats_by_group.get((row["item"], row["material"]))
        if _is_suspect(row["value"], stats):
            suspects.append({**row, "stats": stats})
    suspects.sort(key=_sort_key)

    total = len(suspects)
    total_pages = (total + page_size - 1) // page_size
    page_rows = suspects[(page - 1) * page_size: page * page_size]

    tests = {
        test.id: test
        for test in MechanicalTest.query
        .options(selectinload(MechanicalTest.measurements))
        .filter(MechanicalTest.id.in_({row["test_id"] for row in page_rows}))
        .all()
    } if page_rows else {}

    data = []
    for row in page_rows:
        test = tests[row["test_id"]]
        measurement = next(m for m in test.measurements if m.id == row["id"])
        stats = row["stats"]
        siblings = sorted(
            (
                m for m in test.measurements
                if m.item == row["item"] and m.id != row["id"] and m.value is not None
            ),
            key=lambda m: (
                LOCATION_ORDER.index(m.location) if m.location in LOCATION_ORDER else len(LOCATION_ORDER),
                m.sample_no,
            ),
        )
        data.append({
            "識別碼": row["id"],
            "檢驗ID": row["test_id"],
            "測試日期": row["test_date"].isoformat() if row["test_date"] else None,
            "材質": test.material,
            "產品尺寸": test.product_size,
            "量測項目": row["item"],
            "測量位置": row["location"],
            "取樣序": row["sample_no"],
            "量測值": row["value"],
            "同組中位數": round(stats["median"], 4) if stats else None,
            "正常下界": round(stats["lower"], 4) if stats else None,
            "正常上界": round(stats["upper"], 4) if stats else None,
            "同組筆數": stats["n"] if stats else len(grouped.get((row["item"], row["material"]), [])),
            "同爐次其他值": [
                {
                    "測量位置": m.location,
                    "取樣序": m.sample_no,
                    "量測值": float(m.value),
                    "排除統計": bool(m.excluded),
                }
                for m in siblings
            ],
            "提示": _hint(row["value"], stats),
            "排除統計": bool(measurement.excluded),
            "排除原因": measurement.exclusion_reason,
            "排除時間": measurement.excluded_at.isoformat() if measurement.excluded_at else None,
        })

    return {
        "success": True,
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "rule": {"iqr_fence": IQR_FENCE, "min_group_size": MIN_GROUP_SIZE},
    }
