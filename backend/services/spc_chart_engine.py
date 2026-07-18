"""AIAG & VDA SPC 2026 計量型管制圖選型與界限計算。"""

from math import gamma, sqrt
from typing import Iterable

import numpy as np
from scipy import stats as scipy_stats

from .spc_constants import SPC_CONSTANTS
from .spc_contracts import SpcChartSeries, SpcChartSet, SpcSubgroup


class SpcChartNotApplicable(ValueError):
    """資料結構不適用任何目前支援的管制圖。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _repeat(value: float, count: int) -> tuple[float, ...]:
    return (float(value),) * count


def _c4(n: int) -> float:
    df = n - 1
    return sqrt(2.0 / df) * gamma((df + 1.0) / 2.0) / gamma(df / 2.0)


def _validate_count(subgroups: tuple[SpcSubgroup, ...]) -> None:
    if len(subgroups) < 2:
        raise SpcChartNotApplicable("INSUFFICIENT_SUBGROUPS", "至少需要兩個子組")


def _xbar_s(subgroups: tuple[SpcSubgroup, ...], alpha: float) -> SpcChartSet:
    sizes = tuple(group.n for group in subgroups)
    means = tuple(float(np.mean(group.values)) for group in subgroups)
    variances = tuple(float(np.var(group.values, ddof=1)) for group in subgroups)
    total_df = sum(n - 1 for n in sizes)
    sigma = sqrt(sum((n - 1) * variance for n, variance in zip(sizes, variances)) / total_df)
    if sigma <= 0:
        raise SpcChartNotApplicable("DEGENERATE_VARIATION", "子組變異為零，無法建立管制圖")

    all_values = [value for group in subgroups for value in group.values]
    center = float(np.mean(all_values))
    z_value = float(scipy_stats.norm.ppf(1.0 - alpha / 2.0))
    location_ucl = tuple(center + z_value * sigma / sqrt(n) for n in sizes)
    location_lcl = tuple(center - z_value * sigma / sqrt(n) for n in sizes)

    std_values = tuple(sqrt(variance) for variance in variances)
    variation_cl = tuple(_c4(n) * sigma for n in sizes)
    variation_ucl = tuple(
        sigma * sqrt(float(scipy_stats.chi2.ppf(1.0 - alpha / 2.0, n - 1)) / (n - 1))
        for n in sizes
    )
    variation_lcl = tuple(
        sigma * sqrt(float(scipy_stats.chi2.ppf(alpha / 2.0, n - 1)) / (n - 1))
        for n in sizes
    )

    return SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries(
            statistic="xbar",
            values=means,
            cl=_repeat(center, len(subgroups)),
            ucl=location_ucl,
            lcl=location_lcl,
        ),
        variation=SpcChartSeries(
            statistic="s",
            values=std_values,
            cl=variation_cl,
            ucl=variation_ucl,
            lcl=variation_lcl,
        ),
        subgroup_sizes=sizes,
        sigma_within=float(sigma),
    )


def _xbar_r(subgroups: tuple[SpcSubgroup, ...]) -> SpcChartSet:
    n = subgroups[0].n
    means = tuple(float(np.mean(group.values)) for group in subgroups)
    ranges = tuple(float(np.ptp(group.values)) for group in subgroups)
    center = float(np.mean(means))
    range_center = float(np.mean(ranges))
    if range_center <= 0:
        raise SpcChartNotApplicable("DEGENERATE_VARIATION", "子組變異為零，無法建立管制圖")
    a2, d3, d4, d2 = SPC_CONSTANTS[n]
    count = len(subgroups)

    return SpcChartSet(
        chart_type="xbar_r",
        location=SpcChartSeries(
            statistic="xbar",
            values=means,
            cl=_repeat(center, count),
            ucl=_repeat(center + a2 * range_center, count),
            lcl=_repeat(center - a2 * range_center, count),
        ),
        variation=SpcChartSeries(
            statistic="r",
            values=ranges,
            cl=_repeat(range_center, count),
            ucl=_repeat(d4 * range_center, count),
            lcl=_repeat(d3 * range_center, count),
        ),
        subgroup_sizes=(n,) * count,
        sigma_within=range_center / d2,
    )


def _i_mr(subgroups: tuple[SpcSubgroup, ...]) -> SpcChartSet:
    timestamps = tuple(group.timestamp for group in subgroups)
    if any(timestamp is None for timestamp in timestamps):
        raise SpcChartNotApplicable("INVALID_TIME_ORDER", "個別值管制圖需要完整時間順序")
    try:
        ordered = all(timestamps[index] < timestamps[index + 1] for index in range(len(timestamps) - 1))
    except TypeError as exc:
        raise SpcChartNotApplicable("INVALID_TIME_ORDER", "個別值時間格式無法比較") from exc
    if not ordered:
        raise SpcChartNotApplicable("INVALID_TIME_ORDER", "個別值時間必須嚴格遞增")

    values = tuple(float(group.values[0]) for group in subgroups)
    moving_ranges = tuple(abs(values[index] - values[index - 1]) for index in range(1, len(values)))
    range_center = float(np.mean(moving_ranges))
    if range_center <= 0:
        raise SpcChartNotApplicable("DEGENERATE_VARIATION", "移動全距為零，無法建立管制圖")
    _, d3, d4, d2 = SPC_CONSTANTS[2]
    sigma = range_center / d2
    center = float(np.mean(values))
    count = len(values)

    return SpcChartSet(
        chart_type="i_mr",
        location=SpcChartSeries(
            statistic="individual",
            values=values,
            cl=_repeat(center, count),
            ucl=_repeat(center + 3.0 * sigma, count),
            lcl=_repeat(center - 3.0 * sigma, count),
        ),
        variation=SpcChartSeries(
            statistic="mr",
            values=(None,) + moving_ranges,
            cl=_repeat(range_center, count),
            ucl=_repeat(d4 * range_center, count),
            lcl=_repeat(d3 * range_center, count),
        ),
        subgroup_sizes=(1,) * count,
        sigma_within=sigma,
        variation_source_pairs=(None,) + tuple({
            "previous_record_ids": list(subgroups[index - 1].record_ids),
            "current_record_ids": list(subgroups[index].record_ids),
            "previous_measurement_ids": list(subgroups[index - 1].measurement_ids),
            "current_measurement_ids": list(subgroups[index].measurement_ids),
        } for index in range(1, count)),
    )


def calculate_chart_set(
    subgroups: Iterable[SpcSubgroup],
    *,
    alpha: float = 0.0027,
) -> SpcChartSet:
    """依合理子組結構選圖；電腦計算優先使用 X̄-S。"""

    groups = tuple(subgroups)
    _validate_count(groups)
    sizes = {group.n for group in groups}
    if sizes == {1}:
        return _i_mr(groups)
    if sizes == {2}:
        return _xbar_r(groups)
    if min(sizes) >= 3:
        return _xbar_s(groups, alpha)
    raise SpcChartNotApplicable(
        "INVALID_SUBGROUP_STRUCTURE",
        "子組大小混合了 2 與 3 件以上資料，無法套用同一管制圖",
    )


def calculate_chart_observations(
    subgroups: Iterable[SpcSubgroup],
    chart_type: str,
) -> SpcChartSet:
    """計算持續監控觀測統計量；不由目前批次估計中心或變異。"""

    groups = tuple(subgroups)
    _validate_count(groups)
    sizes = tuple(group.n for group in groups)
    count = len(groups)
    placeholders = _repeat(0.0, count)

    if chart_type == "xbar_s":
        if min(sizes) < 3:
            raise SpcChartNotApplicable(
                "INVALID_SUBGROUP_STRUCTURE", "X̄-S 監控的每個子組至少需要三件資料"
            )
        location_values = tuple(float(np.mean(group.values)) for group in groups)
        variation_values = tuple(float(np.std(group.values, ddof=1)) for group in groups)
        location_statistic, variation_statistic = "xbar", "s"
        variation_source_pairs = ()
    elif chart_type == "xbar_r":
        if set(sizes) != {2}:
            raise SpcChartNotApplicable(
                "INVALID_SUBGROUP_STRUCTURE", "X̄-R 監控只接受大小為二的子組"
            )
        location_values = tuple(float(np.mean(group.values)) for group in groups)
        variation_values = tuple(float(np.ptp(group.values)) for group in groups)
        location_statistic, variation_statistic = "xbar", "r"
        variation_source_pairs = ()
    elif chart_type == "i_mr":
        if set(sizes) != {1}:
            raise SpcChartNotApplicable(
                "INVALID_SUBGROUP_STRUCTURE", "I-MR 監控只接受個別值資料"
            )
        timestamps = tuple(group.timestamp for group in groups)
        if any(timestamp is None for timestamp in timestamps):
            raise SpcChartNotApplicable("INVALID_TIME_ORDER", "個別值管制圖需要完整時間順序")
        try:
            ordered = all(
                timestamps[index] < timestamps[index + 1]
                for index in range(count - 1)
            )
        except TypeError as exc:
            raise SpcChartNotApplicable("INVALID_TIME_ORDER", "個別值時間格式無法比較") from exc
        if not ordered:
            raise SpcChartNotApplicable("INVALID_TIME_ORDER", "個別值時間必須嚴格遞增")
        location_values = tuple(float(group.values[0]) for group in groups)
        variation_values = (None,) + tuple(
            abs(location_values[index] - location_values[index - 1])
            for index in range(1, count)
        )
        location_statistic, variation_statistic = "individual", "mr"
        variation_source_pairs = (None,) + tuple({
            "previous_record_ids": list(groups[index - 1].record_ids),
            "current_record_ids": list(groups[index].record_ids),
            "previous_measurement_ids": list(groups[index - 1].measurement_ids),
            "current_measurement_ids": list(groups[index].measurement_ids),
        } for index in range(1, count))
    else:
        raise SpcChartNotApplicable("CHART_TYPE_UNSUPPORTED", "不支援的正式管制圖類型")

    return SpcChartSet(
        chart_type=chart_type,
        location=SpcChartSeries(
            statistic=location_statistic,
            values=location_values,
            cl=placeholders,
            ucl=placeholders,
            lcl=placeholders,
        ),
        variation=SpcChartSeries(
            statistic=variation_statistic,
            values=variation_values,
            cl=placeholders,
            ucl=placeholders,
            lcl=placeholders,
        ),
        subgroup_sizes=sizes,
        sigma_within=0.0,
        variation_source_pairs=variation_source_pairs,
    )
