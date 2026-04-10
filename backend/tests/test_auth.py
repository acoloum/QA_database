"""
使用者管理 API 測試（auth routes）
"""
import pytest
import json
from backend.models import User
from backend.utils import hash_password, generate_token


# ── 輔助函式 ────────────────────────────────────────────────────

def make_admin_headers(admin_user):
    """產生管理員 JWT Header"""
    token = generate_token(admin_user.id, admin_user.username, 'admin')
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
