"""MSA 正式研究的設備資格與快照契約。"""

from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
import json

import pytest
from sqlalchemy import event

from backend.extensions import db
from backend.models import (
    EquipmentCalibrationRecord,
    EquipmentCorrectionPoint,
    MeasurementEquipment,
)
from backend.services.msa_equipment_service import MsaEquipmentService
from backend.services.msa_errors import MsaServiceError
from backend.services.msa_errors import MsaValidationError
from backend.services.msa_errors import MsaNotFound


STUDY_DATE = date(2026, 7, 27)


def _equipment(db_session, equipment_no, **kwargs):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="MSA 測試量具",
        **kwargs,
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _calibration(db_session, equipment, **kwargs):
    values = {
        "equipment_id": equipment.id,
        "calibration_type": "external",
        "calibration_date": STUDY_DATE - timedelta(days=10),
        "next_due_date": STUDY_DATE + timedelta(days=30),
        "result": "pass",
        "status": "approved",
    }
    values.update(kwargs)
    record = EquipmentCalibrationRecord(**values)
    db_session.add(record)
    db_session.flush()
    return record


def test_pending_equipment_cannot_be_used_for_official_study(db_session):
    """防止待審核設備略過正式資格閘門。"""
    equipment = _equipment(
        db_session, "EQ-PENDING", status="pending_review"
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_PENDING_REVIEW"
    assert error.value.status_code == 422


def test_missing_equipment_returns_the_stable_not_found_contract(db_session):
    """防止正式研究引用已不存在設備時得到不穩定的底層例外。"""
    with pytest.raises(MsaNotFound) as error:
        MsaEquipmentService.assert_officially_usable(
            999_999, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_NOT_FOUND"
    assert error.value.status_code == 404


@pytest.mark.parametrize("status", ["maintenance", "inactive", "scrapped"])
def test_blocked_equipment_status_cannot_be_used_for_official_study(
    db_session, status
):
    """防止維修或報廢量具以有效校驗紀錄通過正式研究。"""
    equipment = _equipment(db_session, f"EQ-{status}", status=status)
    _calibration(db_session, equipment)
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_STATUS_BLOCKED"


def test_official_study_rejects_missing_approved_calibration(db_session):
    """防止啟用設備在沒有核准校驗證據時通過研究。"""
    equipment = _equipment(db_session, "EQ-NO-CAL", status="active")
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_MISSING"


@pytest.mark.parametrize("result", ["fail", "pending"])
def test_official_study_rejects_failed_or_pending_calibration(
    db_session, result
):
    """防止最近核准校驗為失敗或待定時仍被採用。"""
    equipment = _equipment(db_session, f"EQ-CAL-{result}", status="active")
    _calibration(db_session, equipment, result=result)
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_FAILED"


def test_expired_calibration_is_rejected(db_session):
    """防止研究日期晚於校驗到期日仍使用設備。"""
    equipment = _equipment(db_session, "EQ-EXPIRED", status="active")
    _calibration(
        db_session,
        equipment,
        next_due_date=STUDY_DATE - timedelta(days=1),
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_EXPIRED"


def test_latest_approved_calibration_overrides_an_older_pass_record(db_session):
    """防止服務錯選舊的通過校驗而略過最新失敗證據。"""
    equipment = _equipment(db_session, "EQ-LATEST", status="active")
    _calibration(
        db_session,
        equipment,
        calibration_date=STUDY_DATE - timedelta(days=20),
        result="pass",
    )
    _calibration(
        db_session,
        equipment,
        calibration_date=STUDY_DATE - timedelta(days=1),
        result="fail",
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_FAILED"


def test_limited_use_requires_an_exact_matching_measurement_mode(db_session):
    """防止受限校驗被套用到未核准的量測模式。"""
    equipment = _equipment(db_session, "EQ-LIMITED", status="active")
    _calibration(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["內徑量測", " 外徑量測 "],
        restriction_conditions="僅限既定量程",
    )
    db_session.commit()

    eligible = MsaEquipmentService.assert_officially_usable(
        equipment.id, on_date=STUDY_DATE, measurement_mode="外徑量測"
    )
    snapshot = MsaEquipmentService.build_snapshot(
        equipment.id, on_date=STUDY_DATE, measurement_mode="外徑量測"
    )

    assert eligible.eligible is True
    assert eligible.limitation == "僅限既定量程"
    assert snapshot.calibration["applicable_modes"] == ["內徑量測", "外徑量測"]
    assert snapshot.calibration["restriction_conditions"] == "僅限既定量程"

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE, measurement_mode="厚度量測"
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"
    assert error.value.status_code == 422


def test_limited_use_requires_a_non_blank_restriction_before_passing(
    db_session,
):
    """防止模式符合卻沒有受限理由的紀錄通過正式研究。"""
    equipment = _equipment(db_session, "EQ-LIMITED-NO-RESTRICTION", status="active")
    record = _calibration(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["外徑量測"],
        restriction_conditions="僅限既定量程",
    )
    db_session.commit()
    equipment_id = equipment.id
    record.restriction_conditions = "  "

    with db_session.no_autoflush:
        with pytest.raises(MsaValidationError) as error:
            MsaEquipmentService.assert_officially_usable(
                equipment_id, on_date=STUDY_DATE, measurement_mode="外徑量測"
            )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"


def test_limited_use_rejects_blank_structured_modes(db_session):
    """防止非空 JSON 陣列內仍以空白字串繞過模式限制。"""
    equipment = _equipment(db_session, "EQ-LIMITED-BLANK", status="active")
    record = _calibration(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["內徑量測"],
        restriction_conditions="僅限既定量程",
    )
    db_session.commit()
    equipment_id = equipment.id
    record.applicable_modes = ["  "]

    with db_session.no_autoflush:
        with pytest.raises(MsaValidationError) as error:
            MsaEquipmentService.assert_officially_usable(
                equipment_id, on_date=STUDY_DATE, measurement_mode="內徑量測"
            )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"


def test_exempt_equipment_requires_reason_and_snapshots_it(db_session):
    """防止缺少豁免依據的設備通過，或快照遺失豁免追溯資料。"""
    equipment = _equipment(
        db_session,
        "EQ-EXEMPT",
        status="active",
        calibration_type="exempt",
        calibration_exemption_reason="依內控規範免校驗",
        resolution=Decimal("0.01"),
        unit="mm",
    )
    db_session.commit()

    eligible = MsaEquipmentService.assert_officially_usable(
        equipment.id, on_date=STUDY_DATE
    )
    snapshot = MsaEquipmentService.build_snapshot(
        equipment.id, on_date=STUDY_DATE
    )

    assert eligible.eligible is True
    assert eligible.calibration_record_id is None
    assert snapshot.calibration["exemption_reason"] == "依內控規範免校驗"
    assert snapshot.calibration["applicable_modes"] == []


def test_exempt_equipment_rejects_blank_reason_even_before_persistence(
    db_session,
):
    """防止上游尚未寫入時，空白豁免理由被 service 當成有效證據。"""
    equipment = _equipment(
        db_session,
        "EQ-EXEMPT-BLANK",
        status="active",
        calibration_type="exempt",
        calibration_exemption_reason="有效豁免理由",
    )
    db_session.commit()
    equipment_id = equipment.id
    equipment.calibration_exemption_reason = "  "

    with db_session.no_autoflush:
        with pytest.raises(MsaValidationError) as error:
            MsaEquipmentService.assert_officially_usable(
                equipment_id, on_date=STUDY_DATE
            )

    assert error.value.code == "MSA_EQUIPMENT_EXEMPTION_REASON_MISSING"


@pytest.mark.parametrize(
    "calibration_date,effective_date",
    [
        (STUDY_DATE + timedelta(days=1), None),
        (STUDY_DATE - timedelta(days=1), STUDY_DATE + timedelta(days=1)),
    ],
)
def test_official_study_uses_only_calibration_effective_on_study_date(
    db_session, calibration_date, effective_date
):
    """防止研究日後才校驗或生效的證據回填歷史研究資格。"""
    equipment = _equipment(
        db_session,
        f"EQ-AS-OF-{calibration_date}-{effective_date}",
        status="active",
    )
    _calibration(
        db_session,
        equipment,
        calibration_date=calibration_date,
        effective_date=effective_date,
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_MISSING"


def test_snapshot_fails_closed_when_selected_calibration_is_revoked_mid_read(
    db_session,
):
    """防止資格判定後重查最新紀錄而靜默換掉或遺失已選校驗證據。"""
    equipment = _equipment(db_session, "EQ-SNAPSHOT-RACE", status="active")
    record = _calibration(db_session, equipment)
    db_session.commit()
    equipment_id = equipment.id
    record_id = record.id
    select_count = 0

    def revoke_after_first_calibration_select(
        connection, cursor, statement, parameters, context, executemany
    ):
        nonlocal select_count
        if 'FROM "設備校驗紀錄"' not in statement or not statement.lstrip().startswith("SELECT"):
            return
        select_count += 1
        if select_count != 1:
            return
        raw_connection = connection.connection.driver_connection
        update_cursor = raw_connection.cursor()
        try:
            update_cursor.execute(
                'UPDATE "設備校驗紀錄" SET "狀態" = ? WHERE "識別碼" = ?',
                ("draft", record_id),
            )
        finally:
            update_cursor.close()

    event.listen(
        db.engine,
        "after_cursor_execute",
        revoke_after_first_calibration_select,
    )
    try:
        with pytest.raises(MsaValidationError) as error:
            MsaEquipmentService.build_snapshot(
                equipment_id, on_date=STUDY_DATE
            )
    finally:
        event.remove(
            db.engine,
            "after_cursor_execute",
            revoke_after_first_calibration_select,
        )

    assert select_count >= 1
    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_MISSING"


def test_passing_calibration_returns_snapshot_with_correction_evidence(db_session):
    """防止資格通過時遺失設備身分、校驗與逐點補正證據。"""
    equipment = _equipment(
        db_session,
        "EQ-PASS",
        status="active",
        resolution=Decimal("0.001"),
        unit="mm",
    )
    record = _calibration(
        db_session,
        equipment,
        certificate_no="CERT-100",
        traceability_standard="CNS 1234",
        uncertainty_statement="U=0.002 mm",
    )
    db_session.add(
        EquipmentCorrectionPoint(
            calibration_record_id=record.id,
            measurement_mode="外徑量測",
            nominal_value=Decimal("10.000"),
            indicated_value=Decimal("10.002"),
            error_value=Decimal("0.002"),
            correction_value=Decimal("-0.002"),
            unit="mm",
            range_start=Decimal("5.000"),
            range_end=Decimal("15.000"),
        )
    )
    db_session.commit()

    eligible = MsaEquipmentService.assert_officially_usable(
        equipment.id, on_date=STUDY_DATE
    )
    snapshot = MsaEquipmentService.build_snapshot(
        equipment.id, on_date=STUDY_DATE
    )

    assert eligible.calibration_record_id == record.id
    assert snapshot.equipment_no == "EQ-PASS"
    assert snapshot.resolution == "0.0010000000"
    assert json.dumps(asdict(snapshot), sort_keys=True, allow_nan=False)
    assert snapshot.calibration == {
        "record_id": record.id,
        "calibration_type": "external",
        "calibration_date": "2026-07-17",
        "effective_date": None,
        "next_due_date": "2026-08-26",
        "result": "pass",
        "status": "approved",
        "certificate_no": "CERT-100",
        "traceability_standard": "CNS 1234",
        "uncertainty_statement": "U=0.002 mm",
        "applicable_modes": [],
        "restriction_conditions": None,
        "exemption_reason": None,
        "correction_points": [
            {
                "id": 1,
                "measurement_mode": "外徑量測",
                "nominal_value": "10.0000000000",
                "indicated_value": "10.0020000000",
                "error_value": "0.0020000000",
                "correction_value": "-0.0020000000",
                "unit": "mm",
                "range_start": "5.0000000000",
                "range_end": "15.0000000000",
            }
        ],
    }


def test_list_reports_calibration_summary_from_latest_approved_record(
    db_session,
):
    """防止清單使用較舊或 draft 校驗，導致風險排序與正式證據不一致。"""
    due_soon = _equipment(
        db_session, "EQ-LIST-DUE", status="active"
    )
    _calibration(
        db_session,
        due_soon,
        calibration_date=STUDY_DATE - timedelta(days=30),
        next_due_date=STUDY_DATE + timedelta(days=30),
    )
    _calibration(
        db_session,
        due_soon,
        calibration_date=STUDY_DATE - timedelta(days=1),
        next_due_date=STUDY_DATE - timedelta(days=1),
        result="fail",
        status="draft",
    )
    expired = _equipment(
        db_session, "EQ-LIST-EXPIRED", status="active"
    )
    _calibration(
        db_session,
        expired,
        next_due_date=STUDY_DATE - timedelta(days=1),
    )
    failed = _equipment(
        db_session, "EQ-LIST-FAILED", status="active"
    )
    _calibration(db_session, failed, result="fail")
    valid = _equipment(
        db_session, "EQ-LIST-VALID", status="active"
    )
    _calibration(
        db_session,
        valid,
        next_due_date=STUDY_DATE + timedelta(days=31),
    )
    missing = _equipment(
        db_session, "EQ-LIST-MISSING", status="active"
    )
    exempt = _equipment(
        db_session,
        "EQ-LIST-EXEMPT",
        status="active",
        calibration_type="exempt",
        calibration_exemption_reason="依內控規範免校驗",
    )
    db_session.commit()

    result = MsaEquipmentService.list(
        {
            "page": "1",
            "page_size": "25",
            "sort": "equipment_no",
            "as_of": STUDY_DATE.isoformat(),
        }
    )
    items = {item["equipment_no"]: item for item in result["items"]}

    assert items["EQ-LIST-DUE"]["calibration_status"] == "due_soon"
    assert (
        items["EQ-LIST-DUE"]["next_calibration_date"]
        == (STUDY_DATE + timedelta(days=30)).isoformat()
    )
    assert items["EQ-LIST-DUE"]["calibration_block_reason"] is None
    assert items["EQ-LIST-EXPIRED"]["calibration_status"] == "expired"
    assert "2026-07-26" in items["EQ-LIST-EXPIRED"][
        "calibration_block_reason"
    ]
    assert items["EQ-LIST-FAILED"]["calibration_status"] == "failed"
    assert "失敗" in items["EQ-LIST-FAILED"]["calibration_block_reason"]
    assert items["EQ-LIST-VALID"]["calibration_status"] == "valid"
    assert items["EQ-LIST-MISSING"]["calibration_status"] == "missing"
    assert "尚無" in items["EQ-LIST-MISSING"]["calibration_block_reason"]
    assert items["EQ-LIST-EXEMPT"]["calibration_status"] == "exempt"
    assert items["EQ-LIST-EXEMPT"]["next_calibration_date"] is None


def test_list_calibration_status_filter_preserves_total_and_date_boundaries(
    db_session,
):
    """防止校驗篩選只作用於頁面資料，或把到期當日誤判為逾期。"""
    expired = _equipment(
        db_session, "EQ-FILTER-EXPIRED", status="active"
    )
    _calibration(
        db_session,
        expired,
        next_due_date=STUDY_DATE - timedelta(days=1),
    )
    due_today = _equipment(
        db_session, "EQ-FILTER-TODAY", status="active"
    )
    _calibration(
        db_session,
        due_today,
        next_due_date=STUDY_DATE,
    )
    db_session.commit()

    result = MsaEquipmentService.list(
        {
            "page": "1",
            "page_size": "25",
            "sort": "equipment_no",
            "calibration_status": "expired",
            "as_of": STUDY_DATE.isoformat(),
        }
    )

    assert result["total"] == 1
    assert [item["equipment_no"] for item in result["items"]] == [
        "EQ-FILTER-EXPIRED"
    ]


def test_list_calibration_summary_uses_fixed_query_count(db_session):
    """防止每台設備各查一次校驗，造成設備數增加時的 N+1 查詢。"""
    for index in range(8):
        equipment = _equipment(
            db_session, f"EQ-QUERY-{index:02d}", status="active"
        )
        _calibration(db_session, equipment)
    db_session.commit()
    select_count = 0

    def count_selects(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(db.engine, "before_cursor_execute", count_selects)
    try:
        result = MsaEquipmentService.list(
            {
                "page": "1",
                "page_size": "25",
                "sort": "equipment_no",
                "as_of": STUDY_DATE.isoformat(),
            }
        )
    finally:
        event.remove(db.engine, "before_cursor_execute", count_selects)

    assert len(result["items"]) == 8
    assert select_count == 2


def test_detail_uses_the_same_calibration_summary_contract_as_list(
    db_session,
):
    """防止 drawer 取得明細後遺失校驗狀態，導致 badge 無法呈現。"""
    equipment = _equipment(
        db_session, "EQ-DETAIL-SUMMARY", status="active"
    )
    _calibration(
        db_session,
        equipment,
        next_due_date=date.today() - timedelta(days=1),
    )
    db_session.commit()

    detail = MsaEquipmentService.get(equipment.id)

    assert detail["calibration_status"] == "expired"
    assert detail["next_calibration_date"] == (
        date.today() - timedelta(days=1)
    ).isoformat()
    assert "到期" in detail["calibration_block_reason"]


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ({"page": "10001"}, "MSA_PAGE_INVALID"),
        ({"calibration_status": "unknown"}, "MSA_CALIBRATION_STATUS_INVALID"),
        ({"as_of": "2026/07/27"}, "MSA_AS_OF_INVALID"),
    ],
)
def test_list_rejects_unbounded_or_non_whitelisted_summary_arguments(
    db_session, args, code
):
    """防止巨大 offset、未知狀態或模糊日期進入設備清單查詢。"""
    with pytest.raises(MsaServiceError) as error:
        MsaEquipmentService.list(args)

    assert error.value.code == code
