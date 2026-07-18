"""ISO 22514-2 時間相依分布模型候選判定測試。"""

from backend.services.spc_contracts import SpcChartSeries, SpcChartSet
from backend.services.spc_time_model import classify_time_model


def _chart_set() -> SpcChartSet:
    return SpcChartSet(
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
            values=(0.1, 0.12, 0.09, 0.11, 0.1),
            cl=(0.1,) * 5,
            ucl=(0.4,) * 5,
            lcl=(0.01,) * 5,
        ),
        subgroup_sizes=(5,) * 5,
        sigma_within=0.12,
    )


def _stability(location: bool | None, variation: bool | None, *, rules=()):
    evaluated = location is not None and variation is not None
    return {
        "evaluated": evaluated,
        "stable": location is True and variation is True if evaluated else None,
        "location": {
            "evaluated": location is not None,
            "stable": location,
            "violations": [{"rule": rule} for rule in rules],
        },
        "variation": {
            "evaluated": variation is not None,
            "stable": variation,
            "violations": [],
        },
    }


def _distribution(model: str | None, *, accepted: bool = True):
    return {
        "model": model,
        "accepted": accepted,
        "unimodal": accepted,
        "reason_code": None if accepted else "DISTRIBUTION_UNCONFIRMED",
    }


def test_stable_normal_is_a1_candidate_but_not_auto_confirmed():
    result = classify_time_model(
        _chart_set(), _stability(True, True), _distribution("normal")
    )

    assert result["candidate"] == "A1"
    assert result["confirmed"] is False
    assert result["statistically_controlled"] is True


def test_stable_unimodal_non_normal_is_a2_candidate():
    result = classify_time_model(
        _chart_set(), _stability(True, True), _distribution("lognormal")
    )

    assert result["candidate"] == "A2"
    assert result["confirmed"] is False


def test_stable_location_with_unstable_variation_is_b_candidate():
    result = classify_time_model(
        _chart_set(), _stability(True, False), _distribution("normal")
    )

    assert result["candidate"] == "B"
    assert result["statistically_controlled"] is False


def test_unstable_location_trend_with_stable_variation_is_c3_candidate():
    result = classify_time_model(
        _chart_set(),
        _stability(False, True, rules=("trend_6",)),
        _distribution("normal"),
    )

    assert result["candidate"] == "C3"
    assert result["candidate_options"] == ["C1", "C2", "C3", "C4"]
    assert "trend_6" in result["evidence"]["location_rules"]


def test_both_location_and_variation_unstable_is_d_candidate():
    result = classify_time_model(
        _chart_set(), _stability(False, False), _distribution("normal")
    )

    assert result["candidate"] == "D"


def test_insufficient_evidence_keeps_time_model_unconfirmed():
    result = classify_time_model(
        _chart_set(), _stability(None, None), _distribution(None, accepted=False)
    )

    assert result["candidate"] is None
    assert result["confirmed"] is False
    assert result["reason_code"] == "TIME_MODEL_UNCONFIRMED"
