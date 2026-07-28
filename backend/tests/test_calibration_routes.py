import pytest

from backend.models import (
    AuditLog,
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    Role,
    User,
)
from backend.utils import generate_token


def _authorization(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _template_payload(code: str = "CAL-ROUTE") -> dict:
    return {
        "template_code": code,
        "name": "游標卡尺",
        "equipment_type": "游標卡尺",
        "description": "路由契約測試",
    }


def _point() -> dict:
    return {
        "point_order": 1,
        "point_code": "P01",
        "measurement_mode": "外徑",
        "nominal_value": "10.000",
        "unit": "mm",
        "reference_input_mode": "certified_value",
        "required_repetitions": 3,
        "error_lower_limit": "-0.02",
        "error_upper_limit": "0.02",
        "evaluation_basis": "all_readings",
        "repeatability_rule": "range",
        "repeatability_limit": "0.01",
        "qualification_scope_code": "OD-0-150",
        "qualification_range_start": "0",
        "qualification_range_end": "150",
        "uncertainty_required": False,
        "required": True,
        "instruction": "量測三次",
    }


def _version_payload() -> dict:
    return {
        "procedure_code": "WI-CAL-001",
        "procedure_name": "游標卡尺內校",
        "procedure_description": "依程序執行",
        "default_repetitions": 3,
        "environment_requirements": {},
        "allow_limited_use": True,
        "revision_reason": "初版",
        "points": [_point()],
    }


@pytest.fixture
def calibration_users(db_session):
    roles = [
        Role(
            code="route_viewer",
            name="校正檢視者",
            permissions={"calibration.view": True},
        ),
        Role(
            code="route_manager",
            name="校正管理者",
            permissions={
                "calibration.view": True,
                "calibration.manage": True,
                "calibration.approve": True,
            },
        ),
        Role(
            code="route_approver",
            name="校正核准者",
            permissions={
                "calibration.view": True,
                "calibration.approve": True,
            },
        ),
        Role(
            code="route_no_permission",
            name="無校正權限",
            permissions={"msa.manage": True},
        ),
    ]
    db_session.add_all(roles)
    users = {}
    for key, role, active in [
        ("viewer", "route_viewer", True),
        ("manager", "route_manager", True),
        ("approver", "route_approver", True),
        ("no_permission", "route_no_permission", True),
        ("inactive_manager", "route_manager", False),
    ]:
        user = User(
            username=f"route_{key}",
            password="test-password",
            role=role,
            is_active=active,
        )
        db_session.add(user)
        users[key] = user
    db_session.commit()
    return {
        key: {
            "user": user,
            "token": generate_token(user.id, user.username, user.role),
        }
        for key, user in users.items()
    }


def _create_template(client, token: str, code: str = "CAL-ROUTE") -> dict:
    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(token),
        json=_template_payload(code),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _create_version(client, token: str, template_id: int) -> dict:
    response = client.post(
        f"/api/calibration-templates/{template_id}/versions",
        headers=_authorization(token),
        json=_version_payload(),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _submit_version(client, token: str, version: dict) -> dict:
    response = client.post(
        f"/api/calibration-template-versions/{version['id']}/submit",
        headers=_authorization(token),
        json={
            "expected_version": version["row_version"],
            "reason": "送審",
        },
    )
    assert response.status_code == 200
    return response.get_json()["data"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/calibration-templates"),
        ("post", "/api/calibration-templates"),
    ],
)
def test_template_routes_require_authentication(client, method, path):
    response = getattr(client, method)(
        path,
        json=_template_payload() if method == "post" else None,
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_AUTH_REQUIRED"


def test_list_and_get_return_stable_data_envelopes(
    client,
    calibration_users,
):
    manager_token = calibration_users["manager"]["token"]
    viewer_token = calibration_users["viewer"]["token"]
    template = _create_template(client, manager_token)
    version = _create_version(client, manager_token, template["id"])

    listed = client.get(
        "/api/calibration-templates?page=1&page_size=25",
        headers=_authorization(viewer_token),
    )
    detail = client.get(
        f"/api/calibration-templates/{template['id']}",
        headers=_authorization(viewer_token),
    )

    assert listed.status_code == 200
    assert listed.get_json()["data"]["total"] == 1
    listed_item = listed.get_json()["data"]["items"][0]
    assert listed_item["id"] == template["id"]
    assert listed_item["current_approved_version"] is None
    assert "versions" not in listed_item
    assert detail.status_code == 200
    assert detail.get_json()["data"]["versions"][0]["id"] == version["id"]
    assert (
        detail.get_json()["data"]["versions"][0]["points"][0]["nominal_value"]
        == "10"
    )


def test_missing_template_returns_stable_404(client, calibration_users):
    response = client.get(
        "/api/calibration-templates/999999",
        headers=_authorization(calibration_users["viewer"]["token"]),
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == {
        "code": "CALIBRATION_TEMPLATE_NOT_FOUND",
        "message": "找不到校正模板",
        "details": {"template_id": 999999},
    }


@pytest.mark.parametrize("payload", [[], "text", 7, None])
def test_create_rejects_non_object_json_with_422_and_zero_writes(
    client,
    calibration_users,
    db_session,
    payload,
):
    request_args = (
        {"data": "null", "content_type": "application/json"}
        if payload is None
        else {"json": payload}
    )
    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(calibration_users["manager"]["token"]),
        **request_args,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_PAYLOAD_INVALID"
    assert CalibrationTemplate.query.count() == 0


def test_manage_permission_is_required_before_template_write(
    client,
    calibration_users,
):
    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(calibration_users["no_permission"]["token"]),
        json=_template_payload(),
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == {
        "code": "CALIBRATION_PERMISSION_DENIED",
        "message": "權限不足",
        "details": {"permission": "calibration.manage"},
    }
    assert CalibrationTemplate.query.count() == 0


def test_inactive_jwt_is_rejected_before_template_write(
    client,
    calibration_users,
):
    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(
            calibration_users["inactive_manager"]["token"]
        ),
        json=_template_payload(),
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_USER_INACTIVE"
    assert CalibrationTemplate.query.count() == 0


def test_create_template_and_version_return_201(
    client,
    calibration_users,
):
    token = calibration_users["manager"]["token"]

    template = _create_template(client, token)
    version = _create_version(client, token, template["id"])

    assert template["status"] == "active"
    assert version["status"] == "draft"
    assert version["row_version"] == 1
    assert CalibrationTemplate.query.count() == 1
    assert CalibrationTemplateVersion.query.count() == 1
    assert CalibrationTemplatePoint.query.count() == 1


def test_create_version_environment_key_collision_returns_422_and_zero_writes(
    client,
    calibration_users,
):
    token = calibration_users["manager"]["token"]
    template = _create_template(client, token, code="CAL-ROUTE-ENV-CREATE")
    audit_count = AuditLog.query.count()
    payload = _version_payload()
    payload["environment_requirements"] = {
        " temperature ": {"required": True},
        "temperature": {"required": False},
    }

    response = client.post(
        f"/api/calibration-templates/{template['id']}/versions",
        headers=_authorization(token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == {
        "code": "CALIBRATION_FIELD_INVALID",
        "message": "環境要求名稱正規化後不可重複",
        "details": {
            "field": "environment_requirements",
            "requirement": "temperature",
        },
    }
    assert CalibrationTemplateVersion.query.count() == 0
    assert CalibrationTemplatePoint.query.count() == 0
    assert AuditLog.query.count() == audit_count


def test_patch_version_environment_key_collision_returns_422_and_zero_writes(
    client,
    calibration_users,
    db_session,
):
    token = calibration_users["manager"]["token"]
    template = _create_template(client, token, code="CAL-ROUTE-ENV-UPDATE")
    version = _create_version(client, token, template["id"])
    persisted_before = db_session.get(CalibrationTemplateVersion, version["id"])
    original_environment = dict(persisted_before.environment_requirements)
    original_point_ids = [point.id for point in persisted_before.points]
    audit_count = AuditLog.query.count()

    response = client.patch(
        f"/api/calibration-template-versions/{version['id']}",
        headers=_authorization(token),
        json={
            "expected_version": version["row_version"],
            "environment_requirements": {
                " temperature ": {"required": True},
                "temperature": {"required": False},
            },
        },
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == {
        "code": "CALIBRATION_FIELD_INVALID",
        "message": "環境要求名稱正規化後不可重複",
        "details": {
            "field": "environment_requirements",
            "requirement": "temperature",
        },
    }
    db_session.expire_all()
    persisted = db_session.get(CalibrationTemplateVersion, version["id"])
    assert persisted.environment_requirements == original_environment
    assert persisted.row_version == version["row_version"]
    assert [point.id for point in persisted.points] == original_point_ids
    assert AuditLog.query.count() == audit_count


def test_patch_version_returns_200_and_conflict_returns_409(
    client,
    calibration_users,
    db_session,
):
    token = calibration_users["manager"]["token"]
    template = _create_template(client, token)
    version = _create_version(client, token, template["id"])

    updated = client.patch(
        f"/api/calibration-template-versions/{version['id']}",
        headers=_authorization(token),
        json={
            "expected_version": version["row_version"],
            "procedure_name": "更新後程序",
        },
    )
    stale = client.patch(
        f"/api/calibration-template-versions/{version['id']}",
        headers=_authorization(token),
        json={
            "expected_version": version["row_version"],
            "procedure_name": "不得覆寫",
        },
    )

    assert updated.status_code == 200
    assert updated.get_json()["data"]["row_version"] == 2
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "CALIBRATION_VERSION_CONFLICT"
    persisted = db_session.get(CalibrationTemplateVersion, version["id"])
    assert persisted.procedure_name == "更新後程序"


def test_submit_self_approve_and_other_approve_enforce_zero_write_boundaries(
    client,
    calibration_users,
    db_session,
):
    manager = calibration_users["manager"]
    approver = calibration_users["approver"]
    template = _create_template(client, manager["token"])
    draft = _create_version(client, manager["token"], template["id"])
    submitted = _submit_version(client, manager["token"], draft)

    denied = client.post(
        f"/api/calibration-template-versions/{submitted['id']}/approve",
        headers=_authorization(manager["token"]),
        json={
            "expected_version": submitted["row_version"],
            "reason": "自行核准",
        },
    )

    assert denied.status_code == 403
    assert (
        denied.get_json()["error"]["code"]
        == "CALIBRATION_SELF_APPROVAL_FORBIDDEN"
    )
    persisted = db_session.get(CalibrationTemplateVersion, submitted["id"])
    assert persisted.status == "submitted"
    assert persisted.row_version == submitted["row_version"]
    assert db_session.get(
        CalibrationTemplate,
        template["id"]
    ).current_approved_version_id is None

    approved = client.post(
        f"/api/calibration-template-versions/{submitted['id']}/approve",
        headers=_authorization(approver["token"]),
        json={
            "expected_version": submitted["row_version"],
            "reason": "內容符合程序",
        },
    )
    assert approved.status_code == 200
    assert approved.get_json()["data"]["status"] == "approved"
    assert (
        db_session.get(CalibrationTemplate, template["id"])
        .current_approved_version_id
        == submitted["id"]
    )


def test_reject_endpoint_accepts_only_submitted_version(
    client,
    calibration_users,
):
    manager_token = calibration_users["manager"]["token"]
    approver_token = calibration_users["approver"]["token"]
    template = _create_template(client, manager_token)
    draft = _create_version(client, manager_token, template["id"])

    conflict = client.post(
        f"/api/calibration-template-versions/{draft['id']}/reject",
        headers=_authorization(approver_token),
        json={"expected_version": draft["row_version"], "reason": "退回"},
    )
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["code"] == "CALIBRATION_STATUS_CONFLICT"

    submitted = _submit_version(client, manager_token, draft)
    rejected = client.post(
        f"/api/calibration-template-versions/{submitted['id']}/reject",
        headers=_authorization(approver_token),
        json={
            "expected_version": submitted["row_version"],
            "reason": "量程證據不足",
        },
    )
    assert rejected.status_code == 200
    assert rejected.get_json()["data"]["status"] == "rejected"
    assert (
        rejected.get_json()["data"]["rejection_reason"]
        == "量程證據不足"
    )


@pytest.mark.parametrize(
    "query",
    [
        "page=" + "9" * 10_000,
        "page=10001",
        "page_size=" + "9" * 10_000,
        "page_size=101",
    ],
)
def test_huge_or_out_of_range_pagination_returns_422_not_500(
    client,
    calibration_users,
    query,
):
    response = client.get(
        f"/api/calibration-templates?{query}",
        headers=_authorization(calibration_users["viewer"]["token"]),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] in {
        "CALIBRATION_PAGE_INVALID",
        "CALIBRATION_PAGE_SIZE_INVALID",
    }
