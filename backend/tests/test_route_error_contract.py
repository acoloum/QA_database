import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask import jsonify

from backend.routes.shipping import save_data
from backend.models import User
from backend.services.dashboard_service import DashboardService
from backend.services.capa_service import CAPAService
from backend.services.complaint_service import ComplaintService
from backend.services.mechanical_service import MechanicalService
from backend.services.ncmr_service import NCMRService
from backend.services.patrol_service import PatrolService
from backend.services.rework_service import ReworkService
from backend.services.shipping_service import ShippingService
from backend.services.task_service import TaskService
from backend.services.tolerance_service import ToleranceService
from backend.services.vendor_performance_service import VendorPerformanceService
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


@pytest.fixture
def admin_headers(db_session):
    user = User(
        username="route-error-admin",
        password="pw",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {"Authorization": f"Bearer {token}", "X-Correlation-ID": "task8-global-500"}


@pytest.mark.parametrize(
    ('service', 'method_name', 'http_method', 'url', 'payload'),
    [
        (CAPAService, 'close', 'post', '/api/capas/999/close', {'D8_confirmation': '確認'}),
        (ComplaintService, 'delete', 'delete', '/api/complaints/999', None),
        (ReworkService, 'delete_rework', 'post', '/api/rework/delete', {'rework_id': 999}),
    ],
)
def test_workflow_unexpected_error_reaches_global_handler(
    client,
    monkeypatch,
    admin_headers,
    caplog,
    service,
    method_name,
    http_method,
    url,
    payload,
):
    """workflow route 不得吞掉 unexpected exception，必須由 global handler 統一記錄。"""
    caplog.set_level('ERROR')

    def fail_unexpected(*_args, **_kwargs):
        raise RuntimeError('password=WORKFLOW-SECRET')

    monkeypatch.setattr(service, method_name, fail_unexpected)
    response = getattr(client, http_method)(url, json=payload, headers=admin_headers)

    assert response.status_code == 500
    assert response.get_json() == {
        'success': False,
        'error': {'code': 'INTERNAL_ERROR', 'message': '伺服器內部錯誤'},
    }
    assert 'WORKFLOW-SECRET' not in response.get_data(as_text=True)
    assert any(
        '未處理 API 例外 correlation_id=task8-global-500' in record.getMessage()
        for record in caplog.records
    )


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


# =====================================================================
# Task 9：移除 route 例外洩漏
# 禁止 routes 層以 str(e) 包裝例外訊息回傳，或將例外具名重新 raise。
# =====================================================================

ROUTES_DIR = Path(__file__).resolve().parents[1] / "routes"


def _collect_route_leak_violations():
    """掃描 backend/routes/*.py，回傳違反錯誤契約的 (檔名, 行號, 模式) 清單。

    只禁止「500 內部錯誤洩漏 str(e)」與「具名重新 raise」；4xx 的
    str(e) 是設計給使用者的業務訊息（如機械/溫度量測的 domain error
    response），不屬於內部例外洩漏。
    """
    violations = []
    for py_file in sorted(ROUTES_DIR.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            # 模式 1：return api_error(str(e), 500)
            if (
                isinstance(node, ast.Return)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "api_error"
            ):
                args = node.value.args
                kwargs = {kw.arg: kw.value for kw in node.value.keywords}
                status_node = args[1] if len(args) >= 2 else kwargs.get("status")
                if (
                    len(args) >= 1
                    and isinstance(args[0], ast.Call)
                    and isinstance(args[0].func, ast.Name)
                    and args[0].func.id == "str"
                    and isinstance(status_node, ast.Constant)
                    and status_node.value == 500
                ):
                    violations.append((py_file.name, node.lineno, "api_error(str(e), 500)"))
            # 模式 2：return jsonify({"error": str(e)}), 500
            if (
                isinstance(node, ast.Return)
                and isinstance(node.value, ast.Tuple)
                and len(node.value.elts) == 2
            ):
                call, status = node.value.elts
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "jsonify"
                    and call.args
                    and isinstance(call.args[0], ast.Dict)
                    and isinstance(status, ast.Constant)
                    and status.value == 500
                ):
                    for key, value in zip(call.args[0].keys, call.args[0].values):
                        if (
                            isinstance(key, ast.Constant)
                            and key.value == "error"
                            and isinstance(value, ast.Call)
                            and isinstance(value.func, ast.Name)
                            and value.func.id == "str"
                        ):
                            violations.append(
                                (py_file.name, node.lineno, 'jsonify({"error": str(e)}), 500')
                            )
            # 模式 3：raise e（具名重新 raise）
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Name):
                violations.append((py_file.name, node.lineno, "raise <name>"))
    return violations


def test_routes_never_leak_exception_strings():
    """routes 層不得將內部例外訊息回傳給使用者。"""
    assert _collect_route_leak_violations() == []


@pytest.mark.parametrize(
    ('service', 'method_name', 'http_method', 'url', 'payload'),
    [
        (ShippingService, 'get_list', 'get', '/api/data', None),
        (PatrolService, 'get_options', 'get', '/api/patrol/options', None),
        (NCMRService, 'get_ncmr_list', 'get', '/api/ncmr', None),
        (TaskService, 'list_tasks', 'get', '/api/tasks', None),
        (ToleranceService, 'get_options', 'get', '/api/tolerance/options', None),
        (MechanicalService, 'list', 'get', '/api/mechanical/tests', None),
        (VendorPerformanceService, 'list_by_period', 'get', '/api/vendor-performance', None),
    ],
)
def test_domain_unexpected_error_returns_fixed_500_envelope(
    client,
    monkeypatch,
    admin_headers,
    service,
    method_name,
    http_method,
    url,
    payload,
):
    """各 domain route 的未預期例外必須回傳固定 500 envelope，且不洩漏原訊息。"""
    secret = f"password={service.__name__}-SECRET"

    def fail_unexpected(*_args, **_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(service, method_name, fail_unexpected)
    response = getattr(client, http_method)(url, json=payload, headers=admin_headers)

    assert response.status_code == 500
    assert response.get_json() == {
        'success': False,
        'error': {'code': 'INTERNAL_ERROR', 'message': '伺服器內部錯誤'},
    }
    assert secret not in response.get_data(as_text=True)
