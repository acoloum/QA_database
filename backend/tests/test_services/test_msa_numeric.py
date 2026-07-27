"""MSA 數值安全層、canonical hash 與受控方法 registry 測試。"""

from decimal import Decimal
import math

import numpy as np
import pytest

from backend.services.msa_errors import MsaValidationError
from backend.services.msa_method_registry import MsaMethodRegistry
from backend.services.msa_numeric import (
    MsaNumericError,
    canonical_hash,
    require_finite_tree,
    to_float,
)


# ---------------------------------------------------------------------------
# canonical hash
# ---------------------------------------------------------------------------


def test_hash_is_stable_across_dictionary_order():
    assert canonical_hash({"b": 2, "a": [1, 3]}) == canonical_hash(
        {"a": [1, 3], "b": 2}
    )


def test_hash_changes_when_any_value_changes():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 1.0000000001})


def test_hash_handles_decimal_and_numpy_without_precision_drift():
    assert canonical_hash({"v": Decimal("10.001")}) == canonical_hash(
        {"v": Decimal("10.001")}
    )
    assert canonical_hash({"v": np.float64(1.5)}) == canonical_hash({"v": 1.5})


def test_hash_rejects_non_finite_payload():
    with pytest.raises(MsaNumericError) as error:
        canonical_hash({"v": math.inf})

    assert error.value.code == "MSA_NUMERIC_FAILURE"


# ---------------------------------------------------------------------------
# 有限值檢查
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_rejected(value):
    with pytest.raises(MsaNumericError) as error:
        require_finite_tree({"result": value})

    assert error.value.code == "MSA_NUMERIC_FAILURE"


@pytest.mark.parametrize(
    "payload, expected_path",
    [
        ({"a": {"b": [1, math.nan]}}, "$.a.b[1]"),
        ({"grr": {"percent": math.inf}}, "$.grr.percent"),
        ([[0, math.nan]], "$[0][1]"),
    ],
)
def test_non_finite_failure_reports_json_path(payload, expected_path):
    with pytest.raises(MsaNumericError) as error:
        require_finite_tree(payload)

    assert error.value.details["path"] == expected_path


def test_numpy_scalars_and_arrays_are_checked():
    with pytest.raises(MsaNumericError):
        require_finite_tree({"v": np.float64("nan")})
    with pytest.raises(MsaNumericError):
        require_finite_tree({"v": np.array([1.0, np.inf])})


def test_finite_tree_returns_input_untouched():
    payload = {"a": [1, 2.5], "b": {"c": Decimal("3.5")}}

    assert require_finite_tree(payload) is payload


def test_to_float_rejects_non_finite_conversion():
    with pytest.raises(MsaNumericError) as error:
        to_float(Decimal("1") / Decimal("3") * Decimal("0") + Decimal("nan"))

    assert error.value.code == "MSA_NUMERIC_FAILURE"


def test_to_float_accepts_decimal_and_numpy():
    assert to_float(Decimal("10.001")) == pytest.approx(10.001)
    assert to_float(np.float64(2.5)) == 2.5


# ---------------------------------------------------------------------------
# 方法 registry
# ---------------------------------------------------------------------------


def test_registry_exposes_only_controlled_versions():
    descriptor = MsaMethodRegistry.get("MSA4_GRR_ANOVA_1_0")

    assert descriptor.study_variation_multiplier == 6.0
    assert descriptor.alpha == 0.05
    assert descriptor.version == "1.0"


def test_every_fourth_edition_method_uses_six_sigma():
    for code in MsaMethodRegistry.codes():
        descriptor = MsaMethodRegistry.get(code)
        assert descriptor.study_variation_multiplier == 6.0, code


def test_unknown_method_code_is_rejected():
    with pytest.raises(MsaValidationError) as error:
        MsaMethodRegistry.get("MSA4_NOT_A_METHOD_9_9")

    assert error.value.code == "MSA_METHOD_NOT_REGISTERED"


def test_registry_covers_every_planned_method():
    assert set(MsaMethodRegistry.codes()) == {
        "MSA4_GRR_RANGE_1_0",
        "MSA4_GRR_XBAR_R_1_0",
        "MSA4_GRR_ANOVA_1_0",
        "MSA4_BIAS_1_0",
        "MSA4_LINEARITY_1_0",
        "MSA4_STABILITY_1_0",
        "MSA4_ATTRIBUTE_1_0",
        "MSA4_NONREPEATABLE_1_0",
    }


def test_minimum_design_is_enforced_before_analysis():
    descriptor = MsaMethodRegistry.get("MSA4_GRR_ANOVA_1_0")

    shortfalls = descriptor.design_shortfalls(
        {"parts": 1, "appraisers": 2, "trials": 2}
    )

    assert shortfalls == [
        {"dimension": "parts", "required": 2, "actual": 1}
    ]


def test_meeting_minimum_design_reports_no_shortfall():
    descriptor = MsaMethodRegistry.get("MSA4_GRR_ANOVA_1_0")

    assert descriptor.design_shortfalls(
        {"parts": 10, "appraisers": 3, "trials": 3}
    ) == []


def test_descriptors_are_immutable_controlled_records():
    descriptor = MsaMethodRegistry.get("MSA4_BIAS_1_0")

    with pytest.raises(Exception):
        descriptor.alpha = 0.1


def test_legacy_five_fifteen_sigma_is_not_a_fourth_edition_method():
    """5.15σ 只能存在明確 legacy 版本，不得混入第四版正式方法。"""
    for code in MsaMethodRegistry.codes():
        assert "5_15" not in code
        assert MsaMethodRegistry.get(code).study_variation_multiplier != 5.15
