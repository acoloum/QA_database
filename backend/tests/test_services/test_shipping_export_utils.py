from backend.services.shipping_export import (
    build_shipping_export_columns,
    build_shipping_export_row,
)


def test_build_shipping_export_columns_keeps_measurement_order():
    columns = build_shipping_export_columns(max_groups=1)

    assert columns == [
        "識別碼", "檢驗日期", "材質", "檢驗規格", "訂單號碼", "檢驗人員", "廠商名稱", "組數",
        "外徑1-最小", "外徑1-最大", "內徑1-最小", "內徑1-最大", "真圓度1",
        "厚度1-最小", "厚度1-最大", "同心度1", "長度1", "硬度1", "真直度1",
    ]


def test_build_shipping_export_row_maps_nested_measurements_and_empty_values():
    row = {
        "識別碼": 7,
        "檢驗日期": "2026-06-27",
        "材質": "6061",
        "檢驗規格": "10*2",
        "訂單號碼": "SO-1",
        "檢驗人員": "檢驗員A",
        "廠商中文名稱": "廠商A",
        "組數": 1,
        "measurements": {
            "1": {
                "外徑": {"value_min": 9.8, "value_max": 10.2},
                "硬度": {"value_single": None},
            },
        },
    }

    export_row = build_shipping_export_row(row, max_groups=1)

    assert export_row["外徑1-最小"] == 9.8
    assert export_row["外徑1-最大"] == 10.2
    assert export_row["硬度1"] == ""
    assert export_row["廠商名稱"] == "廠商A"
