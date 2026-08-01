"""JWT 簽章驗證與目前帳號狀態的單一認證入口。"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import jwt

from .config import SECRET_KEY
from .errors import AuthenticationError
from .extensions import db
from .models import Role, User


@dataclass(frozen=True)
class AuthenticatedUser:
    """單次請求使用的不可變授權快照，內容一律來自目前資料庫。"""

    id: int
    username: str
    role: str
    permissions: Mapping[str, bool]
    inspector_id: int | None

    def as_request_user(self) -> dict[str, Any]:
        """提供舊式 route 相容的 dict，但不帶入 JWT 授權 claims。"""
        return {
            'id': self.id,
            'user_id': self.id,
            'username': self.username,
            'role': self.role,
            'permissions': dict(self.permissions),
            'inspector_id': self.inspector_id,
        }


def decode_and_validate_signature(token: str) -> dict[str, Any]:
    """驗證 JWT 簽章與期限；無效 token 統一轉為認證錯誤。"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as error:
        raise AuthenticationError(
            '無效或過期的 Token',
            details={'reason': 'invalid_token'},
        ) from error


def authenticated_user_from_model(user: User) -> AuthenticatedUser:
    """從目前 User 與 Role 資料建立授權快照。"""
    role = Role.query.filter_by(code=user.role).first()
    permissions = dict(role.permissions or {}) if role else {}
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        role=user.role,
        permissions=MappingProxyType(permissions),
        inspector_id=user.inspector_id,
    )


def authenticate_request_token(token: str) -> tuple[User, AuthenticatedUser]:
    """驗證 token 版本並載入目前啟用帳號，不信任 JWT 內的授權資料。"""
    claims = decode_and_validate_signature(token)
    user_id = claims.get('user_id')
    token_version = claims.get('token_version')
    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or not isinstance(token_version, int)
        or isinstance(token_version, bool)
    ):
        raise AuthenticationError(
            '登入憑證已失效',
            details={'reason': 'legacy_or_invalid_claims'},
        )

    user = db.session.get(User, user_id)
    if user is None:
        raise AuthenticationError(
            '登入憑證已失效',
            details={'reason': 'user_not_found'},
        )
    if not user.is_active:
        raise AuthenticationError(
            '登入憑證已失效',
            details={'reason': 'user_inactive'},
        )
    if user.token_version != token_version:
        raise AuthenticationError(
            '登入憑證已失效',
            details={'reason': 'token_revoked'},
        )

    return user, authenticated_user_from_model(user)
