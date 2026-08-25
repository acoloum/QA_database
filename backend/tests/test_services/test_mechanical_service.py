from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.models import (
    MechanicalMeasurement,
    MechanicalTest,
    User,
    Vendor,
    VendorToleranceDetail,
    VendorToleranceMain,
)
from backend.services.mechanical_service import (
    MechanicalService,
    MechanicalValidationError,
)


def _seed_spec(db_session):
    v = Vendor(name="安泰")
    db_session.add(v); db_session.flush()
    main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2")
    db_session.add(main); db_session.flush()
    db_session.add(VendorToleranceDetail(main_id=main.id, item="洛氏硬度", tolerance_min=60, unit=""))
    db_session.commit()
    return v.id


def _payload():
    return {
        "產品尺寸": "36x25.2",
        "材質": "6061-T651",
        "測試日期": "2026-01-20",
        "T4溫度時間": "530/40MIN",
        "T6溫度時間": "175/6HR",
        "extrusion_numbers": [
            {"序號": 1, "編號": "010761 D35"},
        ],
        "t4_furnace_numbers": [
            {"序號": 1, "編號": "011313T42"},
            {"序號": 2, "編號": "011314T42"},
        ],
        "measurements": [
            {"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 59},
            {"量測項目": "硬度", "測量位置": "爐頂", "取樣序": 1, "量測值": 73},
        ],
    }


def _required_measurements(value=70):
    return [
        {"量測項目": item, "測量位置": location, "取樣序": 1, "量測值": value}
        for item in ("硬度", "抗拉強度", "降伏強度", "伸長率")
        for location in ("爐門", "爐頂")
    ]


def _replace_trace_numbers_with_legacy(payload, batches):
    payload.pop("extrusion_numbers")
    payload.pop("t4_furnace_numbers")
    payload["batches"] = batches


def test_create_computes_ng_from_spec(db_session):
    vendor_id = _seed_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    new_id = MechanicalService.create(payload, user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row is not None
    # 爐門 59 < 下限 60 → 該明細 NG，主檔 NG
    assert row.is_ng is True
    ng_items = [(m.location, m.is_ng) for m in row.measurements if m.item == "硬度"]
    assert ("爐門", True) in ng_items
    assert ("爐頂", False) in ng_items


def test_create_without_spec_is_not_ng(db_session):
    # 無規格 → 不判定
    new_id = MechanicalService.create(_payload(), user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row.is_ng is False
    assert all(m.is_ng is False for m in row.measurements)


def test_create_accepts_one_extrusion_and_two_t4_furnace_numbers(
    app, db_session
):
    payload = _payload()
    test_id = MechanicalService.create(payload, user_id=None)

    detail = MechanicalService.get_detail(test_id)
    assert [row["編號"] for row in detail["extrusion_numbers"]] == [
        "010761 D35"
    ]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "011313T42",
        "011314T42",
    ]


def test_detail_returns_new_lists_and_unpaired_legacy_rows(app, db_session):
    test_id = MechanicalService.create(_payload(), user_id=None)

    detail = MechanicalService.get_detail(test_id)

    assert [row["編號"] for row in detail["extrusion_numbers"]] == [
        "010761 D35"
    ]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "011313T42",
        "011314T42",
    ]
    assert detail["batches"] == [
        {
            "序號": 1,
            "擠製編號": "010761 D35",
            "爐具編號": None,
        },
        {
            "序號": 2,
            "擠製編號": None,
            "爐具編號": "011313T42",
        },
        {
            "序號": 3,
            "擠製編號": None,
            "爐具編號": "011314T42",
        },
    ]


def test_list_has_independent_trace_summaries(app, db_session):
    MechanicalService.create(_payload(), user_id=None)

    listed = MechanicalService.get_list({})["data"][0]

    assert listed["擠製編號"] == "010761 D35"
    assert listed["T4爐號"] == "011313T42、011314T42"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"extrusion_numbers": {}}),
        lambda payload: payload.update({"t4_furnace_numbers": ["bad"]}),
        lambda payload: payload.update(
            {"extrusion_numbers": [{"序號": 0, "編號": "E1"}]}
        ),
        lambda payload: payload.update(
            {"t4_furnace_numbers": [{"序號": 2, "編號": "T4-1"}]}
        ),
        lambda payload: payload.update(
            {
                "extrusion_numbers": [
                    {"序號": 1, "編號": " E1 "},
                    {"序號": 2, "編號": "E1"},
                ]
            }
        ),
        lambda payload: payload.update(
            {"t4_furnace_numbers": [{"序號": 1, "編號": " "}]}
        ),
        lambda payload: payload.update(
            {"extrusion_numbers": [{"序號": 1, "編號": "x" * 101}]}
        ),
    ],
)
def test_new_trace_number_payload_rejects_invalid_values(
    app, db_session, mutate
):
    payload = _payload()
    mutate(payload)
    with pytest.raises(MechanicalValidationError):
        MechanicalService.create(payload, user_id=None)


