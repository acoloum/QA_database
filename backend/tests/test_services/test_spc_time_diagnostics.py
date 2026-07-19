"""SPC 2026.2 時間模型診斷的固定基準測試。"""

from datetime import date, timedelta
import json

import pytest

from backend.services.spc_contracts import SpcChartSeries, SpcChartSet, SpcSubgroup
from backend.services.spc_time_diagnostics import diagnose_time_model


def _subgroups(means, scales):
    residuals = (-1.2, -0.4, 0.0, 0.4, 1.2)
    return tuple(
        SpcSubgroup(
            key=f"固定:{index}", timestamp=date(2026, 1, 1) + timedelta(days=index),
            values=tuple(mean + scale * residual for residual in residuals), record_ids=(index + 1,),
        )
        for index, (mean, scale) in enumerate(zip(means, scales))
    )


def _chart(means, scales):
    count = len(means)
    return SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries("xbar", tuple(means), (10.0,) * count, (13.0,) * count, (7.0,) * count),
        variation=SpcChartSeries("s", tuple(scales), (1.0,) * count, (3.0,) * count, (0.0,) * count),
        subgroup_sizes=(5,) * count, sigma_within=1.0,
    )


def _distribution(model="normal", normal_ok=True):
    return {"model": model, "accepted": True, "normal_ok": normal_ok, "unimodal": True}


@pytest.mark.parametrize(("means", "scales", "distribution", "expected"), [
    ([10.0, 10.1, 9.9, 10.0, 10.1, 9.9] * 5, [1.0] * 30, _distribution(), "A1"),
    ([10.0, 10.1, 9.9, 10.0, 10.1, 9.9] * 5, [1.0] * 30, _distribution("lognormal", False), "A2"),
    ([10.0, 10.1, 9.9, 10.0, 10.1, 9.9] * 5, [0.35] * 15 + [2.2] * 15, _distribution(), "B"),
    ([9.1, 10.8, 9.4, 10.6, 9.2, 10.9] * 5, [1.0] * 30, _distribution(), "C1"),
    ([9.1, 10.8, 9.4, 10.6, 9.2, 10.9] * 5, [1.0] * 30, _distribution("lognormal", False), "C2"),
    ([9.0 + index * .08 for index in range(30)], [1.0] * 30, _distribution(), "C3"),
    ([9.5] * 10 + [10.5] * 10 + [9.7] * 10, [1.0] * 30, _distribution(), "C4"),
    ([9.0] * 15 + [11.0] * 15, [0.3] * 15 + [2.0] * 15, _distribution(), "D"),
])
def test_fixed_golden_datasets_cover_each_time_model(means, scales, distribution, expected):
    result = diagnose_time_model(_chart(means, scales), _subgroups(means, scales), distribution)
    assert result["candidate"] == expected
    assert result["diagnostic_version"] == "2026.2"
    assert {"trend", "change_points", "variance_change", "instantaneous_distribution", "aggregate_modality", "multiple_testing"} <= set(result["evidence"])


def test_diagnostic_is_deterministic_and_holm_records_are_complete():
    means = [9.5] * 10 + [10.5] * 10 + [9.7] * 10
    result = diagnose_time_model(_chart(means, [1.0] * 30), _subgroups(means, [1.0] * 30), _distribution())
    assert result == diagnose_time_model(_chart(means, [1.0] * 30), _subgroups(means, [1.0] * 30), _distribution())
    for family in result["evidence"]["multiple_testing"]["families"].values():
        assert {"raw_p_value", "adjusted_p_value", "threshold", "reject"} <= set(family[0])

    mean_family = result["evidence"]["multiple_testing"]["families"]["mean_change"]
    running_adjusted = 0.0
    for rank, row in enumerate(sorted(mean_family, key=lambda item: item["raw_p_value"])):
        running_adjusted = max(
            running_adjusted,
            min(1.0, row["raw_p_value"] * (len(mean_family) - rank)),
        )
        assert row["adjusted_p_value"] == pytest.approx(running_adjusted)


