"""不可重複／破壞性研究測試。"""

import math

import pytest

from backend.services.msa_contracts import MsaMethodContext
from backend.services.msa_errors import MsaMethodNotApplicable
from backend.services.msa_nonrepeatable import analyze_nonrepeatable


CONFIRMED = {
    "sample_homogeneity": True,
    "shelf_life": True,
    "process_stability": True,
    "pairing_assumption": True,
}


def _context(design_type, *, confirmations=None, tolerance=1.0):
    return MsaMethodContext(
        method_code="MSA4_NONREPEATABLE_1_0",
        method_version="1.0",
        alpha=0.05,
        study_variation_multiplier=6.0,
        tolerance=tolerance,
        process_sigma=None,
        criteria={
            "design_type": design_type,
            "confirmations": dict(
                CONFIRMED if confirmations is None else confirmations
            ),
        },
    )


def _pairs(count=12):
    """配對讀值：第二筆固定比第一筆高 0.01 上下微幅擺動。"""
    offsets = [0.010, 0.008, 0.012, 0.009, 0.011, 0.010]
    return [
        row
        for index in range(count)
        for row in (
            {
                "unit": f"U{index + 1:02d}", "position": 1,
                "value": 10.0 + index * 0.05,
            },
            {
                "unit": f"U{index + 1:02d}", "position": 2,
                "value": 10.0 + index * 0.05 + offsets[index % len(offsets)],
            },
        )
    ]


def _nested(group_key, groups=6, replicates=3):
    values = []
    for group_index in range(groups):
        for replicate in range(replicates):
            values.append({
                group_key: f"G{group_index + 1}",
                "value": 10.0 + group_index * 0.05 + replicate * 0.002,
            })
    return values


# ---------------------------------------------------------------------------
# 適用性 gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_confirmation",
    ["sample_homogeneity", "shelf_life", "process_stability",
     "pairing_assumption"],
)
def test_nonrepeatable_requires_physical_assumptions(missing_confirmation):
    confirmations = dict(CONFIRMED)
    confirmations[missing_confirmation] = False

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(
            _pairs(),
            _context("split_sample", confirmations=confirmations),
        )

    assert error.value.code == "MSA_METHOD_NOT_APPLICABLE"
    assert error.value.details["reason"] == "physical_assumptions_unconfirmed"
    assert error.value.details["missing_confirmations"] == [
        missing_confirmation
    ]


def test_unsupported_design_type_is_rejected():
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(_pairs(), _context("crossed_grr"))

    assert error.value.details["reason"] == "unsupported_design_type"
    assert sorted(error.value.details["supported"]) == [
        "consecutive_paired", "homogeneous_lot",
        "multiple_stations", "split_sample",
    ]


# ---------------------------------------------------------------------------
# 配對型設計
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "design_type", ["split_sample", "consecutive_paired"],
)
def test_paired_designs_report_repeatability_from_differences(design_type):
    observations = _pairs()
    output = analyze_nonrepeatable(observations, _context(design_type))
    stats = output.statistics

    differences = [0.010, 0.008, 0.012, 0.009, 0.011, 0.010] * 2
    mean_difference = sum(differences) / len(differences)
    sd = math.sqrt(
        sum((value - mean_difference) ** 2 for value in differences)
        / (len(differences) - 1)
    )

    assert stats["design_type"] == design_type
    assert stats["pairs"] == 12
    assert stats["mean_difference"] == pytest.approx(mean_difference, rel=1e-9)
    assert stats["sd_difference"] == pytest.approx(sd, rel=1e-9)
    assert stats["repeatability_sigma"] == pytest.approx(
        sd / math.sqrt(2), rel=1e-9
    )


def test_paired_design_states_what_cannot_be_separated():
    output = analyze_nonrepeatable(_pairs(), _context("split_sample"))

    assert output.statistics["identifiable_sources"] == ["repeatability"]
    assert set(output.statistics["unidentifiable_sources"]) == {
        "reproducibility", "part_variation", "part_appraiser_interaction",
    }
    assert output.applicability["limitations"]


def test_paired_design_records_confirmed_assumptions():
    output = analyze_nonrepeatable(_pairs(), _context("split_sample"))

    assert set(output.statistics["assumptions"]) == set(CONFIRMED)


