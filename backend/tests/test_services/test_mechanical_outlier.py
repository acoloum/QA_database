"""機械性質疑似異常值偵測與排除統計服務測試。"""
from datetime import date

import pytest

from backend.models import AuditLog, MechanicalMeasurement, MechanicalTest
from backend.services.mechanical_outlier import find_suspect_measurements
from backend.services.mechanical_service import (
    MechanicalNotFoundError,
    MechanicalService,
    MechanicalValidationError,
)


def _test(db_session, *, material="6061-T651", test_date=date(2026, 1, 1), values=None):
    """建立一筆爐次；values 為 {(項目, 位置, 取樣序): 量測值}。"""
    test = MechanicalTest(product_size="66.7*59", material=material, test_date=test_date)
    for (item, location, sample_no), value in (values or {}).items():
        test.measurements.append(MechanicalMeasurement(
            item=item, location=location, sample_no=sample_no, value=value,
        ))
    db_session.add(test)
    db_session.flush()
    return test


def _seed_normal_group(db_session, count=12, *, item="抗拉強度", base=370.0, material="6061-T651"):
    """建立一組正常分布的爐次，作為同組統計基準。"""
    for i in range(count):
        _test(
            db_session,
            material=material,
            test_date=date(2026, 1, 1 + i),
            values={(item, "爐門", 1): base + i, (item, "爐頂", 1): base + i - 3},
        )


def _rows(result):
    return [(row["量測項目"], row["量測值"]) for row in result["data"]]


def test_flags_digit_shift_typo_and_keeps_normal_values(db_session):
    _seed_normal_group(db_session)
    typo = _test(db_session, test_date=date(2026, 2, 1), values={
        ("抗拉強度", "爐門", 1): 371.0,
        ("抗拉強度", "爐頂", 1): 37128.0,
    })
    db_session.commit()

    result = find_suspect_measurements({})

    assert _rows(result) == [("抗拉強度", 37128.0)]
    row = result["data"][0]
    assert row["檢驗ID"] == typo.id
    assert row["測量位置"] == "爐頂"
    assert row["同組筆數"] == 26
    assert row["同爐次其他值"] == [
        {"測量位置": "爐門", "取樣序": 1, "量測值": 371.0, "排除統計": False},
    ]
    assert "371.28" in row["提示"]
    assert result["total"] == 1


def test_flags_too_small_value_with_decimal_hint(db_session):
    _seed_normal_group(db_session)
    _test(db_session, values={("抗拉強度", "爐頂", 1): 37.42})
    db_session.commit()

    row = find_suspect_measurements({})["data"][0]

    assert row["量測值"] == 37.42
    assert "374.2" in row["提示"]


def test_flags_zero_even_when_group_too_small(db_session):
    _test(db_session, values={("降伏強度", "爐門", 1): 0})
    db_session.commit()

    result = find_suspect_measurements({})

    assert _rows(result) == [("降伏強度", 0.0)]
    assert "0 或負值" in result["data"][0]["提示"]


def test_skips_fence_check_when_group_below_minimum(db_session):
    _seed_normal_group(db_session, count=4)
    _test(db_session, values={("抗拉強度", "爐頂", 1): 37128.0})
    db_session.commit()

    assert find_suspect_measurements({})["data"] == []


def test_groups_statistics_by_material(db_session):
    _seed_normal_group(db_session, material="6061-T651", base=370.0)
    _seed_normal_group(db_session, material="6063-T5", base=200.0)
    db_session.commit()

    # 兩種材質各自在自己的組內都正常，不可因混組而互相判為異常
    assert find_suspect_measurements({})["data"] == []


def test_excluded_values_do_not_shape_statistics_and_are_hidden_by_default(db_session):
    _seed_normal_group(db_session)
    bad = _test(db_session, values={("抗拉強度", "爐頂", 1): 37128.0})
    bad.measurements[0].excluded = True
    bad.measurements[0].exclusion_reason = "誤植"
    db_session.commit()

    assert find_suspect_measurements({})["data"] == []

    shown = find_suspect_measurements({"include_excluded": "1"})["data"]
    assert [row["量測值"] for row in shown] == [37128.0]
    assert shown[0]["排除統計"] is True
    assert shown[0]["排除原因"] == "誤植"
    assert shown[0]["同組筆數"] == 24


def test_filters_by_item_material_and_date(db_session):
    _seed_normal_group(db_session, item="抗拉強度")
    _seed_normal_group(db_session, item="硬度", base=66.0)
    _test(db_session, test_date=date(2026, 3, 1), values={
        ("抗拉強度", "爐頂", 1): 37128.0, ("硬度", "爐門", 1): 669.0,
    })
    _test(db_session, test_date=date(2025, 3, 1), values={("硬度", "爐門", 1): 655.0})
    db_session.commit()

    assert _rows(find_suspect_measurements({"item": "硬度"})) == [("硬度", 669.0), ("硬度", 655.0)]
    # 同一爐次內依項目固定順序（硬度、抗拉、降伏、伸長率）排列
    assert _rows(find_suspect_measurements({"date_from": "2026-01-01"})) == [
        ("硬度", 669.0), ("抗拉強度", 37128.0),
    ]
    assert find_suspect_measurements({"material": "6063"})["data"] == []


def test_ignores_items_outside_spc_scope(db_session):
    for i in range(12):
        _test(db_session, test_date=date(2026, 1, 1 + i), values={("EC值", "爐門", 1): 50 + i})
    _test(db_session, values={("EC值", "爐門", 1): 9999})
    db_session.commit()

    assert find_suspect_measurements({})["data"] == []


def test_paginates_results(db_session):
    _seed_normal_group(db_session)
    for i in range(3):
        _test(db_session, test_date=date(2026, 5, 1 + i), values={("抗拉強度", "爐頂", 1): 37000.0 + i})
    db_session.commit()

    page = find_suspect_measurements({"page": "2", "page_size": "2"})

    assert page["total"] == 3
    assert page["total_pages"] == 2
    assert [row["量測值"] for row in page["data"]] == [37000.0]


def test_set_exclusion_requires_reason(db_session):
    test = _test(db_session, values={("硬度", "爐門", 1): 669.0})
    db_session.commit()

    with pytest.raises(MechanicalValidationError):
        MechanicalService.set_measurement_exclusion(test.measurements[0].id, True, "  ", actor_id=None)


def test_set_exclusion_missing_measurement(db_session):
    with pytest.raises(MechanicalNotFoundError):
        MechanicalService.set_measurement_exclusion(999999, True, "誤植", actor_id=None)


def test_set_and_restore_exclusion_writes_audit_log(db_session):
    test = _test(db_session, values={("硬度", "爐門", 1): 669.0})
    db_session.commit()
    measurement_id = test.measurements[0].id

    excluded = MechanicalService.set_measurement_exclusion(measurement_id, True, "小數點誤植", actor_id=None)
    assert excluded["排除統計"] is True
    assert excluded["排除原因"] == "小數點誤植"
    assert excluded["排除時間"] is not None

    restored = MechanicalService.set_measurement_exclusion(measurement_id, False, "已確認原值正確", actor_id=None)
    assert restored["排除統計"] is False
    assert restored["排除原因"] is None

    measurement = db_session.get(MechanicalMeasurement, measurement_id)
    assert measurement.excluded is False
    logs = AuditLog.query.filter_by(module="mechanical_measurement", record_id=measurement_id).order_by(AuditLog.id).all()
    assert [log.action for log in logs] == ["exclude", "restore"]
    assert logs[1].new_value["action_reason"] == "已確認原值正確"
