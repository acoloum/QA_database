"""量測設備 API 的真實路由、權限、交易與稽核整合測試。"""

from datetime import date

import pytest

from backend.models import (
    AuditLog,
    EquipmentCalibrationRecord,
    EquipmentCorrectionPoint,
    EquipmentStatusEvent,
    MeasurementEquipment,
    MeasurementEquipmentLink,
    Recorder,
    Role,
    Thermocouple,
    User,
)
from backend.utils import generate_token, hash_password


@pytest.fixture
def msa_user_headers(db_session):
    """建立 MSA 四層權限與無權限使用者，回傳可供 Flask client 使用的 JWT。"""
    permissions_by_role = {
        "no_msa": {},
        "msa_view": {"msa.view": True},
        "msa_execute": {"msa.view": True, "msa.execute": True},
        "msa_manage": {"msa.view": True, "msa.execute": True, "msa.manage": True},
        "msa_approve": {"msa.view": True, "msa.approve": True},
    }
    users = {}
    for role_code, permissions in permissions_by_role.items():
        db_session.add(
            Role(
                code=role_code,
                name=f"{role_code} 測試角色",
                permissions=permissions,
            )
        )
        user = User(
            username=f"{role_code}_user",
            password=hash_password("pw12345678"),
            role=role_code,
            is_active=True,
        )
        db_session.add(user)
        users[role_code] = user
    db_session.commit()

    def headers(role_code):
        user = users[role_code]
        token = generate_token(user.id, user.username, user.role)
        return {"Authorization": f"Bearer {token}"}

    return headers


def _equipment_payload(equipment_no="EQ-API-1", **overrides):
    payload = {
        "equipment_no": equipment_no,
        "name": "高度規",
        "status": "pending_review",
        "calibration_type": "external",
        "resolution": "0.001",
        "unit": "mm",
    }
    payload.update(overrides)
    return payload


