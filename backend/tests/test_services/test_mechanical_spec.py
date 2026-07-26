from backend.models import Vendor, VendorToleranceMain, VendorToleranceDetail
from backend.services.mechanical_spec import (
    MECH_ITEM_TO_TOLERANCE,
    lookup_lower_limits,
    compute_measurement_ng,
    resolve_material_by_spec,
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


def _add_main(db_session, vendor_id, material, spec):
    main = VendorToleranceMain(vendor_id=vendor_id, material=material, spec=spec)
    db_session.add(main)
    db_session.flush()
    return main


def test_resolve_material_returns_unique_exact_match(db_session):
    """規格精確相符且材質唯一時，直接回傳該材質。"""
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    _add_main(db_session, v.id, "6061-T851", "78*66")
    db_session.commit()

    # 來源 Excel 工作表名稱可能使用 X 分隔，需正規化後才相符
    result = resolve_material_by_spec("78X66", v.id)

    assert result["status"] == "resolved"
    assert result["material"] == "6061-T851"
    assert result["match"] == "exact"
    assert result["candidates"] == ["6061-T851"]


def test_resolve_material_reports_ambiguous_with_candidates(db_session):
    """同規格對應多個材質時不得擅自挑選，須回報候選供人工判斷。"""
    v = Vendor(name="加茂")
    db_session.add(v)
    db_session.flush()
    _add_main(db_session, v.id, "2014-T6", "28*3.4")
    _add_main(db_session, v.id, "6066-T6", "28*3.4")
    db_session.commit()

    result = resolve_material_by_spec("28*3.4", v.id)

    assert result["status"] == "ambiguous"
    assert result["material"] is None
    assert result["candidates"] == ["2014-T6", "6066-T6"]


def test_resolve_material_falls_back_to_two_segment_match(db_session):
    """精確規格查無時，才退到「前兩段相同」的相近比對。"""
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    _add_main(db_session, v.id, "6061-F", "64.5*2.3")
    db_session.commit()

    result = resolve_material_by_spec("64.5*2.3*380", v.id)

    assert result["status"] == "resolved"
    assert result["material"] == "6061-F"
    assert result["match"] == "fuzzy"


def test_resolve_material_prefers_exact_over_fuzzy_even_when_fuzzy_is_unique(db_session):
    """精確層級有唯一解時，不得因模糊層級另有資料而改判 ambiguous。"""
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    _add_main(db_session, v.id, "7050-F", "64.5*2.3")        # 僅前兩段相同
    _add_main(db_session, v.id, "6066-F", "64.5*2.3*380")    # 完全相同
    db_session.commit()

    result = resolve_material_by_spec("64.5*2.3*380", v.id)

    assert result["status"] == "resolved"
    assert result["material"] == "6066-F"
    assert result["match"] == "exact"


def test_resolve_material_is_scoped_to_vendor(db_session):
    """不同廠商同規格不得互相污染。"""
    first = Vendor(name="安泰")
    second = Vendor(name="宏達")
    db_session.add_all([first, second])
    db_session.flush()
    _add_main(db_session, first.id, "6061-T651", "36*25.2")
    _add_main(db_session, second.id, "7075-T6", "36*25.2")
    db_session.commit()

    result = resolve_material_by_spec("36*25.2", second.id)

    assert result["material"] == "7075-T6"


def test_resolve_material_not_found_when_spec_absent(db_session):
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    _add_main(db_session, v.id, "6061-T651", "36*25.2")
    db_session.commit()

    result = resolve_material_by_spec("66.7*56.85", v.id)

    assert result["status"] == "not_found"
    assert result["material"] is None
    assert result["candidates"] == []


def test_resolve_material_not_found_without_vendor(db_session):
    """未指定廠商時無從比對，一律回報查無。"""
    result = resolve_material_by_spec("36*25.2", None)

    assert result["status"] == "not_found"


def test_resolve_material_deduplicates_same_material_across_rows(db_session):
    """同材質在公差檔有多筆（不同項目）時仍屬唯一解，不得誤判 ambiguous。"""
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    _add_main(db_session, v.id, "6061-T651", "36*25.2")
    _add_main(db_session, v.id, "6061-t651", "36*25.2")
    db_session.commit()

    result = resolve_material_by_spec("36*25.2", v.id)

    assert result["status"] == "resolved"
    assert result["material"] == "6061-T651"


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
