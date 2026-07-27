"""偏倚與線性統計引擎測試。"""

import json
from pathlib import Path

import pytest

from backend.services.msa_bias_linearity import analyze_bias, analyze_linearity
from backend.services.msa_contracts import MsaMethodContext
from backend.services.msa_errors import MsaMethodNotApplicable


@pytest.fixture(scope="module")
def reference():
    path = (
        Path(__file__).parents[1] / "fixtures"
        / "msa_bias_linearity_reference.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _context(section, **overrides):
    values = dict(section["context"])
    values.update(overrides)
    return MsaMethodContext(**values)


def _bias_input(section):
    return {
        "reference_value": section["reference_value"],
        "readings": list(section["readings"]),
    }


# ---------------------------------------------------------------------------
# 偏倚
# ---------------------------------------------------------------------------


def test_bias_matches_t_test_reference(reference):
    section = reference["bias"]
    output = analyze_bias(_bias_input(section), _context(section))
    stats = output.statistics
    expected = section["expected"]

    assert stats["n"] == expected["n"]
    assert stats["mean"] == pytest.approx(expected["mean"], rel=1e-12)
    assert stats["bias"] == pytest.approx(expected["bias"], rel=1e-9)
    assert stats["repeatability_sd"] == pytest.approx(
        expected["repeatability_sd"], rel=1e-9
    )
    assert stats["t_value"] == pytest.approx(expected["t_value"], rel=1e-9)
    assert stats["p_value"] == pytest.approx(expected["p_value"], rel=1e-6)
    assert stats["confidence_interval"] == pytest.approx(
        expected["confidence_interval"], rel=1e-9
    )


def test_bias_flags_significance_by_confidence_interval(reference):
    section = reference["bias"]
    output = analyze_bias(_bias_input(section), _context(section))

    assert output.statistics["significant"] is True
    assert output.statistics["confidence_interval_excludes_zero"] is True


def test_bias_reports_percentage_of_tolerance(reference):
    section = reference["bias"]
    output = analyze_bias(_bias_input(section), _context(section))

    assert output.statistics["percent_bias_of_tolerance"] == pytest.approx(
        section["expected"]["percent_bias_of_tolerance"], rel=1e-9
    )


def test_bias_without_tolerance_reports_percentage_as_unavailable(reference):
    section = reference["bias"]
    output = analyze_bias(
        _bias_input(section), _context(section, tolerance=None),
    )

    assert output.statistics["percent_bias_of_tolerance"] is None


def test_bias_requires_at_least_two_readings(reference):
    section = reference["bias"]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_bias(
            {"reference_value": 10.0, "readings": [10.0]}, _context(section),
        )

    assert error.value.details["reason"] == "insufficient_readings"


def test_bias_requires_a_reference_value(reference):
    section = reference["bias"]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_bias(
            {"reference_value": None, "readings": [10.0, 10.1]},
            _context(section),
        )

    assert error.value.details["reason"] == "reference_value_missing"


def test_zero_spread_without_bias_reports_no_observed_bias(reference):
    section = reference["bias"]
    output = analyze_bias(
        {"reference_value": 10.0, "readings": [10.0] * 5}, _context(section),
    )

    assert output.statistics["bias"] == 0.0
    assert output.statistics["t_value"] is None
    assert output.statistics["significant"] is False
    assert output.statistics["estimability_note"] == (
        "重複性標準差為 0 且偏倚為 0，無法進行 t 檢定但未觀察到偏倚"
    )


def test_zero_spread_with_bias_is_reported_as_definite_bias(reference):
    section = reference["bias"]
    output = analyze_bias(
        {"reference_value": 10.0, "readings": [10.2] * 5}, _context(section),
    )

    assert output.statistics["bias"] == pytest.approx(0.2, rel=1e-12)
    assert output.statistics["t_value"] is None
    assert output.statistics["significant"] is True
    assert output.statistics["estimability_note"] == (
        "重複性標準差為 0 但偏倚不為 0，判定為明顯偏倚且無法估計檢定統計量"
    )


def test_bias_rejects_non_finite_reading(reference):
    section = reference["bias"]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_bias(
            {"reference_value": 10.0, "readings": [10.0, float("inf")]},
            _context(section),
        )

    assert error.value.details["reason"] == "non_finite_reading"


# ---------------------------------------------------------------------------
# 線性
# ---------------------------------------------------------------------------


def test_linearity_reports_regression_bands_and_residuals(reference):
    section = reference["linearity"]
    output = analyze_linearity(section["groups"], _context(section))
    regression = output.statistics["regression"]
    expected = section["expected"]

    assert regression["slope"] == pytest.approx(expected["slope"], rel=1e-9)
    assert regression["intercept"] == pytest.approx(
        expected["intercept"], rel=1e-9
    )
    assert regression["slope_p_value"] == pytest.approx(
        expected["slope_p"], rel=1e-6
    )
    assert regression["r_squared"] == pytest.approx(
        expected["r_squared"], rel=1e-9
    )
    assert "confidence_band" in output.chart_data
    assert "prediction_band" in output.chart_data
    assert "residuals" in output.chart_data


def test_linearity_reports_slope_standard_error_and_interval(reference):
    section = reference["linearity"]
    output = analyze_linearity(section["groups"], _context(section))
    regression = output.statistics["regression"]
    expected = section["expected"]

    assert regression["slope_std_error"] == pytest.approx(
        expected["slope_se"], rel=1e-9
    )
    assert regression["slope_confidence_interval"] == pytest.approx(
        expected["slope_confidence_interval"], rel=1e-9
    )
    assert regression["residual_mse"] == pytest.approx(
        expected["residual_mse"], rel=1e-9
    )


def test_linearity_reports_each_reference_level_interval(reference):
    section = reference["linearity"]
    output = analyze_linearity(section["groups"], _context(section))
    levels = output.statistics["reference_levels"]
    expected = section["expected"]["group_stats"]

    assert len(levels) == len(expected)
    for actual, wanted in zip(levels, expected):
        assert actual["reference_value"] == wanted["reference_value"]
        assert actual["mean_bias"] == pytest.approx(
            wanted["mean_bias"], rel=1e-9
        )
        assert actual["confidence_interval"] == pytest.approx(
            wanted["confidence_interval"], rel=1e-9
        )
        assert actual["crosses_zero"] is wanted["crosses_zero"]


def test_linearity_conclusion_does_not_rely_on_r_squared_alone(reference):
    """R² 高達 0.95 但斜率顯著且多數量程 CI 不含 0，必須判定不合格。"""
    section = reference["linearity"]
    output = analyze_linearity(section["groups"], _context(section))
    evidence = output.statistics["linearity_evidence"]

    assert output.statistics["regression"]["r_squared"] > 0.9
    assert evidence["slope_significant"] is True
    assert evidence["levels_excluding_zero"] == 4
    assert evidence["acceptable"] is False
    assert "r_squared" not in evidence["decision_basis"]
    assert set(evidence["decision_basis"]) == {
        "slope_significant", "levels_excluding_zero", "intercept_significant",
    }


def test_linearity_requires_at_least_five_reference_levels(reference):
    section = reference["linearity"]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_linearity(section["groups"][:4], _context(section))

    assert error.value.details["reason"] == "insufficient_reference_levels"


def test_linearity_rejects_constant_reference_values(reference):
    section = reference["linearity"]
    groups = [
        {"reference_value": 5.0, "readings": [5.0, 5.01]}
        for _ in range(5)
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_linearity(groups, _context(section))

    assert error.value.details["reason"] == "singular_design"


def test_linearity_warns_when_range_coverage_is_narrow(reference):
    """量程覆蓋不足時仍可計算，但必須明確警告結論外推風險。"""
    section = reference["linearity"]
    groups = [
        {
            "reference_value": 9.90 + index * 0.01,
            "readings": [9.90 + index * 0.01 + 0.001, 9.90 + index * 0.01],
        }
        for index in range(5)
    ]

    output = analyze_linearity(groups, _context(section))

    assert any(
        warning["code"] == "MSA_LINEARITY_RANGE_COVERAGE_LOW"
        for warning in output.warnings
    )


def test_linearity_requires_repeat_readings_per_level(reference):
    section = reference["linearity"]
    groups = [
        {"reference_value": float(index), "readings": [float(index) + 0.01]}
        for index in range(2, 7)
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_linearity(groups, _context(section))

    assert error.value.details["reason"] == "insufficient_trials"


def test_linearity_rejects_non_finite_reading(reference):
    section = reference["linearity"]
    groups = [dict(group) for group in section["groups"]]
    groups[0] = {
        "reference_value": 2.0, "readings": [2.05, float("nan"), 2.04, 2.05],
    }

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_linearity(groups, _context(section))

    assert error.value.details["reason"] == "non_finite_reading"
