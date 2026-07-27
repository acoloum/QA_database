"""MSA 設備與校驗附件的實體權限整合測試。"""

from datetime import date
from io import BytesIO

import pytest

from backend.extensions import db
from backend.models import (
    Attachment,
    AuditLog,
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    Role,
    User,
)
from backend.storage.local import LocalStorage
from backend.utils import generate_token, hash_password


@pytest.fixture
def msa_attachment_headers(db_session):
    users = {}
    for code, permissions in {
        "msa_attachment_view": {"msa.view": True},
        "msa_attachment_manage": {"msa.view": True, "msa.manage": True},
        "manager": {},
        "admin": {},
    }.items():
        db_session.add(Role(code=code, name=code, permissions=permissions))
        user = User(
            username=code,
            password=hash_password("pw12345678"),
            role=code,
            is_active=True,
        )
        db_session.add(user)
        users[code] = user
    db_session.commit()

    def headers(code):
        user = users[code]
        token = generate_token(user.id, user.username, user.role)
        return {"Authorization": f"Bearer {token}"}

    return headers


@pytest.fixture
def msa_attachment_targets(db_session):
    equipment = MeasurementEquipment(
        equipment_no="EQ-ATTACHMENT-TARGET",
        name="附件目標設備",
    )
    db_session.add(equipment)
    db_session.flush()
    calibration = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date(2026, 7, 27),
        result="pass",
        status="draft",
    )
    db_session.add(calibration)
    db_session.commit()
    return {
        "measurement_equipment": equipment.id,
        "equipment_calibration": calibration.id,
        "equipment_id": equipment.id,
        "calibration_id": calibration.id,
    }


@pytest.mark.parametrize(
    "entity_type",
    ["measurement_equipment", "equipment_calibration"],
)
def test_msa_view_can_list_and_download_but_cannot_upload_or_delete(
    app,
    client,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
    entity_type,
):
    """若 msa.view 可寫入，或無法讀取其設備證據附件，此測試應失敗。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    manage_headers = msa_attachment_headers("msa_attachment_manage")
    view_headers = msa_attachment_headers("msa_attachment_view")
    entity_id = msa_attachment_targets[entity_type]
    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"certificate"), "certificate.txt"),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
        },
        headers=manage_headers,
        content_type="multipart/form-data",
    )
    assert created.status_code == 201
    attachment = created.get_json()

    listed = client.get(
        f"/api/attachments?entity_type={entity_type}&entity_id={entity_id}",
        headers=view_headers,
    )
    downloaded = client.get(
        f"/api/attachments/{attachment['id']}/download",
        headers=view_headers,
    )
    forbidden_upload = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"forbidden"), "forbidden.txt"),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
        },
        headers=view_headers,
        content_type="multipart/form-data",
    )
    forbidden_delete = client.delete(
        f"/api/attachments/{attachment['id']}",
        headers=view_headers,
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.get_json()] == [attachment["id"]]
    assert downloaded.status_code == 200
    assert downloaded.data == b"certificate"
    assert forbidden_upload.status_code == 403
    assert forbidden_delete.status_code == 403


@pytest.mark.parametrize(
    "entity_type",
    ["measurement_equipment", "equipment_calibration"],
)
def test_msa_manage_can_upload_and_delete_own_attachment(
    app,
    client,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
    entity_type,
):
    """若 MSA 映射仍查找 msa.edit，manage 會錯誤地無法管理附件。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    headers = msa_attachment_headers("msa_attachment_manage")
    entity_id = msa_attachment_targets[entity_type]

    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"certificate"), "certificate.txt"),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert created.status_code == 201

    deleted = client.delete(
        f"/api/attachments/{created.get_json()['id']}",
        headers=headers,
    )

    assert deleted.status_code == 200
    assert deleted.get_json()["message"] == "刪除成功"
    actions = [
        log.action
        for log in AuditLog.query.filter_by(module="msa_attachment")
        .order_by(AuditLog.id)
        .all()
    ]
    assert actions == ["upload", "delete"]