def test_new_and_legacy_trace_payload_cannot_be_mixed(app, db_session):
    payload = _payload()
    payload["batches"] = []
    with pytest.raises(
        MechanicalValidationError,
        match="不得同時提供新版追溯編號與 batches",
    ):
        MechanicalService.create(payload, user_id=None)


@pytest.mark.parametrize(
    "missing_field",
    ["extrusion_numbers", "t4_furnace_numbers"],
)
def test_new_trace_payload_requires_both_fields(
    app, db_session, missing_field
):
    payload = _payload()
    payload.pop(missing_field)

    with pytest.raises(
        MechanicalValidationError,
        match="新版追溯編號兩個欄位都必須提供",
    ):
        MechanicalService.create(payload, user_id=None)


def test_trace_payload_requires_new_fields_or_legacy_batches(
    app, db_session
):
    payload = _payload()
    payload.pop("extrusion_numbers")
    payload.pop("t4_furnace_numbers")

    with pytest.raises(
        MechanicalValidationError,
        match="必須提供 extrusion_numbers、t4_furnace_numbers 或 batches",
    ):
        MechanicalService.create(payload, user_id=None)


def test_trace_numbers_preserve_case_distinct_values(app, db_session):
    payload = _payload()
    payload["extrusion_numbers"] = [
        {"序號": 1, "編號": "E001"},
        {"序號": 2, "編號": "e001"},
    ]

    test_id = MechanicalService.create(payload, user_id=None)
    detail = MechanicalService.get_detail(test_id)

    assert [
        (row["序號"], row["編號"])
        for row in detail["extrusion_numbers"]
    ] == [(1, "E001"), (2, "e001")]


def test_legacy_batches_split_trim_deduplicate_and_resequence(
    app, db_session
):
    payload = _payload()
    payload.pop("extrusion_numbers")
    payload.pop("t4_furnace_numbers")
    payload["batches"] = [
        {"序號": 2, "擠製編號": " E1 ", "爐具編號": "T4-02"},
        {"序號": 1, "擠製編號": "E1", "爐具編號": "T4-01"},
    ]

    test_id = MechanicalService.create(payload, user_id=None)
    detail = MechanicalService.get_detail(test_id)
    assert [
        (row["序號"], row["編號"])
        for row in detail["extrusion_numbers"]
    ] == [(1, "E1")]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "T4-01",
        "T4-02",
    ]


def test_list_filters_by_size(db_session):
    MechanicalService.create(_payload(), user_id=None)
    res = MechanicalService.get_list({"product_size": "36"})
    assert res["total"] == 1
    assert res["data"][0]["產品尺寸"] == "36x25.2"
    res2 = MechanicalService.get_list({"product_size": "99"})
    assert res2["total"] == 0


def test_list_filters_by_id(db_session):
    """依 ID 精確定位單筆（供稽核清單逐筆調閱）。"""
    new_id = MechanicalService.create(_payload(), user_id=None)

    res = MechanicalService.get_list({"id": str(new_id)})
    assert res["total"] == 1
    assert res["data"][0]["識別碼"] == new_id

    assert MechanicalService.get_list({"id": str(new_id + 999)})["total"] == 0


