from backend.models import Vendor, VendorToleranceMain, VendorToleranceDetail
from backend.services.mechanical_spec import (
    MECH_ITEM_TO_TOLERANCE,
    lookup_lower_limits,
    compute_measurement_ng,
)


def test_mapping_covers_four_judged_items():
    assert MECH_ITEM_TO_TOLERANCE == {
        "硬度": "洛氏硬度",
        "抗拉強度": "抗拉強度",
        "降伏強度": "降伏強度",
        "伸長率": "伸長率",
    }


def _seed_spec(db_session):
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2")
    db_session.add(main)
    db_session.flush()
    for item, low in [("洛氏硬度", 60), ("抗拉強度", 380), ("降伏強度", 350), ("伸長率", 8)]:
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item=item, tolerance_min=low, unit=""
        ))
    db_session.commit()
    return v.id


def test_lookup_lower_limits_matches_material_and_size(db_session):
    _seed_spec(db_session)
    limits = lookup_lower_limits("6061-T651", "36x25.2")
    # 以機械性質項目名回傳（非廠商公差項目名）
    assert float(limits["硬度"]) == 60
    assert float(limits["抗拉強度"]) == 380
    assert float(limits["降伏強度"]) == 350
    assert float(limits["伸長率"]) == 8
    assert "EC值" not in limits


def test_lookup_returns_empty_when_no_spec(db_session):
    limits = lookup_lower_limits("6061-T651", "99x99")
    assert limits == {}


def test_compute_measurement_ng_lower_bound_only():
    # 值 < 下限 → NG
    assert compute_measurement_ng(59, 60) is True
    # 值 == 下限 → 合格（單邊，含界限）
    assert compute_measurement_ng(60, 60) is False
    # 值 > 下限 → 合格（無上限）
    assert compute_measurement_ng(500, 60) is False
    # 無下限或無值 → 不判定
    assert compute_measurement_ng(50, None) is False
    assert compute_measurement_ng(None, 60) is False
