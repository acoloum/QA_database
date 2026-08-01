from unittest.mock import Mock

import pytest
from flask import jsonify

from backend.routes.shipping import save_data
from backend.models import User
from backend.services.dashboard_service import DashboardService
from backend.services.shipping_service import ShippingService
from backend.utils import generate_token


@pytest.fixture
def auth_headers(db_session):
    user = User(
        username="route-error-contract",
        password="pw",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        token_version=user.token_version,
    )
    return {"Authorization": f"Bearer {token}"}


def test_unexpected_error_is_sanitized_even_when_legacy_route_catches_it(
    client, monkeypatch, auth_headers
):
    """若 legacy route 自行攔截例外，正式 500 envelope 仍不可洩漏或退回字串。"""
    monkeypatch.setattr(
        DashboardService,
        "get_todos",
        Mock(side_effect=RuntimeError("password=secret")),
    )

    response = client.get("/api/dashboard/todos", headers=auth_headers)

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "伺服器內部錯誤"},
    }
    assert "password=secret" not in response.get_data(as_text=True)
    assert response.headers["X-Correlation-ID"]


def test_valid_correlation_id_is_reused_on_error_response(
    client, monkeypatch, auth_headers
):
    """若合法追蹤碼被替換，跨層 log 將無法串接同一請求。"""
    monkeypatch.setattr(
        DashboardService,
        "get_todos",
        Mock(side_effect=RuntimeError("controlled failure")),
    )

    response = client.get(
        "/api/dashboard/todos",
        headers={**auth_headers, "X-Correlation-ID": "trace_2026.08-01"},
    )

    assert response.headers["X-Correlation-ID"] == "trace_2026.08-01"


def test_shipping_db_error_branch_uses_new_details_keyword(app, monkeypatch):
    """若 shipping 沿用舊 detail keyword，DB 錯誤分支會拋 TypeError 而失去原 envelope。"""
    monkeypatch.setattr(
        ShippingService,
        "save_data",
        Mock(side_effect=RuntimeError("UNIQUE constraint failed")),
    )

    with app.test_request_context("/api/add", method="POST", json={}):
        response, status = save_data.__wrapped__.__wrapped__()

    assert status == 500
    assert response.get_json() == {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "資料重複：此筆資料已存在",
            "details": {"message": "資料重複：此筆資料已存在"},
        },
    }


@pytest.mark.parametrize("legacy_code", ["INTERNAL_ERROR", "DB_ERROR"])
def test_every_legacy_5xx_code_is_sanitized_without_message_or_details(
    client,
    monkeypatch,
    legacy_code,
):
    """若 5xx 依 code 黑名單消毒，其他 code 仍會洩漏 message/details 中的秘密。"""
    secret = f"password=legacy-{legacy_code.lower()}"

    def legacy_5xx_response():
        return jsonify({
            "success": False,
            "error": {
                "code": legacy_code,
                "message": secret,
                "details": {"driver_message": secret},
            },
        }), 500

    monkeypatch.setitem(
        client.application.view_functions,
        "admin.get_dashboard_todos",
        legacy_5xx_response,
    )

    response = client.get("/api/dashboard/todos")

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "伺服器內部錯誤"},
    }
    assert secret not in response.get_data(as_text=True)


def test_non_object_json_5xx_is_sanitized_before_payload_parsing(client, monkeypatch):
    """若 5xx 先要求 object，JSON 陣列仍可繞過固定錯誤回應並洩漏內容。"""
    secret = "password=legacy-json-array"

    def legacy_5xx_response():
        return jsonify([secret]), 500

    monkeypatch.setitem(
        client.application.view_functions,
        "admin.get_dashboard_todos",
        legacy_5xx_response,
    )

    response = client.get("/api/dashboard/todos")

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "伺服器內部錯誤"},
    }
    assert secret not in response.get_data(as_text=True)
