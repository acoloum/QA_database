"""權限閘門（require_perm）回歸測試。

驗證 pyrometry 等模組的寫入/刪除路由確實受權限保護：
- 無權限角色 → 403
- 有對應權限角色 → 非 403（順利進入處理函式）
- edit 與 delete 為獨立權限
- admin 一律放行
- GET 讀取路由維持對所有已登入者開放
"""
from uuid import UUID

import pytest
from flask import Flask
from sqlalchemy import event, func, select
from werkzeug.routing import (
    AnyConverter,
    FloatConverter,
    IntegerConverter,
    PathConverter,
    UUIDConverter,
)

from backend.extensions import db
from backend.models import (
    CorrectiveAction,
    CustomerComplaint,
    Inspector,
    NCMR,
    PatrolMain,
    ReworkRequest,
    Role,
    ShippingData,
    User,
)
from backend.utils import hash_password, generate_token


def _make_user(db_session, username, role_code):
    user = User(username=username, password=hash_password('pw12345678'),
                role=role_code, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user):
    token = generate_token(user.id, user.username, user.role, user.token_version)
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


@pytest.mark.parametrize(
    ('domain', 'update_path', 'service_name', 'model'),
    [
        ('shipping', '/api/update', 'ShippingService.save_data', ShippingData),
        ('patrol', '/api/patrol/update', 'PatrolService.update_patrol', PatrolMain),
    ],
)
def test_create_only_role_cannot_enter_update_handler_or_write(
    client,
    db_session,
    monkeypatch,
    domain,
    update_path,
    service_name,
    model,
):
    """若 update 錯用 create guard，handler spy 會被呼叫且請求不會是 403。"""
    role_code = f'{domain}_create_only'
    db_session.add(Role(
        code=role_code,
        name=f'{domain} 僅新增',
        permissions={f'{domain}.create': True},
    ))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)
    calls = []

    if service_name.startswith('ShippingService'):
        monkeypatch.setattr(
            'backend.routes.shipping.ShippingService.save_data',
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )
    else:
        monkeypatch.setattr(
            'backend.routes.patrol.PatrolService.update_patrol',
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )
    before = db_session.scalar(select(func.count()).select_from(model))

    response = client.post(update_path, headers=_headers(user), json={'id': 1})

    assert response.status_code == 403
    assert calls == []
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(model)) == before


@pytest.mark.parametrize(
    ('domain', 'update_path', 'monkeypatch_target'),
    [
        ('shipping', '/api/update', 'backend.routes.shipping.ShippingService.save_data'),
        ('patrol', '/api/patrol/update', 'backend.routes.patrol.PatrolService.update_patrol'),
    ],
)
def test_edit_role_enters_update_handler(
    client,
    db_session,
    monkeypatch,
    domain,
    update_path,
    monkeypatch_target,
):
    """若 update 沒有使用 edit guard，具 edit 權限者會在 handler 前被錯擋。"""
    role_code = f'{domain}_edit_only'
    db_session.add(Role(
        code=role_code,
        name=f'{domain} 僅編輯',
        permissions={f'{domain}.edit': True},
    ))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)
    calls = []
    monkeypatch.setattr(
        monkeypatch_target,
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    response = client.post(update_path, headers=_headers(user), json={'id': 1})

    assert response.status_code == 200
    assert len(calls) == 1


@pytest.mark.parametrize(
    ('domain', 'add_path', 'monkeypatch_target'),
    [
        ('shipping', '/api/add', 'backend.routes.shipping.ShippingService.save_data'),
        ('patrol', '/api/patrol/add', 'backend.routes.patrol.PatrolService.add_patrol'),
    ],
)
def test_create_role_still_enters_add_handler(
    client,
    db_session,
    monkeypatch,
    domain,
    add_path,
    monkeypatch_target,
):
    """更新權限分流不可把既有 add 誤改成需要 edit。"""
    role_code = f'{domain}_add_create_only'
    db_session.add(Role(
        code=role_code,
        name=f'{domain} 新增',
        permissions={f'{domain}.create': True},
    ))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)
    calls = []
    monkeypatch.setattr(
        monkeypatch_target,
        lambda *args, **kwargs: calls.append((args, kwargs)) or 1,
    )

    response = client.post(add_path, headers=_headers(user), json={})

    assert response.status_code == 200
    assert len(calls) == 1


