"""進階確效基準的容差必須與它自己的輸入容差相容。

分布轉換的 tail_quantiles 是由擬合參數（λ、mean、std、a、b、loc、scale…）
推導出來的。基準對那些參數各自給了容差，代表「參數在這個範圍內變動仍算通過」；
可是若分位數的容差比「參數在允許範圍內變動所造成的位移」還小，這道守門就自相
矛盾——參數只要落在自己被允許的邊緣，分位數就必然被判為漂移。

這正是 CI 上發生的事：boxcox.tail_quantiles[2] 的容差是 5e-08，但 λ 的容差
5e-08 傳遞過去就足以讓它移動 2e-05（418 倍）。守門看似嚴格，實際上只能靠運氣通過。

因此 tail_quantiles 的容差不是隨手放寬，而是由參數容差傳遞決定的下限。這支測試
把這個不變式釘住：任何人日後想把它調回「看起來比較嚴格」的數字，會在這裡失敗。
"""

import json
import math
from pathlib import Path

import pytest
from scipy import stats

EXPECTED_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "spc_advanced_expected_2026_2.json"
)
PROBABILITIES = (0.00135, 0.5, 0.99865)
# λ 的 loc 不參與分位數計算，納入會高估下限
IGNORED_PARAMS = {"boxcox": {"loc"}}


def _quantile(family: str, params: dict, probability: float) -> float:
    z = stats.norm.ppf(probability)
    if family == "boxcox":
        lam = params["lambda"]
        transformed = params["transformed_mean"] + z * params["transformed_std"]
        return (lam * transformed + 1) ** (1 / lam)
    if family == "johnson_su":
        return float(stats.johnsonsu.ppf(
            probability, params["a"], params["b"],
            loc=params["loc"], scale=params["scale"],
        ))
    if family == "johnson_sb":
        return float(stats.johnsonsb.ppf(
            probability, params["a"], params["b"],
            loc=params["loc"], scale=params["scale"],
        ))
    if family == "johnson_sl":
        return float(stats.lognorm.ppf(
            probability, params["shape"], loc=params["loc"], scale=params["scale"],
        ))
    raise AssertionError(f"未知的轉換族：{family}")


@pytest.fixture(scope="module")
def baseline() -> dict:
    with EXPECTED_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


FAMILIES = ("boxcox", "johnson_su", "johnson_sb", "johnson_sl")


@pytest.mark.parametrize("family", FAMILIES)
def test_quantile_model_reproduces_the_baseline(baseline, family):
    """先確認這裡的重算方式與產生基準的實作一致，否則下一支測試沒有意義。"""
    node = baseline["expected"]["transformations"][family]
    for probability, expected in zip(PROBABILITIES, node["tail_quantiles"]):
        assert _quantile(family, node["params"], probability) == pytest.approx(
            expected, abs=1e-9,
        )


@pytest.mark.parametrize("family", FAMILIES)
def test_tail_quantile_tolerance_covers_propagated_parameter_tolerance(baseline, family):
    """分位數容差不得小於「參數在自己容差內變動」造成的位移。"""
    node = baseline["expected"]["transformations"][family]
    tolerances = baseline["tolerances"]
    params = node["params"]
    ignored = IGNORED_PARAMS.get(family, set())

    for index, probability in enumerate(PROBABILITIES):
        propagated = 0.0
        for name in params:
            if name in ignored:
                continue
            parameter_tolerance = tolerances[
                f"transformations.{family}.params.{name}"
            ]["abs"]
            high = {**params, name: params[name] + parameter_tolerance}
            low = {**params, name: params[name] - parameter_tolerance}
            propagated += abs(
                _quantile(family, high, probability)
                - _quantile(family, low, probability)
            ) / 2

        entry = tolerances[f"transformations.{family}.tail_quantiles[{index}]"]
        allowed = entry["abs"] + entry["rel"] * abs(node["tail_quantiles"][index])
        assert allowed >= propagated, (
            f"{family}.tail_quantiles[{index}] 的容差 {allowed:.3e} 小於參數容差"
            f"傳遞後的下限 {propagated:.3e}；這道守門只能靠運氣通過"
        )
        # 同時避免無節制放寬：留 2 倍餘裕即足夠，超過 20 倍代表另有問題
        assert allowed <= 20 * propagated, (
            f"{family}.tail_quantiles[{index}] 的容差 {allowed:.3e} 遠超過下限"
            f" {propagated:.3e}，放寬得沒有根據"
        )


def test_propagation_bound_is_not_vacuous(baseline):
    """下限本身必須是有限正數，否則上面兩支測試等於沒斷言。"""
    node = baseline["expected"]["transformations"]["boxcox"]
    base = _quantile("boxcox", node["params"], 0.99865)
    shifted = _quantile(
        "boxcox",
        {**node["params"], "lambda": node["params"]["lambda"] + 5e-08},
        0.99865,
    )
    drift = abs(shifted - base)
    assert math.isfinite(drift) and drift > 0
