"""MSA routes 共用的認證、權限與穩定錯誤 adapter。"""

from functools import wraps

from flask import jsonify

from ..authorization import require_permissions
from ..errors import AuthorizationError
from ..services.msa_errors import MsaServiceError
from ..utils import auth_required
from ..authorization import role_grants_permission


def handle_msa_errors(function):
    """將 MSA service 例外轉為穩定且可程式判定的錯誤 envelope。"""

    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MsaServiceError as error:
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

    return wrapped


def _has_msa_error_code(response) -> bool:
    """判斷回應是否已帶穩定 MSA 錯誤碼（代表來自服務層而非權限檢查）。"""
    try:
        body = response.get_json(silent=True)
    except AttributeError:
        return False
    return bool(
        isinstance(body, dict)
        and isinstance(body.get("error"), dict)
        and body["error"].get("code")
    )


def require_msa_permission(permission: str):
    """先拒絕不存在或已停用帳號，再套用既有角色權限判定。"""

    def decorator(function):
        guarded = require_permissions(permission)(function)

        @wraps(function)
        def wrapped(current_user, *args, **kwargs):
            if current_user is None:
                return (
                    jsonify(
                        {
                            "error": {
                                "code": "MSA_USER_NOT_FOUND",
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
                                "code": "MSA_USER_INACTIVE",
                                "message": "使用者帳號已停用",
                                "details": {},
                            }
                        }
                    ),
                    401,
                )
            try:
                result = guarded(current_user, *args, **kwargs)
            except AuthorizationError:
                return (
                    jsonify(
                        {
                            "error": {
                                "code": "MSA_PERMISSION_DENIED",
                                "message": "權限不足",
                                "details": {"permission": permission},
                            }
                        }
                    ),
                    403,
                )
            if isinstance(result, tuple) and len(result) == 2:
                response, status_code = result
                # 只改寫「權限檢查本身」產生的 403。服務層的 403
                # （例如職責分離的 MSA_SELF_APPROVAL_FORBIDDEN）已經帶
                # 自己的錯誤碼，蓋掉它會讓核准者誤以為只是權限不足。
                if status_code == 403 and not _has_msa_error_code(response):
                    return (
                        jsonify(
                            {
                                "error": {
                                    "code": "MSA_PERMISSION_DENIED",
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


# 認證失敗一律以底層帶出的穩定 reason 對應 MSA 錯誤碼；
# 不比對訊息文字，改文案才不會靜默破壞錯誤碼契約。
MSA_AUTH_CODE_BY_REASON = {
    "missing_token": "MSA_AUTH_REQUIRED",
    "invalid_token": "MSA_AUTH_INVALID_TOKEN",
    "legacy_or_invalid_claims": "MSA_AUTH_INVALID_TOKEN",
    "token_revoked": "MSA_AUTH_INVALID_TOKEN",
    "user_not_found": "MSA_USER_NOT_FOUND",
    "user_inactive": "MSA_USER_INACTIVE",
}

# 少數 reason 需覆寫對外訊息，其餘沿用底層訊息
MSA_AUTH_MESSAGE_BY_REASON = {
    "user_not_found": "使用者不存在",
    "user_inactive": "使用者帳號已停用",
}


def msa_auth_required(function):
    """將共用 JWT 401 轉為穩定 MSA auth envelope。"""
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
            if not isinstance(message, str) or reason not in MSA_AUTH_CODE_BY_REASON:
                return result
            return (
                jsonify(
                    {
                        "error": {
                            "code": MSA_AUTH_CODE_BY_REASON[reason],
                            "message": MSA_AUTH_MESSAGE_BY_REASON.get(reason, message),
                            "details": {},
                        }
                    }
                ),
                401,
            )
        return result

    return wrapped


def has_msa_permission(current_user, permission: str) -> bool:
    """在路由內判斷目前身分是否具備指定 MSA 權限（不影響回應）。"""
    if current_user is None or not bool(current_user.is_active):
        return False
    return role_grants_permission(current_user, permission)
