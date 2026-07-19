"""SPC 2026.2 時間模型診斷的固定基準測試。"""

from datetime import date, timedelta
import json

import numpy as np
import pytest

from backend.services.spc_chart_engine import calculate_chart_set
from backend.services.spc_contracts import SpcChartSeries, SpcChartSet, SpcSubgroup
from backend.services.spc_distribution import assess_distribution
from backend.services.spc_stability import evaluate_study_stability
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


@pytest.mark.parametrize("expected", ("A1", "A2", "B", "C1", "C2", "C3", "C4", "D"))
def test_fixed_golden_datasets_cover_each_time_model(expected):
    chart, groups, distribution, stability = _golden_dataset(expected)
    result = diagnose_time_model(
        chart, groups, distribution, stability=stability
    )
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

    assert result["candidate"] is None or result["candidate"] == "B"
    assert result["candidate"] not in {"A1", "A2"}
    assert result["evidence"]["instantaneous_distribution"]["available"] is False
    json.dumps(result, allow_nan=False)


def test_non_finite_location_or_subgroup_values_are_rejected_explicitly():
    with pytest.raises(ValueError, match="有限"):
        diagnose_time_model(
            _chart([10.0] * 24 + [float("nan")], [1.0] * 25),
            _subgroups([10.0] * 25, [1.0] * 25),
            _distribution(),
        )


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

    location_violations = location_result["evidence"]["formal_stability"]["location"]["violations"]
    assert any(item["rule"] == "beyond_limits" and item["index"] == 12 for item in location_violations)
    assert variation_result["candidate"] == "B"
    variation_violations = variation_result["evidence"]["formal_stability"]["variation"]["violations"]
    assert any(item["rule"] == "beyond_limits" and item["index"] == 12 for item in variation_violations)


def _sampled_groups(matrix, *, distribution_matrix=None):
    return tuple(
        SpcSubgroup(
            key=f"raw:{index}",
            timestamp=date(2026, 2, 1) + timedelta(days=index),
            values=tuple(float(value) for value in row),
            distribution_values=(
                tuple(float(value) for value in distribution_matrix[index])
                if distribution_matrix is not None else ()
            ),
            record_ids=(index + 1,),
        )
        for index, row in enumerate(matrix)
    )


def _raw_distribution(groups):
    return assess_distribution([
        value
        for group in groups
        for value in (group.distribution_values or group.values)
    ])


def _controlled_chart(groups):
    """保留真實統計量，但以不產生偶發超限的固定寬界限建立 golden。"""

    calculated = calculate_chart_set(groups)
    count = len(groups)
    location_values = tuple(float(value) for value in calculated.location.values)
    variation_values = tuple(
        float(value) if value is not None else None
        for value in calculated.variation.values
    )
    location_center = float(np.mean(location_values))
    numeric_variation = [value for value in variation_values if value is not None]
    variation_center = float(np.mean(numeric_variation))
    location_span = max(5.0, float(np.std(location_values, ddof=1)) * 10)
    variation_upper = max(numeric_variation) + max(1.0, variation_center * 3)
    return SpcChartSet(
        chart_type=calculated.chart_type,
        location=SpcChartSeries(
            calculated.location.statistic,
            location_values,
            (location_center,) * count,
            (location_center + location_span,) * count,
            (location_center - location_span,) * count,
        ),
        variation=SpcChartSeries(
            calculated.variation.statistic,
            variation_values,
            tuple(
                value if value is not None else variation_center
                for value in variation_values
            ),
            (variation_upper,) * count,
            (0.0,) * count,
        ),
        subgroup_sizes=calculated.subgroup_sizes,
        sigma_within=calculated.sigma_within,
        variation_source_pairs=calculated.variation_source_pairs,
    )


def _normalized_rows(rng, means, scales, size=12, *, skew=False):
    rows = []
    for mean, scale in zip(means, scales):
        sample = (
            rng.exponential(1.0, size=size)
            if skew else rng.normal(0.0, 1.0, size=size)
        )
        sample = (sample - sample.mean()) / sample.std(ddof=1)
        rows.append(mean + scale * sample)
    return np.asarray(rows)


