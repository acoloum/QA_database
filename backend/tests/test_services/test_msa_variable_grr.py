"""計量型 GRR（極差法與平均值－極差法）統計引擎測試。"""

import json
from pathlib import Path

import pytest

from backend.services.msa_contracts import MsaMethodContext
from backend.services.msa_errors import MsaMethodNotApplicable
from backend.services.msa_variable_grr import analyze_range, analyze_xbar_r


@pytest.fixture(scope="module")
def grr_reference():
    path = (
        Path(__file__).parents[1] / "fixtures" / "msa_grr_reference.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _context(reference, **overrides):
    values = dict(reference["context"])
    values.update(overrides)
    return MsaMethodContext(**values)


def _balanced(reference):
    return [dict(row) for row in reference["observations"]]


# ---------------------------------------------------------------------------
# 平均值－極差法
# ---------------------------------------------------------------------------


def test_xbar_r_matches_reference_components(grr_reference):
    output = analyze_xbar_r(
        _balanced(grr_reference), _context(grr_reference)
    )
    stats = output.statistics
    expected = grr_reference["expected"]

    assert stats["ev"] == pytest.approx(expected["ev"], rel=1e-9)
    assert stats["av"] == pytest.approx(expected["av"], rel=1e-9)
    assert stats["grr"] == pytest.approx(expected["grr"], rel=1e-9)
    assert stats["pv"] == pytest.approx(expected["pv"], rel=1e-9)
    assert stats["tv"] == pytest.approx(expected["tv"], rel=1e-9)
    assert stats["ndc"] == expected["ndc"]


def test_xbar_r_reports_percentages_against_study_variation_and_tolerance(
    grr_reference,
):
    output = analyze_xbar_r(
        _balanced(grr_reference), _context(grr_reference)
    )
    expected = grr_reference["expected"]

    assert output.statistics["percent_study_variation"]["grr"] == (
        pytest.approx(expected["percent_study_variation"]["grr"], rel=1e-9)
    )
    assert output.statistics["percent_tolerance"]["grr"] == (
        pytest.approx(expected["percent_tolerance"]["grr"], rel=1e-9)
    )


def test_xbar_r_uses_six_sigma_study_variation(grr_reference):
    output = analyze_xbar_r(
        _balanced(grr_reference), _context(grr_reference)
    )

    assert output.statistics["study_variation_multiplier"] == 6.0
    assert output.statistics["study_variation"]["grr"] == pytest.approx(
        6.0 * grr_reference["expected"]["grr"], rel=1e-9
    )


def test_percent_tolerance_is_unavailable_without_tolerance(grr_reference):
    output = analyze_xbar_r(
        _balanced(grr_reference), _context(grr_reference, tolerance=None),
    )

    assert output.statistics["percent_tolerance"] is None
    assert output.applicability["tolerance_available"] is False
    assert any(
        warning["code"] == "MSA_TOLERANCE_UNAVAILABLE"
        for warning in output.warnings
    )


def test_percent_process_is_reported_when_process_sigma_is_known(
    grr_reference,
):
    output = analyze_xbar_r(
        _balanced(grr_reference), _context(grr_reference, process_sigma=0.05),
    )

    assert output.statistics["percent_process"]["grr"] == pytest.approx(
        100.0 * grr_reference["expected"]["grr"] / 0.05, rel=1e-9
    )


def test_negative_reproducibility_variance_is_clamped_with_reason(
    grr_reference,
):
    """評價人間差異小於重複性時，AV 取 0 並保留原始負值與理由。"""
    observations = _balanced(grr_reference)
    for row in observations:
        # 讓兩位評價人的平均完全相同，av_raw_variance 必為負
        row["value"] = 10.0 if row["trial"] == 1 else 10.2

    output = analyze_xbar_r(observations, _context(grr_reference))

    assert output.statistics["av"] == 0.0
    assert output.statistics["av_raw_variance"] < 0
    assert output.statistics["av_adjustment_reason"] == (
        "再現性變異數計算為負，依 MSA 第四版取 0"
    )


def test_zero_repeatability_and_reproducibility_reports_no_ndc(grr_reference):
    observations = _balanced(grr_reference)
    for row in observations:
        row["value"] = 10.0

    output = analyze_xbar_r(observations, _context(grr_reference))

    assert output.statistics["grr"] == 0.0
    assert output.statistics["ndc"] is None
    assert any(
        warning["code"] == "MSA_GRR_ZERO_VARIATION"
        for warning in output.warnings
    )


def test_single_appraiser_reports_reproducibility_as_not_applicable(
    grr_reference,
):
    observations = [
        row for row in _balanced(grr_reference)
        if row["appraiser"] == "A01"
    ]

    output = analyze_xbar_r(observations, _context(grr_reference))

    assert output.statistics["av"] is None
    assert output.applicability["reproducibility_available"] is False
    assert output.statistics["grr"] == pytest.approx(
        output.statistics["ev"], rel=1e-12
    )


# ---------------------------------------------------------------------------
# 不適用情境
# ---------------------------------------------------------------------------


def test_xbar_r_rejects_unbalanced_design(grr_reference):
    observations = _balanced(grr_reference)[:-1]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_xbar_r(observations, _context(grr_reference))

    assert error.value.code == "MSA_METHOD_NOT_APPLICABLE"
    assert error.value.details["reason"] == "unbalanced_design"


def test_xbar_r_rejects_missing_cell(grr_reference):
    observations = [
        row for row in _balanced(grr_reference)
        if not (row["appraiser"] == "A02" and row["part"] == "P03")
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_xbar_r(observations, _context(grr_reference))

    assert error.value.code == "MSA_METHOD_NOT_APPLICABLE"


def test_xbar_r_rejects_design_outside_the_controlled_d2_table(grr_reference):
    """受控 d2 表沒有的設計規模不得外插。"""
    observations = []
    for part_index in range(1, 12):
        for trial in (1, 2):
            for appraiser in ("A01", "A02"):
                observations.append({
                    "part": f"P{part_index:02d}",
                    "appraiser": appraiser,
                    "trial": trial,
                    "value": 10.0 + part_index * 0.1 + trial * 0.01,
                })

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_xbar_r(observations, _context(grr_reference))

    assert error.value.details["reason"] == "d2_out_of_range"


def test_xbar_r_rejects_non_finite_reading(grr_reference):
    observations = _balanced(grr_reference)
    observations[0]["value"] = float("nan")

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_xbar_r(observations, _context(grr_reference))

    assert error.value.details["reason"] == "non_finite_reading"


def test_xbar_r_requires_at_least_two_trials(grr_reference):
    observations = [
        row for row in _balanced(grr_reference) if row["trial"] == 1
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_xbar_r(observations, _context(grr_reference))

    assert error.value.details["reason"] == "insufficient_trials"


# ---------------------------------------------------------------------------
# 圖表輸出
# ---------------------------------------------------------------------------


def test_chart_data_carries_part_and_appraiser_series_with_limits(
    grr_reference,
):
    output = analyze_xbar_r(
        _balanced(grr_reference), _context(grr_reference)
    )
    chart = output.chart_data

    assert set(chart) == {
        "part_means", "appraiser_means", "xbar_chart", "range_chart",
    }
    assert chart["part_means"]["P01"] == pytest.approx(
        grr_reference["expected"]["part_means"]["P01"], rel=1e-12
    )
    assert chart["range_chart"]["ucl"] > chart["range_chart"]["center"]
    assert chart["range_chart"]["lcl"] == 0.0
    assert chart["xbar_chart"]["ucl"] > chart["xbar_chart"]["lcl"]
    assert "out_of_control_points" in chart["xbar_chart"]


# ---------------------------------------------------------------------------
# 極差法
# ---------------------------------------------------------------------------


def test_range_method_reports_only_overall_grr(grr_reference):
    output = analyze_range(
        _balanced(grr_reference), _context(grr_reference),
    )
    stats = output.statistics

    assert stats["detail_components_available"] is False
    assert "ev" not in stats
    assert "av" not in stats
    assert "pv" not in stats
    assert stats["grr"] > 0
    assert stats["percent_tolerance"]["grr"] == pytest.approx(
        100.0 * 6.0 * stats["grr"] / grr_reference["context"]["tolerance"],
        rel=1e-9,
    )


def test_range_method_records_sample_size_and_constant(grr_reference):
    output = analyze_range(
        _balanced(grr_reference), _context(grr_reference),
    )

    assert output.statistics["sample_size"] == 6
    assert output.statistics["d2"] == 1.128
    assert output.applicability["method"] == "range"


def test_range_method_without_tolerance_reports_unavailable(grr_reference):
    output = analyze_range(
        _balanced(grr_reference), _context(grr_reference, tolerance=None),
    )

    assert output.statistics["percent_tolerance"] is None
