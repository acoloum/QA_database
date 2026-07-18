"""已確認的 2026 SPC 差距之回歸測試。"""

from datetime import datetime, timedelta, timezone

from backend.services.spc_chart_engine import calculate_chart_set
from backend.services.spc_analysis_service import calculate_process_capability
from backend.services.spc_contracts import SpcChartSeries, SpcChartSet, SpcSubgroup
from backend.services.spc_stability import evaluate_study_stability


def test_variable_subgroup_limits_are_not_derived_from_rounded_average_n():
    base = datetime(2026, 7, 1, tzinfo=timezone.utc)
    values = (
        [9.8, 10.0, 10.2],
        [9.8, 9.9, 10.1, 10.2],
        [9.7, 9.9, 10.0, 10.1, 10.3],
        [9.9, 10.0, 10.2],
        [9.8, 9.9, 10.0, 10.1],
    )
    result = calculate_chart_set([
        SpcSubgroup(key=f"G{i + 1}", timestamp=base + timedelta(days=i), values=row)
        for i, row in enumerate(values)
    ])

    assert result.subgroup_sizes == (3, 4, 5, 3, 4)
    assert result.location.ucl[0] != result.location.ucl[1]
    assert result.location.ucl[1] != result.location.ucl[2]


def test_variation_chart_out_of_control_blocks_capability():
    chart_set = SpcChartSet(
        chart_type="xbar_s",
        location=SpcChartSeries(
            statistic="xbar",
            values=(10.0, 10.1, 9.9, 10.05, 9.95),
            cl=(10.0,) * 5,
            ucl=(10.5,) * 5,
            lcl=(9.5,) * 5,
        ),
        variation=SpcChartSeries(
            statistic="s",
            values=(0.1, 0.12, 0.09, 0.11, 0.8),
            cl=(0.1,) * 5,
            ucl=(0.4,) * 5,
            lcl=(0.01,) * 5,
        ),
        subgroup_sizes=(5,) * 5,
        sigma_within=0.12,
    )
    stability = evaluate_study_stability(chart_set, enabled_rules=["beyond_limits"])
    capability = calculate_process_capability(
        avgs=list(chart_set.location.values),
        all_values=[9.8, 10.0, 10.2] * 5,
        r_cl=0.3,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=stability,
    )

    assert stability["location"]["stable"] is True
    assert stability["variation"]["stable"] is False
    assert stability["stable"] is False
    assert capability["cpk"] is None