def test_systematic_position_effect_is_warned():
    """配對差平均遠大於其標準差時，代表存在位置或順序效應。"""
    observations = [
        row
        for index in range(12)
        for row in (
            {"unit": f"U{index}", "position": 1, "value": 10.0},
            {"unit": f"U{index}", "position": 2, "value": 10.5},
        )
    ]
    # 讓差的標準差不為 0，才能通過標準差計算
    observations[1]["value"] = 10.49

    output = analyze_nonrepeatable(observations, _context("split_sample"))

    assert any(
        warning["code"] == "MSA_NONREPEATABLE_PAIR_BIAS"
        for warning in output.warnings
    )


def test_incomplete_pair_is_rejected():
    observations = _pairs()
    observations.pop()

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, _context("split_sample"))

    assert error.value.details["reason"] == "incomplete_pairs"


def test_duplicate_position_within_a_pair_is_rejected():
    observations = _pairs()
    observations[1]["position"] = 1

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, _context("split_sample"))

    assert error.value.details["reason"] == "invalid_pairing"


def test_too_few_pairs_is_rejected():
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(_pairs(count=5), _context("split_sample"))

    assert error.value.details["reason"] == "insufficient_pairs"


def test_paired_design_percent_tolerance_uses_six_sigma():
    output = analyze_nonrepeatable(_pairs(), _context("split_sample"))
    stats = output.statistics

    assert stats["percent_tolerance"]["repeatability"] == pytest.approx(
        100.0 * 6.0 * stats["repeatability_sigma"] / 1.0, rel=1e-9
    )


def test_paired_design_without_tolerance_reports_unavailable():
    output = analyze_nonrepeatable(
        _pairs(), _context("split_sample", tolerance=None),
    )

    assert output.statistics["percent_tolerance"] is None


# ---------------------------------------------------------------------------
# 巢狀設計
# ---------------------------------------------------------------------------


def test_homogeneous_lot_reports_nested_components():
    output = analyze_nonrepeatable(
        _nested("lot"), _context("homogeneous_lot"),
    )
    anova = output.statistics["anova"]

    assert [row["source"] for row in anova["table"]] == [
        "between_lot", "within_group",
    ]
    assert anova["table"][0]["df"] == 5
    assert anova["table"][1]["df"] == 12
    assert "raw_variance_components" in anova
    assert "adjusted_variance_components" in anova
    assert output.statistics["repeatability_sigma"] > 0


def test_multiple_stations_reports_station_component():
    output = analyze_nonrepeatable(
        _nested("station", groups=3), _context("multiple_stations"),
    )

    assert output.statistics["design_type"] == "multiple_stations"
    assert output.statistics["groups"] == 3
    assert "between_station" in (
        output.statistics["anova"]["adjusted_variance_components"]
    )


def test_negative_between_group_component_is_clamped_with_warning():
    observations = [
        {"lot": f"G{index}", "value": 10.0 + replicate * 0.05}
        for index in range(6) for replicate in range(3)
    ]

    output = analyze_nonrepeatable(observations, _context("homogeneous_lot"))
    anova = output.statistics["anova"]

    assert anova["raw_variance_components"]["between_lot"] < 0
    assert anova["adjusted_variance_components"]["between_lot"] == 0.0
    assert any(
        warning["code"] == "MSA_NONREPEATABLE_COMPONENT_CLAMPED"
        for warning in output.warnings
    )


def test_unbalanced_nested_design_is_rejected():
    observations = _nested("lot")
    observations.pop()

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, _context("homogeneous_lot"))

    assert error.value.details["reason"] == "unbalanced_design"


def test_nested_design_requires_replicates():
    observations = [
        {"lot": f"G{index}", "value": 10.0 + index * 0.05}
        for index in range(6)
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, _context("homogeneous_lot"))

    assert error.value.details["reason"] == "insufficient_replicates"


def test_too_few_lots_is_rejected():
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(
            _nested("lot", groups=3), _context("homogeneous_lot"),
        )

    assert error.value.details["reason"] == "insufficient_groups"


def test_missing_group_key_is_rejected():
    observations = _nested("lot")
    observations[0].pop("lot")

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, _context("homogeneous_lot"))

    assert error.value.details["reason"] == "incomplete_observation"


def test_non_finite_reading_is_rejected():
    observations = _nested("lot")
    observations[0]["value"] = float("inf")

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, _context("homogeneous_lot"))

    assert error.value.details["reason"] == "non_finite_reading"
