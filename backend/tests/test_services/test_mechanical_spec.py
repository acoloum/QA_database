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
    for item, low in [
        ("洛氏硬度", 60), ("抗拉強度", 380), ("降伏強度", 350), ("伸長率", 8),
        ("EC值", 55),
    ]:
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item=item, tolerance_min=low, unit=""
        ))
    db_session.commit()
    return v.id


def test_lookup_lower_limits_matches_material_and_size(db_session):
    vendor_id = _seed_spec(db_session)
    limits = lookup_lower_limits("6061-T651", "36x25.2", vendor_id=vendor_id)
    # 以機械性質項目名回傳（非廠商公差項目名）
    assert float(limits["硬度"]) == 60
    assert float(limits["抗拉強度"]) == 380
    assert float(limits["降伏強度"]) == 350
    assert float(limits["伸長率"]) == 8
    assert "EC值" not in limits


def test_lookup_prefers_exact_spec_match_over_fuzzy(db_session):
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()

    # 先插入「僅前兩段相同」的模糊匹配資料（規格不同）
    fuzzy_main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2*100")
    db_session.add(fuzzy_main)
    db_session.flush()
    db_session.add(VendorToleranceDetail(
        main_id=fuzzy_main.id, item="洛氏硬度", tolerance_min=999, unit=""
    ))

    # 後插入「完全相同」規格的資料
    exact_main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2")
    db_session.add(exact_main)
    db_session.flush()
    db_session.add(VendorToleranceDetail(
        main_id=exact_main.id, item="洛氏硬度", tolerance_min=60, unit=""
    ))
    db_session.commit()

    limits = lookup_lower_limits("6061-T651", "36x25.2", vendor_id=v.id)
    # 應採用精確匹配（exact_main）的下限，而非先插入之模糊匹配（fuzzy_main）
    assert float(limits["硬度"]) == 60


def test_lookup_limits_are_scoped_to_requested_vendor(db_session):
    """同材質尺寸的不同廠商必須只讀取指定廠商的下限。"""
    first_vendor = Vendor(name="安泰")
    second_vendor = Vendor(name="宏達")
    db_session.add_all([first_vendor, second_vendor])
    db_session.flush()

    for vendor, lower_limit in [(first_vendor, 60), (second_vendor, 75)]:
        main = VendorToleranceMain(
            vendor_id=vendor.id, material="6061-T651", spec="36*25.2"
        )
        db_session.add(main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item="洛氏硬度", tolerance_min=lower_limit, unit=""
        ))
    db_session.commit()

    limits = lookup_lower_limits("6061-T651", "36x25.2", vendor_id=second_vendor.id)

    assert float(limits["硬度"]) == 75


def test_lookup_returns_empty_when_no_spec(db_session):
    limits = lookup_lower_limits("6061-T651", "99x99")
    assert limits == {}


def test_lookup_without_vendor_never_crosses_vendor_boundary(db_session):
    _seed_spec(db_session)
    assert lookup_lower_limits("6061-T651", "36x25.2") == {}


def test_lookup_prefers_exact_material_and_normalizes_spec_whitespace(db_session):
    vendor = Vendor(name="安泰")
    db_session.add(vendor)
    db_session.flush()
    for material, spec, lower in [
        ("6061", "36 * 25.2", 99),
        ("6061-T651", "36*25.2", 60),
    ]:
        main = VendorToleranceMain(vendor_id=vendor.id, material=material, spec=spec)
        db_session.add(main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item="洛氏硬度", tolerance_min=lower, unit=""
        ))
    db_session.commit()

    limits = lookup_lower_limits(
        " 6061-T651 ", " 36 x 25.2 ", vendor_id=vendor.id
    )

    assert float(limits["硬度"]) == 60


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
