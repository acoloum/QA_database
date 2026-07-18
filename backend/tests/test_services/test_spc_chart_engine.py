"""2026 SPC 計量型管制圖選型與逐組界限測試。"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.spc_chart_engine import (
    SpcChartNotApplicable,
    calculate_chart_set,
)
from backend.services.spc_contracts import SpcReason, SpcStudyInput, SpcSubgroup


def _subgroup(key: str, values: list[float], day: int = 0) -> SpcSubgroup:
    return SpcSubgroup(
        key=key,
        timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(days=day),
        values=values,
        record_ids=[day + 1],
        measurement_ids=list(range(day * 10 + 1, day * 10 + len(values) + 1)),
    )


def test_subgroup_rejects_empty_values():
    with pytest.raises(ValueError, match="子組不可為空"):
        SpcSubgroup(key="G1", timestamp=None, values=[])


def test_study_input_and_reason_keep_a_stable_contract():
    subgroup = _subgroup("G1", [9.9, 10.0, 10.1])
    reason = SpcReason(code="INSUFFICIENT_SUBGROUPS", message="子組數不足")

    study = SpcStudyInput(
        source="shipping",
        filters={"field": "外徑"},
        process_stream_key="stream-hash",
        characteristic="外徑",
        subgroups=[subgroup],
        specification={"USL": 10.5, "LSL": 9.5},
    )

    assert study.subgroups == (subgroup,)
    assert study.filters == {"field": "外徑"}
    assert reason.code == "INSUFFICIENT_SUBGROUPS"


def test_n_at_least_three_selects_xbar_s_and_checks_s_first():
    subgroups = [
        _subgroup("G1", [9.8, 10.0, 10.2], 0),
        _subgroup("G2", [9.9, 10.1, 10.3], 1),
        _subgroup("G3", [9.7, 10.0, 10.1], 2),
        _subgroup("G4", [9.9, 10.0, 10.2], 3),
        _subgroup("G5", [9.8, 10.1, 10.2], 4),
    ]

    result = calculate_chart_set(subgroups)

    assert result.chart_type == "xbar_s"
    assert result.location.statistic == "xbar"
    assert result.variation.statistic == "s"
    assert all(limit > 0 for limit in result.variation.lcl)


def test_unequal_subgroups_have_point_specific_limits():
    subgroups = [
        _subgroup("G1", [9.8, 10.0, 10.2], 0),
        _subgroup("G2", [9.8, 9.9, 10.1, 10.2], 1),
        _subgroup("G3", [9.7, 9.9, 10.0, 10.1, 10.3], 2),
        _subgroup("G4", [9.9, 10.0, 10.2], 3),
        _subgroup("G5", [9.8, 9.9, 10.0, 10.1], 4),
    ]

    result = calculate_chart_set(subgroups)

    assert result.subgroup_sizes == (3, 4, 5, 3, 4)
    assert len(result.location.ucl) == 5
    assert len(set(round(v, 10) for v in result.location.ucl[:3])) == 3
    assert result.location.ucl[0] == result.location.ucl[3]


def test_two_value_subgroups_select_xbar_r():
    result = calculate_chart_set([
        _subgroup(f"G{i}", [9.9 + i * 0.01, 10.1 + i * 0.01], i)
        for i in range(5)
    ])

    assert result.chart_type == "xbar_r"
    assert result.variation.statistic == "r"
    assert result.variation.lcl == (0.0,) * 5


def test_ordered_individual_values_select_i_mr():
    result = calculate_chart_set([
        _subgroup(f"G{i}", [10.0 + i * 0.02], i)
        for i in range(5)
    ])

    assert result.chart_type == "i_mr"
    assert result.location.statistic == "individual"
    assert result.variation.statistic == "mr"
    assert result.variation.values[0] is None


def test_mixed_two_and_three_value_subgroups_are_not_applicable():
    subgroups = [
        _subgroup("G1", [9.9, 10.1], 0),
        _subgroup("G2", [9.8, 10.0, 10.2], 1),
    ]

    with pytest.raises(SpcChartNotApplicable) as exc:
        calculate_chart_set(subgroups)

    assert exc.value.code == "INVALID_SUBGROUP_STRUCTURE"


def test_individual_values_require_strict_time_order():
    same_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    subgroups = [
        SpcSubgroup(key="G1", timestamp=same_time, values=[10.0]),
        SpcSubgroup(key="G2", timestamp=same_time, values=[10.1]),
    ]

    with pytest.raises(SpcChartNotApplicable) as exc:
        calculate_chart_set(subgroups)

    assert exc.value.code == "INVALID_TIME_ORDER"
