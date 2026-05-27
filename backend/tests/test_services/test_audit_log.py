"""審計日誌與角色權限整合測試"""
import pytest
from unittest.mock import patch, MagicMock
from backend.models import AuditLog, User, Role


@pytest.fixture
def setup_roles(app, db_session):
    """建立測試用角色"""
    with app.app_context():
        qc_manager = Role(
            code='qc_manager_test',
            name='品管經理測試',
            permissions={'ncmr.delete': True, 'ncmr.create': True}
        )
        inspector = Role(
            code='inspector_test',
            name='檢驗員測試',
            permissions={'ncmr.create': True}
        )
        db_session.add_all([qc_manager, inspector])
        db_session.commit()
        yield {'qc_manager': qc_manager, 'inspector': inspector}


def test_log_audit_creates_record(app, db_session):
    """log_audit 應建立 AuditLog 記錄"""
    with app.app_context():
        from backend.utils import log_audit
        log_audit(
            user_id=None,
            action='create',
            module='NCMR',
            record_id=999,
            new_val={'ncmr_number': 'TEST-001'}
        )
        db_session.commit()

        log = AuditLog.query.filter_by(module='NCMR', record_id=999).first()
        assert log is not None
        assert log.action == 'create'
        assert log.new_value == {'ncmr_number': 'TEST-001'}


def test_log_audit_stores_old_and_new_value(app, db_session):
    """log_audit 應同時儲存 old_value 與 new_value"""
    with app.app_context():
        from backend.utils import log_audit
        log_audit(
            user_id=None,
            action='update',
            module='NCMR',
            record_id=888,
            old_val={'status': 'open'},
            new_val={'status': 'closed'}
        )
        db_session.commit()

        log = AuditLog.query.filter_by(module='NCMR', record_id=888).first()
        assert log is not None
        assert log.old_value == {'status': 'open'}
        assert log.new_value == {'status': 'closed'}
        assert log.action == 'update'


def test_role_has_permission_true(app, db_session, setup_roles):
    """Role.has_permission 對已授權的權限應回傳 True"""
    with app.app_context():
        qc_role = Role.query.filter_by(code='qc_manager_test').first()
        assert qc_role.has_permission('ncmr.delete') is True
        assert qc_role.has_permission('ncmr.create') is True


def test_role_has_permission_false(app, db_session, setup_roles):
    """Role.has_permission 對未授權的權限應回傳 False"""
    with app.app_context():
        inspector_role = Role.query.filter_by(code='inspector_test').first()
        assert inspector_role.has_permission('ncmr.delete') is False


def test_require_permission_blocks_wrong_role(app, db_session, setup_roles):
    """require_permission 應攔截無此權限的角色，回傳 403"""
    with app.app_context():
        from backend.utils import require_permission

        mock_inspector_role = MagicMock()
        mock_inspector_role.has_permission.return_value = False

        mock_user = MagicMock()
        mock_user.role = 'inspector_test'

        with patch('backend.models.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_inspector_role

            @require_permission('ncmr.delete')
            def protected(current_user):
                return 'ok', 200

            with app.test_request_context():
                resp, code = protected(mock_user)
                assert code == 403


def test_require_permission_allows_correct_role(app, db_session, setup_roles):
    """require_permission 應允許有此權限的角色"""
    with app.app_context():
        from backend.utils import require_permission

        mock_manager_role = MagicMock()
        mock_manager_role.has_permission.return_value = True

        mock_user = MagicMock()
        mock_user.role = 'qc_manager_test'

        with patch('backend.models.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_manager_role

            @require_permission('ncmr.delete')
            def protected(current_user):
                return 'ok', 200

            with app.test_request_context():
                result = protected(mock_user)
                assert result == ('ok', 200)