@pytest.mark.parametrize("alpha", (0, -0.1, 1, float("inf"), float("nan")))
def test_invalid_alpha_is_rejected(alpha):
    with pytest.raises(ValueError, match="alpha"):
        diagnose_time_model(_chart([10.0] * 25, [1.0] * 25), _subgroups([10.0] * 25, [1.0] * 25), _distribution(), alpha=alpha)


def test_insufficient_subgroups_remain_unconfirmable():
    result = diagnose_time_model(_chart([10.0] * 24, [1.0] * 24), _subgroups([10.0] * 24, [1.0] * 24), _distribution())
    assert result["candidate"] is None
    assert result["confirmed"] is False
    assert result["reason_code"] == "TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT"


def test_constant_subgroups_return_a_serializable_preliminary_diagnostic():
    result = diagnose_time_model(
        _chart([10.0] * 25, [0.0] * 25),
        _subgroups([10.0] * 25, [0.0] * 25),
        _distribution(),
    )

    assert result["candidate"] == "A1"
    assert result["evidence"]["instantaneous_distribution"] == {
        "available": False,
        "reason_code": "INSTANTANEOUS_DISTRIBUTION_UNAVAILABLE",
    }
    json.dumps(result, allow_nan=False)


def test_non_finite_location_or_subgroup_values_are_rejected_explicitly():
    with pytest.raises(ValueError, match="有限"):
        diagnose_time_model(
            _chart([10.0] * 24 + [float("nan")], [1.0] * 25),
            _subgroups([10.0] * 25, [1.0] * 25),
            _distribution(),
        )


def test_location_change_threshold_and_all_override_models_are_auditable():
    means = [9.1, 10.8, 9.4, 10.6, 9.2, 10.9] * 5
    result = diagnose_time_model(
        _chart(means, [1.0] * 30),
        _subgroups(means, [1.0] * 30),
        _distribution(),
    )

    assert result["candidate_options"] == [
        "A1", "A2", "B", "C1", "C2", "C3", "C4", "D",
    ]
    location = result["evidence"]["location_change"]
    assert location["method"] == "between_within_scale_ratio"
    assert location["detected"] is True
    assert location["observed"] > location["threshold"]


def test_chart_limit_evidence_participates_in_location_and_variation_diagnosis():
    means = [10.0] * 25
    means[12] = 10.2
    location_chart = SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries(
            "xbar", tuple(means), (10.0,) * 25, (10.1,) * 25, (9.9,) * 25
        ),
        variation=SpcChartSeries(
            "s", (1.0,) * 25, (1.0,) * 25, (1.5,) * 25, (0.5,) * 25
        ),
        subgroup_sizes=(5,) * 25,
        sigma_within=1.0,
    )
    location_result = diagnose_time_model(
        location_chart, _subgroups(means, [1.0] * 25), _distribution()
    )

    scales = [1.0] * 25
    scales[12] = 2.0
    variation_chart = SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries(
            "xbar", (10.0,) * 25, (10.0,) * 25, (10.5,) * 25, (9.5,) * 25
        ),
        variation=SpcChartSeries(
            "s", tuple(scales), (1.0,) * 25, (1.5,) * 25, (0.5,) * 25
        ),
        subgroup_sizes=(5,) * 25,
        sigma_within=1.0,
    )
    variation_result = diagnose_time_model(
        variation_chart, _subgroups([10.0] * 25, scales), _distribution()
    )

    assert location_result["candidate"] == "C1"
    assert location_result["evidence"]["chart_stability"]["location"]["detected"] is True
    assert location_result["evidence"]["chart_stability"]["location"]["indexes"] == [12]
    assert variation_result["candidate"] == "B"
    assert variation_result["evidence"]["chart_stability"]["variation"]["detected"] is True
    assert variation_result["evidence"]["chart_stability"]["variation"]["indexes"] == [12]
