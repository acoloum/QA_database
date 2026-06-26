from backend.services.shipping_import import (
    build_shipping_measurements_from_row,
    get_import_value,
    parse_import_number,
)


def test_parse_import_number_handles_empty_and_invalid_values():
    assert parse_import_number(None) is None
    assert parse_import_number("") is None
    assert parse_import_number("abc") is None
    assert parse_import_number("10.5") == 10.5


def test_build_shipping_measurements_from_row_maps_minmax_and_single_values():
    row = {
        "外徑1-min": "9.8",
        "外徑1-max": "10.2",
        "硬度1": "55",
        "厚度1-min": "",
    }

    measurements = build_shipping_measurements_from_row(row, max_groups=1)

    assert measurements == [
        {"group_num": 1, "item": "外徑", "value_min": 9.8, "value_max": 10.2, "value_single": None},
        {"group_num": 1, "item": "硬度", "value_min": None, "value_max": None, "value_single": 55.0},
    ]
    assert get_import_value({"A": float("nan")}, "A") is None
