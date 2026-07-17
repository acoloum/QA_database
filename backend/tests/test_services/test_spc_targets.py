from backend.services.spc_targets import resolve_targets


def test_critical_class_full_sample_uses_base_targets():
    t = resolve_targets("關鍵", n_values=200)
    assert t["class"] == "關鍵"
    assert t["p_target"] == 1.67
    assert t["pk_target"] == 1.67
    assert t["adjusted"] is False
    assert t["insufficient_sample"] is False


def test_major_class_small_sample_adjusts_upward():
    # 表 8-5，95% 信賴水準，N=100，基準 1.33 → 1.35
    t = resolve_targets("主要", n_values=100)
    assert t["pk_target"] > 1.33
    assert t["adjusted"] is True


def test_sample_between_rows_uses_lower_row():
    # N=105 介於 100 與 110 → 保守採 100 列
    t100 = resolve_targets("主要", n_values=100)
    t105 = resolve_targets("主要", n_values=105)
    assert t105["pk_target"] == t100["pk_target"]


def test_below_75_flags_insufficient():
    t = resolve_targets("次要", n_values=40)
    assert t["insufficient_sample"] is True
    assert t["pk_target"] >= 1.00


def test_unknown_class_falls_back_to_other():
    t = resolve_targets(None, n_values=200)
    assert t["class"] == "其他"
    assert t["pk_target"] == 1.00


def test_non_default_confidence_level_uses_its_own_table():
    # 表 8-5，99.99% 信賴水準，N=100，主要基準1.33 → 1.38（非95%的1.35）
    t = resolve_targets("主要", n_values=100, confidence="99.99%")
    assert t["confidence"] == "99.99%"
    assert t["pk_target"] == 1.38


def test_boundary_n125_vs_n124_differs():
    # 表 8-5，99.99%，主要：N=125 用基準值1.33；N=124 落入120列 → 1.34
    t125 = resolve_targets("主要", n_values=125, confidence="99.99%")
    t124 = resolve_targets("主要", n_values=124, confidence="99.99%")
    assert t125["pk_target"] == 1.33
    assert t124["pk_target"] == 1.34


def test_unsupported_confidence_falls_back_to_95_percent():
    t = resolve_targets("主要", n_values=100, confidence="90%")
    t95 = resolve_targets("主要", n_values=100, confidence="95%")
    assert t["confidence"] == "95%"
    assert t["pk_target"] == t95["pk_target"]
