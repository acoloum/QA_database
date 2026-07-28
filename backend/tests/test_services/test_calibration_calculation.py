from dataclasses import FrozenInstanceError
from decimal import (
    Decimal,
    Inexact,
    ROUND_DOWN,
    ROUND_UP,
    Subnormal,
    localcontext,
)

import pytest

from backend.services.calibration_calculation import (
    CALIBRATION_NUMERIC_FAILURE,
    CALCULATION_VERSION,
    CalibrationPointRule,
    CalibrationReadingInput,
    calculate_calibration,
    calculate_point,
)


def rule(**overrides):
    values = {
        "point_code": "P01",
        "scope_code": "OD-0-150",
        "reference_input_mode": "certified_value",
        "reference_value": Decimal("10.000"),
        "required_repetitions": 3,
        "error_lower_limit": Decimal("-0.05"),
        "error_upper_limit": Decimal("0.05"),
        "evaluation_basis": "all_readings",
        "repeatability_rule": "none",
        "repeatability_limit": None,
        "uncertainty_required": False,
        "expanded_uncertainty": None,
        "coverage_factor": None,
        "required": True,
    }
    values.update(overrides)
    return CalibrationPointRule(**values)


def reading(
    indicated_value,
    *,
    trial_no=1,
    standard_reading=None,
):
    return CalibrationReadingInput(
        trial_no=trial_no,
        indicated_value=indicated_value,
        standard_reading=standard_reading,
    )


def passing_point(*, point_code="P01", scope_code="OD-0-150"):
    return calculate_point(
        rule(
            point_code=point_code,
            scope_code=scope_code,
            required_repetitions=1,
        ),
        [reading("10.000")],
    )


def failing_point(*, point_code="P01", scope_code="OD-0-150"):
    return calculate_point(
        rule(
            point_code=point_code,
            scope_code=scope_code,
            required_repetitions=1,
        ),
        [reading("10.100")],
    )


def pending_point(*, point_code="P01", scope_code="OD-0-150"):
    return calculate_point(
        rule(
            point_code=point_code,
            scope_code=scope_code,
            required_repetitions=1,
        ),
        [reading(None)],
    )


def test_certified_value_calculates_exact_decimal_evidence():
    result = calculate_point(
        rule(
            reference_value=Decimal("10.000"),
            error_lower_limit=Decimal("-0.05"),
            error_upper_limit=Decimal("0.05"),
            evaluation_basis="all_readings",
            repeatability_rule="range",
            repeatability_limit=Decimal("0.05"),
        ),
        [
            reading("10.020", trial_no=1),
            reading("10.040", trial_no=2),
            reading("10.000", trial_no=3),
        ],
    )

    assert result.errors == (
        Decimal("0.020"),
        Decimal("0.040"),
        Decimal("0.000"),
    )
    assert tuple(item.correction for item in result.readings) == (
        Decimal("-0.020"),
        Decimal("-0.040"),
        Decimal("0.000"),
    )
    assert result.mean_error == Decimal("0.020")
    assert result.mean_correction == Decimal("-0.020")
    assert result.minimum_error == Decimal("0.000")
    assert result.maximum_error == Decimal("0.040")
    assert result.error_range == Decimal("0.040")
    assert result.sample_stddev == Decimal("0.020")
    assert result.result == "pass"
    assert result.blockers == ()


def test_paired_reading_uses_each_trial_standard_value():
    result = calculate_point(
        rule(
            reference_input_mode="paired_reading",
            reference_value=None,
            required_repetitions=2,
        ),
        [
            reading(
                "10.000",
                trial_no=1,
                standard_reading="9.990",
            ),
            reading(
                "10.000",
                trial_no=2,
                standard_reading="10.010",
            ),
        ],
    )

    assert tuple(item.effective_reference for item in result.readings) == (
        Decimal("9.990"),
        Decimal("10.010"),
    )
    assert result.errors == (Decimal("0.010"), Decimal("-0.010"))
    assert result.mean_error == Decimal("0.000")
    assert result.result == "pass"


def test_all_readings_fails_when_any_error_is_outside_limit():
    result = calculate_point(
        rule(required_repetitions=2),
        [
            reading("10.000", trial_no=1),
            reading("10.051", trial_no=2),
        ],
    )

    assert tuple(item.result for item in result.readings) == (
        "pass",
        "fail",
    )
    assert result.result == "fail"


