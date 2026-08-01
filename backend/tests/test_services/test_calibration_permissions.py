"""校正模組獨立認證、權限與錯誤轉接器的整合測試。"""

import pytest
from flask import Flask, abort, jsonify, request

from backend.extensions import db
from backend.models import CalibrationTemplate, Role, User
from backend.seeds.seed_roles import ROLES
from backend.utils import generate_token, hash_password


def _calibration_permissions(role_code: str) -> dict[str, bool]:
    permissions = next(
        role["permissions"] for role in ROLES if role["code"] == role_code
    )
    return {
        permission: enabled
        for permission, enabled in permissions.items()
        if permission.startswith("calibration.")
    }


@pytest.mark.parametrize(
    ("class_name", "expected_status"),
    [
        ("CalibrationServiceError", 400),
        ("CalibrationNotFound", 404),
        ("CalibrationForbidden", 403),
        ("CalibrationConflict", 409),
        ("CalibrationValidationError", 422),
    ],
)
def test_calibration_service_errors_keep_stable_contract(
    class_name,
    expected_status,
):
    from backend.services import calibration_errors

    error_class = getattr(calibration_errors, class_name)
    error = error_class(
        "CALIBRATION_TEST_ERROR",
        "校正測試錯誤",
        details={"field": "template_code"},
    )

    assert error.status_code == expected_status
    assert error.code == "CALIBRATION_TEST_ERROR"
    assert error.message == "校正測試錯誤"
    assert error.details == {"field": "template_code"}


@pytest.fixture
def calibration_api():
    """建立只承載校正 adapter 契約的隔離測試 API。"""
    from backend.routes.calibration_adapters import (
        calibration_auth_required,
        handle_calibration_errors,
        require_calibration_permission,
    )
    from backend.services.calibration_errors import CalibrationForbidden

    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    @app.post("/api/calibration-templates")
    @calibration_auth_required
    @require_calibration_permission("calibration.manage")
    @handle_calibration_errors
    def create_template(current_user):
        payload = request.get_json()
        template = CalibrationTemplate(
            template_code=payload["template_code"],
            name=payload["name"],
            equipment_type=payload["equipment_type"],
        )
        db.session.add(template)
        db.session.commit()
        return jsonify({"data": {"id": template.id}}), 201

    @app.post("/api/calibration-approvals/<int:version_id>")
    @calibration_auth_required
    @require_calibration_permission("calibration.approve")
    @handle_calibration_errors
    def approve_template_version(current_user, version_id):
        raise CalibrationForbidden(
            "CALIBRATION_SELF_APPROVAL_FORBIDDEN",
            "建立校正模板版次的人員不得核准同一版次",
            details={
                "template_version_id": version_id,
                "created_by": current_user.id,
            },
        )

    @app.get("/api/calibration-internal-error")
    @calibration_auth_required
    @require_calibration_permission("calibration.view")
    @handle_calibration_errors
    def raise_internal_error(current_user):
        raise RuntimeError("內部資料庫密碼不得回傳")

    @app.get("/api/calibration-http-not-found")
    @calibration_auth_required
    @require_calibration_permission("calibration.view")
    @handle_calibration_errors
    def raise_http_not_found(current_user):
        abort(404)

    @app.post("/api/calibration-json")
    @calibration_auth_required
    @require_calibration_permission("calibration.view")
    @handle_calibration_errors
    def parse_calibration_json(current_user):
        request.get_json()
        return "", 204

    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Role(
                    code="calibration_manager",
                    name="校正管理者",
                    permissions={"calibration.manage": True},
                ),
                Role(
                    code="msa_manager_only",
                    name="僅 MSA 管理者",
                    permissions={
                        "msa.view": True,
                        "msa.execute": True,
                        "msa.manage": True,
                    },
                ),
                Role(
                    code="calibration_approver",
                    name="校正核准者",
                    permissions={
                        "calibration.view": True,
                        "calibration.approve": True,
                    },
                ),
            ]
        )
        users = {
            "inactive_manager": User(
                username="inactive_calibration_manager",
                password=hash_password("pw12345678"),
                role="calibration_manager",
                is_active=False,
            ),
            "msa_manager_only": User(
                username="msa_manager_only",
                password=hash_password("pw12345678"),
                role="msa_manager_only",
                is_active=True,
            ),
            "approver": User(
                username="calibration_approver",
                password=hash_password("pw12345678"),
                role="calibration_approver",
                is_active=True,
            ),
            "inactive_admin": User(
                username="inactive_admin",
                password=hash_password("pw12345678"),
                role="admin",
                is_active=False,
            ),
            "active_admin": User(
                username="active_admin_without_role_row",
                password=hash_password("pw12345678"),
                role="admin",
                is_active=True,
            ),
        }
        db.session.add_all(users.values())
        db.session.commit()

        tokens = {
            key: generate_token(
                user.id, user.username, user.role, user.token_version
            )
            for key, user in users.items()
        }
        tokens["deleted_user"] = generate_token(
            999_999,
            "deleted_calibration_manager",
            "calibration_manager",
            0,
        )
        yield app.test_client(), tokens, app

        db.session.remove()
        db.drop_all()


def _template_payload(template_code: str) -> dict:
    return {
        "template_code": template_code,
        "name": "卡尺",
        "equipment_type": "卡尺",
    }


