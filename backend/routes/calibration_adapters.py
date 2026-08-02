"""校正 routes 共用的認證、權限與穩定錯誤 adapter。"""

from functools import wraps

from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException

from ..authorization import require_permissions
from ..errors import AuthorizationError
from ..services.calibration_errors import CalibrationServiceError
from ..utils import auth_required


def handle_calibration_errors(function):
    """將校正服務例外轉為穩定且可程式判定的錯誤 envelope。"""

    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except CalibrationServiceError as error:
            return (
                jsonify(
                    {
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "details": error.details,
                        }
                    }
                ),
                error.status_code,
            )
        except HTTPException:
            raise
        except Exception:
            current_app.logger.exception("校正服務發生未預期錯誤")
            return (
                jsonify(
                    {
                        "error": {
                            "code": "CALIBRATION_INTERNAL_ERROR",
                            "message": "校正服務發生未預期錯誤",
                            "details": {},
                        }
                    }
                ),
                500,
            )

    return wrapped


def _has_calibration_error_code(response) -> bool:
    """判斷回應是否已帶校正服務的穩定錯誤碼。"""
    try:
        body = response.get_json(silent=True)
    except AttributeError:
        return False
    code = (
        body.get("error", {}).get("code")
        if isinstance(body, dict) and isinstance(body.get("error"), dict)
        else None
    )
    return isinstance(code, str) and code.startswith("CALIBRATION_")


def _reject_if_user_missing_or_inactive(current_user):
    """使用者不存在或已停用時回傳 401 回應；否則回傳 None。"""
    if current_user is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "CALIBRATION_USER_NOT_FOUND",
                        "message": "使用者不存在",
                        "details": {},
                    }
                }
            ),
            401,
        )
    if not bool(current_user.is_active):
        return (
            jsonify(
                {
                    "error": {
                        "code": "CALIBRATION_USER_INACTIVE",
                        "message": "使用者帳號已停用",
                        "details": {},
                    }
                }
            ),
            401,
        )
    return None


def require_calibration_permission(permission: str):
    """先拒絕不存在或已停用帳號，再套用獨立校正權限判定。"""

    def decorator(function):
        guarded = require_permissions(permission)(function)

        @wraps(function)
        def wrapped(current_user, *args, **kwargs):
            rejection = _reject_if_user_missing_or_inactive(current_user)
            if rejection is not None:
                return rejection

            try:
                result = guarded(current_user, *args, **kwargs)
            except AuthorizationError:
                return (
                    jsonify(
                        {
                            "error": {
                                "code": "CALIBRATION_PERMISSION_DENIED",
                                "message": "權限不足",
                                "details": {"permission": permission},
                            }
                        }
                    ),
                    403,
                )
            if isinstance(result, tuple) and len(result) == 2:
                response, status_code = result
                # 僅改寫既有權限檢查產生的 generic 403；服務層的職責
                # 分離錯誤已帶穩定校正 code，必須保留其 status 與 details。
                if (
                    status_code == 403
                    and not _has_calibration_error_code(response)
                ):
                    return (
                        jsonify(
                            {
                                "error": {
                                    "code": "CALIBRATION_PERMISSION_DENIED",
                                    "message": "權限不足",
                                    "details": {"permission": permission},
                                }
                            }
                        ),
                        403,
                    )
            return result

        wrapped.__authorization_guards__ = guarded.__authorization_guards__
        wrapped.__required_permissions__ = guarded.__required_permissions__
        return wrapped

    return decorator


def require_calibration_any_permission(*permissions: str):
    """允許任一指定權限，供跨模組唯讀摘要等受控相容介面使用。"""
    if not permissions:
        raise ValueError("至少必須指定一項權限")

    def decorator(function):
        guarded = require_permissions(*permissions, mode="any")(function)

        @wraps(function)
        def wrapped(current_user, *args, **kwargs):
            rejection = _reject_if_user_missing_or_inactive(current_user)
            if rejection is not None:
                return rejection
            try:
                return guarded(current_user, *args, **kwargs)
            except AuthorizationError:
                return (
                    jsonify(
                        {
                            "error": {
                                "code": "CALIBRATION_PERMISSION_DENIED",
                                "message": "權限不足",
                                "details": {
                                    "permission": " 或 ".join(permissions),
                                },
                            }
                        }
                    ),
                    403,
                )

        wrapped.__authorization_guards__ = guarded.__authorization_guards__
        wrapped.__required_permissions__ = guarded.__required_permissions__
        return wrapped

    return decorator


# 認證失敗一律以底層帶出的穩定 reason 對應校正錯誤碼；
# 不比對訊息文字，改文案才不會靜默破壞錯誤碼契約。
CALIBRATION_AUTH_CODE_BY_REASON = {
    "missing_token": "CALIBRATION_AUTH_REQUIRED",
    "invalid_token": "CALIBRATION_AUTH_INVALID_TOKEN",
    "legacy_or_invalid_claims": "CALIBRATION_AUTH_INVALID_TOKEN",
    "token_revoked": "CALIBRATION_AUTH_INVALID_TOKEN",
    "user_not_found": "CALIBRATION_USER_NOT_FOUND",
    "user_inactive": "CALIBRATION_USER_INACTIVE",
}

# 少數 reason 需覆寫對外訊息，其餘沿用底層訊息
CALIBRATION_AUTH_MESSAGE_BY_REASON = {
    "user_not_found": "使用者不存在",
    "user_inactive": "使用者帳號已停用",
}


def calibration_auth_required(function):
    """將共用 JWT 401 轉為穩定校正認證 envelope。"""
    guarded = auth_required(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        result = guarded(*args, **kwargs)
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and result[1] == 401
        ):
            response = result[0]
            body = (
                response.get_json(silent=True)
                if hasattr(response, "get_json")
                else None
            )
            raw_error = body.get("error") if isinstance(body, dict) else None
            if not isinstance(raw_error, dict):
                return result
            message = raw_error.get("message")
            details = (
                raw_error.get("details")
                if isinstance(raw_error.get("details"), dict)
                else {}
            )
            reason = details.get("reason")
            if not isinstance(message, str) or reason not in CALIBRATION_AUTH_CODE_BY_REASON:
                return result
            return (
                jsonify(
                    {
                        "error": {
                            "code": CALIBRATION_AUTH_CODE_BY_REASON[reason],
                            "message": CALIBRATION_AUTH_MESSAGE_BY_REASON.get(reason, message),
                            "details": {},
                        }
                    }
                ),
                401,
            )
        return result

    return wrapped
