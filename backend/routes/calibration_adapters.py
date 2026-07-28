"""校正 routes 共用的認證、權限與穩定錯誤 adapter。"""

from functools import wraps

from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException

from ..services.calibration_errors import CalibrationServiceError
from ..utils import auth_required, require_permission


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


def require_calibration_permission(permission: str):
    """先拒絕不存在或已停用帳號，再套用獨立校正權限判定。"""

    def decorator(function):
        guarded = require_permission(permission)(function)

        @wraps(function)
        def wrapped(current_user, *args, **kwargs):
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

            result = guarded(current_user, *args, **kwargs)
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

        return wrapped

    return decorator


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
            legacy_message = (
                body.get("error") if isinstance(body, dict) else None
            )
            code_by_message = {
                "缺少認證 Token": "CALIBRATION_AUTH_REQUIRED",
                "無效或過期的 Token": "CALIBRATION_AUTH_INVALID_TOKEN",
            }
            if (
                isinstance(legacy_message, str)
                and legacy_message in code_by_message
            ):
                return (
                    jsonify(
                        {
                            "error": {
                                "code": code_by_message[legacy_message],
                                "message": legacy_message,
                                "details": {},
                            }
                        }
                    ),
                    401,
                )
        return result

    return wrapped