def test_list_id_filter_ignores_blank_and_rejects_non_numeric(db_session):
    """空白視為未篩選；非數字不得拋錯，回報查無即可。"""
    MechanicalService.create(_payload(), user_id=None)

    assert MechanicalService.get_list({"id": "  "})["total"] == 1
    assert MechanicalService.get_list({"id": "abc"})["total"] == 0


def test_update_recomputes_ng(db_session):
    vendor_id = _seed_spec(db_session)
    initial = _payload()
    initial["廠商ID"] = vendor_id
    new_id = MechanicalService.create(initial, user_id=None)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"][0]["量測值"] = 70  # 爐門改為 70 ≥ 60 → 不再 NG
    MechanicalService.update(new_id, payload, user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row.is_ng is False


def test_update_replaces_independent_trace_numbers(db_session):
    test_id = MechanicalService.create(_payload(), user_id=None)
    payload = _payload()
    payload["extrusion_numbers"] = [
        {"序號": 1, "編號": "E2"},
        {"序號": 2, "編號": "E3"},
    ]
    payload["t4_furnace_numbers"] = [
        {"序號": 1, "編號": "T4-99"},
    ]

    MechanicalService.update(test_id, payload, user_id=None)

    detail = MechanicalService.get_detail(test_id)
    assert [
        (row["序號"], row["編號"])
        for row in detail["extrusion_numbers"]
    ] == [(1, "E2"), (2, "E3")]
    assert [
        (row["序號"], row["編號"])
        for row in detail["t4_furnace_numbers"]
    ] == [(1, "T4-99")]


def test_update_twice_with_same_measurement_keys_does_not_raise(db_session):
    """量測明細的 (量測項目, 測量位置, 取樣序) 鍵值不變、僅量測值變動時，
    連續更新兩次應能正確覆蓋量測值（功能面驗證：相同鍵值、值不同，重複更新皆正確）。

    注意：本測試「不能」也「沒有」鎖定 _apply_measurements／
    _apply_trace_numbers 的
    flush() 修正所要防範的那個 bug——該 IntegrityError 只在 PostgreSQL
    （不可延遲的唯一鍵，逐語句檢查）才會於 clear() 後、重新 append 前的同一次
    flush 中因排序不定而觸發；測試在 SQLite 記憶體資料庫上執行（見
    backend/tests/conftest.py），並不會重現此排序問題，因此拿掉 flush() 這
    支測試仍會通過。對正式環境該 bug 的實際防護，來自原始碼中確實存在
    db.session.flush() 這兩行，須以程式碼審查確認，而非本測試的通過與否。"""
    vendor_id = _seed_spec(db_session)
    initial = _payload()
    initial["廠商ID"] = vendor_id
    new_id = MechanicalService.create(initial, user_id=None)

    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"][0]["量測值"] = 61  # 鍵值不變，僅改量測值
    MechanicalService.update(new_id, payload, user_id=None)

    payload2 = _payload()
    payload2["廠商ID"] = vendor_id
    payload2["measurements"][0]["量測值"] = 62  # 再次以相同鍵值更新
    MechanicalService.update(new_id, payload2, user_id=None)

    row = db_session.get(MechanicalTest, new_id)
    values = {(m.item, m.location, m.sample_no): m.value for m in row.measurements}
    assert values[("硬度", "爐門", 1)] == 62
    assert values[("硬度", "爐頂", 1)] == 73


def test_get_detail_and_delete(db_session):
    new_id = MechanicalService.create(_payload(), user_id=None)
    detail = MechanicalService.get_detail(new_id)
    assert detail["main"]["產品尺寸"] == "36x25.2"
    assert len(detail["measurements"]) == 2
    assert [row["編號"] for row in detail["extrusion_numbers"]] == [
        "010761 D35"
    ]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "011313T42",
        "011314T42",
    ]
    MechanicalService.delete(new_id)
    assert db_session.get(MechanicalTest, new_id) is None


