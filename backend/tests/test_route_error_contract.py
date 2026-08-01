from unittest.mock import Mock

from backend.routes.shipping import save_data
from backend.services.dashboard_service import DashboardService
from backend.services.shipping_service import ShippingService
from backend.utils import generate_token


def _auth_headers(**headers):
    token = generate_token(user_id=1, username="route-error-contract")
    return {"Authorization": f"Bearer {token}", **headers}


def test_unexpected_error_is_sanitized_even_when_legacy_route_catches_it(client, monkeypatch):
    """若 legacy route 自行攔截例外，正式 500 envelope 仍不可洩漏或退回字串。"""
    monkeypatch.setattr(
        DashboardService,
        "get_todos",
        Mock(side_effect=RuntimeError("password=secret")),
    )

    response = client.get("/api/dashboard/todos", headers=_auth_headers())

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "伺服器內部錯誤"},
    }
    assert "password=secret" not in response.get_data(as_text=True)
    assert response.headers["X-Correlation-ID"]


def test_valid_correlation_id_is_reused_on_error_response(client, monkeypatch):
    """若合法追蹤碼被替換，跨層 log 將無法串接同一請求。"""
    monkeypatch.setattr(
        DashboardService,
        "get_todos",
        Mock(side_effect=RuntimeError("controlled failure")),
    )

    response = client.get(
        "/api/dashboard/todos",
        headers=_auth_headers(**{"X-Correlation-ID": "trace_2026.08-01"}),
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
