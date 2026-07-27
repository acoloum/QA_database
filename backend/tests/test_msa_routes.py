"""量測設備 API 的真實路由、權限、交易與稽核整合測試。"""

from datetime import date
from io import BytesIO

import pytest

from backend.models import (
    Attachment,
    AuditLog,
    EquipmentCalibrationRecord,
    EquipmentCorrectionPoint,
    EquipmentStatusEvent,
    MeasurementEquipment,
    MeasurementEquipmentLink,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
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


def _import_csv_bytes():
    return (
        "設備編號,名稱,狀態,類別,解析度,單位\n"
        "EQ-IMPORT-API,API 測試量具,使用中,外校,0.01,mm\n"
    ).encode("utf-8-sig")


def _criteria_profile_payload(name="API 一般計量準則"):
    return {
        "name": name,
        "customer_scope": "一般顧客",
        "applicable_study_types": ["grr_anova", "stability"],
    }


def _criteria_version_payload(**overrides):
    payload = {
        "method_version": "MSA4-1.0",
        "effective_date": "2026-07-27",
        "thresholds": {
            "grr_accept_max": 8,
            "grr_conditional_max": 20,
            "ndc_min": 5,
        },
        "stability_rules": {
            "rule_set": "WECO",
            "enabled_rules": [1, 2, 3, 4],
        },
        "conditional_actions": ["記錄接受理由", "建立改善與監控措施"],
        "basis": "AIAG MSA 第四版及顧客要求",
    }
    payload.update(overrides)
    return payload


def _create_criteria_profile(client, headers, name="API 一般計量準則"):
    response = client.post(
        "/api/msa/criteria",
        json=_criteria_profile_payload(name),
        headers=headers("msa_manage"),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _create_criteria_version(client, headers, profile_id, **overrides):
    response = client.post(
        f"/api/msa/criteria/{profile_id}/versions",
        json=_criteria_version_payload(**overrides),
        headers=headers("msa_manage"),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_criteria_routes_use_stable_auth_and_permission_envelopes(
    client,
    msa_user_headers,
):
    missing_auth = client.get("/api/msa/criteria")
    invalid_auth = client.get(
        "/api/msa/criteria",
        headers={"Authorization": "Bearer invalid-token"},
    )
    forbidden_list = client.get(
        "/api/msa/criteria",
        headers=msa_user_headers("no_msa"),
    )
    forbidden_create = client.post(
        "/api/msa/criteria",
        json=_criteria_profile_payload(),
        headers=msa_user_headers("msa_execute"),
    )

    assert missing_auth.status_code == 401
    assert missing_auth.get_json() == {
        "error": {
            "code": "MSA_AUTH_REQUIRED",
            "message": "缺少認證 Token",
            "details": {},
        }
    }
    assert invalid_auth.status_code == 401
    assert invalid_auth.get_json()["error"] == {
        "code": "MSA_AUTH_INVALID_TOKEN",
        "message": "無效或過期的 Token",
        "details": {},
    }
    assert forbidden_list.status_code == 403
    assert forbidden_list.get_json()["error"] == {
        "code": "MSA_PERMISSION_DENIED",
        "message": "權限不足",
        "details": {"permission": "msa.view"},
    }
    assert forbidden_create.status_code == 403
    assert forbidden_create.get_json()["error"]["details"] == {
        "permission": "msa.manage"
    }


def test_manage_can_create_profile_and_complete_draft_version(
    client,
    msa_user_headers,
):
    profile = _create_criteria_profile(client, msa_user_headers)
    version = _create_criteria_version(
        client,
        msa_user_headers,
        profile["id"],
    )

    assert profile["name"] == "API 一般計量準則"
    assert profile["current_version_id"] is None
    assert version["profile_id"] == profile["id"]
    assert version["status"] == "draft"
    assert version["is_current"] is False
    assert version["thresholds"]["alpha"] == 0.05
    assert version["thresholds"]["kappa_min"] == 0.75
    assert version["stability_rules"] == {
        "rule_set": "WECO",
        "enabled_rules": [1, 2, 3, 4],
    }
    assert version["conditional_actions"] == [
        "記錄接受理由",
        "建立改善與監控措施",
    ]
    assert version["basis"] == "AIAG MSA 第四版及顧客要求"


def test_criteria_list_requires_view_and_uses_bounded_sorting(
    client,
    msa_user_headers,
):
    _create_criteria_profile(client, msa_user_headers, "B 準則")
    _create_criteria_profile(client, msa_user_headers, "A 準則")

    response = client.get(
        "/api/msa/criteria?page=1&page_size=1&sort=name&order=asc",
        headers=msa_user_headers("msa_view"),
    )
    invalid = client.get(
        "/api/msa/criteria?page_size=101",
        headers=msa_user_headers("msa_view"),
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["total"] == 2
    assert response.get_json()["data"]["items"][0]["name"] == "A 準則"
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "MSA_CRITERIA_PAGE_SIZE_INVALID"


def test_only_msa_approve_can_approve_criteria_version(
    client,
    db_session,
    msa_user_headers,
):
    profile = _create_criteria_profile(client, msa_user_headers)
    version = _create_criteria_version(
        client,
        msa_user_headers,
        profile["id"],
    )
    payload = {"expected_status": "draft"}

    forbidden = client.post(
        f"/api/msa/criteria/versions/{version['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_manage"),
    )
    approved = client.post(
        f"/api/msa/criteria/versions/{version['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_approve"),
    )
    stale = client.post(
        f"/api/msa/criteria/versions/{version['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_approve"),
    )

    assert forbidden.status_code == 403
    assert approved.status_code == 200
    assert approved.get_json()["data"]["status"] == "approved"
    assert approved.get_json()["data"]["is_current"] is True
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "MSA_VERSION_CONFLICT"
    db_session.expire_all()
    persisted_profile = db_session.get(MsaCriteriaProfile, profile["id"])
    persisted_version = db_session.get(MsaCriteriaVersion, version["id"])
    assert persisted_profile.current_version_id == persisted_version.id
    assert persisted_version.status == "approved"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"expected_status": "approved"},
        {"expected_status": "draft", "unexpected": True},
    ],
)
def test_criteria_approve_rejects_invalid_payload(
    client,
    msa_user_headers,
    payload,
):
    profile = _create_criteria_profile(client, msa_user_headers)
    version = _create_criteria_version(
        client,
        msa_user_headers,
        profile["id"],
    )

    response = client.post(
        f"/api/msa/criteria/versions/{version['id']}/approve",
        json=payload,
        headers=msa_user_headers("msa_approve"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] in {
        "MSA_EXPECTED_STATUS_INVALID",
        "MSA_UNKNOWN_FIELDS",
    }


def test_criteria_validation_and_not_found_use_stable_envelope(
    client,
    msa_user_headers,
):
    invalid = client.post(
        "/api/msa/criteria",
        json={"name": "  "},
        headers=msa_user_headers("msa_manage"),
    )
    missing = client.post(
        "/api/msa/criteria/999999/versions",
        json=_criteria_version_payload(),
        headers=msa_user_headers("msa_manage"),
    )

    assert invalid.status_code == 422
    assert set(invalid.get_json()["error"]) == {"code", "message", "details"}
    assert invalid.get_json()["error"]["code"] == "MSA_CRITERIA_PROFILE_INVALID"
    assert missing.status_code == 404
    assert missing.get_json()["error"]["code"] == "MSA_CRITERIA_PROFILE_NOT_FOUND"


def test_inactive_approver_with_old_jwt_cannot_approve_criteria(
    client,
    db_session,
    msa_user_headers,
):
    profile = _create_criteria_profile(client, msa_user_headers)
    version = _create_criteria_version(
        client,
        msa_user_headers,
        profile["id"],
    )
    old_headers = msa_user_headers("msa_approve")
    approver = User.query.filter_by(username="msa_approve_user").one()
    approver.is_active = False
    db_session.commit()

    response = client.post(
        f"/api/msa/criteria/versions/{version['id']}/approve",
        json={"expected_status": "draft"},
        headers=old_headers,
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": {
            "code": "MSA_USER_INACTIVE",
            "message": "使用者帳號已停用",
            "details": {},
        }
    }
    db_session.expire_all()
    persisted_profile = db_session.get(MsaCriteriaProfile, profile["id"])
    persisted_version = db_session.get(MsaCriteriaVersion, version["id"])
    assert persisted_profile.current_version_id is None
    assert persisted_version.status == "draft"
    assert persisted_version.approved_by is None
    assert persisted_version.approved_at is None
    assert AuditLog.query.filter_by(
        module="msa_criteria",
        action="approve_version",
        record_id=version["id"],
    ).count() == 0


