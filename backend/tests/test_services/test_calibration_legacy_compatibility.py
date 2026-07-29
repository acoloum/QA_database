"""MSA 與獨立校正資格服務之歷史相容契約。"""

from datetime import date, timedelta

import pytest

from backend.models import EquipmentCalibrationRecord, MeasurementEquipment
from backend.services.msa_equipment_service import MsaEquipmentService
from backend.services.measurement_equipment_service import MeasurementEquipmentService
from backend.services.msa_errors import MsaValidationError


ON_DATE = date(2026, 7, 28)


def _equipment(db_session, equipment_no: str) -> MeasurementEquipment:
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="資格相容測試量具",
        status="active",
        calibration_type="external",
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _record(db_session, equipment, **overrides) -> EquipmentCalibrationRecord:
    values = {
        "equipment_id": equipment.id,
        "calibration_type": "external",
        "calibration_date": ON_DATE - timedelta(days=1),
        "next_due_date": ON_DATE + timedelta(days=30),
        "result": "pass",
        "status": "approved",
        "data_level": "summary_legacy",
    }
    values.update(overrides)
    record = EquipmentCalibrationRecord(**values)
    db_session.add(record)
    db_session.flush()
    return record


def test_msa_uses_new_approved_detailed_calibration_qualification(db_session):
    """防止 MSA 仍讀取舊摘要而遺失已核准詳細校正證據。"""
    equipment = _equipment(db_session, "EQ-DETAILED")
    detailed = _record(
        db_session,
        equipment,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="a" * 64,
    )
    db_session.commit()

    qualification = MsaEquipmentService.assert_officially_usable(
        equipment.id,
        on_date=ON_DATE,
    )

    assert qualification.calibration_record_id == detailed.id
    assert qualification.data_level == "detailed"
    assert qualification.data_hash == "a" * 64


def test_msa_keeps_unexpired_legacy_pass_qualified_without_claiming_raw_evidence(
    db_session,
):
    """防止歷史摘要遭拒絕，或被誤標為可還原的詳細原始證據。"""
    equipment = _equipment(db_session, "EQ-LEGACY")
    legacy = _record(db_session, equipment)
    db_session.commit()

    qualification = MsaEquipmentService.assert_officially_usable(
        equipment.id,
        on_date=ON_DATE,
    )
    snapshot = MsaEquipmentService.build_snapshot(equipment.id, on_date=ON_DATE)

    assert qualification.calibration_record_id == legacy.id
    assert qualification.data_level == "summary_legacy"
    assert qualification.data_hash is None
    assert snapshot.calibration["data_level"] == "summary_legacy"
    assert snapshot.calibration["correction_points"] == []


