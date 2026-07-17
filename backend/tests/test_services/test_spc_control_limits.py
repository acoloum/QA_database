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


def test_refreezing_an_already_frozen_key_captures_fresh_data(db_session, setup_data):
    """§9.4 回歸測試：對已凍結的 key 再次執行凍結流程，必須反映「目前」重新計算
    的數值，而非讀回舊的凍結值（否則等同流程變更後仍讀不到最新資料的靜默失敗）。
    模擬 freeze_control_limits_route 的實際呼叫方式：
    ShippingService.get_stats(key, skip_frozen_limits=True)。"""
    key = {"vendor": "Test Vendor", "material": "CTRL-MAT-REFREEZE", "spec": "20*2", "field": "外徑"}

    # 建立 5 筆基準資料，外徑量測平均皆為 10.0（構成初始基準期）
    for i in range(5):
        ShippingService.save_data({
            '檢驗日期': f'2026-01-0{i + 1}', '檢驗人員姓名': 'Test Inspector',
            '廠商中文名稱': 'Test Vendor', '檢驗規格': '20*2', '材質': 'CTRL-MAT-REFREEZE',
            '訂單號碼': f'SO-RF-{i + 1}', '組數': 2,
            'measurements': {
                '1': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},
                '2': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},
            },
        })

    # 第一次凍結：模擬凍結路由（略過既有凍結值，取得依當下資料重新計算的數值）
    stats_first = ShippingService.get_stats(key, skip_frozen_limits=True)
    assert round(stats_first["x_cl"], 4) == 10.0
    limits_first = {k: stats_first[k] for k in ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl")}
    limits_first["avg_n"] = stats_first["avg_subgroup_size"]
    ShippingService.freeze_control_limits(key, limits_first, note="第一次凍結")

    frozen_first = ShippingService.get_frozen_limits(key)
    assert round(frozen_first["x_cl"], 4) == 10.0

    # 新增一筆製程明顯偏移的資料（平均 20.0），代表已記錄在案的製程變更
    ShippingService.save_data({
        '檢驗日期': '2026-01-06', '檢驗人員姓名': 'Test Inspector',
        '廠商中文名稱': 'Test Vendor', '檢驗規格': '20*2', '材質': 'CTRL-MAT-REFREEZE',
        '訂單號碼': 'SO-RF-6', '組數': 2,
        'measurements': {
            '1': {'外徑': {'value_min': 19.9, 'value_max': 20.1}},
            '2': {'外徑': {'value_min': 19.9, 'value_max': 20.1}},
        },
    })

    # 修正前的臭蟲：一般查詢（未 skip）在 key 已凍結時，仍會讀回舊的凍結值，
    # 即使底層資料已經改變——這是預期行為（畫面顯示應維持凍結值直到重新凍結）。
    stats_plain_while_frozen = ShippingService.get_stats(key)
    assert stats_plain_while_frozen["limits_frozen"] is True
    assert round(stats_plain_while_frozen["x_cl"], 4) == 10.0

    # 但凍結路由重新凍結時必須拿到「當下依全部 6 筆重新計算」的數值，而非
    # 讀回步驟一凍結的 10.0（這正是先前造成靜默失敗的臭蟲）
    expected_x_cl = (10.0 * 5 + 20.0) / 6
    stats_for_refreeze = ShippingService.get_stats(key, skip_frozen_limits=True)
    assert round(stats_for_refreeze["x_cl"], 4) == round(expected_x_cl, 4)
    assert stats_for_refreeze["x_cl"] != frozen_first["x_cl"]

    limits_second = {k: stats_for_refreeze[k] for k in ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl")}
    limits_second["avg_n"] = stats_for_refreeze["avg_subgroup_size"]
    ShippingService.freeze_control_limits(key, limits_second, note="製程變更後重新凍結")

    frozen_second = ShippingService.get_frozen_limits(key)
    assert round(frozen_second["x_cl"], 4) == round(expected_x_cl, 4)
    assert frozen_second["x_cl"] != frozen_first["x_cl"]
