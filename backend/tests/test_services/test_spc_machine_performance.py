"""巡檢機器績效 Pm/Pmk G 法計算測試。"""

import numpy as np
import pytest

from backend.services.spc_distribution import assess_distribution
from backend.services.spc_machine_performance import calculate_machine_performance


NORMAL_MACHINE_VALUES_50 = [
    10.0 + value for value in np.linspace(-0.18, 0.18, 50)
]


def test_machine_normal_g_method_matches_six_sigma():
    distribution = assess_distribution(NORMAL_MACHINE_VALUES_50, field="外徑")

    result = calculate_machine_performance(
        NORMAL_MACHINE_VALUES_50,
        {"found": True, "LSL": 9.0, "USL": 11.0},
        distribution,
        "主要",
    )

    expected_pm = 2.0 / (6.0 * np.std(NORMAL_MACHINE_VALUES_50, ddof=1))
    assert result["index_family"] == "machine"
    assert result["pm"] == pytest.approx(expected_pm, rel=0.02)
    assert result["pmk"] == min(result["pmu"], result["pml"])
    assert result["preliminary"] is False
    assert result["targets"] == {"class": "主要", "pm": 2.0, "pmk": 1.67}
    assert result["approvable"] is True


def test_machine_study_under_50_is_preliminary_and_not_approvable():
    distribution = assess_distribution(NORMAL_MACHINE_VALUES_50, field="外徑")

    result = calculate_machine_performance(
        NORMAL_MACHINE_VALUES_50[:49],
        {"found": True, "LSL": 9.0, "USL": 11.0},
        distribution,
        "其他",
    )

    assert result["preliminary"] is True
    assert result["reason_code"] == "MACHINE_SAMPLE_INSUFFICIENT"
    assert result["approvable"] is False


def test_machine_performance_rejects_unconfirmed_distribution():
    result = calculate_machine_performance(
        NORMAL_MACHINE_VALUES_50,
        {"found": True, "LSL": 9.0, "USL": 11.0},
        {"accepted": False, "reason_code": "GOODNESS_OF_FIT_REJECTED"},
        "主要",
    )

    assert result["available"] is False
    assert result["reason_code"] == "GOODNESS_OF_FIT_REJECTED"
