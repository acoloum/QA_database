import numpy as np
import pytest
from scipy import stats as scipy_stats

from backend.services.spc_distribution import assess_distribution, dist_quantiles, tail_ppm


def test_normal_data_detected_as_normal():
    rng = np.random.default_rng(42)
    values = rng.normal(10, 0.5, 300).tolist()
    d = assess_distribution(values)
    assert d["model"] == "normal"
    assert d["accepted"] is True
    assert d["normal_ok"] is True


def test_shape_field_uses_folded_normal():
    rng = np.random.default_rng(42)
    values = np.abs(rng.normal(0, 0.02, 300)).tolist()
    d = assess_distribution(values, field="真圓度")
    assert d["model"] == "folded_normal"
    assert d["accepted"] is True


def test_quantiles_are_ordered():
    rng = np.random.default_rng(1)
    values = rng.normal(10, 0.5, 300).tolist()
    d = assess_distribution(values)
    q_lo, q_mid, q_hi = dist_quantiles(d)
    assert q_lo < q_mid < q_hi
    # 常態下位數應接近平均
    assert q_mid == pytest.approx(10, abs=0.2)


def test_lognormal_data_detected_as_lognormal():
    rng = np.random.default_rng(3)
    values = rng.lognormal(1.0, 0.8, 500).tolist()
    d = assess_distribution(values)
    assert d["model"] == "lognormal"
    assert d["accepted"] is True


def test_rejected_normal_without_accepted_alternative_is_unconfirmed():
    values = (
        [-5 + (i % 5) * 0.02 for i in range(50)]
        + [5 + (i % 5) * 0.02 for i in range(50)]
    )

    d = assess_distribution(values)

    assert d["accepted"] is False
    assert d["model"] is None
    assert d["reason_code"] == "DISTRIBUTION_UNCONFIRMED"
    assert d["candidates"][0]["reason_code"] == "GOODNESS_OF_FIT_REJECTED"
    assert dist_quantiles(d) == (None, None, None)
    assert tail_ppm(d, usl=6, lsl=-6) == {
        "upper": None,
        "lower": None,
        "total": None,
    }


def test_small_sample_does_not_fall_back_to_normal():
    d = assess_distribution([9.9, 10.0, 10.1, 10.0, 9.8, 10.2])

    assert d["accepted"] is False
    assert d["model"] is None
    assert d["reason_code"] == "INSUFFICIENT_DISTRIBUTION_DATA"


def test_tail_ppm_reflects_spec_distance():
    rng = np.random.default_rng(7)
    values = rng.normal(10, 0.5, 500).tolist()
    d = assess_distribution(values)
    near = tail_ppm(d, usl=10.5, lsl=9.5)
    far = tail_ppm(d, usl=13, lsl=7)
    assert near["total"] > far["total"]


def test_original_accepted_distribution_suppresses_transformation_recommendation():
    rng = np.random.default_rng(42)
    result = assess_distribution(rng.normal(10, 0.5, 300).tolist())

    assert result["accepted"] is True
    assert len(result["transformation_candidates"]) == 4
    assert result["transformation_recommendation"] is None
    assert result["transformation_reason_code"] == "ORIGINAL_DISTRIBUTION_ACCEPTED"


def test_unconfirmed_distribution_recommends_best_accepted_transformation():
    probabilities = np.linspace(0.01, 0.99, 99)
    values = scipy_stats.johnsonsu.ppf(
        probabilities, 1.2, 1.8, loc=-2.0, scale=1.5
    ).tolist()

    result = assess_distribution(values)
    accepted = [
        item for item in result["transformation_candidates"] if item["accepted"]
    ]
    if result["accepted"]:
        assert result["transformation_recommendation"] is None
    else:
        assert accepted
        assert result["transformation_recommendation"]["model"] == accepted[0]["model"]