def test_mean_error_uses_average_instead_of_individual_errors():
    result = calculate_point(
        rule(
            required_repetitions=2,
            evaluation_basis="mean_error",
        ),
        [
            reading("9.900", trial_no=1),
            reading("10.100", trial_no=2),
        ],
    )

    assert result.errors == (Decimal("-0.100"), Decimal("0.100"))
    assert result.mean_error == Decimal("0.000")
    assert tuple(item.result for item in result.readings) == (
        "not_individually_evaluated",
        "not_individually_evaluated",
    )
    assert result.result == "pass"


@pytest.mark.parametrize(
    ("lower_limit", "upper_limit", "indicated_value", "expected"),
    [
        (Decimal("-0.050"), None, "9.950", "pass"),
        (Decimal("-0.050"), None, "9.949", "fail"),
        (None, Decimal("0.050"), "10.050", "pass"),
        (None, Decimal("0.050"), "10.051", "fail"),
    ],
)
def test_one_sided_limits_include_the_configured_endpoint(
    lower_limit,
    upper_limit,
    indicated_value,
    expected,
):
    result = calculate_point(
        rule(
            required_repetitions=1,
            error_lower_limit=lower_limit,
            error_upper_limit=upper_limit,
        ),
        [reading(indicated_value)],
    )

    assert result.result == expected


@pytest.mark.parametrize(
    ("repeatability_rule", "values", "limit", "expected_value", "expected"),
    [
        (
            "range",
            ("10.000", "10.050"),
            Decimal("0.050"),
            Decimal("0.050"),
            "pass",
        ),
        (
            "range",
            ("10.000", "10.051"),
            Decimal("0.050"),
            Decimal("0.051"),
            "fail",
        ),
        (
            "stddev",
            ("9.900", "10.000", "10.100"),
            Decimal("0.100"),
            Decimal("0.100"),
            "pass",
        ),
        (
            "stddev",
            ("9.900", "10.000", "10.100"),
            Decimal("0.099"),
            Decimal("0.100"),
            "fail",
        ),
    ],
)
def test_repeatability_limit_is_inclusive(
    repeatability_rule,
    values,
    limit,
    expected_value,
    expected,
):
    result = calculate_point(
        rule(
            required_repetitions=len(values),
            error_lower_limit=Decimal("-1"),
            error_upper_limit=Decimal("1"),
            repeatability_rule=repeatability_rule,
            repeatability_limit=limit,
        ),
        [
            reading(value, trial_no=index)
            for index, value in enumerate(values, start=1)
        ],
    )

    actual_value = (
        result.error_range
        if repeatability_rule == "range"
        else result.sample_stddev
    )
    assert actual_value == expected_value
    assert result.result == expected


@pytest.mark.parametrize(
    ("point_rule", "readings", "expected_blocker"),
    [
        (
            rule(required_repetitions=2),
            [reading("10.000"), reading(None, trial_no=2)],
            "CALIBRATION_READING_MISSING",
        ),
        (
            rule(
                reference_input_mode="paired_reading",
                reference_value=None,
                required_repetitions=1,
            ),
            [reading("10.000", standard_reading=None)],
            "CALIBRATION_REFERENCE_MISSING",
        ),
        (
            rule(reference_value=None, required_repetitions=1),
            [reading("10.000")],
            "CALIBRATION_REFERENCE_MISSING",
        ),
        (
            rule(required_repetitions=2),
            [reading("10.000")],
            "CALIBRATION_REPETITIONS_MISSING",
        ),
        (
            rule(
                required_repetitions=1,
                error_lower_limit=None,
                error_upper_limit=None,
            ),
            [reading("10.000")],
            "CALIBRATION_TOLERANCE_MISSING",
        ),
    ],
)
def test_incomplete_required_evidence_is_pending(
    point_rule,
    readings,
    expected_blocker,
):
    result = calculate_point(point_rule, readings)

    assert result.result == "pending"
    assert expected_blocker in result.blockers


