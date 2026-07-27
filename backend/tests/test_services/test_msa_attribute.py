"""計數型一致性、Kappa 與錯誤率測試。"""

import json
from pathlib import Path

import pytest

from backend.services.msa_attribute import analyze_attribute
from backend.services.msa_contracts import MsaMethodContext
from backend.services.msa_errors import MsaMethodNotApplicable


@pytest.fixture(scope="module")
def reference():
    path = (
        Path(__file__).parents[1] / "fixtures" / "msa_attribute_reference.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _context(reference, **overrides):
    values = dict(reference["context"])
    values.update(overrides)
    return MsaMethodContext(**values)


def _observations(reference):
    return [dict(row) for row in reference["observations"]]


# ---------------------------------------------------------------------------
# 一致性
# ---------------------------------------------------------------------------


def test_attribute_binary_matches_reference(reference):
    output = analyze_attribute(_observations(reference), _context(reference))
    stats = output.statistics
    expected = reference["expected"]

    assert stats["within_appraiser"]["A01"]["agreement"] == pytest.approx(
        expected["within_appraiser"]["A01"]["agreement"], rel=1e-12
    )
    assert stats["against_reference"]["overall"]["kappa"] == pytest.approx(
        expected["overall_kappa"], rel=1e-9
    )
    assert stats["effectiveness"] == pytest.approx(
        expected["effectiveness"], rel=1e-12
    )
    assert stats["false_accept_rate"] == pytest.approx(
        expected["false_accept_rate"], rel=1e-12
    )
    assert stats["false_reject_rate"] == pytest.approx(
        expected["false_reject_rate"], rel=1e-12
    )


def test_within_and_between_appraiser_agreement(reference):
    output = analyze_attribute(_observations(reference), _context(reference))
    stats = output.statistics
    expected = reference["expected"]

    for appraiser, wanted in expected["within_appraiser"].items():
        assert stats["within_appraiser"][appraiser]["agreement"] == (
            pytest.approx(wanted["agreement"], rel=1e-12)
        )
    assert stats["between_appraiser"]["agreement"] == pytest.approx(
        expected["between_appraiser"]["agreement"], rel=1e-12
    )


def test_kappa_reports_standard_error_and_interval(reference):
    output = analyze_attribute(_observations(reference), _context(reference))
    overall = output.statistics["against_reference"]["overall"]
    expected = reference["expected"]

    assert overall["observed_agreement"] == pytest.approx(
        expected["observed_agreement"], rel=1e-12
    )
    assert overall["expected_agreement"] == pytest.approx(
        expected["expected_agreement"], rel=1e-12
    )
    assert overall["kappa_standard_error"] == pytest.approx(
        expected["kappa_standard_error"], rel=1e-9
    )
    assert overall["kappa_confidence_interval"] == pytest.approx(
        expected["kappa_confidence_interval"], rel=1e-9
    )
    assert overall["kappa_method"] == "cohen_vs_reference"


def test_confusion_matrix_matches_reference(reference):
    output = analyze_attribute(_observations(reference), _context(reference))

    assert output.statistics["confusion_matrix"] == (
        reference["expected"]["confusion_matrix"]
    )


def test_grey_zone_results_are_reported_separately(reference):
    output = analyze_attribute(_observations(reference), _context(reference))
    strata = output.statistics["strata"]
    expected = reference["expected"]["strata"]

    assert strata["grey_zone"]["agreement"] == pytest.approx(
        expected["grey_zone"]["agreement"], rel=1e-12
    )
    assert strata["non_grey_zone"]["agreement"] == pytest.approx(
        expected["non_grey_zone"]["agreement"], rel=1e-12
    )
    assert strata["grey_zone"]["agreement"] < strata["non_grey_zone"][
        "agreement"
    ]


# ---------------------------------------------------------------------------
# 沒有可信參考標準
# ---------------------------------------------------------------------------


def test_missing_reference_reports_agreement_not_accuracy(reference):
    observations = _observations(reference)
    for row in observations:
        row.pop("reference", None)

    output = analyze_attribute(observations, _context(reference))

    assert output.statistics["accuracy_available"] is False
    assert "effectiveness" not in output.statistics
    assert "false_accept_rate" not in output.statistics
    assert "against_reference" not in output.statistics
    assert output.statistics["within_appraiser"]
    assert any(
        warning["code"] == "MSA_ATTRIBUTE_REFERENCE_UNAVAILABLE"
        for warning in output.warnings
    )


def test_untrustworthy_reference_blocks_accuracy_conclusions(reference):
    """參考標準標示為不可信時，不得輸出「正確辨識」結論。"""
    observations = _observations(reference)
    for row in observations:
        row["reference_trusted"] = False

    output = analyze_attribute(observations, _context(reference))

    assert output.statistics["accuracy_available"] is False
    assert "effectiveness" not in output.statistics
    assert any(
        warning["code"] == "MSA_ATTRIBUTE_REFERENCE_NOT_TRUSTED"
        for warning in output.warnings
    )


# ---------------------------------------------------------------------------
# 邊界情形
# ---------------------------------------------------------------------------


def test_kappa_is_unavailable_when_expected_agreement_is_one(reference):
    """所有判定與參考都是同一類別時 Kappa 分母為 0，必須回不可用。"""
    observations = _observations(reference)
    for row in observations:
        row["value"] = "pass"
        row["reference"] = "pass"

    output = analyze_attribute(observations, _context(reference))
    overall = output.statistics["against_reference"]["overall"]

    assert overall["kappa"] is None
    assert overall["kappa_unavailable_reason"] == (
        "期望一致性為 1，Kappa 分母為 0，無法估計"
    )


def test_error_rates_report_unavailable_instead_of_zero(reference):
    """沒有任何應判退的樣本時，誤收率必須是不可用而非 0。"""
    observations = _observations(reference)
    for row in observations:
        row["value"] = "pass"
        row["reference"] = "pass"

    output = analyze_attribute(observations, _context(reference))

    assert output.statistics["false_accept_rate"] is None
    assert output.statistics["false_accept_unavailable_reason"] == (
        "參考標準中沒有應判退的樣本，無法估計誤收率"
    )


def test_multiclass_confusion_matrix_is_supported(reference):
    observations = []
    truth = {"S1": "A", "S2": "B", "S3": "C", "S4": "A", "S5": "B"}
    for appraiser in ("A01", "A02"):
        for sample, label in truth.items():
            for trial in (1, 2):
                verdict = "C" if (appraiser == "A02" and sample == "S2") \
                    else label
                observations.append({
                    "sample": sample, "appraiser": appraiser,
                    "trial": trial, "value": verdict, "reference": label,
                })

    output = analyze_attribute(observations, _context(reference))

    assert sorted(output.statistics["labels"]) == ["A", "B", "C"]
    assert output.statistics["confusion_matrix"]["B"]["C"] == 2
    assert output.statistics["against_reference"]["overall"]["kappa"] is not None


def test_binary_only_error_rates_are_skipped_for_multiclass(reference):
    observations = []
    truth = {"S1": "A", "S2": "B", "S3": "C", "S4": "A", "S5": "B"}
    for sample, label in truth.items():
        for trial in (1, 2):
            observations.append({
                "sample": sample, "appraiser": "A01", "trial": trial,
                "value": label, "reference": label,
            })

    output = analyze_attribute(observations, _context(reference))

    assert output.statistics["false_accept_rate"] is None
    assert output.statistics["false_accept_unavailable_reason"] == (
        "誤收與誤拒率只適用於二分類判定"
    )


def test_missing_repeat_trials_are_rejected(reference):
    observations = [
        row for row in _observations(reference) if row["trial"] == 1
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_attribute(observations, _context(reference))

    assert error.value.details["reason"] == "insufficient_trials"


def test_unbalanced_appraiser_coverage_is_rejected(reference):
    observations = [
        row for row in _observations(reference)
        if not (row["appraiser"] == "A03" and row["sample"] == "S20")
    ]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_attribute(observations, _context(reference))

    assert error.value.details["reason"] == "unbalanced_design"


def test_empty_observations_are_rejected(reference):
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_attribute([], _context(reference))

    assert error.value.details["reason"] == "no_observations"