def test_create_uses_selected_vendor_lower_limit(db_session):
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

    payload = _payload()
    payload["廠商ID"] = second_vendor.id
    payload["measurements"][0]["量測值"] = 70
    test_id = MechanicalService.create(payload, user_id=None)

    measurement = db_session.get(MechanicalTest, test_id).measurements[0]
    assert float(measurement.lower_limit) == 75
    assert measurement.is_ng is True


def test_update_preserves_excluded_measurement_evidence(db_session):
    test_id = MechanicalService.create(_payload(), user_id=None)
    excluding_user = User(username="exclude-auditor", password="x")
    db_session.add(excluding_user)
    db_session.flush()
    original = db_session.get(MechanicalTest, test_id).measurements[0]
    original.excluded = True
    original.exclusion_reason = "儀器異常"
    original.exclusion_user_id = excluding_user.id
    original.excluded_at = datetime(2026, 1, 21, tzinfo=timezone.utc)
    original.value = 59
    original.lower_limit = 60
    original.is_ng = True
    db_session.commit()

    payload = _payload()
    payload["measurements"][0]["量測值"] = 70
    MechanicalService.update(test_id, payload, user_id=None)

    updated = MechanicalMeasurement.query.filter_by(
        test_id=test_id, item="硬度", location="爐門", sample_no=1
    ).one()
    assert updated.excluded is True
    assert updated.exclusion_reason == "儀器異常"
    assert updated.exclusion_user_id == excluding_user.id
    assert updated.excluded_at.replace(tzinfo=timezone.utc) == datetime(2026, 1, 21, tzinfo=timezone.utc)
    assert float(updated.value) == 59
    assert float(updated.lower_limit) == 60
    assert updated.is_ng is True


def test_update_keeps_excluded_measurement_omitted_from_general_edit(db_session):
    test_id = MechanicalService.create(_payload(), user_id=None)
    original = db_session.get(MechanicalTest, test_id).measurements[0]
    original.excluded = True
    original.exclusion_reason = "儀器異常"
    db_session.commit()

    payload = _payload()
    payload["measurements"] = [payload["measurements"][1]]
    MechanicalService.update(test_id, payload, user_id=None)

    retained = MechanicalMeasurement.query.filter_by(
        test_id=test_id, item="硬度", location="爐門", sample_no=1
    ).one()
    assert retained.excluded is True
    assert retained.exclusion_reason == "儀器異常"


