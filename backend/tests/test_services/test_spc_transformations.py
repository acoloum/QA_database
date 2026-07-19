import numpy as np
import pytest
from scipy import stats as scipy_stats

from backend.services.spc_transformations import (
    evaluate_transformations,
    inverse_values,
    transform_values,
)


NORMAL_PROBABILITIES = np.linspace(0.01, 0.99, 99)
NORMAL_SCORES = scipy_stats.norm.ppf(NORMAL_PROBABILITIES)
BOXCOX_DATA = np.power(0.25 * NORMAL_SCORES + 2.0, 4.0)
JOHNSON_SU_DATA = scipy_stats.johnsonsu.ppf(
    NORMAL_PROBABILITIES, 1.2, 1.8, loc=4.0, scale=1.5
)
JOHNSON_SB_DATA = scipy_stats.johnsonsb.ppf(
    NORMAL_PROBABILITIES, 1.0, 1.5, loc=2.0, scale=8.0
)
JOHNSON_SL_DATA = scipy_stats.lognorm.ppf(
    NORMAL_PROBABILITIES, 0.6, loc=0.0, scale=np.exp(1.0)
)


@pytest.mark.parametrize(
    "dataset,expected_model",
    [
        (BOXCOX_DATA, "boxcox"),
        (JOHNSON_SU_DATA, "johnson_su"),
        (JOHNSON_SB_DATA, "johnson_sb"),
        (JOHNSON_SL_DATA, "johnson_sl"),
    ],
)
def test_transformation_candidate_and_roundtrip(dataset, expected_model):
    result = evaluate_transformations(dataset)
    candidate = next(
        item for item in result["candidates"] if item["model"] == expected_model
    )

    assert candidate["accepted"] is True
    assert candidate["ad_p_value"] >= 0.05
    assert candidate["monotonic"] is True
    assert candidate["roundtrip_relative_error"] <= 1e-9
    assert all(np.isfinite(candidate["tail_quantiles"]))
    restored = inverse_values(transform_values(dataset, candidate), candidate)
    assert restored == pytest.approx(dataset, rel=1e-9, abs=1e-9)


def test_candidates_are_ranked_deterministically_by_p_then_statistic():
    first = evaluate_transformations(JOHNSON_SL_DATA)
    second = evaluate_transformations(JOHNSON_SL_DATA.tolist())

    assert first == second
    accepted = [item for item in first["candidates"] if item["accepted"]]
    ranking = [(-item["ad_p_value"], item["ad_statistic"], item["model"]) for item in accepted]
    assert ranking == sorted(ranking)
    assert [item["rank"] for item in accepted] == list(range(1, len(accepted) + 1))


def test_boxcox_rejects_nonpositive_values_without_hiding_other_candidates():
    result = evaluate_transformations([-1.0, 0.0, 1.0] * 10)
    boxcox = next(item for item in result["candidates"] if item["model"] == "boxcox")

    assert boxcox["accepted"] is False
    assert boxcox["reason_code"] == "BOXCOX_POSITIVE_VALUES_REQUIRED"
    assert {item["model"] for item in result["candidates"]} == {
        "boxcox", "johnson_su", "johnson_sb", "johnson_sl",
    }


def test_transform_supports_scalar_and_rejects_invalid_decisions_or_values():
    candidate = next(
        item for item in evaluate_transformations(JOHNSON_SU_DATA)["candidates"]
        if item["model"] == "johnson_su"
    )
    transformed = transform_values(float(JOHNSON_SU_DATA[20]), candidate)

    assert isinstance(transformed, float)
    assert inverse_values(transformed, candidate) == pytest.approx(JOHNSON_SU_DATA[20])
    with pytest.raises(ValueError, match="不受支援"):
        transform_values([1.0], {"model": "unknown", "params": {}})
    with pytest.raises(ValueError, match="有限值"):
        transform_values([float("nan")], candidate)
    with pytest.raises(ValueError, match="參數"):
        inverse_values([0.0], {"model": "johnson_su", "params": {}})


def test_small_sample_returns_auditable_rejections():
    result = evaluate_transformations(list(range(20)))

    assert result["available"] is False
    assert result["reason_code"] == "TRANSFORMATION_SAMPLE_INSUFFICIENT"
    assert result["minimum_sample_size"] == 25
    assert all(not item["accepted"] for item in result["candidates"])


def test_no_candidate_passes_returns_unconfirmed_without_recommendation():
    values = (
        [-5 + (index % 5) * 0.02 for index in range(50)]
        + [5 + (index % 5) * 0.02 for index in range(50)]
    )

    result = evaluate_transformations(values)

    assert result["reason_code"] == "TRANSFORMATION_UNCONFIRMED"
    assert result["recommended"] is None
    assert all(candidate["accepted"] is False for candidate in result["candidates"])