def test_required_uncertainty_and_coverage_factor_block_completion():
    result = calculate_point(
        rule(
            required_repetitions=1,
            uncertainty_required=True,
            expanded_uncertainty=None,
            coverage_factor=None,
        ),
        [reading("10.000")],
    )

    assert result.result == "pending"
    assert result.blockers == (
        "CALIBRATION_UNCERTAINTY_MISSING",
        "CALIBRATION_COVERAGE_FACTOR_MISSING",
    )


def test_required_uncertainty_is_preserved_as_decimal_evidence():
    result = calculate_point(
        rule(
            required_repetitions=1,
            uncertainty_required=True,
            expanded_uncertainty="0.010",
            coverage_factor="2.00",
        ),
        [reading("10.000")],
    )

    assert result.expanded_uncertainty == Decimal("0.010")
    assert result.coverage_factor == Decimal("2.00")
    assert result.result == "pass"


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("reference_value", "NaN"),
        ("error_lower_limit", "-Infinity"),
        ("error_upper_limit", "Infinity"),
        ("repeatability_limit", "1E+1001"),
        ("expanded_uncertainty", "1E-1001"),
        ("coverage_factor", "123456789012345678901234567890123456789012345678901"),
    ],
)
def test_invalid_rule_numeric_value_returns_stable_failure_contract(
    field_name,
    invalid_value,
):
    overrides = {
        "required_repetitions": 1,
        field_name: invalid_value,
    }
    if field_name == "repeatability_limit":
        overrides["repeatability_rule"] = "range"
    result = calculate_point(rule(**overrides), [reading("10.000")])

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "NaN",
        "Infinity",
        "1E+1001",
        "1E-1001",
        "123456789012345678901234567890123456789012345678901",
    ],
)
def test_invalid_indicated_value_returns_stable_failure_contract(
    invalid_value,
):
    result = calculate_point(
        rule(required_repetitions=1),
        [reading(invalid_value)],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_invalid_paired_standard_value_returns_stable_failure_contract():
    result = calculate_point(
        rule(
            reference_input_mode="paired_reading",
            reference_value=None,
            required_repetitions=1,
        ),
        [reading("10.000", standard_reading="NaN")],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_non_finite_trial_number_returns_numeric_failure():
    result = calculate_point(
        rule(required_repetitions=1),
        [
            CalibrationReadingInput(
                trial_no=Decimal("NaN"),
                indicated_value=Decimal("10.000"),
            )
        ],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
def test_calculation_is_independent_from_caller_decimal_context(rounding):
    point_rule = rule(
        reference_value=Decimal("0"),
        required_repetitions=3,
        error_lower_limit=Decimal("-2000"),
        error_upper_limit=Decimal("2000"),
    )
    readings = [
        reading(Decimal("0.001"), trial_no=1),
        reading(Decimal("1000"), trial_no=2),
        reading(Decimal("1001"), trial_no=3),
    ]
    expected = calculate_point(point_rule, readings)

    with localcontext() as context:
        context.prec = 3
        context.rounding = rounding
        context.Emin = -2
        context.Emax = 2
        context.clamp = 1
        context.traps[Inexact] = True
        context.traps[Subnormal] = True
        actual = calculate_point(point_rule, readings)

    assert expected.result == "pass"
    assert actual == expected


def test_error_sum_may_exceed_output_significant_digit_limit():
    value = Decimal("9" * 50)
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=2,
            error_lower_limit=Decimal("0"),
            error_upper_limit=value,
        ),
        [
            reading(value, trial_no=1),
            reading(value, trial_no=2),
        ],
    )

    assert result.errors == (value, value)
    assert result.mean_error == value
    assert result.error_range == Decimal("0")
    assert result.result == "pass"


def test_error_sum_exponent_carry_does_not_reject_valid_mean():
    value = Decimal("9E+1000")
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=2,
            error_lower_limit=Decimal("0"),
            error_upper_limit=value,
        ),
        [
            reading(value, trial_no=1),
            reading(value, trial_no=2),
        ],
    )

    assert result.errors == (value, value)
    assert result.mean_error == value
    assert result.error_range == Decimal("0E+1000")
    assert result.result == "pass"


