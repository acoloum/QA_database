"""
使用者管理 API 測試（auth routes）
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import event

from backend.config import SECRET_KEY
from backend.models import AuditLog, NCMR, Inspector, Role, User
from backend.utils import generate_token, hash_password, verify_password


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