def _golden_dataset(model):
    rng = np.random.default_rng(100 + sum(ord(char) for char in model))
    if model == "A1":
        matrix = np.random.default_rng(0).normal(10.0, 1.0, size=(30, 5))
    elif model == "A2":
        matrix = _normalized_rows(rng, [10.0] * 30, [1.0] * 30, skew=True)
    elif model == "B":
        matrix = _normalized_rows(
            rng, [10.0] * 30, [0.35] * 15 + [2.2] * 15
        )
    elif model == "C1":
        raw = np.random.default_rng(0)
        means = raw.normal(10.0, 0.9, size=30)
        matrix = np.asarray([
            mean + raw.normal(0.0, 0.25, size=5) for mean in means
        ])
    elif model == "C2":
        raw = np.random.default_rng(0)
        means = 9.0 + raw.lognormal(-0.2, 0.45, size=30)
        matrix = np.asarray([
            mean + raw.normal(0.0, 0.08, size=5) for mean in means
        ])
    elif model == "C3":
        matrix = _normalized_rows(
            rng, [9.0 + index * 0.08 for index in range(30)], [0.5] * 30
        )
    elif model == "C4":
        matrix = _normalized_rows(
            rng, [9.5] * 10 + [10.5] * 10 + [9.7] * 10, [0.5] * 30
        )
    else:
        matrix = _normalized_rows(
            rng, [9.0] * 15 + [11.0] * 15, [0.3] * 15 + [2.0] * 15
        )
    groups = _sampled_groups(matrix)
    chart = _controlled_chart(groups)
    return chart, groups, _raw_distribution(groups), evaluate_study_stability(chart)


def test_iid_normal_seed_zero_is_not_misclassified_as_random_location():
    matrix = np.random.default_rng(0).normal(10.0, 1.0, size=(30, 5))
    groups = _sampled_groups(matrix)
    chart = _controlled_chart(groups)
    stability = evaluate_study_stability(chart)

    result = diagnose_time_model(
        chart, groups, _raw_distribution(groups), stability=stability
    )

    assert stability["stable"] is True
    assert result["candidate"] == "A1"
    random_effect = result["evidence"]["random_location"]
    assert random_effect["method"] == "one_way_random_effect_f"
    assert random_effect["reject"] is False
    assert random_effect["subgroup_sizes"] == [5] * 30


def test_true_random_group_shift_is_c1_with_significant_effect():
    rng = np.random.default_rng(0)
    group_means = rng.normal(10.0, 0.9, size=30)
    matrix = np.asarray([
        mean + rng.normal(0.0, 0.25, size=5) for mean in group_means
    ])
    groups = _sampled_groups(matrix)
    chart = _controlled_chart(groups)
    stability = evaluate_study_stability(chart)

    result = diagnose_time_model(
        chart, groups, _raw_distribution(groups), stability=stability
    )

    assert result["candidate"] == "C1"
    random_effect = result["evidence"]["random_location"]
    assert random_effect["reject"] is True
    assert random_effect["adjusted_p_value"] <= random_effect["threshold"]
    assert random_effect["omega_squared"] >= random_effect["effect_threshold"]


def test_instantaneous_nonnormality_cannot_be_overridden_by_normal_aggregate():
    rng = np.random.default_rng(7)
    rows = []
    for _ in range(30):
        residuals = rng.exponential(1.0, size=20)
        residuals = (residuals - residuals.mean()) / residuals.std(ddof=1)
        rows.append(10.0 + residuals)
    aggregate_normal = rng.normal(10.0, 1.0, size=(30, 20))
    groups = _sampled_groups(np.asarray(rows), distribution_matrix=aggregate_normal)
    chart = _controlled_chart(groups)
    stability = evaluate_study_stability(chart)
    aggregate = _raw_distribution(groups)
    assert aggregate["normal_ok"] is True

    result = diagnose_time_model(chart, groups, aggregate, stability=stability)

    assert result["candidate"] == "A2"
    assert result["evidence"]["instantaneous_distribution"]["normal"] is False
    assert result["evidence"]["instantaneous_distribution"]["accepted"] is True


def test_formal_run_rule_prevents_a_model_even_without_limit_violation():
    means = [10.2] * 30
    groups = _subgroups(means, [1.0] * 30)
    chart = SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries(
            "xbar", tuple(means), (10.0,) * 30, (11.0,) * 30, (9.0,) * 30
        ),
        variation=SpcChartSeries(
            "s", (1.0,) * 30, (1.0,) * 30, (3.0,) * 30, (0.0,) * 30
        ),
        subgroup_sizes=(5,) * 30,
        sigma_within=1.0,
    )
    stability = evaluate_study_stability(chart)
    assert any(
        item["rule"] == "run_9_same_side"
        for item in stability["location"]["violations"]
    )

    result = diagnose_time_model(
        chart, groups, _raw_distribution(groups), stability=stability
    )

    assert result["candidate"] not in {"A1", "A2"}
    assert result["statistically_controlled"] is False
    assert "run_9_same_side" in {
        item["rule"]
        for item in result["evidence"]["formal_stability"]["location"]["violations"]
    }


