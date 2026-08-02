
import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from backend.errors import APIError
from backend.models import User
from backend.utils import generate_token

@pytest.fixture
def auth_headers(db_session):
    # 測試目的為「錯誤處理」，非權限；admin 為內建全權限角色，不需 DB Role
    user = User(username="testuser", password="pw", role="admin", is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        token_version=user.token_version,
    )
    return {'Authorization': f'Bearer {token}'}

def test_api_error_handler(app, client, auth_headers):
    """Test standard APIError handling"""
    # Ensure handlers are triggered
    app.config['PROPAGATE_EXCEPTIONS'] = False
    
    # Patch a known existing route to raise APIError
    with patch('backend.services.tolerance_service.ToleranceService.search_tolerance') as mock_search:
        mock_search.side_effect = APIError("Custom Error", code="CUSTOM_ERR", status_code=418)
        
        # Call the route that uses this service
        response = client.get('/api/tolerance/search?material=test', headers=auth_headers)
        
        assert response.status_code == 418
        data = response.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "CUSTOM_ERR"
        assert data["error"]["message"] == "Custom Error"

def test_404_handler(client):
    """Test 404 handling for non-existent API routes

    註：非 /api 路徑會由前端 SPA fallback 回 index.html（200），交前端路由處理；
    故此處改測未定義的 /api 路徑，驗證 JSON 格式的 404 錯誤處理器。
    """
    response = client.get('/api/non/existent/route')
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"

def test_generic_exception_never_exposes_original_exception(app, client, auth_headers):
    """若 generic handler 回傳例外字串，憑證資訊會洩漏給 API caller。"""
    # Ensure handlers are triggered
    app.config['PROPAGATE_EXCEPTIONS'] = False

    # Patch a known existing route to raise a generic unexpected exception
    with patch('backend.services.tolerance_service.ToleranceService.search_tolerance') as mock_search:
        mock_search.side_effect = RuntimeError("password=secret")
        
        response = client.get('/api/tolerance/search?material=test', headers=auth_headers)
        
        assert response.status_code == 500
        data = response.get_json()
        assert data == {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "伺服器內部錯誤",
            },
        }
        assert "password=secret" not in response.get_data(as_text=True)
        assert response.headers["X-Correlation-ID"]


def test_unknown_database_exception_never_exposes_driver_message(app, client, auth_headers):
    """若未知 DB 例外直接回傳 driver 字串，連線資訊可能洩漏給 caller。"""
    app.config['PROPAGATE_EXCEPTIONS'] = False
    with patch('backend.services.tolerance_service.ToleranceService.search_tolerance') as mock_search:
        mock_search.side_effect = SQLAlchemyError("password=database-secret")

        response = client.get('/api/tolerance/search?material=test', headers=auth_headers)

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "伺服器內部錯誤",
        },
    }
    assert "password=database-secret" not in response.get_data(as_text=True)


def test_generic_exception_log_includes_supplied_correlation_id(app, client, auth_headers):
    """若例外 log 未帶追蹤碼，回應 header 將無法對回伺服器 traceback。"""
    app.config['PROPAGATE_EXCEPTIONS'] = False
    headers = {**auth_headers, "X-Correlation-ID": "trace-log-500"}
    with (
        patch('backend.services.tolerance_service.ToleranceService.search_tolerance') as mock_search,
        patch.object(app.logger, "exception") as log_exception,
    ):
        mock_search.side_effect = RuntimeError("controlled failure")

        response = client.get('/api/tolerance/search?material=test', headers=headers)

    assert response.status_code == 500
    log_exception.assert_called_once_with(
        "未處理 API 例外 correlation_id=%s",
        "trace-log-500",
    )
