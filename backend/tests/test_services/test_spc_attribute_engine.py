"""p／np 屬性管制圖統計引擎測試。"""

from datetime import date

import pytest

from backend.services.spc_attribute_engine import (
    AttributeSubgroup,
    SpcChartNotApplicable,
    calculate_attribute_chart,
)


def test_p_chart_uses_weighted_center_and_point_specific_exact_limits():
    groups = (
        AttributeSubgroup("2026-07-01", date(2026, 7, 1), 50, 2, (1,)),
        AttributeSubgroup("2026-07-02", date(2026, 7, 2), 100, 8, (2,)),
    )

    result = calculate_attribute_chart(groups, "p")

    assert result["chart_type"] == "p"
    assert result["center"] == pytest.approx(10 / 150)
    assert result["values"] == pytest.approx([0.04, 0.08])
    assert result["ucl"][0] != result["ucl"][1]
    assert all(0 <= value <= 1 for value in result["lcl"] + result["ucl"])
    assert result["n"] == [50, 100]
    assert result["x"] == [2, 8]
    assert result["pearson_residuals"] == pytest.approx(
        [-0.755928946, 0.534522483]
    )
    assert result["sample_size_variation_warning"] is True


def test_np_rejects_variable_subgroup_size():
    with pytest.raises(SpcChartNotApplicable) as error:
        calculate_attribute_chart(
            (
                AttributeSubgroup("a", None, 50, 1, (1,)),
                AttributeSubgroup("b", None, 51, 1, (2,)),
            ),
            "np",
        )

    assert error.value.code == "NP_REQUIRES_FIXED_SUBGROUP_SIZE"


def test_zero_defect_baseline_is_not_turned_into_limits():
    with pytest.raises(SpcChartNotApplicable) as error:
        calculate_attribute_chart(
            (AttributeSubgroup("a", None, 50, 0, (1,)),), "p"
        )

    assert error.value.code == "ZERO_DEFECT_BASELINE"
