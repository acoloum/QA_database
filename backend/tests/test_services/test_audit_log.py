"""審計日誌、交易邊界與角色權限整合測試。"""
import ast
import datetime
from decimal import Decimal
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from flask import g
from backend.errors import AuthorizationError
from backend.models import AuditLog, User, Role
from backend.services.audit_service import AuditService


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


def test_audit_service_serializes_supported_values_and_redacts_secrets(app, db_session):
    """稽核快照需可 JSON 化，且不得保存憑證內容。"""
    with app.app_context():
        AuditService.record(
            actor_id=None,
            action='update',
            module='NCMR',
            record_id=7,
            new_value={
                '日期': datetime.date(2026, 8, 1),
                '時間': datetime.datetime(2026, 8, 1, 9, 30),
                '數值': Decimal('1.2300'),
                '巢狀': ({'password': '不可保存', '內容': '可保存'},),
                'access_token': '不可保存',
            },
        )
        db_session.commit()

        entry = AuditLog.query.filter_by(record_id=7).one()
        assert entry.new_value == {
            '日期': '2026-08-01',
            '時間': '2026-08-01T09:30:00',
            '數值': '1.2300',
            '巢狀': [{'password': '[REDACTED]', '內容': '可保存'}],
            'access_token': '[REDACTED]',
        }


def test_audit_service_rejects_action_longer_than_database_contract(app):
    with app.app_context(), pytest.raises(ValueError, match='20'):
        AuditService.record(
            actor_id=None,
            action='x' * 21,
            module='NCMR',
            record_id=1,
        )


def test_audit_service_flushes_without_committing(app, db_session, monkeypatch):
    """AuditService 只加入呼叫方交易，不得自行切斷原子邊界。"""
    commit_calls = []
    monkeypatch.setattr(db_session, 'commit', lambda: commit_calls.append(True))
    with app.app_context():
        AuditService.record(
            actor_id=None,
            action='create',
            module='NCMR',
            record_id=11,
            new_value={'status': '待處理'},
        )

        assert commit_calls == []
        assert AuditLog.query.filter_by(record_id=11).count() == 1
        db_session.rollback()
        assert AuditLog.query.filter_by(record_id=11).count() == 0


def test_route_modules_do_not_commit():
    """route 不得擁有交易 commit，業務與稽核必須由 service 原子寫入。"""
    route_dir = Path(__file__).parents[2] / 'routes'
    violations = []
    for path in route_dir.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != 'commit':
                continue
            owner = node.func.value
            if (
                isinstance(owner, ast.Attribute)
                and owner.attr == 'session'
                and isinstance(owner.value, ast.Name)
                and owner.value.id == 'db'
            ):
                violations.append(f'{path.name}:{node.lineno}')
    assert violations == []


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
        from backend.authorization import require_permission

        mock_user = MagicMock()
        mock_user.role = 'inspector_test'
        mock_user.is_active = True

        @require_permission('ncmr.delete')
        def protected(current_user):
            return 'ok', 200

        with app.test_request_context(), pytest.raises(AuthorizationError):
            g.current_user_model = mock_user
            protected(mock_user)


def test_require_permission_allows_correct_role(app, db_session, setup_roles):
    """require_permission 應允許有此權限的角色"""
    with app.app_context():
        from backend.authorization import require_permission

        mock_user = MagicMock()
        mock_user.role = 'qc_manager_test'
        mock_user.is_active = True

        @require_permission('ncmr.delete')
        def protected(current_user):
            return 'ok', 200

        with app.test_request_context():
            g.current_user_model = mock_user
            result = protected(mock_user)
            assert result == ('ok', 200)
