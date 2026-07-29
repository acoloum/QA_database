"""校正類型專屬附件格式政策測試。"""

from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from backend.models import EquipmentCalibrationRecord
from backend.services.attachment_service import AttachmentService
from backend.services.msa_errors import MsaValidationError
from backend.storage.local import LocalStorage
from backend.tests.test_services.test_calibration_readings import (
    _create_two_point_draft,
)


def _calibration_target(db_session, calibration_type: str, calibration_users):
    draft = _create_two_point_draft(
        db_session,
        calibration_users["manager"]["user"].id,
        calibration_users["approver"]["user"].id,
    )
    record = db_session.get(EquipmentCalibrationRecord, draft["id"])
    record.calibration_type = calibration_type
    db_session.commit()
    return record


def _file(filename: str, mimetype: str) -> FileStorage:
    return FileStorage(
        stream=BytesIO(b"test attachment"),
        filename=filename,
        content_type=mimetype,
    )


def test_external_calibration_rejects_xlsx_before_storage_write(
    app, db_session, tmp_path, calibration_users
):
    """外校只接受 PDF/JPEG/PNG，格式失敗時不得產生孤兒檔。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    record = _calibration_target(
        db_session, "external", calibration_users
    )

    with pytest.raises(MsaValidationError) as exc:
        AttachmentService.upload(
            _file(
                "certificate.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            entity_type="equipment_calibration",
            entity_id=record.id,
            d_step=None,
            uploader_id=calibration_users["manager"]["user"].id,
            purpose="cert",
        )

    assert exc.value.code == "MSA_ATTACHMENT_FILE_INVALID"
    assert list(tmp_path.rglob("*.xlsx")) == []


def test_internal_calibration_accepts_xlsx_certificate(
    app, db_session, tmp_path, calibration_users
):
    """內校可保存原始 Excel 證據，並保留 cert 用途。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    record = _calibration_target(
        db_session, "internal", calibration_users
    )

    result = AttachmentService.upload(
        _file(
            "raw-data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        entity_type="equipment_calibration",
        entity_id=record.id,
        d_step=None,
        uploader_id=calibration_users["manager"]["user"].id,
        purpose="cert",
    )

    assert result["entity_id"] == record.id
    assert result["purpose"] == "cert"
    assert app.config["STORAGE"].exists(result["file_path"])


def test_calibration_permissions_can_upload_and_view_detailed_attachment(
    app, client, db_session, tmp_path, calibration_users
):
    """獨立校正權限可操作詳細校正附件，不得被迫依賴 msa.manage。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    record = _calibration_target(
        db_session, "external", calibration_users
    )
    manager_token = calibration_users["manager"]["token"]
    viewer_token = calibration_users["viewer"]["token"]

    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"%PDF-test"), "certificate.pdf"),
            "entity_type": "equipment_calibration",
            "entity_id": str(record.id),
            "purpose": "cert",
        },
        headers={"Authorization": f"Bearer {manager_token}"},
        content_type="multipart/form-data",
    )

    assert created.status_code == 201
    listed = client.get(
        (
            "/api/attachments?entity_type=equipment_calibration"
            f"&entity_id={record.id}"
        ),
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.get_json()] == [
        created.get_json()["id"]
    ]