@pytest.mark.parametrize(
    ("series", "field"),
    [
        (series, field)
        for series in ("location", "variation")
        for field in ("values", "cl", "ucl", "lcl")
    ],
)
def test_public_diagnostic_rejects_mismatched_chart_series_lengths(series, field):
    groups = _subgroups([10.0] * 25, [1.0] * 25)
    chart = _chart([10.0] * 25, [1.0] * 25)
    original = getattr(chart, series)
    changed = SpcChartSeries(
        original.statistic,
        original.values[:-1] if field == "values" else original.values,
        original.cl[:-1] if field == "cl" else original.cl,
        original.ucl[:-1] if field == "ucl" else original.ucl,
        original.lcl[:-1] if field == "lcl" else original.lcl,
    )
    mismatched = SpcChartSet(
        chart_type=chart.chart_type,
        location=changed if series == "location" else chart.location,
        variation=changed if series == "variation" else chart.variation,
        subgroup_sizes=chart.subgroup_sizes,
        sigma_within=chart.sigma_within,
    )

    with pytest.raises(ValueError, match="長度"):
        diagnose_time_model(mismatched, groups, _raw_distribution(groups))


def test_unequal_subgroup_sizes_use_weighted_random_effect_test():
    rng = np.random.default_rng(1)
    sizes = [3 + index % 5 for index in range(30)]
    groups = _sampled_groups([
        rng.normal(10.0, 1.0, size=size) for size in sizes
    ])
    chart = _controlled_chart(groups)
    stability = evaluate_study_stability(chart)

    result = diagnose_time_model(
        chart, groups, _raw_distribution(groups), stability=stability
    )

    evidence = result["evidence"]["random_location"]
    assert evidence["subgroup_sizes"] == sizes
    assert evidence["df_within"] == sum(sizes) - len(sizes)
    assert evidence["reject"] is False
    assert result["candidate"] == "A1"


def test_unavailable_instantaneous_distribution_does_not_fall_back_to_a2():
    matrix = np.full((30, 5), 10.0)
    groups = _sampled_groups(matrix)
    chart = SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries(
            "xbar", (10.0,) * 30, (10.0,) * 30, (11.0,) * 30, (9.0,) * 30
        ),
        variation=SpcChartSeries(
            "s", (0.0,) * 30, (0.0,) * 30, (1.0,) * 30, (0.0,) * 30
        ),
        subgroup_sizes=(5,) * 30,
        sigma_within=0.0,
    )
    stability = evaluate_study_stability(chart)

    result = diagnose_time_model(
        chart, groups, _raw_distribution(groups), stability=stability
    )

    assert stability["stable"] is True
    assert result["candidate"] is None
    assert result["reason_code"] == "TIME_DIAGNOSTIC_DISTRIBUTION_UNAVAILABLE"
    assert result["candidate_options"] == []


def test_random_location_requires_confirmed_unimodal_aggregate_distribution():
    chart, groups, _distribution_result, stability = _golden_dataset("C1")
    unavailable = {
        "accepted": False,
        "normal_ok": None,
        "unimodal": False,
        "reason_code": "GOODNESS_OF_FIT_REJECTED",
    }

    result = diagnose_time_model(
        chart, groups, unavailable, stability=stability
    )

    assert result["evidence"]["random_location"]["reject"] is True
    assert result["candidate"] is None
    assert result["reason_code"] == "TIME_DIAGNOSTIC_DISTRIBUTION_UNAVAILABLE"


def test_student_t_random_location_is_c2_without_accepted_alternative_distribution():
    rng = np.random.default_rng(73)
    group_means = rng.standard_t(df=3, size=40) * 1.4
    matrix = np.asarray([
        mean + rng.normal(0.0, 0.18, size=6) for mean in group_means
    ])
    groups = _sampled_groups(matrix)
    chart = _controlled_chart(groups)
    stability = evaluate_study_stability(chart)
    distribution = _raw_distribution(groups)

    assert distribution["candidates"][0]["model"] == "normal"
    assert distribution["candidates"][0]["accepted"] is False
    assert distribution["accepted"] is False

    result = diagnose_time_model(
        chart, groups, distribution, stability=stability
    )

    assert result["evidence"]["random_location"]["reject"] is True
    assert result["evidence"]["aggregate_modality"]["unimodal"] is True
    assert result["candidate"] == "C2"
    assert result["reason_code"] is None


@pytest.mark.parametrize("series_name", ("location", "variation"))
def test_chart_non_none_values_must_be_finite(series_name):
    groups = _subgroups([10.0] * 25, [1.0] * 25)
    chart = _chart([10.0] * 25, [1.0] * 25)
    source = getattr(chart, series_name)
    values = list(source.values)
    values[12] = float("nan")
    changed = SpcChartSeries(
        source.statistic, tuple(values), source.cl, source.ucl, source.lcl
    )
    invalid = SpcChartSet(
        chart_type=chart.chart_type,
        location=changed if series_name == "location" else chart.location,
        variation=changed if series_name == "variation" else chart.variation,
        subgroup_sizes=chart.subgroup_sizes,
        sigma_within=chart.sigma_within,
    )

    with pytest.raises(ValueError, match="有限"):
        diagnose_time_model(invalid, groups, _raw_distribution(groups))
