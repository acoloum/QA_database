"""權限閘門（require_perm）回歸測試。

驗證 pyrometry 等模組的寫入/刪除路由確實受權限保護：
- 無權限角色 → 403
- 有對應權限角色 → 非 403（順利進入處理函式）
- edit 與 delete 為獨立權限
- admin 一律放行
- GET 讀取路由維持對所有已登入者開放
"""
import pytest
from backend.models import Role, User
from backend.utils import hash_password, generate_token


def _make_user(db_session, username, role_code):
    user = User(username=username, password=hash_password('pw12345678'),
                role=role_code, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user):
    token = generate_token(user.id, user.username, user.role)
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


@pytest.fixture
def roles(db_session):
    """editor 具備 pyrometry.edit（無 delete）；viewer 僅有 view。"""
    db_session.add(Role(code='editor', name='可編輯',
                        permissions={'pyrometry.edit': True, 'pyrometry.view': True}))
    db_session.add(Role(code='viewer', name='唯讀',
                        permissions={'pyrometry.view': True}))
    db_session.commit()


def test_write_route_blocks_role_without_permission(client, db_session, roles):
    viewer = _make_user(db_session, 'viewer1', 'viewer')
    resp = client.post('/api/pyrometry/furnaces', headers=_headers(viewer), json={})
    assert resp.status_code == 403


def test_write_route_allows_role_with_permission(client, db_session, roles):
    editor = _make_user(db_session, 'editor1', 'editor')
    # 權限通過後進入處理函式；後續成功或資料驗證錯誤皆可，唯獨不能是 403
    resp = client.post('/api/pyrometry/furnaces', headers=_headers(editor), json={})
    assert resp.status_code != 403


def test_delete_requires_separate_delete_permission(client, db_session, roles):
    # editor 有 edit 但沒有 delete → 刪除應被擋
    editor = _make_user(db_session, 'editor2', 'editor')
    resp = client.delete('/api/pyrometry/furnaces/1', headers=_headers(editor))
    assert resp.status_code == 403


def test_admin_bypasses_permission(client, db_session, roles):
    admin = _make_user(db_session, 'admin_pg', 'admin')
    # admin 一律放行：資源不存在會回 404，但絕不會是 403
    resp = client.delete('/api/pyrometry/furnaces/999', headers=_headers(admin))
    assert resp.status_code != 403


def test_read_route_open_to_any_authenticated_user(client, db_session, roles):
    viewer = _make_user(db_session, 'viewer2', 'viewer')
    resp = client.get('/api/pyrometry/furnaces', headers=_headers(viewer))
    assert resp.status_code != 403
