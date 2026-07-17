from backend.services.shipping_service import ShippingService


def test_freeze_query_and_unfreeze_control_limits(db_session, setup_data):
    key = {"vendor": "", "material": "MAT-X-CTRL", "spec": "1*2*3", "field": "外徑"}
    limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1,
              "r_cl": 0.4, "r_ucl": 0.85, "r_lcl": 0.0, "avg_n": 5}

    # 尚未凍結時查詢應回傳 None
    assert ShippingService.get_frozen_limits(key) is None

    saved = ShippingService.freeze_control_limits(key, limits, note="基準期確認")
    assert saved["X中心線"] == 10.0

    found = ShippingService.get_frozen_limits(key)
    assert found is not None
    assert found["x_ucl"] == 10.9
    assert found["note"] == "基準期確認"

    # 再次凍結相同 key 應更新既有紀錄，而非新增第二筆
    ShippingService.freeze_control_limits(key, {**limits, "x_cl": 11.0}, note="重新確認")
    found2 = ShippingService.get_frozen_limits(key)
    assert found2["x_cl"] == 11.0

    ShippingService.unfreeze_control_limits(key)
    assert ShippingService.get_frozen_limits(key) is None


def test_get_stats_applies_frozen_limits(db_session, setup_data):
    """已凍結的管制界限應覆蓋 get_stats 重新計算的結果，且 limits_frozen 標記為 True。"""
    payload = {
        '檢驗日期': '2026-07-17', '檢驗人員姓名': 'Test Inspector',
        '廠商中文名稱': 'Test Vendor', '檢驗規格': '10*2', '材質': 'CTRL-MAT',
        '訂單號碼': 'SO-CTRL-1', '組數': 1,
        'measurements': {str(i): {'外徑': {'value_min': 9.8, 'value_max': 10.2}} for i in range(1, 6)},
    }
    ShippingService.save_data(payload)

    key = {"vendor": "Test Vendor", "material": "CTRL-MAT", "spec": "10*2", "field": "外徑"}
    stats_before = ShippingService.get_stats(key)
    assert stats_before["limits_frozen"] is False

    frozen_limits = {
        "x_cl": 999.0, "x_ucl": 1000.0, "x_lcl": 998.0,
        "r_cl": 5.0, "r_ucl": 10.0, "r_lcl": 0.0, "avg_n": 5,
    }
    ShippingService.freeze_control_limits(key, frozen_limits, note="測試凍結")

    stats_after = ShippingService.get_stats(key)
    assert stats_after["limits_frozen"] is True
    assert stats_after["x_cl"] == 999.0
    assert stats_after["x_ucl"] == 1000.0
