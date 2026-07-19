"""p／np 屬性型管制圖的精確二項分配計算。"""

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite, sqrt
from typing import Iterable

import numpy as np
from scipy import stats as scipy_stats

from .spc_chart_engine import SpcChartNotApplicable


@dataclass(frozen=True)
class AttributeSubgroup:
    """一個屬性資料合理子組，保存受檢與不符合單位數。"""

    key: str
    timestamp: date | datetime | str | None
    inspected: int
    nonconforming: int
    record_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.inspected <= 0 or not 0 <= self.nonconforming <= self.inspected:
            raise ValueError("屬性子組數量不合法")
        object.__setattr__(self, "record_ids", tuple(int(value) for value in self.record_ids))


def _exact_limits(n: int, p_bar: float, alpha: float) -> tuple[int | None, int]:
    """依二項累積機率不等式求取離散管制界限。"""

    cdf = scipy_stats.binom.cdf(np.arange(n + 1), n, p_bar)
    lower_candidates = np.flatnonzero(cdf <= alpha / 2.0)
    upper_candidates = np.flatnonzero(cdf >= 1.0 - alpha / 2.0)
    lower = int(lower_candidates[-1]) if lower_candidates.size else None
    upper = int(upper_candidates[0]) if upper_candidates.size else n
    return (max(0, lower) if lower is not None else None), min(n, upper)


def _sample_size_metadata(sizes: tuple[int, ...]) -> dict[str, float | bool]:
    minimum = min(sizes)
    maximum = max(sizes)
    variation_ratio = (maximum - minimum) / minimum
    return {
        "sample_size_variation_ratio": float(variation_ratio),
        "sample_size_variation_warning": variation_ratio >= 0.25,
    }


def calculate_attribute_chart(
    subgroups: Iterable[AttributeSubgroup],
    requested_chart: str,
    *,
    alpha: float = 0.0027,
) -> dict:
    """計算 p 或 np 圖，並以精確二項分配產生每點界限。"""

    groups = tuple(subgroups)
    if not groups:
        raise SpcChartNotApplicable("NO_ATTRIBUTE_DATA", "沒有可用屬性子組")
    if requested_chart not in {"p", "np"}:
        raise SpcChartNotApplicable("CHART_TYPE_UNSUPPORTED", "僅支援 p 與 np 管制圖")
    if not isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha 必須介於 0 與 1 之間")

    sizes = tuple(group.inspected for group in groups)
    counts = tuple(group.nonconforming for group in groups)
    total_inspected = sum(sizes)
    total_nonconforming = sum(counts)
    p_bar = total_nonconforming / total_inspected
    if p_bar == 0:
        raise SpcChartNotApplicable(
            "ZERO_DEFECT_BASELINE", "零缺陷基線不可建立屬性管制界限"
        )
    if p_bar == 1:
        raise SpcChartNotApplicable(
            "DEGENERATE_ATTRIBUTE_BASELINE", "全數不符合基線不可建立屬性管制界限"
        )
    if requested_chart == "np" and len(set(sizes)) != 1:
        raise SpcChartNotApplicable(
            "NP_REQUIRES_FIXED_SUBGROUP_SIZE", "np 圖需要固定子組大小"
        )

    exact_counts = tuple(_exact_limits(n, p_bar, alpha) for n in sizes)
    denominator = sqrt(p_bar * (1.0 - p_bar))
    pearson_residuals = [
        (count - size * p_bar) / (sqrt(size) * denominator)
        for size, count in zip(sizes, counts)
    ]
    metadata = _sample_size_metadata(sizes)

    if requested_chart == "p":
        values = [count / size for size, count in zip(sizes, counts)]
        cl = [p_bar] * len(groups)
        lcl = [
            lower / size if lower is not None else 0.0
            for size, (lower, _upper) in zip(sizes, exact_counts)
        ]
        ucl = [upper / size for size, (_lower, upper) in zip(sizes, exact_counts)]
    else:
        values = list(counts)
        cl = [sizes[0] * p_bar] * len(groups)
        lcl = [float(lower) if lower is not None else 0.0 for lower, _upper in exact_counts]
        ucl = [float(upper) for _lower, upper in exact_counts]

    lower_counts = [lower for lower, _upper in exact_counts]
    upper_counts = [upper for _lower, upper in exact_counts]
    ooc_flags = [
        {
            "lower": lower is not None and count <= lower,
            "upper": count > upper,
            "out_of_control": (lower is not None and count <= lower) or count > upper,
        }
        for count, (lower, upper) in zip(counts, exact_counts)
    ]

    return {
        "chart_type": requested_chart,
        "center": float(p_bar),
        "values": values,
        "cl": cl,
        "ucl": ucl,
        "lcl": lcl,
        "n": list(sizes),
        "x": list(counts),
        "subgroup_count": len(groups),
        "total_inspected": total_inspected,
        "total_nonconforming": total_nonconforming,
        "pearson_residuals": pearson_residuals,
        "lower_counts": lower_counts,
        "upper_counts": upper_counts,
        "boundary_semantics": {
            "lower": "x <= lower_count（lower_count 為 null 時不判定下界訊號）",
            "upper": "x > upper_count",
        },
        "ooc_flags": ooc_flags,
        **metadata,
    }