@pytest.mark.parametrize("status", ["submitted", "rejected", "voided"])
def test_unapproved_detailed_calibration_never_qualifies_msa(
    db_session,
    status: str,
):
    """防止送審、退回或作廢詳細紀錄被錯當正式資格。"""
    equipment = _equipment(db_session, f"EQ-{status}")
    _record(
        db_session,
        equipment,
        status=status,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="b" * 64,
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id,
            on_date=ON_DATE,
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_MISSING"


def test_latest_approved_detailed_fail_overrides_legacy_pass(db_session):
    """防止新核准失敗證據被較舊的歷史通過摘要掩蓋。"""
    equipment = _equipment(db_session, "EQ-FAIL-OVERRIDES")
    _record(
        db_session,
        equipment,
        calibration_date=ON_DATE - timedelta(days=10),
    )
    failed = _record(
        db_session,
        equipment,
        calibration_date=ON_DATE - timedelta(days=1),
        result="fail",
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="c" * 64,
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id,
            on_date=ON_DATE,
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_FAILED"
    assert error.value.details["calibration_record_id"] == failed.id


@pytest.mark.parametrize(
    ("measurement_mode", "expected_code"),
    [
        (None, "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"),
        ("", "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"),
        ("厚度量測", "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"),
        (" 外徑量測 ", "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"),
    ],
)
def test_limited_use_rejects_missing_or_non_exact_mode(
    db_session,
    measurement_mode: str | None,
    expected_code: str,
):
    """防止受限校正缺少或不精確的量測模式仍可通過 MSA。"""
    equipment = _equipment(db_session, "EQ-EXACT-MODE")
    _record(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["外徑量測"],
        restriction_conditions="只限外徑量測",
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="d" * 64,
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id,
            on_date=ON_DATE,
            measurement_mode=measurement_mode,
        )

    assert error.value.code == expected_code


def test_limited_use_accepts_only_exact_approved_mode(db_session):
    """防止修正缺少模式後反向拒絕明確已核准的模式。"""
    equipment = _equipment(db_session, "EQ-EXACT-APPROVED-MODE")
    _record(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["外徑量測"],
        restriction_conditions="只限外徑量測",
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="f" * 64,
    )
    db_session.commit()

    qualification = MsaEquipmentService.assert_officially_usable(
        equipment.id,
        on_date=ON_DATE,
        measurement_mode="外徑量測",
    )

    assert qualification.is_qualified is True


def test_msa_maps_uncovered_mode_and_incomplete_limited_use_separately(
    db_session,
):
    """防止不同校正阻擋原因被壓成同一份不完整錯誤細節。"""
    uncovered = _equipment(db_session, "EQ-MODE-UNCOVERED")
    uncovered_record = _record(
        db_session,
        uncovered,
        result="limited_use",
        applicable_modes=["外徑量測"],
        restriction_conditions="只限外徑量測",
    )
    incomplete = _equipment(db_session, "EQ-MODE-INCOMPLETE")
    incomplete_record = _record(
        db_session,
        incomplete,
        result="limited_use",
        applicable_modes=["外徑量測"],
        restriction_conditions="只限已登錄模式",
    )
    db_session.commit()
    uncovered_id = uncovered.id
    incomplete_id = incomplete.id
    incomplete_record.applicable_modes = []

    with db_session.no_autoflush:
        with pytest.raises(MsaValidationError) as uncovered_error:
            MsaEquipmentService.assert_officially_usable(
                uncovered_id,
                on_date=ON_DATE,
                measurement_mode="厚度量測",
            )
        with pytest.raises(MsaValidationError) as incomplete_error:
            MsaEquipmentService.assert_officially_usable(
                incomplete_id,
                on_date=ON_DATE,
                measurement_mode="外徑量測",
            )

    assert uncovered_error.value.code == (
        "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"
    )
    assert uncovered_error.value.message == "受限校驗不適用於指定量測模式"
    assert uncovered_error.value.details == {
        "calibration_record_id": uncovered_record.id,
        "applicable_modes": ["外徑量測"],
        "measurement_mode": "厚度量測",
    }
    assert incomplete_error.value.code == (
        "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"
    )
    assert incomplete_error.value.message == "受限校驗限制資訊不完整"
    assert incomplete_error.value.details == {
        "calibration_record_id": incomplete_record.id,
        "applicable_modes": [],
        "restriction_conditions": "只限已登錄模式",
    }


def test_measurement_equipment_service_does_not_expose_retired_calibration_or_msa_methods():
    """防止設備主檔服務重新暴露舊校正 mutation 或 MSA 資格／快照。"""
    for method in (
        "create_calibration",
        "approve_calibration",
        "assert_officially_usable",
        "build_snapshot",
    ):
        assert not hasattr(MeasurementEquipmentService, method)

    public_methods = {
        name for name, member in vars(MeasurementEquipmentService).items()
        if isinstance(member, staticmethod) and not name.startswith("_")
    }
    assert public_methods == {
        "list", "get", "create", "update", "create_status_event",
        "create_link", "retire_link",
    }


def test_detailed_snapshot_keeps_evidence_while_legacy_snapshot_fails_closed(
    db_session,
):
    """防止移除重複快照後詳細證據遺失或舊摘要洩漏原始補正。"""
    from decimal import Decimal

    from backend.models import EquipmentCorrectionPoint

    detailed_equipment = _equipment(db_session, "EQ-DETAILED-SNAPSHOT")
    detailed = _record(
        db_session,
        detailed_equipment,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="g" * 64,
    )
    db_session.add(EquipmentCorrectionPoint(
        calibration_record_id=detailed.id,
        measurement_mode="外徑量測",
        nominal_value=Decimal("10.000"),
        indicated_value=Decimal("10.001"),
        unit="mm",
    ))
    legacy_equipment = _equipment(db_session, "EQ-LEGACY-SNAPSHOT")
    legacy = _record(db_session, legacy_equipment)
    db_session.add(EquipmentCorrectionPoint(
        calibration_record_id=legacy.id,
        measurement_mode="外徑量測",
        nominal_value=Decimal("10.000"),
        indicated_value=Decimal("10.001"),
        unit="mm",
    ))
    db_session.commit()

    detailed_snapshot = MsaEquipmentService.build_snapshot(
        detailed_equipment.id, on_date=ON_DATE,
    )
    legacy_snapshot = MsaEquipmentService.build_snapshot(
        legacy_equipment.id, on_date=ON_DATE,
    )

    assert detailed_snapshot.calibration["data_level"] == "detailed"
    assert len(detailed_snapshot.calibration["correction_points"]) == 1
    assert legacy_snapshot.calibration["data_level"] == "summary_legacy"
    assert legacy_snapshot.calibration["correction_points"] == []


def test_missing_due_date_is_never_serialized_as_valid(db_session):
    """防止缺少下次校正日的詳細紀錄被設備摘要標示為有效。"""
    equipment = _equipment(db_session, "EQ-NO-DUE")
    _record(
        db_session,
        equipment,
        next_due_date=None,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="e" * 64,
    )
    db_session.commit()

    summary = MsaEquipmentService.list({"as_of": ON_DATE.isoformat()})

    assert summary["items"][0]["calibration_status"] == "missing"
    assert summary["items"][0]["calibration_status"] != "valid"