def _authorization(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _template_count(app: Flask) -> int:
    with app.app_context():
        return CalibrationTemplate.query.count()


@pytest.mark.parametrize(
    ("headers", "expected_code", "expected_message"),
    [
        ({}, "CALIBRATION_AUTH_REQUIRED", "缺少認證 Token"),
        (
            {"Authorization": "Bearer invalid-token"},
            "CALIBRATION_AUTH_INVALID_TOKEN",
            "無效或過期的 Token",
        ),
    ],
)
def test_calibration_auth_errors_use_stable_envelope(
    calibration_api,
    headers,
    expected_code,
    expected_message,
):
    client, _tokens, app = calibration_api

    response = client.post(
        "/api/calibration-templates",
        headers=headers,
        json=_template_payload("CAL-AUTH"),
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": {
            "code": expected_code,
            "message": expected_message,
            "details": {},
        }
    }
    assert _template_count(app) == 0


def test_deleted_user_is_rejected_before_calibration_manage_mutation(
    calibration_api,
):
    client, tokens, app = calibration_api

    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(tokens["deleted_user"]),
        json=_template_payload("CAL-DELETED-USER"),
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_USER_NOT_FOUND"
    assert _template_count(app) == 0


def test_inactive_user_is_rejected_before_calibration_manage_mutation(
    calibration_api,
):
    client, tokens, app = calibration_api

    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(tokens["inactive_manager"]),
        json=_template_payload("CAL-INACTIVE"),
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_USER_INACTIVE"
    assert _template_count(app) == 0


def test_msa_manage_does_not_grant_calibration_manage(calibration_api):
    client, tokens, app = calibration_api

    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(tokens["msa_manager_only"]),
        json=_template_payload("CAL-MSA-ONLY"),
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == {
        "code": "CALIBRATION_PERMISSION_DENIED",
        "message": "權限不足",
        "details": {"permission": "calibration.manage"},
    }
    assert _template_count(app) == 0


def test_service_self_approval_error_is_preserved(calibration_api):
    client, tokens, app = calibration_api
    with app.app_context():
        approver_id = User.query.filter_by(
            username="calibration_approver"
        ).one().id

    response = client.post(
        "/api/calibration-approvals/17",
        headers=_authorization(tokens["approver"]),
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == {
        "code": "CALIBRATION_SELF_APPROVAL_FORBIDDEN",
        "message": "建立校正模板版次的人員不得核准同一版次",
        "details": {
            "template_version_id": 17,
            "created_by": approver_id,
        },
    }


def test_inactive_admin_is_rejected_before_calibration_manage_mutation(
    calibration_api,
):
    client, tokens, app = calibration_api

    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(tokens["inactive_admin"]),
        json=_template_payload("CAL-INACTIVE-ADMIN"),
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_USER_INACTIVE"
    assert _template_count(app) == 0


def test_unexpected_exception_returns_sanitized_error(calibration_api):
    client, tokens, _app = calibration_api

    response = client.get(
        "/api/calibration-internal-error",
        headers=_authorization(tokens["approver"]),
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": {
            "code": "CALIBRATION_INTERNAL_ERROR",
            "message": "校正服務發生未預期錯誤",
            "details": {},
        }
    }
    assert "內部資料庫密碼" not in response.get_data(as_text=True)


def test_http_not_found_is_not_converted_to_calibration_internal_error(
    calibration_api,
):
    client, tokens, _app = calibration_api

    response = client.get(
        "/api/calibration-http-not-found",
        headers=_authorization(tokens["approver"]),
    )

    assert response.status_code == 404
    assert "CALIBRATION_INTERNAL_ERROR" not in response.get_data(as_text=True)


def test_malformed_json_is_not_converted_to_calibration_internal_error(
    calibration_api,
):
    client, tokens, _app = calibration_api

    response = client.post(
        "/api/calibration-json",
        data="{",
        content_type="application/json",
        headers=_authorization(tokens["approver"]),
    )

    assert response.status_code == 400
    assert "CALIBRATION_INTERNAL_ERROR" not in response.get_data(as_text=True)


def test_active_admin_without_role_row_can_create_calibration_template(
    calibration_api,
):
    client, tokens, app = calibration_api
    with app.app_context():
        assert Role.query.filter_by(code="admin").first() is None

    response = client.post(
        "/api/calibration-templates",
        headers=_authorization(tokens["active_admin"]),
        json=_template_payload("CAL-ACTIVE-ADMIN"),
    )

    assert response.status_code == 201
    with app.app_context():
        template = CalibrationTemplate.query.one()
        assert template.template_code == "CAL-ACTIVE-ADMIN"
        assert CalibrationTemplate.query.count() == 1


def test_seed_roles_follow_exact_calibration_permission_matrix():
    assert _calibration_permissions("inspector") == {
        "calibration.view": True,
        "calibration.execute": True,
    }
    assert _calibration_permissions("qa_supervisor") == {
        "calibration.view": True,
        "calibration.execute": True,
        "calibration.manage": True,
    }
    assert _calibration_permissions("qc_manager") == {
        "calibration.view": True,
        "calibration.approve": True,
    }
    assert _calibration_permissions("admin") == {
        "calibration.view": True,
        "calibration.execute": True,
        "calibration.manage": True,
        "calibration.approve": True,
    }
