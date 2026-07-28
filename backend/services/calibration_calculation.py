"""校正詳細讀值的純 Decimal 計算與判定。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    Decimal,
    DecimalException,
    InvalidOperation,
    localcontext,
)
from typing import Literal, Sequence


CALCULATION_VERSION = "CALIBRATION_1_0"
CALIBRATION_NUMERIC_FAILURE = "CALIBRATION_NUMERIC_FAILURE"

_MAX_SIGNIFICANT_DIGITS = 50
_MAX_DECIMAL_EXPONENT = 1000

ReadingResult = Literal[
    "pending",
    "pass",
    "fail",
    "not_individually_evaluated",
]
PointResult = Literal["pending", "pass", "fail"]
CalibrationResult = Literal["pending", "pass", "fail", "limited_use"]


class _NumericFailure(ValueError):
    """內部數值防線；對外一律轉成穩定 blocker。"""


@dataclass(frozen=True)
class CalibrationPointRule:
    """單一校正點的不可變計算規則與點位證據。"""

    point_code: str
    scope_code: str
    reference_input_mode: Literal["certified_value", "paired_reading"]
    reference_value: Decimal | None
    required_repetitions: int
    error_lower_limit: Decimal | None
    error_upper_limit: Decimal | None
    evaluation_basis: Literal["all_readings", "mean_error"]
    repeatability_rule: Literal["none", "range", "stddev"] | None = "none"
    repeatability_limit: Decimal | None = None
    uncertainty_required: bool = False
    expanded_uncertainty: Decimal | None = None
    coverage_factor: Decimal | None = None
    required: bool = True


@dataclass(frozen=True)
class CalibrationReadingInput:
    """一次試驗的原始輸入。"""

    trial_no: int
    indicated_value: Decimal | None
    standard_reading: Decimal | None = None


@dataclass(frozen=True)
class CalibrationReadingCalculation:
    """一次試驗的可追溯計算證據。"""

    trial_no: int
    indicated_value: Decimal | None
    standard_reading: Decimal | None
    effective_reference: Decimal | None
    error: Decimal | None
    correction: Decimal | None
    result: ReadingResult
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationPointCalculation:
    """單一校正點的摘要與正式計算結果。"""

    point_code: str
    scope_code: str
    required: bool
    readings: tuple[CalibrationReadingCalculation, ...]
    mean_error: Decimal | None
    mean_correction: Decimal | None
    minimum_error: Decimal | None
    maximum_error: Decimal | None
    error_range: Decimal | None
    sample_stddev: Decimal | None
    expanded_uncertainty: Decimal | None
    coverage_factor: Decimal | None
    result: PointResult
    blockers: tuple[str, ...]

    @property
    def errors(self) -> tuple[Decimal, ...]:
        """依原始讀值順序回傳已完成的器差證據。"""

        return tuple(
            item.error
            for item in self.readings
            if item.error is not None
        )


@dataclass(frozen=True)
class CalibrationCalculation:
    """整筆校正依資格範圍分組後的判定。"""

    points: tuple[CalibrationPointCalculation, ...]
    result: CalibrationResult
    passed_scope_codes: tuple[str, ...]
    failed_scope_codes: tuple[str, ...]
    blockers: tuple[str, ...]
    calculation_version: str = CALCULATION_VERSION


def _decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise _NumericFailure from exc
    if not converted.is_finite():
        raise _NumericFailure

    decimal_tuple = converted.as_tuple()
    exponent = decimal_tuple.exponent
    if not isinstance(exponent, int):
        raise _NumericFailure
    if len(decimal_tuple.digits) > _MAX_SIGNIFICANT_DIGITS:
        raise _NumericFailure
    if abs(exponent) > _MAX_DECIMAL_EXPONENT:
        raise _NumericFailure
    if converted and abs(converted.adjusted()) > _MAX_DECIMAL_EXPONENT:
        raise _NumericFailure
    return converted


def _positive_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _NumericFailure
    return value


def _numeric_failure_result(
    rule: CalibrationPointRule,
) -> CalibrationPointCalculation:
    return CalibrationPointCalculation(
        point_code=rule.point_code,
        scope_code=rule.scope_code or rule.point_code,
        required=rule.required,
        readings=(),
        mean_error=None,
        mean_correction=None,
        minimum_error=None,
        maximum_error=None,
        error_range=None,
        sample_stddev=None,
        expanded_uncertainty=None,
        coverage_factor=None,
        result="pending",
        blockers=(CALIBRATION_NUMERIC_FAILURE,),
    )


def _append_once(blockers: list[str], blocker: str) -> None:
    if blocker not in blockers:
        blockers.append(blocker)


def _within_limits(
    value: Decimal,
    lower_limit: Decimal | None,
    upper_limit: Decimal | None,
) -> bool:
    if lower_limit is not None and value < lower_limit:
        return False
    if upper_limit is not None and value > upper_limit:
        return False
    return True


def _validate_rule(
    rule: CalibrationPointRule,
    *,
    lower_limit: Decimal | None,
    upper_limit: Decimal | None,
    repeatability_limit: Decimal | None,
    expanded_uncertainty: Decimal | None,
    coverage_factor: Decimal | None,
) -> None:
    _positive_integer(rule.required_repetitions)
    if rule.reference_input_mode not in {
        "certified_value",
        "paired_reading",
    }:
        raise _NumericFailure
    if rule.evaluation_basis not in {"all_readings", "mean_error"}:
        raise _NumericFailure
    if rule.repeatability_rule not in {None, "none", "range", "stddev"}:
        raise _NumericFailure
    if (
        lower_limit is not None
        and upper_limit is not None
        and lower_limit > upper_limit
    ):
        raise _NumericFailure
    if repeatability_limit is not None and repeatability_limit < 0:
        raise _NumericFailure
    if expanded_uncertainty is not None and expanded_uncertainty < 0:
        raise _NumericFailure
    if coverage_factor is not None and coverage_factor <= 0:
        raise _NumericFailure


def calculate_point(
    rule: CalibrationPointRule,
    readings: Sequence[CalibrationReadingInput],
) -> CalibrationPointCalculation:
    """計算單一校正點；數值異常不拋到服務層，也不產生 pass。"""

    try:
        reference_value = _decimal(rule.reference_value)
        lower_limit = _decimal(rule.error_lower_limit)
        upper_limit = _decimal(rule.error_upper_limit)
        repeatability_limit = _decimal(rule.repeatability_limit)
        expanded_uncertainty = _decimal(rule.expanded_uncertainty)
        coverage_factor = _decimal(rule.coverage_factor)
        _validate_rule(
            rule,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            repeatability_limit=repeatability_limit,
            expanded_uncertainty=expanded_uncertainty,
            coverage_factor=coverage_factor,
        )

        normalized_readings = tuple(
            (
                item,
                _positive_integer(item.trial_no),
                _decimal(item.indicated_value),
                _decimal(item.standard_reading),
            )
            for item in readings
        )
    except (_NumericFailure, DecimalException, OverflowError):
        return _numeric_failure_result(rule)

    blockers: list[str] = []
    if (
        rule.reference_input_mode == "certified_value"
        and reference_value is None
    ):
        _append_once(blockers, "CALIBRATION_REFERENCE_MISSING")
    if lower_limit is None and upper_limit is None:
        _append_once(blockers, "CALIBRATION_TOLERANCE_MISSING")
    if (
        rule.repeatability_rule in {"range", "stddev"}
        and repeatability_limit is None
    ):
        _append_once(blockers, "CALIBRATION_REPEATABILITY_LIMIT_MISSING")
    if rule.uncertainty_required and expanded_uncertainty is None:
        _append_once(blockers, "CALIBRATION_UNCERTAINTY_MISSING")
    if rule.uncertainty_required and coverage_factor is None:
        _append_once(blockers, "CALIBRATION_COVERAGE_FACTOR_MISSING")

    calculated_readings: list[CalibrationReadingCalculation] = []
    completed_errors: list[Decimal] = []
    for (
        item,
        trial_no,
        indicated_value,
        standard_reading,
    ) in normalized_readings:
        reading_blockers: list[str] = []
        if indicated_value is None:
            _append_once(
                reading_blockers,
                "CALIBRATION_READING_MISSING",
            )

        effective_reference = (
            reference_value
            if rule.reference_input_mode == "certified_value"
            else standard_reading
        )
        if effective_reference is None:
            _append_once(
                reading_blockers,
                "CALIBRATION_REFERENCE_MISSING",
            )

        error = None
        correction = None
        if indicated_value is not None and effective_reference is not None:
            try:
                with localcontext() as context:
                    context.prec = _MAX_SIGNIFICANT_DIGITS
                    error = _decimal(
                        indicated_value - effective_reference
                    )
                    correction = _decimal(-error)
            except (_NumericFailure, DecimalException, OverflowError):
                return _numeric_failure_result(rule)
            completed_errors.append(error)

        for blocker in reading_blockers:
            _append_once(blockers, blocker)

        if reading_blockers or lower_limit is None and upper_limit is None:
            reading_result: ReadingResult = "pending"
        elif rule.evaluation_basis == "mean_error":
            reading_result = "not_individually_evaluated"
        else:
            reading_result = (
                "pass"
                if _within_limits(error, lower_limit, upper_limit)
                else "fail"
            )

        calculated_readings.append(
            CalibrationReadingCalculation(
                trial_no=trial_no,
                indicated_value=indicated_value,
                standard_reading=standard_reading,
                effective_reference=effective_reference,
                error=error,
                correction=correction,
                result=reading_result,
                blockers=tuple(reading_blockers),
            )
        )

    if len(normalized_readings) < rule.required_repetitions:
        _append_once(blockers, "CALIBRATION_REPETITIONS_MISSING")

    mean_error = None
    mean_correction = None
    minimum_error = None
    maximum_error = None
    error_range = None
    sample_stddev = None
    if completed_errors:
        try:
            with localcontext() as context:
                context.prec = _MAX_SIGNIFICANT_DIGITS
                error_count = Decimal(len(completed_errors))
                mean_error = (
                    sum(completed_errors, Decimal("0")) / error_count
                )
                mean_correction = -mean_error
                minimum_error = min(completed_errors)
                maximum_error = max(completed_errors)
                error_range = maximum_error - minimum_error
                for value in (
                    mean_error,
                    mean_correction,
                    minimum_error,
                    maximum_error,
                    error_range,
                ):
                    _decimal(value)
                if len(completed_errors) >= 2:
                    sample_variance = (
                        sum(
                            (value - mean_error) ** 2
                            for value in completed_errors
                        )
                        / Decimal(len(completed_errors) - 1)
                    )
                    _decimal(sample_variance)
                    sample_stddev = _decimal(sample_variance.sqrt())
        except (_NumericFailure, DecimalException, OverflowError):
            return _numeric_failure_result(rule)

    if (
        rule.repeatability_rule == "stddev"
        and sample_stddev is None
        and len(completed_errors) >= rule.required_repetitions
    ):
        _append_once(
            blockers,
            "CALIBRATION_REPEATABILITY_EVIDENCE_MISSING",
        )

    if blockers:
        point_result: PointResult = "pending"
    else:
        if rule.evaluation_basis == "all_readings":
            error_rule_passed = all(
                item.result == "pass" for item in calculated_readings
            )
        else:
            error_rule_passed = _within_limits(
                mean_error,
                lower_limit,
                upper_limit,
            )

        repeatability_passed = True
        if rule.repeatability_rule == "range":
            repeatability_passed = error_range <= repeatability_limit
        elif rule.repeatability_rule == "stddev":
            repeatability_passed = sample_stddev <= repeatability_limit

        point_result = (
            "pass"
            if error_rule_passed and repeatability_passed
            else "fail"
        )

    return CalibrationPointCalculation(
        point_code=rule.point_code,
        scope_code=rule.scope_code or rule.point_code,
        required=rule.required,
        readings=tuple(calculated_readings),
        mean_error=mean_error,
        mean_correction=mean_correction,
        minimum_error=minimum_error,
        maximum_error=maximum_error,
        error_range=error_range,
        sample_stddev=sample_stddev,
        expanded_uncertainty=expanded_uncertainty,
        coverage_factor=coverage_factor,
        result=point_result,
        blockers=tuple(blockers),
    )


def calculate_calibration(
    points: Sequence[CalibrationPointCalculation],
    *,
    allow_limited_use: bool,
) -> CalibrationCalculation:
    """依必要校正點的資格範圍產生整體判定。"""

    point_tuple = tuple(points)
    required_points = tuple(point for point in point_tuple if point.required)
    if not required_points:
        return CalibrationCalculation(
            points=point_tuple,
            result="pending",
            passed_scope_codes=(),
            failed_scope_codes=(),
            blockers=("CALIBRATION_REQUIRED_POINT_MISSING",),
        )

    scope_points: dict[str, list[CalibrationPointCalculation]] = {}
    for point in required_points:
        scope_points.setdefault(point.scope_code, []).append(point)

    passed_scope_codes = tuple(
        scope_code
        for scope_code, grouped_points in scope_points.items()
        if all(point.result == "pass" for point in grouped_points)
    )
    failed_scope_codes = tuple(
        scope_code
        for scope_code, grouped_points in scope_points.items()
        if any(point.result == "fail" for point in grouped_points)
    )
    pending_points = tuple(
        point for point in required_points if point.result == "pending"
    )
    blockers = tuple(
        dict.fromkeys(
            blocker
            for point in pending_points
            for blocker in point.blockers
        )
    )

    if pending_points:
        result: CalibrationResult = "pending"
    elif len(passed_scope_codes) == len(scope_points):
        result = "pass"
    elif (
        allow_limited_use
        and passed_scope_codes
        and failed_scope_codes
    ):
        result = "limited_use"
    else:
        result = "fail"

    return CalibrationCalculation(
        points=point_tuple,
        result=result,
        passed_scope_codes=passed_scope_codes,
        failed_scope_codes=failed_scope_codes,
        blockers=blockers,
    )
