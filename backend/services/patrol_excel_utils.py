from typing import Any, Mapping

import pandas as pd


PATROL_MEASUREMENT_COLUMNS = [
    ("外徑前段最小", "外徑", "前段", "min"), ("外徑前段最大", "外徑", "前段", "max"),
    ("外徑中段最小", "外徑", "中段", "min"), ("外徑中段最大", "外徑", "中段", "max"),
    ("外徑後段最小", "外徑", "後段", "min"), ("外徑後段最大", "外徑", "後段", "max"),
    ("內徑前段最小", "內徑", "前段", "min"), ("內徑前段最大", "內徑", "前段", "max"),
    ("內徑中段最小", "內徑", "中段", "min"), ("內徑中段最大", "內徑", "中段", "max"),
    ("內徑後段最小", "內徑", "後段", "min"), ("內徑後段最大", "內徑", "後段", "max"),
    ("厚度前段最小", "厚度", "前段", "min"), ("厚度前段最大", "厚度", "前段", "max"),
    ("厚度中段最小", "厚度", "中段", "min"), ("厚度中段最大", "厚度", "中段", "max"),
    ("厚度後段最小", "厚度", "後段", "min"), ("厚度後段最大", "厚度", "後段", "max"),
]


def sanitize_sheet_name(name: str) -> str:
    sanitized = name.replace('*', 'X')
    for ch in ['?', '/', '\\', '[', ']', ':']:
        sanitized = sanitized.replace(ch, '')
    return sanitized.strip()


def build_patrol_measurements_from_row(row: Mapping[str, Any]) -> list[dict[str, str | None]]:
    grouped: dict[str, dict[str, str | None]] = {}

    for col_name, item, position, min_max in PATROL_MEASUREMENT_COLUMNS:
        value = row.get(col_name)
        if value is None or pd.isna(value) or str(value).strip() == "":
            continue

        key = f"{item}_{position}"
        if key not in grouped:
            grouped[key] = {"item": item, "position": position, "min_val": None, "max_val": None}
        grouped[key][f"{min_max}_val"] = str(value)

    return list(grouped.values())
