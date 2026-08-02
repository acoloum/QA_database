"""集中權限裝飾器的行為測試。"""

import pytest
from flask import g
from unittest.mock import MagicMock, patch

from backend.models import Role, User


def test_require_permission_allows_when_has_perm(app):
    """有權限時裝飾器允許通過"""
    with app.app_context():
        from backend.authorization import require_permission

        mock_role = MagicMock()
        mock_role.has_permission.return_value = True

        mock_user = MagicMock()
        mock_user.role = 'qc_manager'

        with patch('backend.authorization.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_role

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                g.current_user_model = mock_user
                result = view(mock_user)
                assert result == ('ok', 200)


def test_require_permission_blocks_when_no_perm(app):
    """無權限時回傳 403"""
    with app.app_context():
        from backend.authorization import require_permission

        mock_role = MagicMock()
        mock_role.has_permission.return_value = False

        mock_user = MagicMock()
        mock_user.role = 'inspector'

        with patch('backend.authorization.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_role

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                from backend.errors import AuthorizationError
                g.current_user_model = mock_user
                with pytest.raises(AuthorizationError) as caught:
                    view(mock_user)
                assert caught.value.status_code == 403


def test_require_permission_blocks_when_no_role(app):
    """角色不存在時回傳 403"""
    with app.app_context():
        from backend.authorization import require_permission

        mock_user = MagicMock()
        mock_user.role = 'nonexistent'

        with patch('backend.authorization.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = None

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                from backend.errors import AuthorizationError
                g.current_user_model = mock_user
                with pytest.raises(AuthorizationError) as caught:
                    view(mock_user)
                assert caught.value.status_code == 403


def test_require_permissions_uses_request_user_model_without_changing_signature(
    app,
    db_session,
):
    """若 decorator 改用 request.user 或對 view 注入額外參數，此測試會失敗。"""
    from backend.authorization import require_permissions

    role = Role(
        code='matrix_editor',
        name='矩陣編輯者',
        permissions={'complaint.edit': True, 'capa.create': True},
    )
    user = User(
        username='matrix-editor',
        password='test',
        role=role.code,
        is_active=True,
    )
    db_session.add_all([role, user])
    db_session.commit()

    @require_permissions('complaint.edit', 'capa.create')
    def view(record_id):
        return {'record_id': record_id}, 200

    with app.test_request_context():
        g.current_user_model = user
        assert view(17) == ({'record_id': 17}, 200)


def test_require_permissions_any_mode_accepts_one_current_role_grant(
    app,
    db_session,
):
    """若 any 模式誤用 all，只有一項權限的使用者會被誤擋。"""
    from backend.authorization import require_permissions

    role = Role(
        code='one_grant',
        name='單一權限',
        permissions={'calibration.view': True},
    )
    user = User(
        username='one-grant',
        password='test',
        role=role.code,
        is_active=True,
    )
    db_session.add_all([role, user])
    db_session.commit()

    @require_permissions('calibration.view', 'msa.view', mode='any')
    def view():
        return 'ok', 200

    with app.test_request_context():
        g.current_user_model = user
        assert view() == ('ok', 200)


def test_require_permissions_rejects_missing_context_with_stable_403(app):
    """權限 decorator 若離開 auth_required 使用，不可放行或拋出 AttributeError。"""
    from backend.authorization import require_permissions
    from backend.errors import AuthorizationError

    @require_permissions('ncmr.view')
    def view():
        return 'unsafe', 200

    with app.test_request_context():
        with pytest.raises(AuthorizationError) as caught:
            view()
        assert caught.value.status_code == 403
        assert caught.value.details == {
            'required': ['ncmr.view'],
            'mode': 'all',
        }


def test_seed_roles_applies_approved_route_permission_matrix(app, db_session):
    """執行真實 seed，確保新部署與 Migration 51 的角色矩陣同步。"""
    from backend.seeds.seed_roles import seed

    untouched = Role(
        code='custom_seed_role',
        name='未批准自訂角色',
        permissions={'custom.keep': True, 'mechanical.delete': True},
    )
    db_session.add(untouched)
    db_session.commit()
    seed()

    roles = {role.code: role.permissions for role in Role.query.all()}
    task_4_keys = {
        'tolerance.view', 'mechanical.view', 'mechanical.create',
        'mechanical.edit', 'mechanical.delete', 'task.view',
        'analytics.view', 'vendor.view',
    }
    expected_grants = {
        'inspector': {
            'tolerance.view', 'mechanical.view', 'mechanical.create', 'task.view',
        },
        'qa_supervisor': {
            'tolerance.view', 'mechanical.view', 'mechanical.create',
            'mechanical.edit', 'task.view',
        },
        'qc_manager': task_4_keys,
        'admin': task_4_keys,
    }

    for role_code, expected in expected_grants.items():
        expected_boolean_patch = {
            key: key in expected
            for key in task_4_keys
        }
        actual_boolean_patch = {
            key: roles[role_code].get(key)
            for key in task_4_keys
        }
        assert actual_boolean_patch == expected_boolean_patch

    assert roles['inspector']['ncmr.create'] is True
    assert roles['qa_supervisor']['capa.edit'] is True
    assert roles['qc_manager']['spc.approve'] is True
    assert roles['admin']['user.manage'] is True
    assert roles['custom_seed_role'] == {
        'custom.keep': True,
        'mechanical.delete': True,
    }
