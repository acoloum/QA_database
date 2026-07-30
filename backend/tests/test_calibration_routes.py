import pytest

from backend.models import (
    AuditLog,
    CalibrationReferenceSnapshot,
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


def test_template_list_searches_code_name_and_equipment_type(
    client,
    calibration_users,
):
    """前端搜尋不得因查詢契約漂移而回未知欄位錯誤。"""
    manager_token = calibration_users["manager"]["token"]
    viewer_token = calibration_users["viewer"]["token"]
    _create_template(client, manager_token, "CAL-MICROMETER")
    second = client.post(
        "/api/calibration-templates",
        headers=_authorization(manager_token),
        json={
            **_template_payload("CAL-CALIPER"),
            "name": "量測室游標卡尺",
            "equipment_type": "環規",
        },
    )
    assert second.status_code == 201

    by_code = client.get(
        "/api/calibration-templates?search=MICROMETER",
        headers=_authorization(viewer_token),
    )
    by_name = client.get(
        "/api/calibration-templates?search=量測室",
        headers=_authorization(viewer_token),
    )
    by_type = client.get(
        "/api/calibration-templates?search=環規",
        headers=_authorization(viewer_token),
    )

    assert by_code.status_code == 200
    assert [item["template_code"] for item in by_code.get_json()["data"]["items"]] == [
        "CAL-MICROMETER"
    ]
    assert by_name.status_code == 200
    assert by_name.get_json()["data"]["total"] == 1
    assert by_type.status_code == 200
    assert by_type.get_json()["data"]["total"] == 1


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


def test_patch_replacement_points_persists_new_response_database_and_audit(
    client,
    calibration_users,
    db_session,
):
    token = calibration_users["manager"]["token"]
    template = _create_template(client, token, code="CAL-ROUTE-AUDIT-REPLACE")
    version = _create_version(client, token, template["id"])
    replacement = _point()
    replacement.update(
        {
            "point_order": 2,
            "point_code": "P02",
            "nominal_value": "20",
        }
    )

    response = client.patch(
        f"/api/calibration-template-versions/{version['id']}",
        headers=_authorization(token),
        json={
            "expected_version": version["row_version"],
            "points": [replacement],
        },
    )

    assert response.status_code == 200
    assert [
        point["point_code"] for point in response.get_json()["data"]["points"]
    ] == ["P02"]
    db_session.expire_all()
    persisted = db_session.get(CalibrationTemplateVersion, version["id"])
    assert [point.point_code for point in persisted.points] == ["P02"]
    audit = AuditLog.query.filter_by(
        action="update_version",
        module="calibration_template",
        record_id=version["id"],
    ).one()
    assert [
        point["point_code"] for point in audit.old_value["points"]
    ] == ["P01"]
    assert [
        point["point_code"] for point in audit.new_value["points"]
    ] == ["P02"]


def test_patch_empty_points_persists_empty_response_database_and_audit(
    client,
    calibration_users,
    db_session,
):
    token = calibration_users["manager"]["token"]
    template = _create_template(client, token, code="CAL-ROUTE-AUDIT-EMPTY")
    version = _create_version(client, token, template["id"])

    response = client.patch(
        f"/api/calibration-template-versions/{version['id']}",
        headers=_authorization(token),
        json={
            "expected_version": version["row_version"],
            "points": [],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["points"] == []
    assert CalibrationTemplatePoint.query.filter_by(
        template_version_id=version["id"]
    ).count() == 0
    audit = AuditLog.query.filter_by(
        action="update_version",
        module="calibration_template",
        record_id=version["id"],
    ).one()
    assert [
        point["point_code"] for point in audit.old_value["points"]
    ] == ["P01"]
    assert audit.new_value["points"] == []


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


# ============================================================
# 校正紀錄 API 契約測試
# ============================================================

from datetime import date, timedelta
from decimal import Decimal

from backend.models import (
    CalibrationReferenceSnapshot,
    EquipmentCalibrationRecord,
    EquipmentCalibrationPoint,
    MeasurementEquipment,
)


def _calibration_payload(code: str = "CAL-REC") -> dict:
    return {
        "equipment_id": 1,  # 會在測試中替換
        "template_version_id": 1,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": 1,
    }


def _reading_patch_version_payload() -> dict:
    return {
        "expected_version": 1,
        "calibration_location": "新位置",
    }


def _readings_payload(point_id: int) -> dict:
    return {
        "expected_version": 1,
        "points": [
            {
                "point_id": point_id,
                "reference_value": "10.000",
                "expanded_uncertainty": "0.003",
                "coverage_factor": "2",
                "readings": [
                    {"trial_no": 1, "indicated_value": "10.010"},
                    {"trial_no": 2, "indicated_value": "10.020"},
                    {"trial_no": 3, "indicated_value": "10.000"},
                ],
            }
        ],
    }


def _validate_payload() -> dict:
    return {}


def _decision_payload(reason: str = "理由") -> dict:
    return {
        "expected_version": 1,
        "reason": reason,
    }


def _create_approved_template_and_version(db_session, calibration_users):
    """建立已核准的模板與版本（用於校正記錄測試）。透過服務層走完整流程。"""
    from backend.services.calibration_template_service import CalibrationTemplateService
    import uuid

    manager_user = calibration_users["manager"]["user"]
    approver_user = calibration_users["approver"]["user"]

    # 使用唯一的模板代碼避免並行測試衝突
    unique_suffix = uuid.uuid4().hex[:8]
    template_code = f"CAL-REC-TEST-{unique_suffix}"

    template = CalibrationTemplate(
        template_code=template_code,
        name="記錄測試模板",
        equipment_type="游標卡尺",
        status="active",
    )
    db_session.add(template)
    db_session.flush()

    # 用服務層建立版本
    version = CalibrationTemplateService.create_version(
        template.id,
        {
            "procedure_code": f"WI-CAL-REC-{unique_suffix}",
            "procedure_name": "記錄測試程序",
            "default_repetitions": 3,
            "environment_requirements": {"temperature": {"required": True, "unit": "°C"}},
            "allow_limited_use": False,
            "revision_reason": "初版",
            "points": [
                {
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
                    "repeatability_limit": "0.03",
                    "qualification_scope_code": "OD-0-150",
                    "qualification_range_start": "0",
                    "qualification_range_end": "150",
                    "uncertainty_required": False,
                    "required": True,
                }
            ],
        },
        actor_id=manager_user.id,
    )
    version_obj = db_session.get(CalibrationTemplateVersion, version["id"])

    # 送審
    CalibrationTemplateService.submit_version(
        version_obj.id,
        {"expected_version": 1, "reason": "送審"},
        actor_id=manager_user.id,
    )

    # 核准（用不同使用者避免自我核准）
    CalibrationTemplateService.approve_version(
        version_obj.id,
        {"expected_version": 2, "reason": "核准"},
        actor_id=approver_user.id,
    )

    db_session.commit()
    return db_session.get(CalibrationTemplate, template.id), db_session.get(CalibrationTemplateVersion, version_obj.id)


def _create_equipment(db_session, equipment_no: str, name: str, equipment_type: str = "游標卡尺", is_ref: bool = False, status: str = "active"):
    eq = MeasurementEquipment(
        equipment_no=equipment_no,
        name=name,
        equipment_type=equipment_type,
        is_reference_standard=is_ref,
        status=status,
        calibration_interval_months=12,
    )
    db_session.add(eq)
    db_session.flush()
    return eq


def _create_approved_calibration(db_session, equipment_id: int, calibration_date: date, result: str = "pass"):
    from datetime import timedelta
    next_due = calibration_date + timedelta(days=365)
    record = EquipmentCalibrationRecord(
        equipment_id=equipment_id,
        calibration_type="internal",
        calibration_date=calibration_date,
        next_due_date=next_due,
        result=result,
        data_level="summary_legacy",
        status="approved",
        approved_by=1,
        approved_at=date.today(),
    )
    db_session.add(record)
    db_session.flush()
    return record


@pytest.fixture
def calibration_record_setup(db_session, calibration_users):
    """建立完整的校正記錄測試環境。"""
    manager = calibration_users["manager"]
    approver = calibration_users["approver"]

    template, version = _create_approved_template_and_version(db_session, calibration_users)

    equipment = _create_equipment(db_session, "EQ-REC-01", "記錄測試卡尺")
    ref_equipment = _create_equipment(db_session, "REF-REC-01", "參考環規", is_ref=True)
    _create_approved_calibration(db_session, ref_equipment.id, date.today(), "pass")
    db_session.commit()

    return {
        "manager": {
            "user": manager["user"],
            "token": manager["token"],
        },
        "approver": {
            "user": approver["user"],
            "token": approver["token"],
        },
        "template": template,
        "version": version,
        "equipment": equipment,
        "ref_equipment": ref_equipment,
    }


def test_list_calibrations_requires_authentication(client):
    response = client.get("/api/calibrations")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_AUTH_REQUIRED"


def test_create_calibration_requires_calibration_execute_permission(client, calibration_users):
    response = client.post(
        "/api/calibrations",
        headers=_authorization(calibration_users["no_permission"]["token"]),
        json={},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "CALIBRATION_PERMISSION_DENIED"
    assert response.get_json()["error"]["details"]["permission"] == "calibration.execute"


def test_create_calibration_rejects_inactive_user(client, calibration_users):
    response = client.post(
        "/api/calibrations",
        headers=_authorization(calibration_users["inactive_manager"]["token"]),
        json={},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_USER_INACTIVE"


def test_create_calibration_internal_draft_instantiates_points(
    client, calibration_record_setup
):
    """內校草稿應從核准模板實例化點位與讀值。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    payload = {
        "equipment_id": setup["equipment"].id,
        "template_version_id": setup["version"].id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": setup["ref_equipment"].id,
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["data_level"] == "detailed"
    assert data["status"] == "draft"
    assert data["template_version_id"] == setup["version"].id
    assert data["reference_standard_equipment_id"] == setup["ref_equipment"].id
    assert len(data["points"]) == 1
    assert data["points"][0]["point_code"] == "P01"
    assert data["points"][0]["required_repetitions"] == 3
    assert len(data["points"][0]["readings"]) == 3
    assert all(r["result"] == "pending" for r in data["points"][0]["readings"])


def test_create_calibration_external_draft_allows_missing_certificate(
    client, calibration_record_setup
):
    """外校草稿可先不填證書。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    payload = {
        "equipment_id": setup["equipment"].id,
        "template_version_id": setup["version"].id,
        "calibration_type": "external",
        "calibration_date": date.today().isoformat(),
        "calibration_provider": "校正實驗室 A",
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["calibration_type"] == "external"
    assert data["reference_standard_equipment_id"] is None
    assert data.get("certificate_attachment_id") is None
    audit = AuditLog.query.filter_by(
        module="equipment_calibration",
        record_id=data["id"],
    ).one()
    assert audit.action == "create_calibration"


def test_create_calibration_template_not_approved_rejected(
    client, calibration_users, db_session
):
    """未核准的模板版本應拒絕建立草稿。"""
    manager_token = calibration_users["manager"]["token"]

    # 建立草稿模板
    template = CalibrationTemplate(
        template_code="CAL-REC-DRAFT",
        name="草稿模板",
        equipment_type="游標卡尺",
        status="active",
    )
    db_session.add(template)
    db_session.flush()

    version = CalibrationTemplateVersion(
        template_id=template.id,
        version_no=1,
        procedure_code="WI-CAL-DRAFT",
        procedure_name="草稿程序",
        default_repetitions=3,
        environment_requirements={},
        allow_limited_use=False,
        status="draft",  # 未核准
        row_version=1,
        created_by=1,
    )
    db_session.add(version)
    db_session.commit()

    equipment = _create_equipment(db_session, "EQ-REC-REJECT", "拒絕卡尺")

    payload = {
        "equipment_id": equipment.id,
        "template_version_id": version.id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": 1,
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_STATUS_CONFLICT"
    assert "只有核准版本可用於建立詳細校正" in response.get_json()["error"]["message"]


def test_create_calibration_equipment_type_mismatch_rejected(
    client, calibration_record_setup, db_session
):
    """設備類型與模板不符應拒絕。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    equipment = _create_equipment(db_session, "EQ-REC-TYPE", "錯誤類型", equipment_type="環規")

    payload = {
        "equipment_id": equipment.id,
        "template_version_id": setup["version"].id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": setup["ref_equipment"].id,
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_STATUS_CONFLICT"
    assert "受校設備類型與模板適用類型不符" in response.get_json()["error"]["message"]


def test_create_calibration_inactive_equipment_rejected(
    client, calibration_record_setup, db_session
):
    """停用設備應拒絕。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    equipment = _create_equipment(db_session, "EQ-REC-INACTIVE", "停用卡尺", status="inactive")

    payload = {
        "equipment_id": equipment.id,
        "template_version_id": setup["version"].id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": setup["ref_equipment"].id,
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_STATUS_CONFLICT"
    assert "受校設備狀態非啟用" in response.get_json()["error"]["message"]


def test_create_calibration_internal_missing_reference_rejected(
    client, calibration_record_setup, db_session
):
    """內校缺少參考標準器應拒絕。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    equipment = _create_equipment(db_session, "EQ-REC-NO-REF", "缺標準器卡尺")

    payload = {
        "equipment_id": equipment.id,
        "template_version_id": setup["version"].id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_REFERENCE_REQUIRED"


def test_create_calibration_reference_standard_not_usable_rejected(
    client, calibration_record_setup, db_session
):
    """不可用的參考標準器應拒絕。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    equipment = _create_equipment(db_session, "EQ-REC-REF-FAIL", "參考器失效卡尺")

    # 建立參考標準器但校正失效
    ref_equipment = _create_equipment(db_session, "REF-FAIL-REC", "失效參考器", is_ref=True)
    _create_approved_calibration(db_session, ref_equipment.id, date.today() - timedelta(days=400), "fail")
    db_session.commit()

    payload = {
        "equipment_id": equipment.id,
        "template_version_id": setup["version"].id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": ref_equipment.id,
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_REFERENCE_INVALID"


def test_create_calibration_equipment_cannot_be_own_reference(
    client, calibration_record_setup, db_session
):
    """受校設備不能同時作為自己的標準器。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    equipment = _create_equipment(
        db_session, "EQ-REC-SELF", "自循環卡尺", is_ref=True
    )
    _create_approved_calibration(db_session, equipment.id, date.today(), "pass")
    db_session.commit()

    payload = {
        "equipment_id": equipment.id,
        "template_version_id": setup["version"].id,
        "calibration_type": "internal",
        "calibration_date": date.today().isoformat(),
        "reference_standard_equipment_id": equipment.id,
    }

    response = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_REFERENCE_INVALID"
    assert "受校設備不能同時作為自己的參考標準器" in response.get_json()["error"]["message"]


def test_get_calibration_requires_authentication(client):
    response = client.get("/api/calibrations/1")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_AUTH_REQUIRED"


def test_get_calibration_returns_full_detail(client, calibration_record_setup):
    """取得校正紀錄應回傳完整細節。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    # 先建立草稿
    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record_id = create_resp.get_json()["data"]["id"]

    # 取得詳細資料
    response = client.get(
        f"/api/calibrations/{record_id}",
        headers=_authorization(manager_token),
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["id"] == record_id
    assert "points" in data
    assert "readings" in data["points"][0]
    assert "reference_snapshots" in data


def test_patch_calibration_update_environment_conditions(
    client, calibration_record_setup, db_session
):
    """更新草稿環境條件應成功。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    expected_version = record["row_version"]

    # 更新環境條件
    response = client.patch(
        f"/api/calibrations/{record_id}",
        headers=_authorization(manager_token),
        json={
            "expected_version": expected_version,
            "environment_conditions": {"temperature": {"value": "23.5", "unit": "°C"}},
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["row_version"] == expected_version + 1
    assert data["environment_conditions"]["temperature"]["value"] == "23.5"


def test_patch_calibration_submitted_rejected(client, calibration_record_setup, db_session):
    """已送審狀態不可更新。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]

    # 直接修改資料庫狀態模擬送審
    record_obj = db_session.get(EquipmentCalibrationRecord, record_id)
    record_obj.status = "submitted"
    record_obj.row_version += 1
    db_session.commit()

    response = client.patch(
        f"/api/calibrations/{record_id}",
        headers=_authorization(manager_token),
        json={
            "expected_version": record_obj.row_version,
            "environment_conditions": {},
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CALIBRATION_STATUS_CONFLICT"
    assert "目前狀態不可編輯" in response.get_json()["error"]["message"]


def test_patch_calibration_version_conflict_rejected(
    client, calibration_record_setup, db_session
):
    """版本衝突應回 409。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    stale_version = record["row_version"]

    # 先更新一次
    client.patch(
        f"/api/calibrations/{record_id}",
        headers=_authorization(manager_token),
        json={
            "expected_version": stale_version,
            "calibration_location": "新位置",
        },
    )

    # 再用舊版本號更新應失敗
    response = client.patch(
        f"/api/calibrations/{record_id}",
        headers=_authorization(manager_token),
        json={
            "expected_version": stale_version,
            "calibration_location": "舊位置",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CALIBRATION_VERSION_CONFLICT"


def test_save_readings_recalculates_and_persists_evidence(
    client, calibration_record_setup, db_session
):
    """保存讀值應觸發後端重算並持久化證據。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]
    expected_version = record["row_version"]

    # 保存讀值
    response = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": expected_version,
            "points": [
                {
                    "point_id": point_id,
                    "reference_value": "10.000",
                    "expanded_uncertainty": "0.003",
                    "coverage_factor": "2",
                    "readings": [
                        {"trial_no": 1, "indicated_value": "10.010"},
                        {"trial_no": 2, "indicated_value": "10.020"},
                        {"trial_no": 3, "indicated_value": "10.000"},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["result"] == "pass"
    assert data["status"] == "in_progress"
    assert data["row_version"] == expected_version + 1
    assert data["data_hash"] is not None

    point = data["points"][0]
    assert point["mean_error"] == "0.0100000000"
    assert point["mean_correction"] == "-0.0100000000"
    assert point["result"] == "pass"


def test_save_readings_paired_reading_calculates_correctly(
    client, calibration_record_setup, db_session
):
    """paired_reading 模式應使用各自標準器讀值。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    # 建立 paired_reading 模板（透過服務層走完整流程）
    from backend.services.calibration_template_service import CalibrationTemplateService
    import uuid
    unique_suffix = uuid.uuid4().hex[:8]

    template = CalibrationTemplate(
        template_code=f"CAL-PAIRED-ROUTE-{unique_suffix}",
        name="雙讀值路由模板",
        equipment_type="游標卡尺",
        status="active",
    )
    db_session.add(template)
    db_session.flush()

    # 用服務層建立版本
    version = CalibrationTemplateService.create_version(
        template.id,
        {
            "procedure_code": f"WI-CAL-PAIRED-{unique_suffix}",
            "procedure_name": "雙讀值程序",
            "default_repetitions": 3,
            "environment_requirements": {},
            "allow_limited_use": False,
            "revision_reason": "初版",
            "points": [
                {
                    "point_order": 1,
                    "point_code": "P01",
                    "measurement_mode": "外徑",
                    "nominal_value": "10.000",
                    "unit": "mm",
                    "reference_input_mode": "paired_reading",
                    "required_repetitions": 3,
                    "error_lower_limit": "-0.02",
                    "error_upper_limit": "0.02",
                    "evaluation_basis": "all_readings",
                    "repeatability_rule": "range",
"repeatability_limit": "0.02",
                    "qualification_scope_code": "OD-0-150",
                    "qualification_range_start": "0",
                    "qualification_range_end": "150",
                    "uncertainty_required": False,
                    "required": True,
                }
            ],
        },
        actor_id=1,
    )
    version_obj = db_session.get(CalibrationTemplateVersion, version["id"])

    # 送審
    CalibrationTemplateService.submit_version(
        version_obj.id,
        {"expected_version": 1, "reason": "送審"},
        actor_id=1,
    )

    # 核准（用不同使用者避免自我核准）
    CalibrationTemplateService.approve_version(
        version_obj.id,
        {"expected_version": 2, "reason": "核准"},
        actor_id=2,
    )

    db_session.commit()

    equipment = _create_equipment(db_session, "EQ-PAIRED-ROUTE", "雙讀值卡尺")
    ref_equipment = _create_equipment(db_session, "REF-PAIRED-ROUTE", "參考環規", is_ref=True)
    _create_approved_calibration(db_session, ref_equipment.id, date.today(), "pass")
    db_session.commit()

    version_obj = db_session.get(CalibrationTemplateVersion, version_obj.id)

    # 建立草稿
    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": equipment.id,
            "template_version_id": version_obj.id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": ref_equipment.id,
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]
    expected_version = record["row_version"]

    # paired_reading：每筆提供 standard_reading
    response = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": expected_version,
            "points": [
                {
                    "point_id": point_id,
                    "readings": [
                        {
                            "trial_no": 1,
                            "indicated_value": "10.015",
                            "standard_reading": "10.000",
                        },
                        {
                            "trial_no": 2,
                            "indicated_value": "10.025",
                            "standard_reading": "10.005",
                        },
                        {
                            "trial_no": 3,
                            "indicated_value": "10.005",
                            "standard_reading": "10.000",
                        },
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["result"] == "pass"

    point_data = data["points"][0]
    readings = point_data["readings"]
    assert readings[0]["effective_reference"] == "10.0000000000"
    assert readings[1]["effective_reference"] == "10.0050000000"
    assert readings[2]["effective_reference"] == "10.0000000000"


def test_save_readings_unknown_point_id_rejected(client, calibration_record_setup):
    """不存在的 point_id 應拒絕整批。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    expected_version = record["row_version"]

    response = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": expected_version,
            "points": [
                {
                    "point_id": 999999,
                    "readings": [{"trial_no": 1, "indicated_value": "10.010"}],
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_POINT_INVALID"
    assert "校正點不屬於此校正紀錄" in response.get_json()["error"]["message"]


def test_save_readings_submitted_record_cannot_save(client, calibration_record_setup, db_session):
    """已送審紀錄不可保存讀值。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]

    # 修改資料庫狀態
    record_obj = db_session.get(EquipmentCalibrationRecord, record_id)
    record_obj.status = "submitted"
    record_obj.row_version += 1
    db_session.commit()

    response = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": record_obj.row_version,
            "points": [
                {
                    "point_id": record_obj.calibration_points[0].id,
                    "readings": [{"trial_no": 1, "indicated_value": "10.010"}],
                }
            ],
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CALIBRATION_STATUS_CONFLICT"
    assert "目前狀態不可編輯" in response.get_json()["error"]["message"]


def test_validate_calibration_returns_blockers_when_incomplete(
    client, calibration_record_setup
):
    """未填讀值時驗證應回傳 blockers。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    created = create_resp.get_json()["data"]
    record_id = created["id"]

    # 尚未保存讀值，驗證
    response = client.post(
        f"/api/calibrations/{record_id}/validate",
        headers=_authorization(manager_token),
        json={"expected_version": created["row_version"]},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["result"] == "pending"
    assert "CALIBRATION_READING_MISSING" in data["blockers"]


def test_validate_route_rejects_stale_version_then_accepts_current_version(
    client,
    calibration_record_setup,
    db_session,
):
    """route 必須把 expected_version 傳入 service 並保留穩定 conflict。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]
    created = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    ).get_json()["data"]
    saved_response = client.put(
        f"/api/calibrations/{created['id']}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": created["row_version"],
            "points": [{
                "point_id": created["points"][0]["id"],
                "reference_value": "10.000",
                "readings": [
                    {"trial_no": 1, "indicated_value": "10.001"},
                    {"trial_no": 2, "indicated_value": "10.002"},
                    {"trial_no": 3, "indicated_value": "10.003"},
                ],
            }],
        },
    )
    assert saved_response.status_code == 200
    saved = saved_response.get_json()["data"]

    missing = client.post(
        f"/api/calibrations/{created['id']}/validate",
        headers=_authorization(manager_token),
        json={},
    )
    stale = client.post(
        f"/api/calibrations/{created['id']}/validate",
        headers=_authorization(manager_token),
        json={"expected_version": saved["row_version"] - 1},
    )
    current = client.post(
        f"/api/calibrations/{created['id']}/validate",
        headers=_authorization(manager_token),
        json={"expected_version": saved["row_version"]},
    )

    assert missing.status_code == 422
    assert missing.get_json()["error"] == {
        "code": "CALIBRATION_FIELD_INVALID",
        "message": "expected_version 必須是整數",
        "details": {"field": "expected_version"},
    }
    assert stale.status_code == 409
    assert stale.get_json()["error"] == {
        "code": "CALIBRATION_VERSION_CONFLICT",
        "message": "校正紀錄已被其他人更新，請重新載入",
        "details": {
            "calibration_id": created["id"],
            "current_version": saved["row_version"],
            "expected_version": saved["row_version"] - 1,
        },
    }
    assert current.status_code == 200
    assert current.get_json()["data"]["row_version"] == saved["row_version"] + 1
    persisted = db_session.get(EquipmentCalibrationRecord, created["id"])
    assert persisted.status == "ready_for_submission"
    assert persisted.row_version == saved["row_version"] + 1


def test_validate_calibration_pass_sets_ready_for_submission(
    client, calibration_record_setup, db_session
):
    """全部合格時驗證應將狀態設為 ready_for_submission。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]

    # 保存合格讀值
    save_resp = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": record["row_version"],
            "points": [
                {
                    "point_id": point_id,
                    "reference_value": "10.000",
                    "readings": [
                        {"trial_no": 1, "indicated_value": "10.010"},
                        {"trial_no": 2, "indicated_value": "10.005"},
                        {"trial_no": 3, "indicated_value": "10.000"},
                    ],
                }
            ],
        },
    )

    # 驗證
    response = client.post(
        f"/api/calibrations/{record_id}/validate",
        headers=_authorization(manager_token),
        json={
            "expected_version": save_resp.get_json()["data"]["row_version"],
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["result"] == "pass"
    assert data["blockers"] == []

    # 狀態應變為 ready_for_submission
    record_obj = db_session.get(EquipmentCalibrationRecord, record_id)
    assert record_obj.status == "ready_for_submission"


# Submit, Approve, Reject, Void tests
def test_submit_calibration_internal_revalidates_reference_standard(
    client, calibration_record_setup, db_session
):
    """送審內校應重新驗證參考標準器。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]

    # 保存合格讀值
    save_resp = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": record["row_version"],
            "points": [
                {
                    "point_id": point_id,
                    "reference_value": "10.000",
                    "readings": [
                        {"trial_no": 1, "indicated_value": "10.010"},
                        {"trial_no": 2, "indicated_value": "10.005"},
                        {"trial_no": 3, "indicated_value": "10.000"},
                    ],
                }
            ],
        },
    )
    saved_record = save_resp.get_json()["data"]
    # 驗證並送審
    validate_resp = client.post(
        f"/api/calibrations/{record_id}/validate",
        headers=_authorization(manager_token),
        json={"expected_version": saved_record["row_version"]},
    )
    validated_record = validate_resp.get_json()["data"]

    response = client.post(
        f"/api/calibrations/{record_id}/submit",
        headers=_authorization(manager_token),
        json={
            "expected_version": validated_record["row_version"],
            "reason": "送交審查",
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "submitted"
    assert data["submitted_by"] == setup["manager"]["user"].id
    assert len(data["reference_snapshots"]) == 1

    snapshot = db_session.get(
        CalibrationReferenceSnapshot,
        data["reference_snapshots"][0]["id"],
    )
    snapshot.name = "竄改後名稱"
    with pytest.raises(ValueError, match="參考標準器快照"):
        db_session.commit()
    db_session.rollback()


def test_submit_calibration_external_requires_certificate(client, calibration_record_setup):
    """外校送審必須上傳證書附件。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "external",
            "calibration_date": date.today().isoformat(),
            "calibration_provider": "外校實驗室",
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]

    # 保存讀值（外校也需要讀值以產生計算摘要）
    save_resp = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": record["row_version"],
            "points": [
                {
                    "point_id": point_id,
                    "reference_value": "10.000",
                    "readings": [
                        {"trial_no": 1, "indicated_value": "10.010"},
                        {"trial_no": 2, "indicated_value": "10.005"},
                        {"trial_no": 3, "indicated_value": "10.000"},
                    ],
                }
            ],
        },
    )

    # 驗證
    validate_resp = client.post(
        f"/api/calibrations/{record_id}/validate",
        headers=_authorization(manager_token),
        json={
            "expected_version": save_resp.get_json()["data"]["row_version"],
        },
    )
    validated_record = validate_resp.get_json()["data"]

    # 送審（無證書附件）
    response = client.post(
        f"/api/calibrations/{record_id}/submit",
        headers=_authorization(manager_token),
        json={
            "expected_version": validated_record["row_version"],
            "reason": "送交外校證書審查",
        },
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "CALIBRATION_CERTIFICATE_REQUIRED"


def test_approve_calibration_self_approval_forbidden(client, calibration_record_setup):
    """建立者、輸入者、送審者不可核准自己的校正紀錄。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]
    approver_token = setup["approver"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]

    # 保存合格讀值
    save_resp = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": record["row_version"],
            "points": [
                {
                    "point_id": point_id,
                    "reference_value": "10.000",
                    "readings": [
                        {"trial_no": 1, "indicated_value": "10.010"},
                        {"trial_no": 2, "indicated_value": "10.005"},
                        {"trial_no": 3, "indicated_value": "10.000"},
                    ],
                }
            ],
        },
    )

    # 驗證
    validate_resp = client.post(
        f"/api/calibrations/{record_id}/validate",
        headers=_authorization(manager_token),
        json={
            "expected_version": save_resp.get_json()["data"]["row_version"],
        },
    )
    validated_record = validate_resp.get_json()["data"]

    # 送審
    submit_resp = client.post(
        f"/api/calibrations/{record_id}/submit",
        headers=_authorization(manager_token),
        json={
            "expected_version": validated_record["row_version"],
            "reason": "送交審查",
        },
    )
    submitted = submit_resp.get_json()["data"]

    # 管理者（建立者/送審者）嘗試核准應失敗
    denied = client.post(
        f"/api/calibrations/{submitted['id']}/approve",
        headers=_authorization(manager_token),
        json={
            "expected_version": submitted["row_version"],
            "reason": "自行核准",
        },
    )

    assert denied.status_code == 403
    assert denied.get_json()["error"]["code"] == "CALIBRATION_SELF_APPROVAL_FORBIDDEN"
    assert "建立、輸入或送審人員不得核准自己的校正紀錄" in denied.get_json()["error"]["message"]

    # 核准者核准應成功
    approved = client.post(
        f"/api/calibrations/{submitted['id']}/approve",
        headers=_authorization(approver_token),
        json={
            "expected_version": submitted["row_version"],
            "reason": "計算與追溯證據均已核對",
        },
    )

    assert approved.status_code == 200
    assert approved.get_json()["data"]["status"] == "approved"


def test_reject_calibration_creates_successor_draft(client, calibration_record_setup):
    """退回應保存送審證據並建立後繼草稿。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]
    approver_token = setup["approver"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(manager_token),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]
    point_id = record["points"][0]["id"]

    # 保存合格讀值
    save_resp = client.put(
        f"/api/calibrations/{record_id}/readings",
        headers=_authorization(manager_token),
        json={
            "expected_version": record["row_version"],
            "points": [
                {
                    "point_id": point_id,
                    "reference_value": "10.000",
                    "readings": [
                        {"trial_no": 1, "indicated_value": "10.010"},
                        {"trial_no": 2, "indicated_value": "10.005"},
                        {"trial_no": 3, "indicated_value": "10.000"},
                    ],
                }
            ],
        },
    )

    # 驗證
    validate_resp = client.post(
        f"/api/calibrations/{record_id}/validate",
        headers=_authorization(manager_token),
        json={
            "expected_version": save_resp.get_json()["data"]["row_version"],
        },
    )
    validated_record = validate_resp.get_json()["data"]

    # 送審
    submit_resp = client.post(
        f"/api/calibrations/{record_id}/submit",
        headers=_authorization(manager_token),
        json={
            "expected_version": validated_record["row_version"],
            "reason": "送交審查",
        },
    )
    submitted = submit_resp.get_json()["data"]

    # 核准者退回
    rejected = client.post(
        f"/api/calibrations/{submitted['id']}/reject",
        headers=_authorization(approver_token),
        json={
            "expected_version": submitted["row_version"],
            "reason": "量程證據不足",
        },
    )

    assert rejected.status_code == 200
    data = rejected.get_json()["data"]
    assert data["status"] == "draft"
    assert data["predecessor_id"] == submitted["id"]
    assert data["rejection_reason"] == "量程證據不足"


def test_void_calibration_requires_reason(client, calibration_record_setup):
    """作廢需填寫理由。"""
    setup = calibration_record_setup
    manager_token = setup["manager"]["token"]

    create_resp = client.post(
        "/api/calibrations",
        headers=_authorization(setup["manager"]["token"]),
        json={
            "equipment_id": setup["equipment"].id,
            "template_version_id": setup["version"].id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": setup["ref_equipment"].id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"}
            },
        },
    )
    record = create_resp.get_json()["data"]
    record_id = record["id"]

    response = client.post(
        f"/api/calibrations/{record_id}/void",
        headers=_authorization(manager_token),
        json={
            "expected_version": record["row_version"],
            "reason": "測試作廢",
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "voided"
    assert data["void_reason"] == "測試作廢"
