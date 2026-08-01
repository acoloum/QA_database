import re
import uuid

from flask import current_app, g, request

from .errors import build_error_envelope


CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_STATUS_ERROR_CODES = {
    400: "VALIDATION_ERROR",
    401: "AUTH_ERROR",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def before_request_context() -> None:
    """驗證或產生本次請求的追蹤識別碼。"""
    supplied = request.headers.get("X-Correlation-ID", "")
    g.correlation_id = (
        supplied if CORRELATION_ID.fullmatch(supplied) else uuid.uuid4().hex
    )


def get_correlation_id() -> str:
    """取得目前請求追蹤碼；防禦性補值供錯誤處理器使用。"""
    correlation_id = getattr(g, "correlation_id", None)
    if correlation_id is None:
        correlation_id = uuid.uuid4().hex
        g.correlation_id = correlation_id
    return correlation_id


def _replace_json(response, payload: dict) -> None:
    response.set_data(current_app.json.dumps(payload))
    response.content_type = "application/json"


def _normalize_api_error(response) -> None:
    """在 Task 9 完成 route 清理前，收斂既有錯誤回應至正式契約。"""
    if not request.path.startswith("/api/") or response.status_code < 400:
        return
    if response.status_code >= 500 and response.is_json:
        _replace_json(
            response,
            build_error_envelope("伺服器內部錯誤", "INTERNAL_ERROR"),
        )
        return

    payload = response.get_json(silent=True)
    if not isinstance(payload, dict):
        return

    raw_error = payload.get("error")
    if isinstance(raw_error, str):
        details = payload.get("details", payload.get("detail"))
        normalized = build_error_envelope(
            raw_error,
            _STATUS_ERROR_CODES.get(response.status_code, "API_ERROR"),
            details,
        )
        _replace_json(response, normalized)
        return

    if not isinstance(raw_error, dict):
        return

    code = raw_error.get("code")
    message = raw_error.get("message")
    if not isinstance(code, str) or not isinstance(message, str):
        return

    details = raw_error.get("details")
    if details is None and isinstance(raw_error.get("field"), str):
        details = {"field": raw_error["field"]}
    _replace_json(response, build_error_envelope(message, code, details))


def add_response_headers(response):
    """統一錯誤契約並加入請求追蹤與瀏覽器安全 headers。"""
    _normalize_api_error(response)
    response.headers["X-Correlation-ID"] = get_correlation_id()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response
