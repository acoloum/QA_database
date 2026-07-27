"""計量型 GRR（極差法與平均值－極差法）統計引擎測試。"""

import json
from pathlib import Path

import pytest

from backend.services.msa_contracts import MsaMethodContext
from backend.services.msa_errors import MsaMethodNotApplicable
from backend.services.msa_variable_grr import (
    analyze_crossed_anova,
    analyze_range,
    analyze_xbar_r,
)


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


# ---------------------------------------------------------------------------
# 交叉型 ANOVA
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def anova_reference():
    path = (
        Path(__file__).parents[1] / "fixtures" / "msa_anova_reference.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _anova_case(reference, name):
    case = reference["cases"][name]
    return (
        [dict(row) for row in case["observations"]],
        MsaMethodContext(**reference["context"]),
        case["expected"],
    )


def test_crossed_anova_preserves_full_and_reduced_model_evidence(
    anova_reference,
):
    observations, context, expected = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    output = analyze_crossed_anova(observations, context)
    full = output.statistics["anova"]["full_model"]

    assert [row["source"] for row in full["table"]] == [
        "part", "appraiser", "part_appraiser", "repeatability",
    ]
    assert full["table"][0]["ss"] == pytest.approx(
        expected["part_ss"], rel=1e-9
    )
    assert "raw_variance_components" in full
    assert "adjusted_variance_components" in full
    assert output.statistics["anova"]["selected_model"] in {"full", "reduced"}
    # 即使採用 reduced，full 的證據仍必須完整保存
    assert output.statistics["anova"]["reduced_model"]["error_ss"] == (
        pytest.approx(expected["reduced_model"]["error_ss"], rel=1e-9)
    )


def test_anova_table_matches_independently_computed_sums_of_squares(
    anova_reference,
):
    observations, context, expected = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    table = analyze_crossed_anova(
        observations, context
    ).statistics["anova"]["full_model"]["table"]
    by_source = {row["source"]: row for row in table}

    for source, key in (
        ("part", "part"), ("appraiser", "appraiser"),
        ("part_appraiser", "interaction"), ("repeatability", "repeatability"),
    ):
        assert by_source[source]["ss"] == pytest.approx(
            expected[f"{key}_ss"], rel=1e-9
        )
        assert by_source[source]["df"] == expected[f"{key}_df"]
        assert by_source[source]["ms"] == pytest.approx(
            expected[f"{key}_ms"], rel=1e-9
        )


def test_anova_sums_of_squares_decompose_to_the_total(anova_reference):
    """四個來源的平方和必須恰好等於總平方和。"""
    observations, context, expected = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    table = analyze_crossed_anova(
        observations, context
    ).statistics["anova"]["full_model"]["table"]

    assert sum(row["ss"] for row in table) == pytest.approx(
        expected["total_ss"], rel=1e-9
    )


def test_interaction_not_significant_selects_reduced_model(anova_reference):
    observations, context, expected = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    output = analyze_crossed_anova(observations, context)

    assert expected["selected_model"] == "reduced"
    assert output.statistics["anova"]["selected_model"] == "reduced"
    assert output.statistics["anova"]["p_interaction"] == pytest.approx(
        expected["p_interaction"], rel=1e-6
    )
    assert output.statistics["grr"] == pytest.approx(
        expected["grr"], rel=1e-9
    )
    assert output.statistics["ndc"] == expected["ndc"]


def test_interaction_significant_keeps_full_model(anova_reference):
    observations, context, expected = _anova_case(
        anova_reference, "interaction_significant"
    )

    output = analyze_crossed_anova(observations, context)

    assert expected["selected_model"] == "full"
    assert output.statistics["anova"]["selected_model"] == "full"
    assert output.statistics["anova"]["p_interaction"] < context.alpha
    assert output.statistics["grr"] == pytest.approx(
        expected["grr"], rel=1e-9
    )


def test_anova_reports_negative_components_before_clamping(anova_reference):
    observations, context, expected = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    full = analyze_crossed_anova(
        observations, context
    ).statistics["anova"]["full_model"]

    raw = full["raw_variance_components"]
    adjusted = full["adjusted_variance_components"]
    assert raw["part_appraiser"] == pytest.approx(
        expected["raw_variance_components"]["part_appraiser"], rel=1e-9
    )
    assert all(value >= 0 for value in adjusted.values())
    for key, value in raw.items():
        if value < 0:
            assert adjusted[key] == 0.0


def test_anova_uses_six_sigma_and_reports_percent_tolerance(anova_reference):
    observations, context, expected = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    output = analyze_crossed_anova(observations, context)

    assert output.statistics["study_variation_multiplier"] == 6.0
    assert output.statistics["percent_tolerance"]["grr"] == pytest.approx(
        expected["percent_tolerance_grr"], rel=1e-9
    )


def test_anova_rejects_unbalanced_data(anova_reference):
    observations, context, _ = _anova_case(
        anova_reference, "interaction_not_significant"
    )

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_crossed_anova(observations[:-1], context)

    assert error.value.details["reason"] == "unbalanced_design"


def test_anova_rejects_designs_without_error_degrees_of_freedom(
    anova_reference,
):
    """每格只有一次試驗時誤差自由度為 0，無法估計重複性。"""
    observations, context, _ = _anova_case(
        anova_reference, "interaction_not_significant"
    )
    single_trial = [row for row in observations if row["trial"] == 1]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_crossed_anova(single_trial, context)

    assert error.value.details["reason"] == "no_error_degrees_of_freedom"


def test_anova_rejects_single_appraiser_design(anova_reference):
    observations, context, _ = _anova_case(
        anova_reference, "interaction_not_significant"
    )
    single = [row for row in observations if row["appraiser"] == "A01"]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_crossed_anova(single, context)

    assert error.value.details["reason"] == "insufficient_appraisers"


def test_anova_rejects_zero_variation_that_makes_f_undefined(anova_reference):
    observations, context, _ = _anova_case(
        anova_reference, "interaction_not_significant"
    )
    for row in observations:
        row["value"] = 10.0

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_crossed_anova(observations, context)

    assert error.value.details["reason"] == "degenerate_model"
