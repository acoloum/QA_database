"""校正送審、職責分離、附件綁定與核准工作流測試。"""

from datetime import date

import pytest

from backend.models import Attachment, EquipmentCalibrationRecord
from backend.services.calibration_errors import (
    CalibrationForbidden,
    CalibrationValidationError,
)
from backend.services.calibration_service import CalibrationService
from backend.tests.test_services.test_calibration_readings import (
    _create_two_point_draft,
    _point_payload,
)


def _ready_external(db_session, calibration_users) -> dict:
    manager = calibration_users["manager"]["user"]
    approver = calibration_users["approver"]["user"]
    draft = _create_two_point_draft(db_session, manager.id, approver.id)
    saved = CalibrationService.save_readings(
        draft["id"],
        {
            "expected_version": draft["row_version"],
            "points": [
                _point_payload(
                    draft["points"][0],
                    ("10.001", "10.002", "10.003"),
                ),
                _point_payload(
                    draft["points"][1],
                    ("20.001", "20.002", "20.003"),
                ),
            ],
        },
        actor_id=manager.id,
    )
    CalibrationService.validate(saved["id"], {}, actor_id=manager.id)
    return CalibrationService.get(saved["id"])


def _certificate(
    db_session,
    record_id: int,
    uploader_id: int,
    *,
    entity_id: int | None = None,
    mime_type: str = "application/pdf",
) -> Attachment:
    attachment = Attachment(
        entity_type="equipment_calibration",
        entity_id=record_id if entity_id is None else entity_id,
        file_name="certificate.pdf",
        file_path=f"test/{record_id}/certificate.pdf",
        mime_type=mime_type,
        file_size=128,
        uploaded_by=uploader_id,
        purpose="cert",
    )
    db_session.add(attachment)
    db_session.commit()
    return attachment


def test_external_submit_without_certificate_is_zero_write(
    db_session, calibration_users
):
    """外校缺少證書時不得送審，ready 狀態與版本必須保留。"""
    manager = calibration_users["manager"]["user"]
    ready = _ready_external(db_session, calibration_users)

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.submit(
            ready["id"],
            {
                "expected_version": ready["row_version"],
                "reason": "送交證書審查",
            },
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_CERTIFICATE_REQUIRED"
    db_session.expire_all()
    persisted = db_session.get(EquipmentCalibrationRecord, ready["id"])
    assert persisted.status == "ready_for_submission"
    assert persisted.row_version == ready["row_version"]
    assert persisted.submitted_by is None


def test_certificate_from_other_calibration_cannot_be_bound(
    db_session, calibration_users
):
    """其他草稿的附件不得以 ID 猜測方式綁入本校正。"""
    manager = calibration_users["manager"]["user"]
    ready = _ready_external(db_session, calibration_users)
    attachment = _certificate(
        db_session,
        ready["id"],
        manager.id,
        entity_id=ready["id"] + 999,
    )

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.update(
            ready["id"],
            {
                "expected_version": ready["row_version"],
                "certificate_attachment_id": attachment.id,
            },
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_ATTACHMENT_INVALID"
    db_session.expire_all()
    persisted = db_session.get(EquipmentCalibrationRecord, ready["id"])
    assert persisted.certificate_attachment_id is None
    assert persisted.row_version == ready["row_version"]


def test_submit_and_approve_enforces_separation_and_preserves_hash(
    db_session, calibration_users
):
    """送審人不可自行核准；獨立核准者可核准且正式 hash 不變。"""
    manager = calibration_users["manager"]["user"]
    approver = calibration_users["approver"]["user"]
    ready = _ready_external(db_session, calibration_users)
    attachment = _certificate(db_session, ready["id"], manager.id)
    bound = CalibrationService.update(
        ready["id"],
        {
            "expected_version": ready["row_version"],
            "certificate_attachment_id": attachment.id,
        },
        actor_id=manager.id,
    )
    validated = CalibrationService.validate(
        bound["id"], {}, actor_id=manager.id
    )
    submitted = CalibrationService.submit(
        bound["id"],
        {
            "expected_version": validated["row_version"],
            "reason": "送交核准",
        },
        actor_id=manager.id,
    )
    submitted_hash = submitted["data_hash"]

    submitted_record = db_session.get(
        EquipmentCalibrationRecord, submitted["id"]
    )
    submitted_record.template_snapshot = {"tampered": True}
    with pytest.raises(ValueError, match="送審後"):
        db_session.commit()
    db_session.rollback()

    with pytest.raises(CalibrationForbidden) as exc:
        CalibrationService.approve(
            submitted["id"],
            {
                "expected_version": submitted["row_version"],
                "reason": "自行核准",
            },
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_SELF_APPROVAL_FORBIDDEN"
    approved = CalibrationService.approve(
        submitted["id"],
        {
            "expected_version": submitted["row_version"],
            "reason": "證據完整，同意核准",
        },
        actor_id=approver.id,
    )

    assert approved["status"] == "approved"
    assert approved["approved_by"] == approver.id
    assert approved["effective_date"] == date.today().isoformat()
    assert approved["next_due_date"] is not None
    assert approved["data_hash"] == submitted_hash


def test_submit_rejects_tampered_hash_and_rolls_back(db_session, calibration_users):
    """送審前若正式 hash 被竄改，狀態與送審稽核不得寫入。"""
    manager = calibration_users["manager"]["user"]
    ready = _ready_external(db_session, calibration_users)
    attachment = _certificate(db_session, ready["id"], manager.id)
    bound = CalibrationService.update(
        ready["id"],
        {
            "expected_version": ready["row_version"],
            "certificate_attachment_id": attachment.id,
        },
        actor_id=manager.id,
    )
    validated = CalibrationService.validate(
        bound["id"], {}, actor_id=manager.id
    )
    record = db_session.get(EquipmentCalibrationRecord, bound["id"])
    record.data_hash = "0" * 64
    db_session.commit()

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.submit(
            record.id,
            {
                "expected_version": validated["row_version"],
                "reason": "送交核准",
            },
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_DATA_CHANGED"
    db_session.expire_all()
    persisted = db_session.get(EquipmentCalibrationRecord, record.id)
    assert persisted.status == "ready_for_submission"
    assert persisted.submitted_by is None