@pytest.fixture
def patrol_roles(db_session):
    """一般巡檢編輯與具 SPC 管理權的編輯角色。"""
    db_session.add(Role(code='patrol_editor', name='巡檢可編輯',
                        permissions={'patrol.edit': True, 'patrol.view': True}))
    db_session.add(Role(code='patrol_spc_manager', name='巡檢 SPC 管理',
                        permissions={
                            'patrol.edit': True, 'patrol.view': True,
                            'spc.view': True, 'spc.manage': True,
                        }))
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
    assert resp.status_code == 403

    manager = _make_user(db_session, 'patrol_spc_manager1', 'patrol_spc_manager')
    resp = client.patch(f'/api/patrol-details/{detail.id}/exclusion',
                         headers=_headers(manager), json={'排除統計': True, '排除原因': '測試'})
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

    # GET 同樣需領域 view；viewer 具有該權限。
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


@pytest.mark.parametrize(
    ('method', 'path', 'payload', 'model'),
    [
        ('post', '/api/ncmr/add', {}, NCMR),
        ('post', '/api/capa/create', {}, CorrectiveAction),
        ('post', '/api/complaints', {}, CustomerComplaint),
        ('put', '/api/complaints/1', {}, CustomerComplaint),
        ('post', '/api/rework/apply', {}, ReworkRequest),
        ('post', '/api/rework/approve', {}, ReworkRequest),
        ('post', '/api/rework/close', {}, ReworkRequest),
    ],
)
def test_view_only_roles_cannot_mutate_and_leave_database_unchanged(
    client,
    db_session,
    method,
    path,
    payload,
    model,
):
    """如果代表性 mutation 只檢查登入或 view，回應與 row count 都會暴露。"""
    domain = {
        NCMR: 'ncmr',
        CorrectiveAction: 'capa',
        CustomerComplaint: 'complaint',
        ReworkRequest: 'rework',
    }[model]
    role_code = f'{domain}_view_only_{method}_{path.count("/")}'
    db_session.add(Role(
        code=role_code,
        name=f'{domain} 唯讀',
        permissions={f'{domain}.view': True},
    ))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)
    before = db_session.scalar(select(func.count()).select_from(model))

    response = getattr(client, method)(path, headers=_headers(user), json=payload)

    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(model)) == before


@pytest.mark.parametrize(
    ('path', 'required_view'),
    [
        ('/api/ncmr', 'ncmr.view'),
        ('/api/capas', 'capa.view'),
        ('/api/complaints', 'complaint.view'),
        ('/api/rework/statistics', 'rework.view'),
        ('/api/data', 'shipping.view'),
        ('/api/patrol/options', 'patrol.view'),
        ('/api/tolerance/search', 'tolerance.view'),
        ('/api/extrusion-tolerance/search', 'tolerance.view'),
        ('/api/mechanical/tests', 'mechanical.view'),
        ('/api/pyrometry/furnaces', 'pyrometry.view'),
        ('/api/quality-analytics/pareto', 'analytics.view'),
        ('/api/vendor-performance', 'vendor.view'),
        ('/api/tasks', 'task.view'),
    ],
)
def test_domain_get_requires_its_view_permission(
    client,
    db_session,
    path,
    required_view,
):
    """少掉領域 view decorator 時，空權限的已登入帳號不可讀取資料。"""
    role_code = f'no_view_{required_view.replace(".", "_")}'
    db_session.add(Role(code=role_code, name='無檢視權限', permissions={}))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)

    response = client.get(path, headers=_headers(user))

    assert response.status_code == 403


def test_vendor_performance_refresh_requires_manage_permission(client, db_session):
    """只有 vendor.view 而無 vendor.manage 時，不可觸發績效快照重算。"""
    role_code = 'vendor_view_only'
    db_session.add(Role(
        code=role_code,
        name='廠商績效唯讀',
        permissions={'vendor.view': True},
    ))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)

    response = client.post(
        '/api/vendor-performance/refresh',
        headers=_headers(user),
        json={'period': '2026-08'},
    )

    assert response.status_code == 403


def test_vendor_performance_refresh_allowed_with_manage_permission(client, db_session):
    """具 vendor.manage 權限時 refresh 可執行（無資料月份回 200 與 0 筆）。"""
    role_code = 'vendor_manager'
    db_session.add(Role(
        code=role_code,
        name='廠商績效管理',
        permissions={'vendor.view': True, 'vendor.manage': True},
    ))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)

    response = client.post(
        '/api/vendor-performance/refresh',
        headers=_headers(user),
        json={'period': '2026-08'},
    )

    assert response.status_code == 200
    assert response.get_json()['data']['updated'] == 0