def _create_equipment(client, headers, equipment_no="EQ-API-1", **overrides):
    response = client.post(
        "/api/measurement-equipment",
        json=_equipment_payload(equipment_no, **overrides),
        headers=headers("msa_manage"),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _calibration_payload(**overrides):
    payload = {
        "calibration_type": "external",
        "calibration_date": "2026-07-01",
        "effective_date": "2026-07-01",
        "next_due_date": "2027-07-01",
        "calibration_provider": "校驗實驗室",
        "certificate_no": "CERT-001",
        "traceability_standard": "ISO/IEC 17025",
        "uncertainty_statement": "U=0.002 mm, k=2",
        "result": "pass",
        "correction_points": [
            {
                "measurement_mode": "高度",
                "nominal_value": "10.000",
                "indicated_value": "10.001",
                "error_value": "0.001",
                "correction_value": "-0.001",
                "unit": "mm",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_equipment_list_requires_msa_view(client, msa_user_headers):
    """移除 msa.view 權限時，清單路由必須拒絕存取。"""
    response = client.get(
        "/api/measurement-equipment",
        headers=msa_user_headers("no_msa"),
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": {
            "code": "MSA_PERMISSION_DENIED",
            "message": "權限不足",
            "details": {"permission": "msa.view"},
        }
    }


def test_equipment_create_requires_msa_manage(client, msa_user_headers):
    """誤把 msa.execute 當成管理權限時，此測試應失敗。"""
    response = client.post(
        "/api/measurement-equipment",
        json={"equipment_no": "EQ-API-1", "name": "高度規"},
        headers=msa_user_headers("msa_execute"),
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": {
            "code": "MSA_PERMISSION_DENIED",
            "message": "權限不足",
            "details": {"permission": "msa.manage"},
        }
    }


def test_equipment_list_is_paginated(client, msa_user_headers):
    """移除分頁 envelope 或忽略 page_size 時，此測試應失敗。"""
    _create_equipment(client, msa_user_headers, "EQ-API-2")
    _create_equipment(client, msa_user_headers, "EQ-API-1")

    response = client.get(
        "/api/measurement-equipment?page=1&page_size=1&sort=equipment_no",
        headers=msa_user_headers("msa_view"),
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert set(data) == {"items", "page", "page_size", "total"}
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] == 2
    assert [item["equipment_no"] for item in data["items"]] == ["EQ-API-1"]


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ("page_size=101", "MSA_PAGE_SIZE_INVALID"),
        ("sort=created_by", "MSA_SORT_INVALID"),
    ],
)
def test_equipment_list_rejects_unbounded_or_unknown_sort(
    client,
    msa_user_headers,
    query,
    code,
):
    """放寬清單上限或允許任意欄位排序時，此測試應失敗。"""
    response = client.get(
        f"/api/measurement-equipment?{query}",
        headers=msa_user_headers("msa_view"),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == code


def test_equipment_detail_and_patch_use_view_and_manage_permissions(
    client,
    msa_user_headers,
):
    """detail 若未受 msa.view 保護，或 patch 錯放給 execute，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)

    forbidden_detail = client.get(
        f"/api/measurement-equipment/{equipment['id']}",
        headers=msa_user_headers("no_msa"),
    )
    allowed_detail = client.get(
        f"/api/measurement-equipment/{equipment['id']}",
        headers=msa_user_headers("msa_view"),
    )
    forbidden_patch = client.patch(
        f"/api/measurement-equipment/{equipment['id']}",
        json={"name": "更新名稱"},
        headers=msa_user_headers("msa_execute"),
    )
    allowed_patch = client.patch(
        f"/api/measurement-equipment/{equipment['id']}",
        json={"name": "更新名稱"},
        headers=msa_user_headers("msa_manage"),
    )

    assert forbidden_detail.status_code == 403
    assert allowed_detail.status_code == 200
    assert forbidden_patch.status_code == 403
    assert allowed_patch.status_code == 200
    assert allowed_patch.get_json()["data"]["name"] == "更新名稱"


def test_equipment_patch_cannot_change_equipment_number(
    client,
    msa_user_headers,
):
    """若 PATCH 可改寫穩定設備編號，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)

    response = client.patch(
        f"/api/measurement-equipment/{equipment['id']}",
        json={"equipment_no": "EQ-REUSED"},
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "MSA_EQUIPMENT_NO_IMMUTABLE"
    assert db_equipment_no(equipment["id"]) == "EQ-API-1"


def db_equipment_no(equipment_id):
    """測試用資料庫查詢，確認失敗 mutation 沒有留下部分變更。"""
    return MeasurementEquipment.query.filter_by(id=equipment_id).one().equipment_no


def test_equipment_api_does_not_offer_hard_delete(client, msa_user_headers):
    """若新增 DELETE 而破壞研究引用保護，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)

    response = client.delete(
        f"/api/measurement-equipment/{equipment['id']}",
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 405
    assert MeasurementEquipment.query.filter_by(id=equipment["id"]).count() == 1


def test_manage_creates_draft_calibration_with_correction_points_atomically(
    client,
    msa_user_headers,
):
    """若校驗與補正點分開提交，或管理者不能建立 draft，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)

    response = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(),
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["status"] == "draft"
    assert data["correction_points"] == [
        {
            "id": data["correction_points"][0]["id"],
            "measurement_mode": "高度",
            "nominal_value": "10.0000000000",
            "indicated_value": "10.0010000000",
            "error_value": "0.0010000000",
            "correction_value": "-0.0010000000",
            "unit": "mm",
            "range_start": None,
            "range_end": None,
        }
    ]
    assert EquipmentCalibrationRecord.query.count() == 1
    assert EquipmentCorrectionPoint.query.count() == 1


