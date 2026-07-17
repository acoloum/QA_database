import pytest

from backend.services.shipping_service import ShippingService
from backend.services.patrol_service import PatrolService


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


def test_freeze_then_exclude_keeps_frozen_limits_but_updates_dataset(db_session, setup_data):
    """凍結管制界限（§9.4）後,再排除離群量測值（§6.6）:
    已凍結的 x_cl/x_ucl/x_lcl 必須維持不變,但 get_stats 用於穩定性/能力
    計算的資料集(avgs/all_values/excluded_count)須反映排除後的最新結果。"""
    from backend.models import ShippingMeasurement

    key = {"vendor": "Test Vendor", "material": "CTRL-MAT-FREEZE-EXCL", "spec": "10*2", "field": "外徑"}

    # 建立5筆乾淨的基準資料(平均皆為10.0),再加1筆含離群量測值的資料，
    # 讓「凍結當下」的資料集已包含之後才會被排除的離群值。
    for i in range(5):
        ShippingService.save_data({
            '檢驗日期': f'2026-03-0{i + 1}', '檢驗人員姓名': 'Test Inspector',
            '廠商中文名稱': 'Test Vendor', '檢驗規格': '10*2', '材質': 'CTRL-MAT-FREEZE-EXCL',
            '訂單號碼': f'SO-FE-{i + 1}', '組數': 2,
            'measurements': {
                '1': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},
                '2': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},
            },
        })

    ShippingService.save_data({
        '檢驗日期': '2026-03-06', '檢驗人員姓名': 'Test Inspector',
        '廠商中文名稱': 'Test Vendor', '檢驗規格': '10*2', '材質': 'CTRL-MAT-FREEZE-EXCL',
        '訂單號碼': 'SO-FE-6', '組數': 3,
        'measurements': {
            '1': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},
            '2': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},
            '3': {'外徑': {'value_min': 7.9, 'value_max': 7.9}},  # 離群值，稍後排除
        },
    })

    stats_before = ShippingService.get_stats(key)
    assert stats_before["limits_frozen"] is False
    assert 7.9 in stats_before["all_values"]

    # 凍結目前的管制界限
    limits = {k: stats_before[k] for k in ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl")}
    limits["avg_n"] = stats_before["avg_subgroup_size"]
    ShippingService.freeze_control_limits(key, limits, note="基準期確認")

    stats_frozen = ShippingService.get_stats(key)
    assert stats_frozen["limits_frozen"] is True
    frozen_x_cl, frozen_x_ucl, frozen_x_lcl = (
        stats_frozen["x_cl"], stats_frozen["x_ucl"], stats_frozen["x_lcl"],
    )
    assert stats_frozen["excluded_count"] == 0

    # 排除離群量測值（§6.6：不刪除、保留追溯、排除統計）
    outlier = ShippingMeasurement.query.filter_by(item="外徑", group_num=3).one()
    ShippingService.set_measurement_exclusion(outlier.id, excluded=True, reason="量測異常，設備校正誤差")

    stats_after = ShippingService.get_stats(key)

    # 凍結界限須維持不變（不受排除影響）
    assert stats_after["limits_frozen"] is True
    assert stats_after["x_cl"] == frozen_x_cl
    assert stats_after["x_ucl"] == frozen_x_ucl
    assert stats_after["x_lcl"] == frozen_x_lcl

    # 但統計用資料集已反映排除後的最新結果
    assert stats_after["excluded_count"] == 1
    assert 7.9 not in stats_after["all_values"]
    # 第6筆原本平均為(10.0+10.0+7.9)/3，排除離群值後只剩前兩組，平均回到10.0
    assert abs(stats_after["avgs"][-1] - 10.0) < 1e-9


def test_patrol_get_frozen_limits_returns_none_when_absent(app, db_session):
    with app.app_context():
        assert PatrolService.get_frozen_limits({
            "material": "6061", "spec": "10*2", "item": "外徑", "position": ""
        }) is None


def test_patrol_freeze_and_unfreeze_control_limits_round_trip(app, db_session):
    with app.app_context():
        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        PatrolService.freeze_control_limits(key, limits, note="製程確認穩定")
        frozen = PatrolService.get_frozen_limits(key)
        assert frozen is not None
        assert frozen["x_cl"] == pytest.approx(10.0)
        assert frozen["note"] == "製程確認穩定"

        PatrolService.unfreeze_control_limits(key)
        assert PatrolService.get_frozen_limits(key) is None


def test_patrol_refreeze_control_limits_updates_existing_record(app, db_session):
    """再次凍結相同 key 應更新既有紀錄，而非新增第二筆（迴歸測試，比照出貨端行為）"""
    with app.app_context():
        from backend.models import SpcControlLimit

        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        limits_first = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}
        limits_second = {"x_cl": 15.0, "x_ucl": 15.9, "x_lcl": 14.1, "r_cl": 0.6, "r_ucl": 1.3, "r_lcl": 0, "avg_n": 6}

        PatrolService.freeze_control_limits(key, limits_first, note="第一次凍結")
        PatrolService.freeze_control_limits(key, limits_second, note="第二次凍結")

        frozen = PatrolService.get_frozen_limits(key)
        assert frozen["x_cl"] == pytest.approx(15.0)
        assert frozen["note"] == "第二次凍結"

        rows = SpcControlLimit.query.filter_by(
            source='patrol', vendor='', material="6061", spec="10*2", field="外徑", position="前段",
        ).all()
        assert len(rows) == 1


def test_patrol_freeze_control_limits_is_scoped_by_position(app, db_session):
    """同一材質/規格/項目但位置不同時，凍結界限互不影響（巡檢特有的位置維度）"""
    with app.app_context():
        key_front = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        key_mid = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "中段"}
        limits_front = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}
        limits_mid = {"x_cl": 20.0, "x_ucl": 20.9, "x_lcl": 19.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        PatrolService.freeze_control_limits(key_front, limits_front)
        PatrolService.freeze_control_limits(key_mid, limits_mid)

        assert PatrolService.get_frozen_limits(key_front)["x_cl"] == pytest.approx(10.0)
        assert PatrolService.get_frozen_limits(key_mid)["x_cl"] == pytest.approx(20.0)


def test_patrol_and_shipping_control_limits_do_not_collide(app, db_session):
    """相同材質/規格/項目時，巡檢與出貨的凍結界限彼此獨立（source 欄位區隔）"""
    with app.app_context():
        from backend.services.shipping_service import ShippingService

        shipping_key = {"vendor": "", "material": "6061", "spec": "10*2", "field": "外徑"}
        patrol_key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": ""}
        limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}
        limits_patrol = {"x_cl": 50.0, "x_ucl": 50.9, "x_lcl": 49.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        ShippingService.freeze_control_limits(shipping_key, limits)
        PatrolService.freeze_control_limits(patrol_key, limits_patrol)

        assert ShippingService.get_frozen_limits(shipping_key)["x_cl"] == pytest.approx(10.0)
        assert PatrolService.get_frozen_limits(patrol_key)["x_cl"] == pytest.approx(50.0)