@pytest.mark.parametrize(
    ('permissions', 'path'),
    [
        ({'complaint.edit': True}, '/api/complaints/999/open-capa'),
        ({'capa.create': True}, '/api/complaints/999/open-capa'),
        ({'complaint.edit': True}, '/api/complaints/999/open-rework'),
        ({'rework.create': True}, '/api/complaints/999/open-rework'),
    ],
)
def test_complaint_cross_domain_mutations_require_both_permissions(
    client,
    db_session,
    permissions,
    path,
):
    """跨領域動作少檢查任一側權限時，不可進入資源查詢。"""
    suffix = '_'.join(sorted(key.replace('.', '_') for key in permissions))
    role_code = f'cross_{suffix}'
    db_session.add(Role(code=role_code, name='跨領域單側權限', permissions=permissions))
    db_session.commit()
    user = _make_user(db_session, f'{role_code}_user', role_code)

    response = client.post(path, headers=_headers(user), json={})

    assert response.status_code == 403
    assert db_session.scalar(select(func.count()).select_from(CorrectiveAction)) == 0
    assert db_session.scalar(select(func.count()).select_from(ReworkRequest)) == 0


def _create_ncmr_edit_user(db_session, username, inspector_id, permissions):
    role_code = f'{username}_role'
    db_session.add(Role(code=role_code, name=username, permissions=permissions))
    user = User(
        username=username,
        password=hash_password('pw12345678'),
        role=role_code,
        inspector_id=inspector_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_ncmr_edit_own_allows_only_exact_non_null_inspector_ownership(
    client,
    db_session,
):
    """若 None == None 被當成 ownership，或只檢查 edit_own 不比對擁有者，此測試會失敗。"""
    owner_inspector = Inspector(name='本人')
    other_inspector = Inspector(name='他人')
    db_session.add_all([owner_inspector, other_inspector])
    db_session.flush()
    owned = NCMR(
        ncmr_number='NCMR-OWNED',
        source='測試',
        inspector_id=owner_inspector.id,
        description='原始',
        status='待處理',
    )
    unowned_null = NCMR(
        ncmr_number='NCMR-NULL',
        source='測試',
        inspector_id=None,
        description='原始',
        status='待處理',
    )
    db_session.add_all([owned, unowned_null])
    db_session.commit()

    owner = _create_ncmr_edit_user(
        db_session,
        'ncmr_owner',
        owner_inspector.id,
        {'ncmr.edit_own': True},
    )
    other = _create_ncmr_edit_user(
        db_session,
        'ncmr_other',
        other_inspector.id,
        {'ncmr.edit_own': True},
    )
    no_inspector = _create_ncmr_edit_user(
        db_session,
        'ncmr_none',
        None,
        {'ncmr.edit_own': True},
    )

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(owner),
        json={'識別碼': owned.id, '不良描述': '本人更新'},
    )
    assert response.status_code == 200
    assert db_session.get(NCMR, owned.id).description == '本人更新'

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(other),
        json={'識別碼': owned.id, '不良描述': '越權更新'},
    )
    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(NCMR, owned.id).description == '本人更新'

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(no_inspector),
        json={'識別碼': unowned_null.id, '不良描述': 'None 誤配'},
    )
    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(NCMR, unowned_null.id).description == '原始'


def test_inactive_admin_cannot_bypass_ncmr_ownership(client, db_session):
    """admin 的權限 bypass 不可跳過 Task 3 當前帳號啟用狀態。"""
    ncmr = NCMR(
        ncmr_number='NCMR-ADMIN-INACTIVE',
        source='測試',
        description='原始',
        status='待處理',
    )
    admin = User(
        username='inactive_ncmr_admin',
        password=hash_password('pw12345678'),
        role='admin',
        is_active=False,
    )
    db_session.add_all([ncmr, admin])
    db_session.commit()

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(admin),
        json={'識別碼': ncmr.id, '不良描述': '不應更新'},
    )

    assert response.status_code == 401
    db_session.expire_all()
    assert db_session.get(NCMR, ncmr.id).description == '原始'


