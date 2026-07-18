import pytest

from backend.extensions import db
from backend.models import SpcControlLimit
from backend.services.shipping_service import ShippingService
from backend.services.patrol_service import PatrolService


def _seed_legacy(source, key, limits, note=""):
    record = SpcControlLimit.query.filter_by(
        source=source,
        vendor=key.get("vendor") or "",
        material=key.get("material") or "",
        spec=key.get("spec") or "",
        field=key.get("field") or key.get("item"),
        position=key.get("position") or "",
    ).first()
    if record is None:
        record = SpcControlLimit(
            source=source,
            vendor=key.get("vendor") or "",
            material=key.get("material") or "",
            spec=key.get("spec") or "",
            field=key.get("field") or key.get("item"),
            position=key.get("position") or "",
        )
        db.session.add(record)
    record.x_cl, record.x_ucl, record.x_lcl = (
        limits["x_cl"], limits["x_ucl"], limits["x_lcl"]
    )
    record.r_cl, record.r_ucl, record.r_lcl = (
        limits["r_cl"], limits["r_ucl"], limits.get("r_lcl", 0)
    )
    record.avg_n = limits.get("avg_n", 5)
    record.note = note
    db.session.commit()
    return {"X中心線": float(record.x_cl), "識別碼": record.id}


def _seed_shipping(key, limits, note=""):
    return _seed_legacy("shipping", key, limits, note)


def _seed_patrol(key, limits, note=""):
    return _seed_legacy("patrol", key, limits, note)


def test_legacy_shipping_limits_are_readable_but_have_no_delete_service(db_session, setup_data):
    key = {"vendor": "", "material": "MAT-X-CTRL", "spec": "1*2*3", "field": "外徑"}
    limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1,
              "r_cl": 0.4, "r_ucl": 0.85, "r_lcl": 0.0, "avg_n": 5}

    # 尚未凍結時查詢應回傳 None
    assert ShippingService.get_frozen_limits(key) is None

    saved = _seed_shipping(key, limits, note="基準期確認")
    assert saved["X中心線"] == 10.0

    found = ShippingService.get_frozen_limits(key)
    assert found is not None
    assert found["x_ucl"] == 10.9
    assert found["note"] == "基準期確認"

    # 再次凍結相同 key 應更新既有紀錄，而非新增第二筆
    _seed_shipping(key, {**limits, "x_cl": 11.0}, note="重新確認")
    found2 = ShippingService.get_frozen_limits(key)
    assert found2["x_cl"] == 11.0

    assert not hasattr(ShippingService, "unfreeze_control_limits")
    assert not hasattr(ShippingService, "freeze_control_limits")
    assert ShippingService.get_frozen_limits(key) is not None


def test_get_stats_ignores_legacy_frozen_limits(db_session, setup_data):
    """舊界限保留供追溯，但不得覆蓋 2026 共用引擎結果。"""
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
    _seed_shipping(key, frozen_limits, note="測試凍結")

    stats_after = ShippingService.get_stats(key)
    assert stats_after["limits_frozen"] is False
    assert stats_after["x_cl"] == stats_before["x_cl"]
    assert stats_after["x_ucl"] == stats_before["x_ucl"]
    assert stats_after["data_hash"] == stats_before["data_hash"]


def test_source_change_updates_hash_even_when_legacy_limit_exists(db_session, setup_data):
    """來源資料變更必須改變雜湊；舊界限存在與否不影響即時結果。"""
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

    stats_first = ShippingService.get_stats(key, skip_frozen_limits=True)
    assert stats_first["applicability"]["applicable"] is False
    _seed_shipping(key, {
        "x_cl": 99.0, "x_ucl": 100.0, "x_lcl": 98.0,
        "r_cl": 1.0, "r_ucl": 2.0, "r_lcl": 0.0, "avg_n": 2,
    }, note="舊版資料")

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

    changed = ShippingService.get_stats(key)
    assert changed["data_hash"] != stats_first["data_hash"]
    assert changed["limits_frozen"] is False
    assert changed["x_cl"] != 99.0


def test_exclusion_updates_dataset_and_hash_without_applying_legacy_limit(db_session, setup_data):
    """排除會更新資料集與雜湊，舊界限仍只供追溯。"""
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

    _seed_shipping(key, {
        "x_cl": 99.0, "x_ucl": 100.0, "x_lcl": 98.0,
        "r_cl": 1.0, "r_ucl": 2.0, "r_lcl": 0.0, "avg_n": 2,
    }, note="舊版資料")

    stats_frozen = ShippingService.get_stats(key)
    assert stats_frozen["limits_frozen"] is False
    assert stats_frozen["excluded_count"] == 0

    # 排除離群量測值（§6.6：不刪除、保留追溯、排除統計）
    outlier = ShippingMeasurement.query.filter_by(item="外徑", group_num=3).one()
    ShippingService.set_measurement_exclusion(outlier.id, excluded=True, reason="量測異常，設備校正誤差")

    stats_after = ShippingService.get_stats(key)

    assert stats_after["limits_frozen"] is False
    assert stats_after["data_hash"] != stats_before["data_hash"]
    assert stats_after["excluded_count"] == 1
    assert 7.9 not in stats_after["all_values"]
    # 第6筆原本平均為(10.0+10.0+7.9)/3，排除離群值後只剩前兩組，平均回到10.0
    assert abs(stats_after["avgs"][-1] - 10.0) < 1e-9


def test_patrol_get_frozen_limits_returns_none_when_absent(app, db_session):
    with app.app_context():
        assert PatrolService.get_frozen_limits({
            "material": "6061", "spec": "10*2", "item": "外徑", "position": ""
        }) is None


def test_legacy_patrol_limits_are_readable_but_have_no_delete_service(app, db_session):
    with app.app_context():
        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        _seed_patrol(key, limits, note="製程確認穩定")
        frozen = PatrolService.get_frozen_limits(key)
        assert frozen is not None
        assert frozen["x_cl"] == pytest.approx(10.0)
        assert frozen["note"] == "製程確認穩定"

        assert not hasattr(PatrolService, "unfreeze_control_limits")
        assert not hasattr(PatrolService, "freeze_control_limits")
        assert PatrolService.get_frozen_limits(key) is not None


def test_patrol_refreeze_control_limits_updates_existing_record(app, db_session):
    """再次凍結相同 key 應更新既有紀錄，而非新增第二筆（迴歸測試，比照出貨端行為）"""
    with app.app_context():
        from backend.models import SpcControlLimit

        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        limits_first = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}
        limits_second = {"x_cl": 15.0, "x_ucl": 15.9, "x_lcl": 14.1, "r_cl": 0.6, "r_ucl": 1.3, "r_lcl": 0, "avg_n": 6}

        _seed_patrol(key, limits_first, note="第一次凍結")
        _seed_patrol(key, limits_second, note="第二次凍結")

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

        _seed_patrol(key_front, limits_front)
        _seed_patrol(key_mid, limits_mid)

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

        _seed_shipping(shipping_key, limits)
        _seed_patrol(patrol_key, limits_patrol)

        assert ShippingService.get_frozen_limits(shipping_key)["x_cl"] == pytest.approx(10.0)
        assert PatrolService.get_frozen_limits(patrol_key)["x_cl"] == pytest.approx(50.0)