@pytest.mark.parametrize(("measurements", "expected"), [
    ([], "INCOMPLETE"),
    ([{"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 70}], "INCOMPLETE"),
])
def test_judgement_status_without_complete_spec(db_session, measurements, expected):
    payload = _payload()
    payload["measurements"] = measurements
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == expected
    assert MechanicalService.get_list({})["data"][0]["判定狀態"] == expected


def test_judgement_status_ok_requires_all_four_items(db_session):
    vendor_id = _seed_spec(db_session)
    main = VendorToleranceMain.query.one()
    for item, lower in [("抗拉強度", 60), ("降伏強度", 60), ("伸長率", 60)]:
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item=item, tolerance_min=lower, unit=""
        ))
    db_session.commit()
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements()
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "OK"


def test_judgement_status_complete_with_single_location(db_session):
    # 只取單一位置（爐門）但四項力學特性都有值 → 視為完整檢驗，非 INCOMPLETE。
    payload = _payload()
    payload["measurements"] = [
        {"量測項目": item, "測量位置": "爐門", "取樣序": 1, "量測值": 70}
        for item in ("硬度", "抗拉強度", "降伏強度", "伸長率")
    ]
    test_id = MechanicalService.create(payload, user_id=None)
    # 無規格 → NO_SPEC（重點是不再因為缺爐頂而落入 INCOMPLETE）
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "NO_SPEC"


# count 取前 N 筆（項目為外層迴圈）：0=空、1=只有硬度、6=缺伸長率一整項 → 皆缺項目 → INCOMPLETE
@pytest.mark.parametrize("count", [0, 1, 6])
def test_judgement_status_is_incomplete_when_an_item_is_missing(db_session, count):
    payload = _payload()
    payload["measurements"] = _required_measurements()[:count]
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "INCOMPLETE"


def _non_hardness_measurements():
    """抗拉/降伏/伸長率三項（爐門+爐頂），缺硬度。"""
    return [
        m for m in _required_measurements()
        if m["量測項目"] != "硬度"
    ]


def test_waived_item_excludes_missing_item_from_completeness(db_session):
    # 缺硬度但標記硬度免測 → 不再是 INCOMPLETE（無規格 → NO_SPEC）
    payload = _payload()
    payload["measurements"] = _non_hardness_measurements()
    payload["waived_items"] = [{"項目": "硬度", "原因": "硬度機故障"}]
    test_id = MechanicalService.create(payload, user_id=None)
    detail = MechanicalService.get_detail(test_id)
    assert detail["main"]["判定狀態"] == "NO_SPEC"
    assert detail["waived_items"] == [{"項目": "硬度", "原因": "硬度機故障"}]


def test_waived_item_reason_is_required(db_session):
    payload = _payload()
    payload["measurements"] = _non_hardness_measurements()
    payload["waived_items"] = [{"項目": "硬度", "原因": "   "}]
    with pytest.raises(MechanicalValidationError):
        MechanicalService.create(payload, user_id=None)


def test_waived_item_rejects_unsupported_and_duplicate(db_session):
    payload = _payload()
    payload["waived_items"] = [{"項目": "EC值", "原因": "x"}]
    with pytest.raises(MechanicalValidationError):
        MechanicalService.create(payload, user_id=None)

    payload["waived_items"] = [
        {"項目": "硬度", "原因": "a"}, {"項目": "硬度", "原因": "b"},
    ]
    with pytest.raises(MechanicalValidationError):
        MechanicalService.create(payload, user_id=None)


def test_waived_items_can_be_updated_and_cleared(db_session):
    payload = _payload()
    payload["measurements"] = _non_hardness_measurements()
    payload["waived_items"] = [{"項目": "硬度", "原因": "硬度機故障"}]
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "NO_SPEC"

    # 清空免測 → 缺硬度又變回 INCOMPLETE
    payload["waived_items"] = []
    MechanicalService.update(test_id, payload, user_id=None)
    detail = MechanicalService.get_detail(test_id)
    assert detail["waived_items"] == []
    assert detail["main"]["判定狀態"] == "INCOMPLETE"


def test_judgement_status_ng_takes_priority_over_incomplete(db_session):
    vendor_id = _seed_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements(70)[:3]
    payload["measurements"][0]["量測值"] = 59
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "NG"


def test_judgement_status_no_spec_requires_all_eight_measurements(db_session):
    payload = _payload()
    payload["measurements"] = _required_measurements()
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "NO_SPEC"


def test_judgement_status_no_spec_when_one_of_eight_limits_missing(db_session):
    vendor_id = _seed_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements()
    test_id = MechanicalService.create(payload, user_id=None)
    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "NO_SPEC"


def _seed_full_spec(db_session):
    """完整公差：四項力學特性 + 韋伯氏硬度（上下限）+ 真直度（僅上限）。"""
    vendor = Vendor(name="安泰")
    db_session.add(vendor); db_session.flush()
    main = VendorToleranceMain(vendor_id=vendor.id, material="6061-T651", spec="36*25.2")
    db_session.add(main); db_session.flush()
    for item, dim_min, dim_max in (
        ("洛氏硬度", 60, 70),
        ("抗拉強度", 60, None),
        ("降伏強度", 60, None),
        ("伸長率", 60, None),
        ("韋伯氏硬度", 10, 12),
        ("真直度", None, 0.3),
    ):
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item=item, dim_min=dim_min, dim_max=dim_max, unit=""
        ))
    db_session.commit()
    return vendor.id