def test_ncmr_update_rejects_non_integer_identifier_before_lookup(
    client,
    db_session,
):
    """若權限邊界直接使用未解析 ID，錯誤類型會變成查無資源 404。"""
    editor = _create_ncmr_edit_user(
        db_session,
        'ncmr_invalid_id_editor',
        None,
        {'ncmr.edit': True},
    )
    before = db_session.scalar(select(func.count()).select_from(NCMR))

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(editor),
        json={'識別碼': 'not-an-integer', '不良描述': '不應查詢'},
    )

    assert response.status_code == 422
    assert response.get_json()['error']['code'] == 'VALIDATION_ERROR'
    assert db_session.scalar(select(func.count()).select_from(NCMR)) == before


def test_ncmr_update_checks_ownership_before_full_payload_validation(
    client,
    db_session,
):
    """edit_own 不屬於本人時，即使其餘 payload 無效也須先回 403 且零寫入。"""
    owner_inspector = Inspector(name='NCMR 擁有者')
    other_inspector = Inspector(name='NCMR 非擁有者')
    db_session.add_all([owner_inspector, other_inspector])
    db_session.flush()
    ncmr = NCMR(
        ncmr_number='NCMR-OWNERSHIP-BEFORE-SCHEMA',
        source='測試',
        inspector_id=owner_inspector.id,
        description='原始內容',
        status='待處理',
    )
    db_session.add(ncmr)
    db_session.commit()
    editor = _create_ncmr_edit_user(
        db_session,
        'ncmr_non_owner_invalid_payload',
        other_inspector.id,
        {'ncmr.edit_own': True},
    )

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(editor),
        json={
            '識別碼': ncmr.id,
            '日期': 'not-a-date',
            '未知欄位': 'x',
        },
    )

    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(NCMR, ncmr.id).description == '原始內容'


def test_ncmr_edit_own_hides_missing_record_as_same_ownership_denial(
    client,
    db_session,
):
    """edit_own 不可由 403／404 差異判斷任意 active NCMR 是否存在。"""
    owner_inspector = Inspector(name='存在性測試擁有者')
    other_inspector = Inspector(name='存在性測試查詢者')
    db_session.add_all([owner_inspector, other_inspector])
    db_session.flush()
    ncmr = NCMR(
        ncmr_number='NCMR-EXISTENCE-ORACLE',
        source='測試',
        inspector_id=owner_inspector.id,
        description='原始內容',
        status='待處理',
    )
    db_session.add(ncmr)
    db_session.commit()
    editor = _create_ncmr_edit_user(
        db_session,
        'ncmr_existence_probe',
        other_inspector.id,
        {'ncmr.edit_own': True},
    )
    headers = _headers(editor)

    existing_response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': ncmr.id, '不良描述': '不應更新'},
    )
    missing_response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': ncmr.id + 9999, '不良描述': '不應更新'},
    )

    assert existing_response.status_code == missing_response.status_code == 403
    existing_error = existing_response.get_json()['error']
    missing_error = missing_response.get_json()['error']
    assert {
        key: existing_error.get(key)
        for key in ('code', 'message', 'details')
    } == {
        key: missing_error.get(key)
        for key in ('code', 'message', 'details')
    }
    db_session.expire_all()
    assert db_session.get(NCMR, ncmr.id).description == '原始內容'


def test_ncmr_full_editor_keeps_missing_record_not_found(client, db_session):
    """完整編輯權限可保留正常的找不到資源語意。"""
    editor = _create_ncmr_edit_user(
        db_session,
        'ncmr_full_editor_missing',
        None,
        {'ncmr.edit': True},
    )

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(editor),
        json={'識別碼': 999999, '不良描述': '不存在'},
    )

    assert response.status_code == 404
    assert response.get_json()['error']['code'] == 'NOT_FOUND'
    assert db_session.scalar(select(func.count()).select_from(NCMR)) == 0


def test_ncmr_update_checks_route_permission_before_payload_validation(
    client,
    db_session,
):
    """完全無編輯權限時，非法 payload 不可先洩漏 schema 驗證結果。"""
    ncmr = NCMR(
        ncmr_number='NCMR-PERMISSION-BEFORE-SCHEMA',
        source='測試',
        description='原始內容',
        status='待處理',
    )
    db_session.add(ncmr)
    db_session.commit()
    viewer = _create_ncmr_edit_user(
        db_session,
        'ncmr_viewer_invalid_payload',
        None,
        {'ncmr.view': True},
    )

    response = client.post(
        '/api/ncmr/update',
        headers=_headers(viewer),
        json={'識別碼': True, '日期': 'not-a-date'},
    )

    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(NCMR, ncmr.id).description == '原始內容'


