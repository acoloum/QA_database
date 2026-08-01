"""後端授權的單一實作點與正式領域權限矩陣。"""

from functools import wraps
from typing import Literal

from flask import g

from .errors import AuthorizationError
from .models import NCMR, Role, User


# 此矩陣是 route decorator 的共用詞彙；實際後端控制仍由
# require_permissions 在每次請求根據當前 DB User/Role 決定。
DOMAIN_PERMISSIONS: dict[str, dict[str, str]] = {
    'ncmr': {
        'view': 'ncmr.view', 'create': 'ncmr.create', 'edit': 'ncmr.edit',
        'edit_own': 'ncmr.edit_own', 'delete': 'ncmr.delete',
        'disposition': 'ncmr.disposition',
    },
    'capa': {
        'view': 'capa.view', 'create': 'capa.create', 'edit': 'capa.edit',
        'close': 'capa.close',
    },
    'complaint': {
        'view': 'complaint.view', 'create': 'complaint.create',
        'edit': 'complaint.edit', 'delete': 'complaint.delete',
    },
    'rework': {
        'view': 'rework.view', 'create': 'rework.create',
        'approve': 'rework.approve', 'delete': 'rework.delete',
    },
    'shipping': {
        'view': 'shipping.view', 'create': 'shipping.create',
        'edit': 'shipping.edit', 'delete': 'shipping.delete',
    },
    'patrol': {
        'view': 'patrol.view', 'create': 'patrol.create',
        'edit': 'patrol.edit', 'delete': 'patrol.delete',
    },
    'tolerance': {'view': 'tolerance.view', 'manage': 'tolerance.manage'},
    'mechanical': {
        'view': 'mechanical.view', 'create': 'mechanical.create',
        'edit': 'mechanical.edit', 'delete': 'mechanical.delete',
    },
    'pyrometry': {
        'view': 'pyrometry.view', 'edit': 'pyrometry.edit',
        'delete': 'pyrometry.delete',
    },
    'task': {
        'view': 'task.view', 'create': 'task.create',
        'edit': 'task.edit', 'delete': 'task.delete',
    },
    'analytics': {'view': 'analytics.view'},
    'vendor': {'view': 'vendor.view', 'manage': 'vendor.manage'},
}


def role_grants_permission(current_user: User | None, permission: str) -> bool:
    """以當前 ORM User 對應的 DB Role 權限判定，不信任 JWT 內容。"""
    if current_user is None or not bool(current_user.is_active):
        return False
    if current_user.role == 'admin':
        return True
    role = Role.query.filter_by(code=current_user.role).first()
    return bool(role and role.has_permission(permission))


def has_permission(current_user: User | None, permission: str) -> bool:
    """供 ownership 等 route 內授權邊界使用的同一判定。"""
    return role_grants_permission(current_user, permission)


def require_permissions(
    *permissions: str,
    mode: Literal['all', 'any'] = 'all',
):
    """不改變 view 呼叫參數，以 g.current_user_model 檢查當前權限。"""
    if not permissions or any(not isinstance(item, str) or not item for item in permissions):
        raise ValueError('至少必須指定一項有效權限')
    if mode not in {'all', 'any'}:
        raise ValueError("mode 只能是 'all' 或 'any'")

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            current_user = getattr(g, 'current_user_model', None)
            checks = [
                role_grants_permission(current_user, permission)
                for permission in permissions
            ]
            allowed = all(checks) if mode == 'all' else any(checks)
            if not allowed:
                raise AuthorizationError(
                    '權限不足',
                    details={'required': list(permissions), 'mode': mode},
                )
            return view(*args, **kwargs)

        inherited_guards = tuple(getattr(view, '__authorization_guards__', ()))
        wrapped.__authorization_guards__ = (
            *inherited_guards,
            {'permissions': tuple(permissions), 'mode': mode},
        )
        inherited_permissions = tuple(getattr(view, '__required_permissions__', ()))
        wrapped.__required_permissions__ = tuple(dict.fromkeys(
            (*inherited_permissions, *permissions)
        ))
        return wrapped

    return decorator


def require_permission(permission: str):
    """單一權限的相容 alias。"""
    return require_permissions(permission)


def require_perm(permission: str):
    """舊式 route 名稱的相容 alias。"""
    return require_permissions(permission)


def can_edit_ncmr(current_user: User | None, ncmr: NCMR) -> bool:
    """NCMR 全域編輯或非空 inspector ownership 的精確邊界。"""
    return has_permission(current_user, 'ncmr.edit') or (
        has_permission(current_user, 'ncmr.edit_own')
        and current_user is not None
        and current_user.inspector_id is not None
        and current_user.inspector_id == ncmr.inspector_id
    )
