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


def test_capa_step_update_requires_capa_edit_permission(client, db_session):
    """CAPA 步驟更新不可只靠登入，需具備 capa.edit 權限。"""
    db_session.add(Role(code='capa_viewer', name='CAPA 唯讀',
                        permissions={'capa.view': True}))
    db_session.commit()
    viewer = _make_user(db_session, 'capa_viewer1', 'capa_viewer')

    resp = client.patch(
        '/api/capas/1/step',
        headers=_headers(viewer),
        json={'D2_what': '未授權更新'},
    )

    assert resp.status_code == 403


@pytest.fixture
def patrol_roles(db_session):
    """patrol_editor 具備 patrol.edit；patrol_viewer 僅有 patrol.view。"""
    db_session.add(Role(code='patrol_editor', name='巡檢可編輯',
                        permissions={'patrol.edit': True, 'patrol.view': True}))
    db_session.add(Role(code='patrol_viewer', name='巡檢唯讀',
                        permissions={'patrol.view': True}))
    db_session.commit()


def test_patrol_exclusion_route_requires_patrol_edit_permission(client, db_session, patrol_roles):
    from backend.models import PatrolMain, PatrolDetail
    from datetime import date

    patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
    db_session.add(patrol)
    db_session.flush()
    detail = PatrolDetail(main_id=patrol.id, group=1, item='外徑', position='前段', min_val=9.8, max_val=10.2)
    db_session.add(detail)
    db_session.commit()

    viewer = _make_user(db_session, 'patrol_viewer1', 'patrol_viewer')
    resp = client.patch(f'/api/patrol-details/{detail.id}/exclusion',
                         headers=_headers(viewer), json={'排除統計': True, '排除原因': '測試'})
    assert resp.status_code == 403

    editor = _make_user(db_session, 'patrol_editor1', 'patrol_editor')
    resp = client.patch(f'/api/patrol-details/{detail.id}/exclusion',
                         headers=_headers(editor), json={'排除統計': True, '排除原因': '測試'})
    assert resp.status_code != 403


def test_patrol_legacy_control_limit_writes_are_read_only(client, db_session, patrol_roles):
    from backend.models import PatrolMain, PatrolDetail
    from datetime import date

    # 供 POST 呼叫 get_spc 時有實際資料可計算，避免因無資料早退路徑
    # （空 rows 只回傳 {"labels": [], "avgs": [], "ranges": []}）導致
    # 路由裡 stats[k] 的 dict comprehension 因缺鍵而 500，與權限測試本意無關。
    patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
    db_session.add(patrol)
    db_session.flush()
    detail = PatrolDetail(main_id=patrol.id, group=1, item='外徑', position='', min_val=9.8, max_val=10.2)
    db_session.add(detail)
    db_session.commit()

    viewer = _make_user(db_session, 'patrol_viewer2', 'patrol_viewer')
    body = {'material': '6061', 'spec': '10*2', 'item': '外徑', 'position': ''}

    resp = client.post('/api/patrol/control-limits', headers=_headers(viewer), json=body)
    assert resp.status_code == 410
    assert resp.get_json()['code'] == 'LEGACY_SPC_LIMITS_READ_ONLY'

    resp = client.delete(
        '/api/patrol/control-limits?material=6061&spec=10*2&item=外徑&position=',
        headers=_headers(viewer),
    )
    assert resp.status_code == 410

    # GET（查詢）不受權限限制，僅需登入
    resp = client.get(
        '/api/patrol/control-limits?material=6061&spec=10*2&item=外徑&position=',
        headers=_headers(viewer),
    )
    assert resp.status_code != 403

    editor = _make_user(db_session, 'patrol_editor2', 'patrol_editor')

    resp = client.post('/api/patrol/control-limits', headers=_headers(editor), json=body)
    assert resp.status_code == 410

    resp = client.delete(
        '/api/patrol/control-limits?material=6061&spec=10*2&item=外徑&position=',
        headers=_headers(editor),
    )
    assert resp.status_code == 410