_MUTATION_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
_MUTATION_AUTH_EXEMPT_ENDPOINTS = {'auth.login'}


def _probe_value(converter):
    """依 Werkzeug converter 產生可通過 URL build 的固定測試值。"""
    if isinstance(converter, IntegerConverter):
        return 1
    if isinstance(converter, FloatConverter):
        return 1.0
    if isinstance(converter, UUIDConverter):
        return UUID('00000000-0000-0000-0000-000000000001')
    if isinstance(converter, PathConverter):
        return 'probe/path'
    if isinstance(converter, AnyConverter):
        return next(iter(converter.items))
    return 'probe'


def _concrete_rule_path(rule):
    values = {
        argument: _probe_value(converter)
        for argument, converter in rule._converters.items()
    }
    return rule.build(values, append_unknown=False)[1]


def _probe_mutation_routes(app, client, headers):
    """實際呼叫所有已註冊 mutation rule；不讀 decorator 名稱或 metadata。"""
    failures = []
    probes = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if rule.endpoint in _MUTATION_AUTH_EXEMPT_ENDPOINTS:
            continue
        for method in sorted(set(rule.methods) & _MUTATION_METHODS):
            path = _concrete_rule_path(rule)
            response = client.open(path, method=method, headers=headers, json={})
            probes.append((method, path, rule.endpoint))
            if response.status_code != 403:
                failures.append(
                    (method, path, rule.endpoint, response.status_code, response.get_data(as_text=True))
                )
    return probes, failures


def test_every_registered_mutation_route_rejects_zero_permission_user_before_write(
    app,
    client,
    db_session,
):
    """若 mutation guard 缺失、晚於 validation/lookup 或只有 metadata，實際回應不會是 403。"""
    db_session.add(Role(code='runtime_zero_permission', name='執行期零權限', permissions={}))
    db_session.commit()
    user = _make_user(db_session, 'runtime_zero_permission_user', 'runtime_zero_permission')
    before_counts = {
        table.name: db_session.scalar(select(func.count()).select_from(table))
        for table in db.metadata.sorted_tables
    }
    attempted_writes = []

    def reject_write(_connection, _cursor, statement, _parameters, _context, _many):
        operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ''
        if operation in {'INSERT', 'UPDATE', 'DELETE'}:
            attempted_writes.append(statement)
            raise AssertionError('零權限 mutation probe 不得執行資料庫寫入')

    event.listen(db.engine, 'before_cursor_execute', reject_write)
    try:
        probes, failures = _probe_mutation_routes(app, client, _headers(user))
    finally:
        event.remove(db.engine, 'before_cursor_execute', reject_write)

    assert probes
    assert failures == []
    assert attempted_writes == []
    db_session.expire_all()
    after_counts = {
        table.name: db_session.scalar(select(func.count()).select_from(table))
        for table in db.metadata.sorted_tables
    }
    assert after_counts == before_counts


def test_runtime_gate_catches_metadata_only_alias_and_dynamic_rules():
    """只複製權限 metadata 的 add_url_rule/alias/dynamic route 不得騙過 gate。"""
    fake_app = Flask('metadata-only-runtime-gate')

    def metadata_only_handler(item_id=None):
        return {'item_id': item_id}, 204

    metadata_only_handler.__required_permissions__ = ({'fake.edit'}, 'all')
    fake_app.add_url_rule(
        '/fake/<int:item_id>/update',
        endpoint='fake.dynamic_update',
        view_func=metadata_only_handler,
        methods=['PATCH'],
    )
    fake_app.add_url_rule(
        '/fake/alias-one',
        endpoint='fake.alias_update',
        view_func=metadata_only_handler,
        methods=['POST'],
    )
    fake_app.add_url_rule(
        '/fake/alias-two',
        endpoint='fake.alias_update',
        view_func=metadata_only_handler,
        methods=['POST'],
    )

    probes, failures = _probe_mutation_routes(fake_app, fake_app.test_client(), {})

    assert {(method, path) for method, path, _endpoint in probes} == {
        ('PATCH', '/fake/1/update'),
        ('POST', '/fake/alias-one'),
        ('POST', '/fake/alias-two'),
    }
    assert {(method, path, status) for method, path, _endpoint, status, _body in failures} == {
        ('PATCH', '/fake/1/update', 204),
        ('POST', '/fake/alias-one', 204),
        ('POST', '/fake/alias-two', 204),
    }