def test_straightness_is_ng_when_above_upper_limit(db_session):
    vendor_id = _seed_full_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements() + [
        {"量測項目": "真直度", "測量位置": "爐門", "取樣序": 1, "量測值": 0.31},
        {"量測項目": "真直度", "測量位置": "爐頂", "取樣序": 1, "量測值": 0.30},
    ]
    test_id = MechanicalService.create(payload, user_id=None)

    detail = MechanicalService.get_detail(test_id)
    by_location = {
        m["測量位置"]: m for m in detail["measurements"] if m["量測項目"] == "真直度"
    }
    assert by_location["爐門"]["是否超差"] is True
    assert by_location["爐頂"]["是否超差"] is False
    # 上限判定的項目下限恆為空，界限存在「上限」欄
    assert by_location["爐門"]["下限"] is None
    assert by_location["爐門"]["上限"] == 0.3
    assert detail["main"]["判定狀態"] == "NG"


def test_straightness_with_upper_limit_does_not_degrade_status_to_no_spec(db_session):
    """真直度沒有下限。若「無規格」仍只看下限，整筆會被誤判成 NO_SPEC。"""
    vendor_id = _seed_full_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements() + [
        {"量測項目": "真直度", "測量位置": "爐門", "取樣序": 1, "量測值": 0.1},
    ]
    test_id = MechanicalService.create(payload, user_id=None)

    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "OK"