def test_invalid_correction_point_rolls_back_whole_calibration(
    client,
    msa_user_headers,
):
    """若第二個補正點驗證失敗後仍留下校驗主檔，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)
    payload = _calibration_payload()
    payload["correction_points"].append(
        {"measurement_mode": "高度", "indicated_value": "20.002"}
    )

    response = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=payload,
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "MSA_CORRECTION_POINT_INVALID"
    assert EquipmentCalibrationRecord.query.count() == 0
    assert EquipmentCorrectionPoint.query.count() == 0


def test_only_msa_approve_can_approve_calibration_with_expected_status(
    client,
    msa_user_headers,
):
    """若 manage 可越權核准，或 stale expected_status 未被拒絕，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)
    calibration = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(),
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]
    payload = {
        "expected_status": "draft",
        "reason": "證書與補正資料查核完成",
    }

    forbidden = client.post(
        f"/api/measurement-equipment/calibrations/{calibration['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_manage"),
    )
    approved = client.post(
        f"/api/measurement-equipment/calibrations/{calibration['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_approve"),
    )
    stale = client.post(
        f"/api/measurement-equipment/calibrations/{calibration['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_approve"),
    )

    assert forbidden.status_code == 403
    assert approved.status_code == 200
    assert approved.get_json()["data"]["status"] == "approved"
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "MSA_CALIBRATION_STATUS_CONFLICT"


