"""MSA 判定準則 profile、版本與核准 API。"""

from functools import wraps

from flask import Blueprint, jsonify, request

from ..services.msa_criteria_service import MsaCriteriaService
from ..services.msa_errors import MsaServiceError
from ..utils import auth_required, require_permission


msa_bp = Blueprint("msa", __name__)


def _handle_msa_errors(function):
    """將 MSA service 例外轉為穩定錯誤 envelope。"""

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


def _require_msa_permission(permission: str):
    """沿用共用權限判定，並轉為穩定 MSA permission envelope。"""

    def decorator(function):
        guarded = require_permission(permission)(function)

        @wraps(function)
        def wrapped(current_user, *args, **kwargs):
            result = guarded(current_user, *args, **kwargs)
            if isinstance(result, tuple) and len(result) == 2:
                _response, status_code = result
                if status_code == 403:
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
                if status_code == 401:
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
            return result

        return wrapped

    return decorator


def _msa_auth_required(function):
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
            legacy_message = (
                body.get("error") if isinstance(body, dict) else None
            )
            code_by_message = {
                "缺少認證 Token": "MSA_AUTH_REQUIRED",
                "無效或過期的 Token": "MSA_AUTH_INVALID_TOKEN",
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


@msa_bp.get("/api/msa/criteria")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_criteria(current_user):
    """列出目前身分可檢視的準則 profile 與歷史版本。"""
    return jsonify({"data": MsaCriteriaService.list(request.args)})


@msa_bp.post("/api/msa/criteria")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_criteria_profile(current_user):
    """建立受控判定準則 profile。"""
    profile = MsaCriteriaService.create_profile(
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify(
        {
            "data": MsaCriteriaService.serialize_profile(
                profile,
                include_versions=False,
            )
        }
    ), 201


@msa_bp.post("/api/msa/criteria/<int:profile_id>/versions")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_criteria_version(current_user, profile_id: int):
    """建立具完整預設補值與驗證的 draft 版本。"""
    version = MsaCriteriaService.create_version(
        profile_id,
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify(
        {"data": MsaCriteriaService.serialize_version(version)}
    ), 201


@msa_bp.post("/api/msa/criteria/versions/<int:version_id>/approve")
@_msa_auth_required
@_require_msa_permission("msa.approve")
@_handle_msa_errors
def approve_criteria_version(current_user, version_id: int):
    """核准畫面確認仍為 draft 的完整準則版本。"""
    version = MsaCriteriaService.approve_version(
        version_id,
        current_user.id,
        payload=request.get_json(silent=True),
    )
    return jsonify(
        {"data": MsaCriteriaService.serialize_version(version)}
    )