def test_error_above_endpoint_is_not_rounded_back_to_limit():
    result = calculate_point(
        rule(
            reference_value=Decimal("-1E-50"),
            required_repetitions=1,
            error_lower_limit=None,
            error_upper_limit=Decimal("1"),
        ),
        [reading(Decimal("1"))],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_large_exponent_span_is_not_truncated_before_precision_check():
    result = calculate_point(
        rule(
            reference_value=Decimal("1E+1000"),
            required_repetitions=1,
            error_lower_limit=Decimal("-1E+1000"),
            error_upper_limit=Decimal("0"),
        ),
        [reading(Decimal("-1E-1000"))],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_mean_error_decision_uses_exact_sum_relation():
    rounded_mean = Decimal(
        "0.33333333333333333333333333333333333333333333333333"
    )
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=3,
            error_lower_limit=None,
            error_upper_limit=rounded_mean,
            evaluation_basis="mean_error",
        ),
        [
            reading(Decimal("0"), trial_no=1),
            reading(Decimal("0"), trial_no=2),
            reading(Decimal("1"), trial_no=3),
        ],
    )

    assert result.mean_error == rounded_mean
    assert result.result == "fail"


def test_stddev_decision_uses_exact_variance_relation():
    rounded_stddev = Decimal(
        "0.70710678118654752440084436210484903928483593768847"
    )
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=2,
            error_lower_limit=Decimal("-2"),
            error_upper_limit=Decimal("2"),
            repeatability_rule="stddev",
            repeatability_limit=rounded_stddev,
        ),
        [
            reading(Decimal("0"), trial_no=1),
            reading(Decimal("1"), trial_no=2),
        ],
    )

    assert result.sample_stddev == rounded_stddev
    assert result.result == "fail"


def test_required_repetitions_above_postgresql_integer_returns_failure():
    result = calculate_point(
        rule(required_repetitions=2_147_483_648),
        [reading(Decimal("10.000"))],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_trial_number_above_postgresql_integer_returns_failure():
    result = calculate_point(
        rule(required_repetitions=1),
        [
            reading(
                Decimal("10.000"),
                trial_no=2_147_483_648,
            )
        ],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_adjusted_exponent_boundary_allows_insignificant_trailing_zero():
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=1,
            error_lower_limit=Decimal("0"),
            error_upper_limit=Decimal("1E-999"),
        ),
        [reading(Decimal("1.0E-1000"))],
    )

    assert result.errors == (Decimal("1.0E-1000"),)
    assert result.result == "pass"


@pytest.mark.parametrize(
    "value",
    [Decimal("0E-1001"), Decimal("0E+1001")],
)
def test_zero_outside_adjusted_exponent_limit_returns_failure(value):
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=1,
            error_lower_limit=Decimal("-1"),
            error_upper_limit=Decimal("1"),
        ),
        [reading(value)],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


@pytest.mark.parametrize(
    "value",
    [Decimal("0E-1000"), Decimal("0E+1000")],
)
def test_zero_at_adjusted_exponent_limit_is_valid(value):
    result = calculate_point(
        rule(
            reference_value=Decimal("0"),
            required_repetitions=1,
            error_lower_limit=Decimal("-1"),
            error_upper_limit=Decimal("1"),
        ),
        [reading(value)],
    )

    assert result.errors == (value,)
    assert result.result == "pass"


def test_calculated_error_exponent_overflow_returns_numeric_failure():
    result = calculate_point(
        rule(
            reference_value="-9E+1000",
            required_repetitions=1,
            error_lower_limit="-9E+1000",
            error_upper_limit="9E+1000",
        ),
        [reading("9E+1000")],
    )

    assert result.result == "pending"
    assert result.blockers == (CALIBRATION_NUMERIC_FAILURE,)


def test_all_numeric_outputs_are_decimal_even_for_float_input():
    result = calculate_point(
        rule(
            reference_value=10.0,
            required_repetitions=2,
        ),
        [
            reading(10.01, trial_no=1),
            reading(10.03, trial_no=2),
        ],
    )

    numeric_outputs = (
        result.mean_error,
        result.mean_correction,
        result.minimum_error,
        result.maximum_error,
        result.error_range,
        result.sample_stddev,
        *(item.effective_reference for item in result.readings),
        *(item.error for item in result.readings),
        *(item.correction for item in result.readings),
    )
    assert all(isinstance(value, Decimal) for value in numeric_outputs)
    assert result.errors == (Decimal("0.01"), Decimal("0.03"))