def test_inactive_approver_with_old_jwt_cannot_approve_calibration(
    client,
    db_session,
    msa_user_headers,
):
    equipment = _create_equipment(client, msa_user_headers)
    calibration = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(),
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]
    old_headers = msa_user_headers("msa_approve")
    approver = User.query.filter_by(username="msa_approve_user").one()
    approver.is_active = False
    db_session.commit()

    response = client.post(
        f"/api/measurement-equipment/calibrations/{calibration['id']}/approve",
        json={
            "expected_status": "draft",
            "reason": "停用帳號不得寫入此理由",
        },
        headers=old_headers,
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": {
            "code": "MSA_USER_INACTIVE",
            "message": "使用者帳號已停用",
            "details": {},
        }
    }
    db_session.expire_all()
    persisted = db_session.get(
        EquipmentCalibrationRecord,
        calibration["id"],
    )
    assert persisted.status == "draft"
    assert persisted.approved_by is None
    assert persisted.approved_at is None
    assert AuditLog.query.filter_by(
        module="msa_equipment",
        action="approve_calibration",
        record_id=calibration["id"],
    ).count() == 0


def test_criteria_extreme_integer_returns_stable_validation_envelope(
    client,
    msa_user_headers,
):
    profile = _create_criteria_profile(client, msa_user_headers)

    response = client.post(
        f"/api/msa/criteria/{profile['id']}/versions",
        json={
            "thresholds": {
                "false_accept_max": 10**1000,
            }
        },
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == {
        "code": "MSA_CRITERIA_THRESHOLDS_INVALID",
        "message": "false_accept_max 必須是有限數值",
        "details": {"field": "false_accept_max"},
    }
    assert MsaCriteriaVersion.query.filter_by(
        profile_id=profile["id"]
    ).count() == 0


def test_criteria_list_rejects_page_above_explicit_limit_before_db_query(
    client,
    msa_user_headers,
):
    response = client.get(
        f"/api/msa/criteria?page={'9' * 1000}",
        headers=msa_user_headers("msa_view"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == {
        "code": "MSA_CRITERIA_PAGE_INVALID",
        "message": "page 超出允許範圍",
        "details": {
            "field": "page",
            "minimum": 1,
            "maximum": 1000000,
        },
    }


def test_equipment_import_preview_requires_msa_manage(
    client,
    msa_user_headers,
):
    """若匯入預覽錯放給 msa.execute，此測試應失敗。"""
    response = client.post(
        "/api/measurement-equipment/imports/preview",
        data={"file": (BytesIO(_import_csv_bytes()), "equipment.csv")},
        content_type="multipart/form-data",
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


def test_equipment_import_preview_and_confirm_use_stable_envelope(
    client,
    msa_user_headers,
):
    """若 preview 建設備、confirm envelope 漂移或無法冪等，此測試應失敗。"""
    preview = client.post(
        "/api/measurement-equipment/imports/preview?as_of=2026-07-27",
        data={"file": (BytesIO(_import_csv_bytes()), "equipment.csv")},
        content_type="multipart/form-data",
        headers=msa_user_headers("msa_manage"),
    )

    assert preview.status_code == 201
    batch = preview.get_json()["data"]
    assert batch["status"] == "previewed"
    assert batch["total_rows"] == 1
    assert len(batch["rows"]) == 1
    assert MeasurementEquipment.query.count() == 0

    confirm = client.post(
        f"/api/measurement-equipment/imports/{batch['id']}/confirm",
        json={"resolutions": {}, "confirmation_date": "2026-07-27"},
        headers=msa_user_headers("msa_manage"),
    )
    repeated = client.post(
        f"/api/measurement-equipment/imports/{batch['id']}/confirm",
        json={"resolutions": {}, "confirmation_date": "2026-07-27"},
        headers=msa_user_headers("msa_manage"),
    )

    assert confirm.status_code == 200
    assert repeated.status_code == 200
    assert confirm.get_json()["data"]["status"] == "confirmed"
    assert repeated.get_json()["data"]["id"] == batch["id"]
    assert MeasurementEquipment.query.count() == 1


def test_equipment_import_history_lists_batches_and_loads_row_evidence(
    client,
    msa_user_headers,
):
    """防止匯入歷程頁只能依賴前端暫存，重新載入後失去逐列證據。"""
    preview = client.post(
        "/api/measurement-equipment/imports/preview?as_of=2026-07-27",
        data={"file": (BytesIO(_import_csv_bytes()), "equipment.csv")},
        content_type="multipart/form-data",
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]

    history = client.get(
        "/api/measurement-equipment/imports?page=1&page_size=20",
        headers=msa_user_headers("msa_view"),
    )
    detail = client.get(
        f"/api/measurement-equipment/imports/{preview['id']}",
        headers=msa_user_headers("msa_view"),
    )

    assert history.status_code == 200
    assert history.get_json()["data"] == {
        "items": [{
            key: value
            for key, value in preview.items()
            if key != "rows"
        }],
        "page": 1,
        "page_size": 20,
        "total": 1,
    }
    assert detail.status_code == 200
    assert detail.get_json()["data"]["rows"] == preview["rows"]


def test_equipment_import_history_requires_msa_view(
    client,
    msa_user_headers,
):
    """防止匯入原始值與人工處置證據暴露給無 MSA 檢視權限帳號。"""
    response = client.get(
        "/api/measurement-equipment/imports",
        headers=msa_user_headers("no_msa"),
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["details"] == {
        "permission": "msa.view"
    }


def test_equipment_import_error_uses_stable_msa_envelope(
    client,
    msa_user_headers,
):
    """錯誤若退化成 HTML 或舊式字串格式，此測試應失敗。"""
    response = client.post(
        "/api/measurement-equipment/imports/preview",
        data={"file": (BytesIO(b"not csv"), "equipment.txt")},
        content_type="multipart/form-data",
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "error": {
            "code": "MSA_IMPORT_FILE_TYPE_INVALID",
            "message": "設備匯入僅接受 CSV 檔案",
            "details": {"filename": "equipment.txt"},
        }
    }


@pytest.mark.parametrize(
    ("path", "headers", "code", "message"),
    [
        (
            "/api/measurement-equipment/imports/preview",
            {},
            "MSA_AUTH_REQUIRED",
            "缺少認證 Token",
        ),
        (
            "/api/measurement-equipment/imports/999/confirm",
            {},
            "MSA_AUTH_REQUIRED",
            "缺少認證 Token",
        ),
        (
            "/api/measurement-equipment/imports/preview",
            {"Authorization": "Bearer invalid-token"},
            "MSA_AUTH_INVALID_TOKEN",
            "無效或過期的 Token",
        ),
        (
            "/api/measurement-equipment/imports/999/confirm",
            {"Authorization": "Bearer invalid-token"},
            "MSA_AUTH_INVALID_TOKEN",
            "無效或過期的 Token",
        ),
    ],
)
def test_equipment_import_auth_errors_use_stable_msa_envelope(
    client,
    path,
    headers,
    code,
    message,
):
    """import auth 若在 MSA adapter 外返回舊式字串，此測試應失敗。"""
    response = client.post(path, headers=headers)

    assert response.status_code == 401
    assert response.get_json() == {
        "error": {
            "code": code,
            "message": message,
            "details": {},
        }
    }


def test_msa_import_auth_adapter_preserves_missing_user_envelope(client):
    """有效 Token 找不到使用者時，不得誤報成 Token 無效。"""
    token = generate_token(999999, "missing-user", "msa_manage")
    response = client.post(
        "/api/measurement-equipment/imports/preview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": {
            "code": "MSA_USER_NOT_FOUND",
            "message": "使用者不存在",
            "details": {},
        }
    }


def test_all_msa_routes_share_the_stable_auth_envelope(client):
    """MSA 共用 adapter 必須涵蓋設備與匯入 route。"""
    response = client.get("/api/measurement-equipment")

    assert response.status_code == 401
    assert response.get_json() == {
        "error": {
            "code": "MSA_AUTH_REQUIRED",
            "message": "缺少認證 Token",
            "details": {},
        }
    }


def test_equipment_import_rejects_control_character_with_stable_envelope(
    client,
    msa_user_headers,
):
    """控制字元若進入 preview 或錯誤 envelope 漂移，此測試應失敗。"""
    content = "設備編號,名稱\nEQ-1,量具\u0000\n".encode("utf-8")
    response = client.post(
        "/api/measurement-equipment/imports/preview",
        data={"file": (BytesIO(content), "equipment.csv")},
        content_type="multipart/form-data",
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == {
        "code": "MSA_IMPORT_CONTROL_CHARACTER_INVALID",
        "message": "CSV 含有不允許的控制字元",
        "details": {"codepoint": "U+0000"},
    }


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


def test_equipment_patch_status_requires_status_event(
    client,
    db_session,
    msa_user_headers,
):
    """若泛用 PATCH 仍可改設備狀態，狀態事件與 expected_status 可被繞過。"""
    equipment = _create_equipment(client, msa_user_headers)

    response = client.patch(
        f"/api/measurement-equipment/{equipment['id']}",
        json={"status": "maintenance"},
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "MSA_STATUS_REQUIRES_EVENT"
    assert (
        db_session.get(MeasurementEquipment, equipment["id"]).status
        == "pending_review"
    )


def test_equipment_patch_validates_range_against_persisted_value(
    client,
    db_session,
    msa_user_headers,
):
    """若 PATCH 只比較 payload 內欄位，單改下限可越過既有上限。"""
    equipment = _create_equipment(
        client,
        msa_user_headers,
        range_min="0",
        range_max="10",
    )

    response = client.patch(
        f"/api/measurement-equipment/{equipment['id']}",
        json={"range_min": "11"},
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "MSA_EQUIPMENT_RANGE_INVALID"
    persisted = db_session.get(MeasurementEquipment, equipment["id"])
    assert str(persisted.range_min) == "0E-10"
    assert str(persisted.range_max) == "10.0000000000"


def test_equipment_create_rejects_varchar_over_model_limit(
    client,
    msa_user_headers,
):
    """若 service 依賴 SQLite 接受超長 VARCHAR，PostgreSQL 才會在正式環境失敗。"""
    response = client.post(
        "/api/measurement-equipment",
        json=_equipment_payload("E" * 81),
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == {
        "code": "MSA_FIELD_TOO_LONG",
        "message": "equipment_no 超過允許長度",
        "details": {"field": "equipment_no", "max_length": 80},
    }
    assert MeasurementEquipment.query.count() == 0


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


def test_calibration_create_rejects_certificate_from_non_msa_entity(
    client,
    db_session,
    msa_user_headers,
):
    """若 draft 可引用 CAPA 附件，證書證據歸屬無法稽核。"""
    equipment = _create_equipment(client, msa_user_headers)
    attachment = Attachment(
        entity_type="capa",
        entity_id=equipment["id"],
        file_name="wrong.pdf",
        file_path="uploads/capa/1/wrong.pdf",
        mime_type="application/pdf",
        file_size=1,
    )
    db_session.add(attachment)
    db_session.commit()

    response = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(certificate_attachment_id=attachment.id),
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == (
        "MSA_CERTIFICATE_ATTACHMENT_OWNERSHIP_INVALID"
    )
    assert EquipmentCalibrationRecord.query.count() == 0


def test_calibration_create_atomically_rebinds_staged_equipment_certificate(
    client,
    db_session,
    msa_user_headers,
):
    """若設備暫存附件未在建立 draft 時原子轉綁，附件與校驗會斷鏈。"""
    equipment = _create_equipment(client, msa_user_headers)
    attachment = Attachment(
        entity_type="measurement_equipment",
        entity_id=equipment["id"],
        file_name="certificate.pdf",
        file_path=f"uploads/measurement_equipment/{equipment['id']}/certificate.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    db_session.add(attachment)
    db_session.commit()

    response = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(certificate_attachment_id=attachment.id),
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 201
    calibration = response.get_json()["data"]
    db_session.refresh(attachment)
    assert calibration["certificate_attachment_id"] == attachment.id
    assert attachment.entity_type == "equipment_calibration"
    assert attachment.entity_id == calibration["id"]
    bind_audit = AuditLog.query.filter_by(
        module="msa_attachment",
        action="bind_certificate",
        record_id=attachment.id,
    ).one()
    assert bind_audit.new_value["entity_id"] == calibration["id"]


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


def test_calibration_approve_rejects_unknown_payload_fields(
    client,
    msa_user_headers,
):
    """若 approve 靜默忽略未知欄位，呼叫端拼字錯誤可能留下錯誤證據。"""
    equipment = _create_equipment(client, msa_user_headers)
    calibration = client.post(
        f"/api/measurement-equipment/{equipment['id']}/calibrations",
        json=_calibration_payload(),
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]

    response = client.post(
        f"/api/measurement-equipment/calibrations/{calibration['id']}/approve",
        json={
            "expected_status": "draft",
            "reason": "查核完成",
            "unexpected": True,
        },
        headers=msa_user_headers("msa_approve"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "MSA_UNKNOWN_FIELDS"


def test_calibration_approve_binds_only_its_own_draft_attachment(
    client,
    db_session,
    msa_user_headers,
):
    """核准不得引用另一筆 calibration 的證書附件。"""
    first_equipment = _create_equipment(client, msa_user_headers, "EQ-CERT-1")
    second_equipment = _create_equipment(client, msa_user_headers, "EQ-CERT-2")
    first_calibration = client.post(
        f"/api/measurement-equipment/{first_equipment['id']}/calibrations",
        json=_calibration_payload(certificate_no="CERT-FIRST"),
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]
    second_calibration = client.post(
        f"/api/measurement-equipment/{second_equipment['id']}/calibrations",
        json=_calibration_payload(certificate_no="CERT-SECOND"),
        headers=msa_user_headers("msa_manage"),
    ).get_json()["data"]
    attachment = Attachment(
        entity_type="equipment_calibration",
        entity_id=second_calibration["id"],
        file_name="other.pdf",
        file_path="uploads/equipment_calibration/2/other.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    db_session.add(attachment)
    db_session.commit()

    rejected = client.post(
        f"/api/measurement-equipment/calibrations/{first_calibration['id']}/approve",
        json={
            "expected_status": "draft",
            "reason": "不得引用他筆證書",
            "certificate_attachment_id": attachment.id,
        },
        headers=msa_user_headers("msa_approve"),
    )
    assert rejected.status_code == 422
    assert rejected.get_json()["error"]["code"] == (
        "MSA_CERTIFICATE_ATTACHMENT_OWNERSHIP_INVALID"
    )

    attachment.entity_id = first_calibration["id"]
    db_session.commit()
    approved = client.post(
        f"/api/measurement-equipment/calibrations/{first_calibration['id']}/approve",
        json={
            "expected_status": "draft",
            "reason": "證書歸屬查核完成",
            "certificate_attachment_id": attachment.id,
        },
        headers=msa_user_headers("msa_approve"),
    )

    assert approved.status_code == 200
    assert approved.get_json()["data"]["certificate_attachment_id"] == attachment.id


def test_status_event_requires_manage_and_persists_event(
    client,
    db_session,
    msa_user_headers,
):
    """若 execute 可建立設備狀態事件，或事件未落庫，此測試應失敗。"""
    equipment = _create_equipment(client, msa_user_headers)
    payload = {
        "event_type": "maintenance",
        "expected_status": "pending_review",
        "target_status": "maintenance",
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
    assert created.get_json()["data"]["previous_status"] == "pending_review"
    assert created.get_json()["data"]["target_status"] == "maintenance"
    assert EquipmentStatusEvent.query.filter_by(equipment_id=equipment["id"]).count() == 1
    assert (
        db_session.get(MeasurementEquipment, equipment["id"]).status
        == "maintenance"
    )


def test_status_event_rejects_stale_expected_status_without_partial_changes(
    client,
    db_session,
    msa_user_headers,
):
    """若 expected_status 已過期，主檔、事件與 audit 都不得部分寫入。"""
    equipment = _create_equipment(
        client,
        msa_user_headers,
        status="active",
    )

    response = client.post(
        f"/api/measurement-equipment/{equipment['id']}/status-events",
        json={
            "event_type": "maintenance",
            "expected_status": "pending_review",
            "target_status": "maintenance",
            "reason": "畫面狀態已過期",
        },
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "MSA_EQUIPMENT_STATUS_CONFLICT"
    assert (
        db_session.get(MeasurementEquipment, equipment["id"]).status
        == "active"
    )
    assert EquipmentStatusEvent.query.count() == 0
    assert AuditLog.query.filter_by(
        module="msa_equipment",
        action="create_status_event",
    ).count() == 0


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


def test_retire_link_rejects_unknown_payload_fields(
    client,
    db_session,
    msa_user_headers,
):
    """retire payload 的未知欄位不得被靜默忽略。"""
    recorder = Recorder(serial="REC-RETIRE-UNKNOWN", is_active=True)
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

    response = client.post(
        f"/api/measurement-equipment/{equipment['id']}/links/{link['id']}/retire",
        json={
            "expected_link_id": link["id"],
            "expected_status": "current",
            "unexpected": True,
        },
        headers=msa_user_headers("msa_manage"),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "MSA_UNKNOWN_FIELDS"
    assert db_session.get(MeasurementEquipmentLink, link["id"]).is_current is True


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
            "expected_status": "pending_review",
            "target_status": "maintenance",
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
