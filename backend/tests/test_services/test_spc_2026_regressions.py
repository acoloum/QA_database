"""已確認的 2026 SPC 差距之回歸測試。"""

from datetime import datetime, timedelta, timezone

from backend.services.spc_chart_engine import calculate_chart_set
from backend.services.spc_contracts import SpcSubgroup


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
