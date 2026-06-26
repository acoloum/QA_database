from typing import Any, Mapping

import pandas as pd


IMPORT_ITEMS = (
    ('外徑', True), ('內徑', True), ('厚度', True),
    ('同心度', False), ('長度', False), ('硬度', False),
    ('韋伯氏硬度', False), ('真直度', False), ('真圓度', False),
)


def parse_import_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_import_value(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return str(value)


def build_shipping_measurements_from_row(row: Mapping[str, Any], max_groups: int = 10) -> list[dict[str, Any]]:
    measurements: list[dict[str, Any]] = []
    for group_num in range(1, max_groups + 1):
        for item_name, is_minmax in IMPORT_ITEMS:
            if is_minmax:
                value_min = parse_import_number(get_import_value(row, f'{item_name}{group_num}-min'))
                value_max = parse_import_number(get_import_value(row, f'{item_name}{group_num}-max'))
                value_single = None
            else:
                value_min = None
                value_max = None
                value_single = parse_import_number(get_import_value(row, f'{item_name}{group_num}'))

            if value_min is None and value_max is None and value_single is None:
                continue

            measurements.append({
                "group_num": group_num,
                "item": item_name,
                "value_min": value_min,
                "value_max": value_max,
                "value_single": value_single,
            })
    return measurements