def test_webster_hardness_is_judged_on_lower_limit_only(db_session):
    """公差登錄 10~12 HW，但超出上限不算 NG——與同表的洛氏硬度規則一致。"""
    vendor_id = _seed_full_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements() + [
        {"量測項目": "韋伯氏硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 9},
        {"量測項目": "韋伯氏硬度", "測量位置": "爐頂", "取樣序": 1, "量測值": 13},
    ]
    test_id = MechanicalService.create(payload, user_id=None)

    detail = MechanicalService.get_detail(test_id)
    by_location = {
        m["測量位置"]: m for m in detail["measurements"] if m["量測項目"] == "韋伯氏硬度"
    }
    assert by_location["爐門"]["是否超差"] is True   # 9 < 下限 10
    assert by_location["爐頂"]["是否超差"] is False  # 13 > 上限 12，仍不判 NG
    assert by_location["爐頂"]["上限"] is None


def test_new_items_are_not_required_for_completion(db_session):
    """既有紀錄都沒有這兩項數值；納入必測會讓它們全數變成 INCOMPLETE。"""
    vendor_id = _seed_full_spec(db_session)
    payload = _payload()
    payload["廠商ID"] = vendor_id
    payload["measurements"] = _required_measurements()
    test_id = MechanicalService.create(payload, user_id=None)

    assert MechanicalService.get_detail(test_id)["main"]["判定狀態"] == "OK"


def test_new_items_cannot_be_marked_as_waived(db_session):
    payload = _payload()
    payload["waived_items"] = [{"項目": "真直度", "原因": "設備故障"}]
    with pytest.raises(MechanicalValidationError, match="免測項目不受支援"):
        MechanicalService.create(payload, user_id=None)


def test_nullable_fields_are_serialized_as_null(db_session):
    payload = _payload()
    payload.update({"測試日期": None, "T4溫度時間": None, "T6溫度時間": None, "備註": None})
    payload["extrusion_numbers"] = []
    payload["t4_furnace_numbers"] = [{"序號": 1, "編號": "F1"}]
    payload["measurements"][0]["量測值"] = None
    test_id = MechanicalService.create(payload, user_id=None)

    detail = MechanicalService.get_detail(test_id)
    listed = MechanicalService.get_list({})["data"][0]
    assert detail["main"]["測試日期"] is None
    assert detail["main"]["T4溫度時間"] is None
    assert detail["main"]["備註"] is None
    assert detail["extrusion_numbers"] == []
    assert detail["measurements"][0]["量測值"] is None
    assert detail["measurements"][0]["下限"] is None
    assert listed["測試日期"] is None
    assert listed["T4溫度時間"] is None
    assert listed["備註"] is None


def test_options_are_vendor_scoped_trimmed_and_deduplicated(db_session):
    first = Vendor(name="安泰")
    second = Vendor(name="宏達")
    db_session.add_all([first, second])
    db_session.flush()
    db_session.add_all([
        VendorToleranceMain(vendor_id=first.id, material=" 6061-T651 ", spec=" 36*25.2 "),
        VendorToleranceMain(vendor_id=first.id, material="6061-T651", spec="36*25.2"),
        VendorToleranceMain(vendor_id=first.id, material="6063", spec=None),
        VendorToleranceMain(vendor_id=second.id, material="7075", spec="99*99"),
    ])
    db_session.commit()

    assert MechanicalService.options(first.id) == {
        "materials": ["6061-T651", "6063"],
        "product_sizes": ["36*25.2"],
    }
    assert MechanicalService.options(None) == {"materials": [], "product_sizes": []}


@pytest.mark.parametrize("mutate", [
    lambda payload: payload.pop("產品尺寸"),
    lambda payload: payload.pop("材質"),
    lambda payload: payload["measurements"][0].update({"量測項目": "未知項目"}),
    lambda payload: payload["measurements"][0].update({"測量位置": "中央"}),
    lambda payload: payload["measurements"][0].update({"取樣序": 3}),
    lambda payload: payload["measurements"][0].update({"量測值": "not-a-number"}),
    lambda payload: payload["measurements"][0].update({"量測值": "NaN"}),
    lambda payload: payload["measurements"][0].update({"量測值": "Infinity"}),
    lambda payload: payload["measurements"][0].update({"量測值": "-Infinity"}),
    lambda payload: payload.update({"測試日期": "2026-99-99"}),
    lambda payload: payload.update({"測試日期": False}),
    lambda payload: payload.update({"測試日期": 0}),
    lambda payload: payload.update({"測試日期": "2026-01-20garbage"}),
    lambda payload: payload.update({"廠商ID": 0}),
    lambda payload: payload.update({"廠商ID": "invalid-vendor"}),
    lambda payload: payload.update({"廠商ID": 999999}),
    lambda payload: _replace_trace_numbers_with_legacy(payload, {}),
    lambda payload: _replace_trace_numbers_with_legacy(payload, ["bad"]),
    lambda payload: _replace_trace_numbers_with_legacy(payload, [{"序號": 0}]),
    lambda payload: _replace_trace_numbers_with_legacy(
        payload, [{"序號": 1}, {"序號": 1}]
    ),
    lambda payload: _replace_trace_numbers_with_legacy(
        payload, [{"序號": "1"}]
    ),
    lambda payload: payload.update({"measurements": {}}),
    lambda payload: payload.update({"measurements": ["bad"]}),
    lambda payload: payload["measurements"].append(dict(payload["measurements"][0])),
    lambda payload: payload.update({"產品尺寸": "x" * 51}),
    lambda payload: payload.update({"材質": "x" * 51}),
    lambda payload: payload.update({"T4溫度時間": "x" * 101}),
    lambda payload: payload.update({"T6溫度時間": 123}),
    lambda payload: payload.update({"備註": 123}),
    lambda payload: _replace_trace_numbers_with_legacy(
        payload,
        [{"序號": 1, "擠製編號": "x" * 101, "爐具編號": ""}],
    ),
    lambda payload: payload["measurements"][0].update({"量測值": "1e100"}),
])
def test_create_rejects_invalid_payload_without_persisting_data(db_session, mutate):
    payload = _payload()
    mutate(payload)

    with pytest.raises(ValueError):
        MechanicalService.create(payload, user_id=None)

    assert MechanicalTest.query.count() == 0


@pytest.mark.parametrize(("raw", "expected"), [
    ("99999999.9999", Decimal("99999999.9999")),
    ("1.23456", Decimal("1.2346")),
    ("-1.23455", Decimal("-1.2346")),
])
def test_measurement_numeric_12_4_uses_decimal_rounding(db_session, raw, expected):
    payload = _payload()
    payload["measurements"] = [{
        "量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": raw
    }]

    test_id = MechanicalService.create(payload, user_id=None)

    measurement = db_session.get(MechanicalTest, test_id).measurements[0]
    assert measurement.value == expected
