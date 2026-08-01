"""
使用者管理 API 測試（auth routes）
"""
from datetime import datetime, timedelta, timezone
from functools import wraps
import os
from threading import Event, Thread, current_thread
from uuid import uuid4

import jwt
import pytest
from flask import g, jsonify
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.app import app as flask_app
from backend.config import SECRET_KEY
from backend.extensions import db
from backend.models import AuditLog, NCMR, Inspector, Role, User
from backend.services.user_service import UserService
from backend.utils import auth_required, generate_token, hash_password, verify_password


# ── 輔助函式 ────────────────────────────────────────────────────

def make_admin_headers(admin_user):
    """產生管理員 JWT Header"""
    token = generate_token(
        admin_user.id,
        admin_user.username,
        'admin',
        admin_user.token_version,
    )
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def make_user_headers(user):
    """以使用者目前憑證版本產生 JWT Header。"""
    token = generate_token(
        user.id,
        user.username,
        user.role,
        user.token_version,
    )
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _read_current_user_model_from_g(handler):
    """測試用內層 decorator：透過真實 Flask request context 讀取 g。"""
    @wraps(handler)
    def wrapped(*args, **kwargs):
        current_user_model = getattr(g, 'current_user_model', None)
        g.inner_current_user_id = getattr(current_user_model, 'id', None)
        return handler(*args, **kwargs)
    return wrapped


@flask_app.get('/_test/auth/current-user-model')
@auth_required
@_read_current_user_model_from_g
def _protected_current_user_model_route():
    """以真實 protected route 驗證 auth seam 對 Flask g 的契約。"""
    current_user_model = getattr(g, 'current_user_model', None)
    return jsonify({
        'inner_user_id': getattr(g, 'inner_current_user_id', None),
        'handler_user_id': getattr(current_user_model, 'id', None),
        'handler_username': getattr(current_user_model, 'username', None),
        'is_user_model': isinstance(current_user_model, User),
    })


