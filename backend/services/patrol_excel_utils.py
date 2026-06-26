from copy import copy
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


def create_unique_sheet_name(prefix: str, sheet_name: str, existing_names: set[str]) -> str:
    base_name = sanitize_sheet_name(f"{prefix} {sheet_name}")
    if len(base_name) > 31:
        base_name = base_name[:31]

    unique_name = base_name
    counter = 1
    while unique_name in existing_names:
        suffix = f"_{counter}"
        unique_name = base_name[:31 - len(suffix)] + suffix
        counter += 1
    return unique_name


def remap_sheet_ref(formula: str, name_map: dict[str, str]) -> str:
    for old_name, new_name in name_map.items():
        formula = formula.replace(f"'{old_name}'!", f"'{new_name}'!")
        formula = formula.replace(f"{old_name}!", f"'{new_name}'!")
    return formula


def copy_spc_workbook_sheets(target_wb: Any, source_wb: Any, prefix: str) -> dict[str, str]:
    sheet_name_map: dict[str, str] = {}
    existing_names = set(target_wb.sheetnames)

    for source_sheet_name in source_wb.sheetnames:
        new_name = create_unique_sheet_name(prefix, source_sheet_name, existing_names)
        existing_names.add(new_name)
        sheet_name_map[source_sheet_name] = new_name

    for source_sheet_name in source_wb.sheetnames:
        source_ws = source_wb[source_sheet_name]
        target_ws = target_wb.create_sheet(title=sheet_name_map[source_sheet_name])

        for row_cells in source_ws.iter_rows():
            for cell in row_cells:
                new_cell = target_ws.cell(row=cell.row, column=cell.column, value=cell.value)
                if cell.has_style:
                    new_cell.font = copy(cell.font)
                    new_cell.fill = copy(cell.fill)
                    new_cell.border = copy(cell.border)
                    new_cell.alignment = copy(cell.alignment)
                    new_cell.number_format = cell.number_format

        for merged_range in source_ws.merged_cells.ranges:
            target_ws.merge_cells(str(merged_range))

        for col_letter, dim in source_ws.column_dimensions.items():
            target_ws.column_dimensions[col_letter].width = dim.width

        for chart in source_ws._charts:
            for series in chart.series:
                if series.val and hasattr(series.val, 'numRef') and series.val.numRef:
                    series.val.numRef.f = remap_sheet_ref(series.val.numRef.f, sheet_name_map)
                if series.cat and hasattr(series.cat, 'numRef') and series.cat.numRef:
                    series.cat.numRef.f = remap_sheet_ref(series.cat.numRef.f, sheet_name_map)
                if series.cat and hasattr(series.cat, 'strRef') and series.cat.strRef:
                    series.cat.strRef.f = remap_sheet_ref(series.cat.strRef.f, sheet_name_map)
            target_ws.add_chart(chart)

    return sheet_name_map


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
