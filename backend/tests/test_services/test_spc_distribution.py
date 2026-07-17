import numpy as np
import pytest

from backend.services.spc_distribution import assess_distribution, dist_quantiles, tail_ppm


def test_normal_data_detected_as_normal():
    rng = np.random.default_rng(42)
    values = rng.normal(10, 0.5, 300).tolist()
    d = assess_distribution(values)
    assert d["model"] == "normal"
    assert d["normal_ok"] is True


def test_shape_field_uses_folded_normal():
    rng = np.random.default_rng(42)
    values = np.abs(rng.normal(0, 0.02, 300)).tolist()
    d = assess_distribution(values, field="真圓度")
    assert d["model"] == "folded_normal"


def test_quantiles_are_ordered():
    rng = np.random.default_rng(1)
    values = rng.normal(10, 0.5, 300).tolist()
    d = assess_distribution(values)
    q_lo, q_mid, q_hi = dist_quantiles(d)
    assert q_lo < q_mid < q_hi
    # 常態下位數應接近平均
    assert q_mid == pytest.approx(10, abs=0.2)


def test_tail_ppm_reflects_spec_distance():
    rng = np.random.default_rng(7)
    values = rng.normal(10, 0.5, 500).tolist()
    d = assess_distribution(values)
    near = tail_ppm(d, usl=10.5, lsl=9.5)
    far = tail_ppm(d, usl=13, lsl=7)
    assert near["total"] > far["total"]