@pytest.mark.parametrize(
    ("action", "method", "path"),
    [
        (
            "view",
            "get",
            "/api/attachments?entity_type=measurement_equipment&entity_id={id}",
        ),
        ("edit", "post", "/api/attachments/upload"),
    ],
)
def test_legacy_manager_does_not_bypass_msa_permissions(
    app,
    client,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
    action,
    method,
    path,
):
    """既有 manager 超級放行不得越過 MSA 四層權限。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    entity_id = msa_attachment_targets["measurement_equipment"]
    kwargs = {"headers": msa_attachment_headers("manager")}
    if action == "edit":
        kwargs.update(
            data={
                "file": (BytesIO(b"manager"), "manager.txt"),
                "entity_type": "measurement_equipment",
                "entity_id": str(entity_id),
            },
            content_type="multipart/form-data",
        )
    response = getattr(client, method)(path.format(id=entity_id), **kwargs)

    assert response.status_code == 403
    assert response.get_json() == {
        "error": {
            "code": "MSA_ATTACHMENT_PERMISSION_DENIED",
            "message": "權限不足",
            "details": {
                "entity_type": "measurement_equipment",
                "permission": "msa.view" if action == "view" else "msa.manage",
            },
        }
    }


def test_msa_attachment_validation_uses_stable_error_envelope(
    app,
    client,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
):
    """MSA 附件欄位驗證不得回傳 legacy 字串 error。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    response = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"bad"), "bad.exe"),
            "entity_type": "measurement_equipment",
            "entity_id": str(msa_attachment_targets["measurement_equipment"]),
        },
        headers=msa_attachment_headers("msa_attachment_manage"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    body = response.get_json()["error"]
    assert body["code"] == "MSA_ATTACHMENT_FILE_INVALID"
    assert body["message"]
    assert body["details"]["entity_type"] == "measurement_equipment"


def test_msa_attachment_upload_rejects_missing_target_before_saving_file(
    app,
    client,
    tmp_path,
    msa_attachment_headers,
):
    """若 MSA target 不存在，不得產生多型孤兒附件或實體檔案。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    response = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"orphan"), "orphan.txt"),
            "entity_type": "measurement_equipment",
            "entity_id": "999999",
        },
        headers=msa_attachment_headers("msa_attachment_manage"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": {
            "code": "MSA_ATTACHMENT_TARGET_NOT_FOUND",
            "message": "找不到附件所屬的 MSA 實體",
            "details": {
                "entity_type": "measurement_equipment",
                "entity_id": 999999,
            },
        }
    }
    assert Attachment.query.count() == 0
    assert list(tmp_path.rglob("orphan.txt")) == []


def test_msa_attachment_upload_rejects_approved_calibration_target(
    app,
    client,
    db_session,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
):
    """核准後校驗不得再新增或改寫證據附件。"""
    calibration = db_session.get(
        EquipmentCalibrationRecord,
        msa_attachment_targets["calibration_id"],
    )
    calibration.status = "approved"
    db_session.commit()
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))

    response = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"late"), "late.txt"),
            "entity_type": "equipment_calibration",
            "entity_id": str(calibration.id),
        },
        headers=msa_attachment_headers("msa_attachment_manage"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == (
        "MSA_ATTACHMENT_TARGET_IMMUTABLE"
    )
    assert Attachment.query.count() == 0


@pytest.mark.parametrize("operation", ["upload", "delete"])
def test_msa_calibration_attachment_write_locks_target_before_status_check(
    app,
    client,
    db_session,
    monkeypatch,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
    operation,
):
    """移除校驗目標的 FOR UPDATE 時，上傳與刪除都必須偵測契約退化。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    headers = msa_attachment_headers("msa_attachment_manage")
    calibration_id = msa_attachment_targets["calibration_id"]
    attachment = None
    if operation == "delete":
        attachment = Attachment(
            entity_type="equipment_calibration",
            entity_id=calibration_id,
            file_name="locked-target.txt",
            file_path=(
                f"uploads/equipment_calibration/{calibration_id}/"
                "locked-target.txt"
            ),
            mime_type="text/plain",
            file_size=6,
            uploaded_by=User.query.filter_by(
                username="msa_attachment_manage"
            ).one().id,
        )
        db_session.add(attachment)
        db_session.commit()

    original_execute = db.session.execute
    locked_calibration_queries = []

    def capture_execute(statement, *args, **kwargs):
        entity = None
        descriptions = getattr(statement, "column_descriptions", ())
        if descriptions:
            entity = descriptions[0].get("entity")
        if (
            entity is EquipmentCalibrationRecord
            and getattr(statement, "_for_update_arg", None) is not None
        ):
            locked_calibration_queries.append(statement)
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db.session, "execute", capture_execute)
    if operation == "upload":
        response = client.post(
            "/api/attachments/upload",
            data={
                "file": (BytesIO(b"locked"), "locked-target.txt"),
                "entity_type": "equipment_calibration",
                "entity_id": str(calibration_id),
            },
            headers=headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 201
    else:
        response = client.delete(
            f"/api/attachments/{attachment.id}",
            headers=headers,
        )
        assert response.status_code == 200

    assert len(locked_calibration_queries) == 1


def test_msa_attachment_delete_rechecks_locked_calibration_status(
    app,
    client,
    db_session,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
):
    """校驗核准後，既有附件也不得再由共用刪除路由移除。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    calibration_id = msa_attachment_targets["calibration_id"]
    uploader = User.query.filter_by(
        username="msa_attachment_manage"
    ).one()
    attachment = Attachment(
        entity_type="equipment_calibration",
        entity_id=calibration_id,
        file_name="approved.txt",
        file_path=(
            f"uploads/equipment_calibration/{calibration_id}/approved.txt"
        ),
        mime_type="text/plain",
        file_size=8,
        uploaded_by=uploader.id,
    )
    db_session.add(attachment)
    db_session.flush()
    attachment_id = attachment.id
    calibration = db_session.get(
        EquipmentCalibrationRecord,
        calibration_id,
    )
    calibration.status = "approved"
    db_session.commit()

    response = client.delete(
        f"/api/attachments/{attachment_id}",
        headers=msa_attachment_headers("msa_attachment_manage"),
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == (
        "MSA_ATTACHMENT_TARGET_IMMUTABLE"
    )
    assert db_session.get(Attachment, attachment_id) is not None


def test_msa_attachment_missing_id_uses_stable_not_found(
    client,
    msa_attachment_headers,
):
    """明確提供 MSA 實體 context 時，missing ID 使用 stable code。"""
    response = client.delete(
        "/api/attachments/999999?entity_type=measurement_equipment",
        headers=msa_attachment_headers("msa_attachment_manage"),
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": {
            "code": "MSA_ATTACHMENT_NOT_FOUND",
            "message": "附件不存在",
            "details": {"attachment_id": 999999},
        }
    }


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/attachments/999999/download"),
        ("delete", "/api/attachments/999999"),
    ],
)
def test_shared_missing_attachment_keeps_legacy_error_contract(
    client,
    msa_attachment_headers,
    method,
    path,
):
    """共用路由缺少實體 context 時，不得把不存在 ID 猜成 MSA。"""
    response = getattr(client, method)(
        path,
        headers=msa_attachment_headers("admin"),
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "附件不存在"}


def test_msa_upload_db_failure_compensates_saved_file(
    app,
    client,
    monkeypatch,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
):
    """檔案儲存後 DB commit 失敗時，必須 rollback 並移除孤兒檔。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))

    def fail_commit():
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr("backend.services.attachment_service.db.session.commit", fail_commit)
    response = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"rollback"), "rollback.txt"),
            "entity_type": "measurement_equipment",
            "entity_id": str(msa_attachment_targets["measurement_equipment"]),
        },
        headers=msa_attachment_headers("msa_attachment_manage"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == (
        "MSA_ATTACHMENT_PERSIST_FAILED"
    )
    assert Attachment.query.count() == 0
    assert list(tmp_path.rglob("rollback.txt")) == []


def test_msa_delete_db_failure_keeps_file_and_database_link(
    app,
    client,
    monkeypatch,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
):
    """DB 刪除未提交前不得先移除實體檔案。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    headers = msa_attachment_headers("msa_attachment_manage")
    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"keep"), "keep.txt"),
            "entity_type": "measurement_equipment",
            "entity_id": str(msa_attachment_targets["measurement_equipment"]),
        },
        headers=headers,
        content_type="multipart/form-data",
    ).get_json()
    path = app.config["STORAGE"].get_abs_path(created["file_path"])
    assert path is not None

    def fail_commit():
        raise RuntimeError("forced delete commit failure")

    monkeypatch.setattr("backend.services.attachment_service.db.session.commit", fail_commit)
    response = client.delete(
        f"/api/attachments/{created['id']}",
        headers=headers,
    )

    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == (
        "MSA_ATTACHMENT_PERSIST_FAILED"
    )
    assert db.session.get(Attachment, created["id"]) is not None
    assert app.config["STORAGE"].exists(created["file_path"]) is True


def test_msa_delete_storage_failure_restores_database_link(
    app,
    client,
    monkeypatch,
    tmp_path,
    msa_attachment_headers,
    msa_attachment_targets,
):
    """DB 已提交但實體刪檔失敗時，補償交易必須恢復附件 link。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path / "uploads"))
    headers = msa_attachment_headers("msa_attachment_manage")
    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"restore"), "restore.txt"),
            "entity_type": "measurement_equipment",
            "entity_id": str(msa_attachment_targets["measurement_equipment"]),
        },
        headers=headers,
        content_type="multipart/form-data",
    ).get_json()

    def fail_delete(_rel_path):
        raise OSError("forced storage delete failure")

    monkeypatch.setattr(app.config["STORAGE"], "delete", fail_delete)
    response = client.delete(
        f"/api/attachments/{created['id']}",
        headers=headers,
    )

    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == (
        "MSA_ATTACHMENT_STORAGE_DELETE_FAILED"
    )
    assert db.session.get(Attachment, created["id"]) is not None
    assert app.config["STORAGE"].exists(created["file_path"]) is True
    actions = [
        log.action
        for log in AuditLog.query.filter_by(
            module="msa_attachment",
            record_id=created["id"],
        )
        .order_by(AuditLog.id)
        .all()
    ]
    assert actions == ["upload", "delete", "delete_compensated"]
