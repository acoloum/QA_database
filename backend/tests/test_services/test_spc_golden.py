# backend/tests/test_services/test_spc_golden.py
"""黃金資料集回歸測試 — §10.2 軟體確效：鎖定統計輸出防止未察覺的行為變更"""
import numpy as np
import pytest

from backend.services.spc_analysis_service import (
    calculate_control_limits, calculate_process_capability)
from backend.services.spc_stability import evaluate_stability


def _golden_dataset():
    rng = np.random.default_rng(2026)
    subs = [sorted(rng.normal(10, 0.3, 5).tolist()) for _ in range(30)]
    avgs = [float(np.mean(s)) for s in subs]
    ranges = [float(max(s) - min(s)) for s in subs]
    all_values = [v for s in subs for v in s]
    return avgs, ranges, all_values


def test_golden_dataset_outputs_are_stable():
    avgs, ranges, all_values = _golden_dataset()
    cl = calculate_control_limits(avgs, ranges, [5] * 30)
    st = evaluate_stability(avgs, cl["x_cl"], cl["x_ucl"], cl["x_lcl"])
    pc = calculate_process_capability(
        avgs, all_values, cl["r_cl"], cl["d2"],
        {"USL": 11, "LSL": 9}, stability=st, characteristic_class="主要")

    assert cl["x_cl"] == pytest.approx(10.018411004048945, rel=1e-6)
    assert cl["x_ucl"] == pytest.approx(10.401818475000116, rel=1e-6)
    assert cl["r_cl"] == pytest.approx(0.6644843517351339, rel=1e-6)
    assert st["stable"] is False
    assert pc["applicable"] == "performance"
    assert pc["ppk"] == pytest.approx(1.027, abs=1e-3)
    assert pc["pp"] == pytest.approx(1.048, abs=1e-3)
    assert pc["cwk"] == pytest.approx(1.144, abs=1e-3)
    assert pc["ppm"]["total"] == pytest.approx(1698.4, abs=0.1)
    assert pc["targets"]["pk_target"] == 1.33