def test_calculation_types_are_immutable_and_versioned():
    result = passing_point()

    assert CALCULATION_VERSION == "CALIBRATION_1_0"
    with pytest.raises(FrozenInstanceError):
        result.result = "fail"
    with pytest.raises(FrozenInstanceError):
        result.readings[0].error = Decimal("999")


def test_mixed_pass_and_fail_scopes_become_limited_use_when_allowed():
    result = calculate_calibration(
        [
            passing_point(point_code="P01", scope_code="OD-0-150"),
            passing_point(point_code="P02", scope_code="OD-0-150"),
            failing_point(point_code="P03", scope_code="OD-150-300"),
        ],
        allow_limited_use=True,
    )

    assert result.result == "limited_use"
    assert result.passed_scope_codes == ("OD-0-150",)
    assert result.failed_scope_codes == ("OD-150-300",)
    assert result.calculation_version == CALCULATION_VERSION


def test_mixed_pass_and_fail_scopes_fail_when_limited_use_is_disabled():
    result = calculate_calibration(
        [
            passing_point(scope_code="OD-0-150"),
            failing_point(scope_code="OD-150-300"),
        ],
        allow_limited_use=False,
    )

    assert result.result == "fail"
    assert result.passed_scope_codes == ("OD-0-150",)
    assert result.failed_scope_codes == ("OD-150-300",)


def test_scope_with_any_failed_required_point_is_not_a_passing_scope():
    result = calculate_calibration(
        [
            passing_point(point_code="P01", scope_code="OD-0-150"),
            failing_point(point_code="P02", scope_code="OD-0-150"),
            failing_point(point_code="P03", scope_code="OD-150-300"),
        ],
        allow_limited_use=True,
    )

    assert result.result == "fail"
    assert result.passed_scope_codes == ()
    assert result.failed_scope_codes == ("OD-0-150", "OD-150-300")


def test_all_required_scopes_passing_returns_pass():
    result = calculate_calibration(
        [
            passing_point(scope_code="OD-0-150"),
            passing_point(scope_code="OD-150-300"),
        ],
        allow_limited_use=True,
    )

    assert result.result == "pass"
    assert result.passed_scope_codes == ("OD-0-150", "OD-150-300")
    assert result.failed_scope_codes == ()


def test_pending_required_scope_keeps_calibration_pending():
    result = calculate_calibration(
        [
            passing_point(scope_code="OD-0-150"),
            pending_point(
                point_code="P02",
                scope_code="OD-150-300",
            ),
        ],
        allow_limited_use=True,
    )

    assert result.result == "pending"
    assert result.passed_scope_codes == ("OD-0-150",)
    assert result.failed_scope_codes == ()
    assert result.blockers == ("CALIBRATION_READING_MISSING",)


def test_fail_and_pending_without_passing_scope_returns_fail():
    result = calculate_calibration(
        [
            failing_point(scope_code="OD-0-150"),
            pending_point(
                point_code="P02",
                scope_code="OD-150-300",
            ),
        ],
        allow_limited_use=True,
    )

    assert result.result == "fail"
    assert result.passed_scope_codes == ()
    assert result.failed_scope_codes == ("OD-0-150",)
    assert result.blockers == ("CALIBRATION_READING_MISSING",)


def test_pass_fail_and_pending_waits_before_limited_use_decision():
    result = calculate_calibration(
        [
            passing_point(scope_code="OD-0-150"),
            failing_point(scope_code="OD-150-300"),
            pending_point(
                point_code="P03",
                scope_code="ID-0-150",
            ),
        ],
        allow_limited_use=True,
    )

    assert result.result == "pending"
    assert result.passed_scope_codes == ("OD-0-150",)
    assert result.failed_scope_codes == ("OD-150-300",)
    assert result.blockers == ("CALIBRATION_READING_MISSING",)


def test_optional_failed_point_does_not_fail_required_scope():
    optional_failure = calculate_point(
        rule(
            point_code="P99",
            scope_code="OPTIONAL",
            required_repetitions=1,
            required=False,
        ),
        [reading("10.100")],
    )

    result = calculate_calibration(
        [
            passing_point(scope_code="OD-0-150"),
            optional_failure,
        ],
        allow_limited_use=True,
    )

    assert optional_failure.result == "fail"
    assert result.result == "pass"
    assert result.passed_scope_codes == ("OD-0-150",)
    assert result.failed_scope_codes == ()