def test_status_event_requires_manage_and_persists_event(
    client,
    msa_user_headers,
):
    """若 execute 可建立設備狀態事件，或事件未落庫，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)
    payload = {
        "event_type": "maintenance",
        "occurred_at": "2026-07-27T09:30:00+08:00",
        "reason": "年度保養",
        "triggers_msa_restudy": True,
    }

    forbidden = client.post(
        f"/api/measurement-equipment/{equipment['id']}/status-events",
        json=payload,
        headers=msa_user_headers("msa_execute"),
    )
    created = client.post(
        f"/api/measurement-equipment/{equipment['id']}/status-events",
        json=payload,
        headers=msa_user_headers("msa_manage"),
    )

    assert forbidden.status_code == 403
    assert created.status_code == 201
    assert created.get_json()["data"]["event_type"] == "maintenance"
    assert EquipmentStatusEvent.query.filter_by(equipment_id=equipment["id"]).count() == 1


def test_current_source_link_switch_is_guarded_by_expected_id(
    client,
    db_session,
    msa_user_headers,
):
    """若同一 Recorder 可同時連兩台設備，或 stale expected id 可切換，此測試應失敗。"""
    recorder = Recorder(serial="REC-API-1", is_active=True)
    db_session.add(recorder)
    db_session.commit()
    first_equipment = _create_equipment(client, msa_user_headers, "EQ-LINK-1")
    second_equipment = _create_equipment(client, msa_user_headers, "EQ-LINK-2")
    source = {
        "source_module": "pyrometry",
        "source_entity_type": "Recorder",
        "source_entity_id": recorder.id,
        "is_current": True,
        "expected_current_link_id": None,
    }

    first = client.post(
        f"/api/measurement-equipment/{first_equipment['id']}/links",
        json=source,
        headers=msa_user_headers("msa_manage"),
    )
    stale = client.post(
        f"/api/measurement-equipment/{second_equipment['id']}/links",
        json=source,
        headers=msa_user_headers("msa_manage"),
    )
    source["expected_current_link_id"] = first.get_json()["data"]["id"]
    switched = client.post(
        f"/api/measurement-equipment/{second_equipment['id']}/links",
        json=source,
        headers=msa_user_headers("msa_manage"),
    )

    assert first.status_code == 201
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "MSA_SOURCE_LINK_VERSION_CONFLICT"
    assert switched.status_code == 201
    links = MeasurementEquipmentLink.query.order_by(MeasurementEquipmentLink.id).all()
    assert [link.is_current for link in links] == [False, True]
    assert links[1].equipment_id == second_equipment["id"]
    switch_audit = (
        AuditLog.query.filter_by(
            module="msa_equipment",
            action="create_link",
            record_id=links[1].id,
        )
        .one()
    )
    assert switch_audit.old_value["id"] == links[0].id
    assert switch_audit.old_value["status"] == "current"
    assert switch_audit.new_value["status"] == "current"


def test_source_link_uses_existing_cqi9_entity_names(
    client,
    db_session,
    msa_user_headers,
):
    """若 CQI-9 名稱大小寫或實體 ID 未對應現行模型，此測試應失敗。"""
    thermocouple = Thermocouple(serial="TC-API-1", is_active=True)
    db_session.add(thermocouple)
    db_session.commit()
    equipment = _create_equipment(client, msa_user_headers)

    valid = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links",
        json={
            "source_module": "pyrometry",
            "source_entity_type": "Thermocouple",
            "source_entity_id": thermocouple.id,
            "is_current": True,
            "expected_current_link_id": None,
        },
        headers=msa_user_headers("msa_manage"),
    )
    invalid = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links",
        json={
            "source_module": "pyrometry",
            "source_entity_type": "thermocouple",
            "source_entity_id": thermocouple.id,
            "is_current": False,
        },
        headers=msa_user_headers("msa_manage"),
    )

    assert valid.status_code == 201
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "MSA_SOURCE_ENTITY_TYPE_INVALID"


def test_retire_link_requires_expected_id_and_status(
    client,
    db_session,
    msa_user_headers,
):
    """若 retire 不檢查畫面看到的 link id/status，舊畫面可能覆蓋新狀態。"""
    recorder = Recorder(serial="REC-RETIRE-1", is_active=True)
    db_session.add(recorder)
    db_session.commit()
    equipment = _create_equipment(client, msa_user_headers)
    link = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links",
        json={
            "source_module": "pyrometry",
            "source_entity_type": "Recorder",
            "source_entity_id": recorder.id,
            "is_current": True,
            "expected_current_link_id": None,
        },
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]

    wrong_id = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links/{link['id']}/retire",
        json={"expected_link_id": link["id"] + 1, "expected_status": "current"},
        headers=msa_user_headers("msa_manage"),
    )
    retired = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links/{link['id']}/retire",
        json={"expected_link_id": link["id"], "expected_status": "current"},
        headers=msa_user_headers("msa_manage"),
    )
    stale = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links/{link['id']}/retire",
        json={"expected_link_id": link["id"], "expected_status": "current"},
        headers=msa_user_headers("msa_manage"),
    )

    assert wrong_id.status_code == 409
    assert retired.status_code == 200
    assert retired.get_json()["data"]["status"] == "retired"
    assert stale.status_code == 409


def test_all_equipment_mutations_write_audit_logs(
    client,
    db_session,
    msa_user_headers,
):
    """移除任一 mutation 的 log_audit 呼叫時，此測試應失敗。"""
    recorder = Recorder(serial="REC-AUDIT-1", is_active=True)
    db_session.add(recorder)
    db_session.commit()
    equipment = _create_equipment(client, msa_user_headers)
    client.patch(
        f"/api/measurement-equipment/{equipment['id']}",
        json={"location": "量測室"},
        headers=msa_user_headers("msa_manage"),
    )
    calibration = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(),
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]
    client.post(
        f"/api/measurement-equipment/calibrations/{calibration['id']}/approve",
        json={"expected_status": "draft", "reason": "查核完成"},
        headers=msa_user_headers("msa_approve"),
    )
    link = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links",
        json={
            "source_module": "pyrometry",
            "source_entity_type": "Recorder",
            "source_entity_id": recorder.id,
            "is_current": True,
            "expected_current_link_id": None,
        },
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]
    client.post(
        f"/api/measurement-equipment/{equipment['id']}/links/{link['id']}/retire",
        json={"expected_link_id": link["id"], "expected_status": "current"},
        headers=msa_user_headers("msa_manage"),
    )
    client.post(
        f"/api/measurement-equipment/{equipment['id']}/status-events",
        json={
            "event_type": "major_adjustment",
            "reason": "更換量測頭",
            "triggers_msa_restudy": True,
        },
        headers=msa_user_headers("msa_manage"),
    )

    actions = [
        row.action
        for row in AuditLog.query.filter_by(module="msa_equipment")
        .order_by(AuditLog.id)
        .all()
    ]
    assert actions == [
        "create",
        "update",
        "create_calibration",
        "approve_calibration",
        "create_link",
        "retire_link",
        "create_status_event",
    ]
