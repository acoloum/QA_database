# backend/tests/test_services/test_spc_golden.py
"""黃金資料集回歸測試 — §10.2 軟體確效：鎖定統計輸出防止未察覺的行為變更

注意：下方各測試斷言的數值是針對特定固定亂數種子（fixed seed）之合成資料集，
實際執行一次計算所得的結果，並非由公式在測試中重新推導而來（純粹「鎖值」）。
若未來計算邏輯有變動導致測試失敗，請先檢視 spc_analysis_service.py /
spc_stability.py / spc_distribution.py 等計算邏輯是否為預期中的變更，
確認無誤後再回頭更新此處的期望值；切勿在未理解失敗原因前就直接貼上新數值。
"""
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
    """兩側公差、非形狀欄位、stable=False → performance 路徑、常態分布模型"""
    avgs, ranges, all_values = _golden_dataset()
    cl = calculate_control_limits(avgs, ranges, [5] * 30)
    st = evaluate_stability(avgs, cl["x_cl"], cl["x_ucl"], cl["x_lcl"])
    pc = calculate_process_capability(
        avgs, all_values, cl["r_cl"], cl["d2"],
        {"USL": 11, "LSL": 9}, stability=st, characteristic_class="主要",
        time_model={"model": "A1", "confirmed": True})

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


def test_golden_dataset_stable_uses_capability_path():
    """stable=True → 應回報 Cp/Cpk（能力），而非僅 Pp/Ppk（績效）"""
    rng = np.random.default_rng(0)
    subs = [sorted(rng.normal(10, 0.3, 5).tolist()) for _ in range(25)]
    avgs = [float(np.mean(s)) for s in subs]
    ranges = [float(max(s) - min(s)) for s in subs]
    all_values = [v for s in subs for v in s]

    cl = calculate_control_limits(avgs, ranges, [5] * 25)
    st = evaluate_stability(avgs, cl["x_cl"], cl["x_ucl"], cl["x_lcl"])
    pc = calculate_process_capability(
        avgs, all_values, cl["r_cl"], cl["d2"],
        {"USL": 11, "LSL": 9}, stability=st, characteristic_class="主要",
        time_model={"model": "A1", "confirmed": True})

    assert cl["x_cl"] == pytest.approx(10.023738880249919, rel=1e-6)
    assert cl["x_ucl"] == pytest.approx(10.40734957551807, rel=1e-6)
    assert cl["r_cl"] == pytest.approx(0.664836560256762, rel=1e-6)
    assert st["stable"] is True
    assert pc["applicable"] == "capability"
    # 穩定時 Cp/Cpk 應有值，且與 Pp/Ppk 數值相同（§6.2：公式相同，僅命名依穩定性而異）
    assert pc["cpk"] == pytest.approx(1.137, abs=1e-3)
    assert pc["cp"] == pytest.approx(1.165, abs=1e-3)
    assert pc["cpk"] == pytest.approx(pc["ppk"], abs=1e-9)
    assert pc["cp"] == pytest.approx(pc["pp"], abs=1e-9)
    assert pc["ppk"] == pytest.approx(1.137, abs=1e-3)
    assert pc["pp"] == pytest.approx(1.165, abs=1e-3)
    assert pc["cwk"] == pytest.approx(1.139, abs=1e-3)
    assert pc["ppm"]["total"] == pytest.approx(496.5, abs=0.1)
    assert pc["targets"]["pk_target"] == 1.33


def test_golden_dataset_one_sided_upper_only_computes_upper_side():
    """單側公差（僅 USL，one_sided='upper'）：只計算上側 ppu/cpu，下側維持 None"""
    avgs, ranges, all_values = _golden_dataset()
    cl = calculate_control_limits(avgs, ranges, [5] * 30)
    st = evaluate_stability(avgs, cl["x_cl"], cl["x_ucl"], cl["x_lcl"])
    pc = calculate_process_capability(
        avgs, all_values, cl["r_cl"], cl["d2"],
        {"USL": 11, "one_sided": "upper"}, stability=st, characteristic_class="次要")

    assert pc["one_sided"] == "upper"
    assert pc["applicable"] == "performance"
    # 單側規格：pp（雙側指數）與 ppl（下側）不計算，只計算 ppu/ppk（上側）
    assert pc["pp"] is None
    assert pc["ppl"] is None
    assert pc["cw"] is None
    assert pc["ppu"] == pytest.approx(1.027, abs=1e-3)
    assert pc["ppk"] == pytest.approx(1.027, abs=1e-3)
    assert pc["ppu"] == pytest.approx(pc["ppk"], abs=1e-9)
    assert pc["cwk"] == pytest.approx(1.144, abs=1e-3)
    assert pc["ppm"]["lower"] == 0.0
    assert pc["ppm"]["total"] == pytest.approx(1026.9, abs=0.1)
    assert pc["targets"]["pk_target"] == 1.00
