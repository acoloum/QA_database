"""爐溫測試純計算 helper 測試。"""
import pytest

from backend.services.pyrometry_calculations import (
    PyrometryValidationError,
    evaluate_sat,
    evaluate_tus,
    interp_error,
    validate_test_payload,
)


def test_interp_error_clamps_and_interpolates():
    points = [(100, 0.2), (200, 0.6)]
    assert interp_error(points, 50) == 0.2
    assert interp_error(points, 150) == 0.4
    assert interp_error(points, 300) == 0.6


def test_validate_test_payload_normalizes_default_test_type():
    payload = validate_test_payload({
        "爐子ID": 1,
        "測試日期": "2026-06-20",
        "設定溫度": "180",
        "允許公差": "10",
        "points": [],
    }, default_test_type="TUS")
    assert payload["測試類型"] == "TUS"


def test_validate_test_payload_rejects_invalid_type():
    with pytest.raises(PyrometryValidationError):
        validate_test_payload({
            "爐子ID": 1,
            "測試日期": "2026-06-20",
            "設定溫度": "180",
            "測試類型": "BAD",
            "points": [],
        })


def test_evaluate_helpers_keep_existing_judgement_contract():
    tus = evaluate_tus(180, 10, [{"最高溫": 191, "最低溫": 180}])
    sat = evaluate_sat(5, [{"控溫區": "Z1", "修正值": 0, "readings": [
        {"控制儀表讀值": 180, "校正測試讀值": 187},
    ]}])
    assert tus["是否合格"] is False
    assert tus["points"][0]["最大偏差"] == 11
    assert sat["是否合格"] is False
    assert sat["points"][0]["readings"][0]["偏差"] == 7
