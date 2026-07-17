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
