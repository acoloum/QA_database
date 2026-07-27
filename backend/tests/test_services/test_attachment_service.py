"""MSA 設備與校驗附件的實體權限整合測試。"""

from io import BytesIO

import pytest

from backend.models import Role, User
from backend.storage.local import LocalStorage
from backend.utils import generate_token, hash_password


@pytest.fixture
def msa_attachment_headers(db_session):
    users = {}
    for code, permissions in {
        "msa_attachment_view": {"msa.view": True},
        "msa_attachment_manage": {"msa.view": True, "msa.manage": True},
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


@pytest.mark.parametrize(
    "entity_type",
    ["measurement_equipment", "equipment_calibration"],
)
def test_msa_view_can_list_and_download_but_cannot_upload_or_delete(
    app,
    client,
    tmp_path,
    msa_attachment_headers,
    entity_type,
):
    """若 msa.view 可寫入，或無法讀取其設備證據附件，此測試應失敗。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path))
    manage_headers = msa_attachment_headers("msa_attachment_manage")
    view_headers = msa_attachment_headers("msa_attachment_view")
    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"certificate"), "certificate.txt"),
            "entity_type": entity_type,
            "entity_id": "91",
        },
        headers=manage_headers,
        content_type="multipart/form-data",
    )
    assert created.status_code == 201
    attachment = created.get_json()

    listed = client.get(
        f"/api/attachments?entity_type={entity_type}&entity_id=91",
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
            "entity_id": "91",
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
    entity_type,
):
    """若 MSA 映射仍查找 msa.edit，manage 會錯誤地無法管理附件。"""
    app.config["STORAGE"] = LocalStorage(str(tmp_path))
    headers = msa_attachment_headers("msa_attachment_manage")

    created = client.post(
        "/api/attachments/upload",
        data={
            "file": (BytesIO(b"certificate"), "certificate.txt"),
            "entity_type": entity_type,
            "entity_id": "92",
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