@pytest.fixture
def admin_user(db_session):
    """在測試資料庫中建立管理員帳號"""
    user = User(
        username='admin_test',
        password=hash_password('adminpass123'),
        role='admin',
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def normal_user(db_session):
    """在測試資料庫中建立一般使用者"""
    user = User(
        username='user_test',
        password=hash_password('userpass123'),
        role='user',
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


# ── 新增使用者：role 驗證 ────────────────────────────────────────

def test_create_user_rejects_invalid_role(client, admin_user):
    """create_user 應拒絕非法 role 值"""
    headers = make_admin_headers(admin_user)
    resp = client.post('/api/users', headers=headers, json={
        'username': 'newuser',
        'password': 'password123',
        'role': 'superuser'  # 非法值
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'error' in data


def test_create_user_accepts_valid_roles(client, admin_user):
    """create_user 應接受 'user' 與 'admin' 角色"""
    headers = make_admin_headers(admin_user)

    resp = client.post('/api/users', headers=headers, json={
        'username': 'new_user_role',
        'password': 'password123',
        'role': 'user'
    })
    assert resp.status_code == 200

    resp2 = client.post('/api/users', headers=headers, json={
        'username': 'new_admin_role',
        'password': 'password123',
        'role': 'admin'
    })
    assert resp2.status_code == 200


def test_create_user_accepts_role_defined_in_role_table(client, admin_user, db_session):
    """create_user 應接受角色表中已定義的細粒度角色。"""
    db_session.add(Role(
        code='qc_manager',
        name='品管主管',
        permissions={'user.manage': True},
    ))
    db_session.commit()

    headers = make_admin_headers(admin_user)
    resp = client.post('/api/users', headers=headers, json={
        'username': 'qc_manager_user',
        'password': 'password123',
        'role': 'qc_manager'
    })

    assert resp.status_code == 200
    created = User.query.filter_by(username='qc_manager_user').first()
    assert created.role == 'qc_manager'


def test_user_manage_permission_can_create_user(client, db_session):
    """具備 user.manage 權限的非 admin 角色也應可管理使用者。"""
    db_session.add(Role(
        code='qc_manager',
        name='品管主管',
        permissions={'user.manage': True},
    ))
    manager = User(
        username='manager_test',
        password=hash_password('managerpass123'),
        role='qc_manager',
        is_active=True
    )
    db_session.add(manager)
    db_session.commit()

    token = generate_token(
        manager.id,
        manager.username,
        manager.role,
        manager.token_version,
    )
    resp = client.post('/api/users', headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }, json={
        'username': 'managed_user',
        'password': 'password123',
        'role': 'user'
    })

    assert resp.status_code == 200
    assert User.query.filter_by(username='managed_user').first() is not None


# ── 新增使用者：使用者名稱格式驗證 ──────────────────────────────

def test_create_user_rejects_short_username(client, admin_user):
    """create_user 應拒絕長度不足的使用者名稱（< 3 字元）"""
    headers = make_admin_headers(admin_user)
    resp = client.post('/api/users', headers=headers, json={
        'username': 'ab',
        'password': 'password123',
        'role': 'user'
    })
    assert resp.status_code == 400


def test_create_user_rejects_too_long_username(client, admin_user):
    """create_user 應拒絕超過 50 字元的使用者名稱"""
    headers = make_admin_headers(admin_user)
    resp = client.post('/api/users', headers=headers, json={
        'username': 'a' * 51,
        'password': 'password123',
        'role': 'user'
    })
    assert resp.status_code == 400


def test_create_user_rejects_invalid_characters(client, admin_user):
    """create_user 應拒絕含有特殊字元的使用者名稱"""
    headers = make_admin_headers(admin_user)
    resp = client.post('/api/users', headers=headers, json={
        'username': 'user name!',  # 含空格與驚嘆號
        'password': 'password123',
        'role': 'user'
    })
    assert resp.status_code == 400


# ── 新增使用者：ORM 正確建立 ────────────────────────────────────

def test_create_user_persists_via_orm(client, admin_user, db_session):
    """create_user 應透過 ORM 將使用者存入資料庫"""
    headers = make_admin_headers(admin_user)
    resp = client.post('/api/users', headers=headers, json={
        'username': 'orm_created_user',
        'password': 'password123',
        'role': 'user'
    })
    assert resp.status_code == 200

    # 驗證資料確實透過 ORM 寫入
    created = User.query.filter_by(username='orm_created_user').first()
    assert created is not None
    assert created.role == 'user'
    assert created.is_active is True


# ── 使用者列表：回傳 created_at ──────────────────────────────────

def test_list_users_returns_created_at(client, admin_user):
    """GET /api/users 應回傳每位使用者的 created_at 欄位"""
    headers = make_admin_headers(admin_user)
    resp = client.get('/api/users', headers=headers)
    assert resp.status_code == 200
    users = resp.get_json()
    assert len(users) > 0
    for u in users:
        assert 'created_at' in u, f"使用者 {u.get('username')} 缺少 created_at 欄位"


def test_create_user_has_created_at(client, admin_user, db_session):
    """新建使用者後 created_at 應自動填入"""
    headers = make_admin_headers(admin_user)
    client.post('/api/users', headers=headers, json={
        'username': 'ts_user',
        'password': 'password123',
        'role': 'user'
    })
    user = User.query.filter_by(username='ts_user').first()
    assert user is not None
    assert user.created_at is not None


# ── Token 即時撤銷與目前帳號狀態 ─────────────────────────────────

def test_legacy_token_without_version_is_rejected(client, normal_user):
    """移除 token_version 檢查會讓舊 JWT 繼續通過。"""
    token = jwt.encode({
        'user_id': normal_user.id,
        'username': normal_user.username,
        'role': normal_user.role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=1),
    }, SECRET_KEY, algorithm='HS256')

    response = client.get(
        '/api/verify-token',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 401


def test_token_version_mismatch_is_rejected(client, normal_user):
    """忽略資料庫中的目前版本會讓已撤銷 JWT 繼續通過。"""
    token = generate_token(
        normal_user.id,
        normal_user.username,
        normal_user.role,
        normal_user.token_version + 1,
    )

    response = client.get(
        '/api/verify-token',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ('mutation', 'expected_version_increase'),
    (
        ('deactivate', 1),
        ('activate', 2),
        ('promote_role', 1),
        ('demote_role', 1),
        ('reset_password', 1),
    ),
)
def test_account_security_change_revokes_existing_token(
    client,
    db_session,
    admin_user,
    normal_user,
    mutation,
    expected_version_increase,
):
    """任一安全狀態異動若未遞增版本，舊 JWT 仍可重播。"""
    if mutation == 'demote_role':
        normal_user.role = 'admin'
        db_session.commit()
    admin_headers = make_admin_headers(admin_user)
    old_headers = make_user_headers(normal_user)
    original_version = normal_user.token_version

    if mutation == 'deactivate':
        changed = client.put(
            f'/api/users/{normal_user.id}/active',
            headers=admin_headers,
            json={'is_active': False},
        )
    elif mutation == 'activate':
        disabled = client.put(
            f'/api/users/{normal_user.id}/active',
            headers=admin_headers,
            json={'is_active': False},
        )
        assert disabled.status_code == 200
        changed = client.put(
            f'/api/users/{normal_user.id}/active',
            headers=admin_headers,
            json={'is_active': True},
        )
    elif mutation in {'promote_role', 'demote_role'}:
        changed = client.put(
            f'/api/users/{normal_user.id}/role',
            headers=admin_headers,
            json={'role': 'user' if mutation == 'demote_role' else 'admin'},
        )
    else:
        changed = client.put(
            f'/api/users/{normal_user.id}/password',
            headers=admin_headers,
            json={'password': 'new-password-123'},
        )

    assert changed.status_code == 200
    db_session.refresh(normal_user)
    assert normal_user.token_version == original_version + expected_version_increase
    assert client.get('/api/verify-token', headers=old_headers).status_code == 401


def test_disabled_account_cannot_read_or_mutate_ncmr(
    client,
    db_session,
    admin_user,
):
    """認證若未先查停用狀態，舊 JWT 仍可讀取及寫入 NCMR。"""
    writer_role = Role(
        code='ncmr_writer',
        name='NCMR 建立者',
        permissions={'ncmr.create': True},
    )
    inspector = Inspector(name='停用帳號檢驗員')
    user = User(
        username='disabled_ncmr_writer',
        password=hash_password('writer-password'),
        role='ncmr_writer',
        is_active=True,
        inspector=inspector,
    )
    db_session.add_all([writer_role, inspector, user])
    db_session.commit()
    old_headers = make_user_headers(user)

    disabled = client.put(
        f'/api/users/{user.id}/active',
        headers=make_admin_headers(admin_user),
        json={'is_active': False},
    )
    assert disabled.status_code == 200
    before_count = NCMR.query.count()

    read_response = client.get('/api/ncmr', headers=old_headers)
    write_response = client.post('/api/ncmr/add', headers=old_headers, json={
        '日期': '2026-08-01',
        '來源': '停用帳號測試',
        '發現人員姓名': inspector.name,
        '不良描述': '此筆不得建立',
    })

    assert read_response.status_code == 401
    assert write_response.status_code == 401
    assert NCMR.query.count() == before_count


def test_authentication_uses_current_role_permissions_and_inspector(
    app,
    db_session,
    normal_user,
):
    """把 JWT claims 當授權來源會回傳過期的角色、權限與檢驗員。"""
    original_role = Role(
        code='original_role',
        name='原角色',
        permissions={'mechanical.create': True},
    )
    current_role = Role(
        code='current_role',
        name='目前角色',
        permissions={'mechanical.create': False, 'shipping.view': True},
    )
    inspector = Inspector(name='目前檢驗員')
    db_session.add_all([original_role, current_role, inspector])
    normal_user.role = original_role.code
    db_session.commit()
    token = generate_token(
        normal_user.id,
        normal_user.username,
        normal_user.role,
        normal_user.token_version,
    )

    normal_user.role = current_role.code
    normal_user.inspector_id = inspector.id
    db_session.commit()

    from backend.authentication import authenticate_request_token

    with app.app_context():
        current_model, authenticated = authenticate_request_token(token)

    assert current_model.id == normal_user.id
    assert authenticated.role == 'current_role'
    assert authenticated.permissions == {
        'mechanical.create': False,
        'shipping.view': True,
    }
    assert authenticated.inspector_id == inspector.id


def test_protected_route_exposes_current_database_user_model_on_g(
    client,
    db_session,
    normal_user,
):
    """若 auth seam 未設定 g.current_user_model，內層 decorator 與 handler 讀不到目前 User。"""
    headers = make_user_headers(normal_user)
    normal_user.username = '目前資料庫帳號名稱'
    db_session.commit()

    response = client.get('/_test/auth/current-user-model', headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {
        'inner_user_id': normal_user.id,
        'handler_user_id': normal_user.id,
        'handler_username': '目前資料庫帳號名稱',
        'is_user_model': True,
    }


def test_require_perm_uses_current_database_role(client, db_session, normal_user):
    """舊式 require_perm 若仍信任 JWT role，降權後會進入 mutation handler。"""
    allowed = Role(
        code='mechanical_writer',
        name='機械寫入者',
        permissions={'mechanical.create': True},
    )
    denied = Role(
        code='mechanical_viewer',
        name='機械檢視者',
        permissions={'mechanical.create': False},
    )
    db_session.add_all([allowed, denied])
    normal_user.role = allowed.code
    db_session.commit()
    headers = make_user_headers(normal_user)

    normal_user.role = denied.code
    db_session.commit()

    response = client.post('/api/mechanical/tests', headers=headers, json={})

    assert response.status_code == 403


# ── 使用者安全狀態異動的交易與稽核 ─────────────────────────────

@pytest.mark.parametrize(
    ('path_suffix', 'payload', 'expected_action'),
    (
        ('active', {'is_active': False}, 'update_active'),
        ('role', {'role': 'admin'}, 'update_role'),
        ('password', {'password': 'audited-password'}, 'reset_password'),
    ),
)
def test_account_security_change_increments_version_and_writes_audit(
    client,
    db_session,
    admin_user,
    normal_user,
    path_suffix,
    payload,
    expected_action,
):
    """漏掉版本或 audit 任一 side effect 都會失去撤銷追溯證據。"""
    original_version = normal_user.token_version

    response = client.put(
        f'/api/users/{normal_user.id}/{path_suffix}',
        headers=make_admin_headers(admin_user),
        json=payload,
    )

    assert response.status_code == 200
    db_session.refresh(normal_user)
    assert normal_user.token_version == original_version + 1
    audit = AuditLog.query.filter_by(
        user_id=admin_user.id,
        action=expected_action,
        module='USER',
        record_id=normal_user.id,
    ).one()
    assert audit.new_value['token_version'] == normal_user.token_version
    if path_suffix == 'password':
        assert verify_password(payload['password'], normal_user.password)
        assert 'password' not in audit.new_value


def test_account_change_rolls_back_when_audit_insert_fails(
    client,
    db_session,
    admin_user,
    normal_user,
):
    """audit 失敗若未共用交易，角色與憑證版本會留下無稽核異動。"""
    original_role = normal_user.role
    original_version = normal_user.token_version

    def reject_audit(_mapper, _connection, _target):
        raise RuntimeError('audit insert failed')

    event.listen(AuditLog, 'before_insert', reject_audit)
    try:
        response = client.put(
            f'/api/users/{normal_user.id}/role',
            headers=make_admin_headers(admin_user),
            json={'role': 'admin'},
        )
    finally:
        event.remove(AuditLog, 'before_insert', reject_audit)

    assert response.status_code == 500
    db_session.expire_all()
    persisted = db_session.get(User, normal_user.id)
    assert persisted.role == original_role
    assert persisted.token_version == original_version


def test_reset_password_requires_user_manage_permission(
    client,
    normal_user,
    db_session,
):
    """重設密碼 endpoint 若缺正式後端權限可被一般帳號濫用。"""
    target = User(
        username='password_reset_target',
        password=hash_password('original-password'),
        role='user',
        is_active=True,
    )
    db_session.add(target)
    db_session.commit()

    response = client.put(
        f'/api/users/{target.id}/password',
        headers=make_user_headers(normal_user),
        json={'password': 'unauthorized-password'},
    )

    assert response.status_code == 403
    db_session.refresh(target)
    assert verify_password('original-password', target.password)


@pytest.mark.parametrize('password', ('', '1234567'))
def test_reset_password_requires_at_least_eight_characters(
    client,
    admin_user,
    normal_user,
    password,
):
    """密碼重設缺少長度邊界會接受空白或七字元密碼。"""
    response = client.put(
        f'/api/users/{normal_user.id}/password',
        headers=make_admin_headers(admin_user),
        json={'password': password},
    )

    assert response.status_code == 400


@pytest.fixture
def postgres_user_service_app():
    """以唯一 schema 建立 UserService PostgreSQL 併發測試環境。"""
    database_url = os.getenv('TOKEN_VERSION_TEST_DATABASE_URL')
    if not database_url:
        pytest.skip('未設定 TOKEN_VERSION_TEST_DATABASE_URL')

    root_engine = create_engine(database_url, pool_pre_ping=True)
    schema_name = f'token_version_service_{uuid4().hex}'
    pg_app = None
    try:
        with root_engine.connect() as connection:
            if connection.dialect.name != 'postgresql':
                pytest.fail('TOKEN_VERSION_TEST_DATABASE_URL 必須指向 PostgreSQL')
            current_database = connection.execute(text('SELECT current_database()')).scalar_one()
            if not current_database.startswith('codex_token50_'):
                pytest.fail('UserService 併發測試僅允許 codex_token50_ 前綴的隔離資料庫')
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.commit()

        from flask import Flask

        pg_app = Flask(f'user-service-postgresql-{schema_name}')
        pg_app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=database_url,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={
                'pool_pre_ping': True,
                'connect_args': {
                    'options': f'-csearch_path={schema_name},public',
                },
            },
        )
        db.init_app(pg_app)

        @pg_app.get('/protected')
        @auth_required
        def protected_route():
            return jsonify({'user_id': g.current_user_model.id})

        with pg_app.app_context():
            db.metadata.create_all(
                bind=db.engine,
                tables=[
                    Inspector.__table__,
                    Role.__table__,
                    User.__table__,
                    AuditLog.__table__,
                ],
            )
            actor = User(
                username='postgres_actor',
                password=hash_password('actor-password'),
                role='admin',
                is_active=True,
            )
            target = User(
                username='postgres_target',
                password=hash_password('target-password'),
                role='user',
                is_active=True,
            )
            db.session.add_all([actor, target])
            db.session.commit()
            identifiers = {
                'actor_id': actor.id,
                'target_id': target.id,
                'initial_version': target.token_version,
            }

        yield pg_app, identifiers
    finally:
        if pg_app is not None:
            with pg_app.app_context():
                db.session.remove()
                db.engine.dispose()
        try:
            with root_engine.connect() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                connection.commit()
        finally:
            root_engine.dispose()


def test_postgresql_concurrent_security_changes_increment_each_commit_and_revoke_intermediate_token(
    postgres_user_service_app,
):
    """未鎖定 User row 的 RMW 會遺失一次版本遞增，並讓中間版本 token 繼續有效。"""
    pg_app, identifiers = postgres_user_service_app
    first_at_commit = Event()
    allow_first_commit = Event()
    second_at_commit = Event()
    intermediate_token_issued = Event()
    results = {}
    errors = []

    def synchronize_commits(_session):
        if current_thread().name == 'token-change-first':
            first_at_commit.set()
            if not allow_first_commit.wait(timeout=5):
                raise TimeoutError('等待第一個安全異動提交逾時')
        elif current_thread().name == 'token-change-second':
            second_at_commit.set()
            if not intermediate_token_issued.wait(timeout=5):
                raise TimeoutError('等待中間版本 token 簽發逾時')

    def first_change():
        with pg_app.app_context():
            try:
                changed = UserService.set_role(
                    identifiers['actor_id'],
                    identifiers['target_id'],
                    'admin',
                )
                results['first_version'] = changed.token_version
                results['intermediate_token'] = generate_token(
                    changed.id,
                    changed.username,
                    changed.role,
                    changed.token_version,
                )
                intermediate_token_issued.set()
            except Exception as error:  # pragma: no cover - 由主執行緒顯示原始錯誤
                errors.append(error)
                intermediate_token_issued.set()
            finally:
                db.session.remove()

    def second_change():
        with pg_app.app_context():
            try:
                changed = UserService.reset_password(
                    identifiers['actor_id'],
                    identifiers['target_id'],
                    'concurrent-password',
                )
                results['second_version'] = changed.token_version
            except Exception as error:  # pragma: no cover - 由主執行緒顯示原始錯誤
                errors.append(error)
            finally:
                db.session.remove()

    event.listen(Session, 'before_commit', synchronize_commits)
    first_thread = Thread(target=first_change, name='token-change-first')
    second_thread = Thread(target=second_change, name='token-change-second')
    try:
        first_thread.start()
        assert first_at_commit.wait(timeout=5), '第一個安全異動未進入 commit'
        second_thread.start()
        second_entered_commit_while_first_locked = second_at_commit.wait(timeout=0.75)
        allow_first_commit.set()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)
    finally:
        allow_first_commit.set()
        intermediate_token_issued.set()
        first_thread.join(timeout=1)
        second_thread.join(timeout=1)
        event.remove(Session, 'before_commit', synchronize_commits)

    assert not first_thread.is_alive(), '第一個 PostgreSQL session 未在 timeout 內結束'
    assert not second_thread.is_alive(), '第二個 PostgreSQL session 未在 timeout 內結束'
    assert errors == []
    assert second_entered_commit_while_first_locked is False
    assert results['first_version'] == identifiers['initial_version'] + 1

    with pg_app.app_context():
        persisted = db.session.get(User, identifiers['target_id'])
        assert persisted.token_version == identifiers['initial_version'] + 2
        assert results['second_version'] == persisted.token_version
        audits = AuditLog.query.filter_by(record_id=persisted.id).order_by(AuditLog.id).all()
        assert [audit.new_value['token_version'] for audit in audits] == [1, 2]
        response = pg_app.test_client().get(
            '/protected',
            headers={'Authorization': f"Bearer {results['intermediate_token']}"},
        )
        assert response.status_code == 401
