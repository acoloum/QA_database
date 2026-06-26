from backend.services.patrol_excel_utils import (
    build_patrol_measurements_from_row,
    create_unique_sheet_name,
    sanitize_sheet_name,
)


def test_sanitize_sheet_name_replaces_invalid_excel_chars():
    assert sanitize_sheet_name("85*2.8/6061?[T6]") == "85X2.86061T6"


def test_create_unique_sheet_name_truncates_and_deduplicates():
    existing_names = {"85X2.8-6061 管制圖數據"}

    sheet_name = create_unique_sheet_name("85*2.8-6061", "管制圖數據", existing_names)

    assert sheet_name == "85X2.8-6061 管制圖數據_1"
    assert len(create_unique_sheet_name("A" * 40, "管制圖數據", set())) <= 31


def test_build_patrol_measurements_from_row_filters_empty_values():
    row = {
        "外徑前段最小": "84.9",
        "外徑前段最大": "85.1",
        "內徑前段最小": "",
        "厚度後段最大": "2.8",
    }

    measurements = build_patrol_measurements_from_row(row)

    assert measurements == [
        {"item": "外徑", "position": "前段", "min_val": "84.9", "max_val": "85.1"},
        {"item": "厚度", "position": "後段", "min_val": None, "max_val": "2.8"},
    ]
