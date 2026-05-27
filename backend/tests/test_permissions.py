"""require_permission 裝飾器單元測試"""
import pytest
from unittest.mock import MagicMock, patch


def test_require_permission_allows_when_has_perm(app):
    """有權限時裝飾器允許通過"""
    with app.app_context():
        from backend.utils import require_permission

        mock_role = MagicMock()
        mock_role.has_permission.return_value = True

        mock_user = MagicMock()
        mock_user.role = 'qc_manager'

        with patch('backend.models.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_role

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                result = view(mock_user)
                assert result == ('ok', 200)


def test_require_permission_blocks_when_no_perm(app):
    """無權限時回傳 403"""
    with app.app_context():
        from backend.utils import require_permission

        mock_role = MagicMock()
        mock_role.has_permission.return_value = False

        mock_user = MagicMock()
        mock_user.role = 'inspector'

        with patch('backend.models.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_role

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                resp, code = view(mock_user)
                assert code == 403


def test_require_permission_blocks_when_no_role(app):
    """角色不存在時回傳 403"""
    with app.app_context():
        from backend.utils import require_permission

        mock_user = MagicMock()
        mock_user.role = 'nonexistent'

        with patch('backend.models.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = None

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                resp, code = view(mock_user)
                assert code == 403
