from typing import Any, Mapping


BASE_EXPORT_COLUMNS = ["識別碼", "檢驗日期", "材質", "檢驗規格", "訂單號碼", "檢驗人員", "廠商名稱", "組數"]


def build_shipping_export_columns(max_groups: int = 10) -> list[str]:
    columns = list(BASE_EXPORT_COLUMNS)
    for group_num in range(1, max_groups + 1):
        columns.extend([
            f"外徑{group_num}-最小", f"外徑{group_num}-最大",
            f"內徑{group_num}-最小", f"內徑{group_num}-最大",
            f"真圓度{group_num}",
            f"厚度{group_num}-最小", f"厚度{group_num}-最大",
            f"同心度{group_num}", f"長度{group_num}", f"硬度{group_num}", f"真直度{group_num}",
        ])
    return columns


def _measurement_value(measurements: Mapping[str, Any], group_num: int, item_name: str, key: str) -> Any:
    cell = measurements.get(str(group_num), {}).get(item_name)
    if not cell:
        return ""
    value = cell.get(key)
    return value if value is not None else ""


def _segmented_minmax(measurements: Mapping[str, Any], group_num: int, item_name: str) -> tuple[Any, Any]:
    """取該組該項目所有段(含未分段)的整體最小/最大值。

    分段資料的鍵為「項目@位置」;未分段即項目名。無資料時回傳空字串。
    """
    group = measurements.get(str(group_num), {}) or {}
    mins: list[Any] = []
    maxs: list[Any] = []
    for key, cell in group.items():
        if not cell or key.split('@', 1)[0] != item_name:
            continue
        if cell.get("value_min") is not None:
            mins.append(cell["value_min"])
        if cell.get("value_max") is not None:
            maxs.append(cell["value_max"])
    return (min(mins) if mins else "", max(maxs) if maxs else "")


def build_shipping_export_row(row: Mapping[str, Any], max_groups: int = 10) -> dict[str, Any]:
    measurements = row.get("measurements", {})
    export_row = {
        "識別碼": row["識別碼"],
        "檢驗日期": row["檢驗日期"],
        "材質": row["材質"],
        "檢驗規格": row["檢驗規格"],
        "訂單號碼": row["訂單號碼"],
        "檢驗人員": row["檢驗人員"],
        "廠商名稱": row["廠商中文名稱"],
        "組數": row.get("組數", 5),
    }

    for group_num in range(1, max_groups + 1):
        od_min, od_max = _segmented_minmax(measurements, group_num, "外徑")
        id_min, id_max = _segmented_minmax(measurements, group_num, "內徑")
        th_min, th_max = _segmented_minmax(measurements, group_num, "厚度")
        export_row[f"外徑{group_num}-最小"] = od_min
        export_row[f"外徑{group_num}-最大"] = od_max
        export_row[f"內徑{group_num}-最小"] = id_min
        export_row[f"內徑{group_num}-最大"] = id_max
        export_row[f"真圓度{group_num}"] = _measurement_value(measurements, group_num, "真圓度", "value_single")
        export_row[f"厚度{group_num}-最小"] = th_min
        export_row[f"厚度{group_num}-最大"] = th_max
        export_row[f"同心度{group_num}"] = _measurement_value(measurements, group_num, "同心度", "value_single")
        export_row[f"長度{group_num}"] = _measurement_value(measurements, group_num, "長度", "value_single")
        export_row[f"硬度{group_num}"] = _measurement_value(measurements, group_num, "硬度", "value_single")
        export_row[f"真直度{group_num}"] = _measurement_value(measurements, group_num, "真直度", "value_single")

    return export_row
