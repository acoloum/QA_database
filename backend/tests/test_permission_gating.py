"""權限閘門（require_perm）回歸測試。

驗證 pyrometry 等模組的寫入/刪除路由確實受權限保護：
- 無權限角色 → 403
- 有對應權限角色 → 非 403（順利進入處理函式）
- edit 與 delete 為獨立權限
- admin 一律放行
- GET 讀取路由維持對所有已登入者開放
"""
import ast
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.models import (
    CorrectiveAction,
    CustomerComplaint,
    Inspector,
    NCMR,
    ReworkRequest,
    Role,
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

    assert response.status_code == 400
    assert db_session.scalar(select(func.count()).select_from(NCMR)) == before


def _route_methods(route_decorator):
    """從實際 route decorator AST 取得 HTTP methods，支援 route/post/put/patch/delete。"""
    call = route_decorator
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
        return set()
    method_name = call.func.attr.lower()
    if method_name in {'post', 'put', 'patch', 'delete'}:
        return {method_name.upper()}
    if method_name != 'route':
        return set()
    for keyword in call.keywords:
        if keyword.arg == 'methods':
            return {str(value).upper() for value in ast.literal_eval(keyword.value)}
    return {'GET'}


def test_every_mutation_route_has_runtime_authorization_semantics(app):
    """
    AST 只用來找出真實 mutation route；通過條件必須來自已註冊
    Flask view 的權限語意 metadata，不接受名稱像 decorator 的假陽性。
    """
    route_dir = Path(__file__).resolve().parents[1] / 'routes'
    missing = []
    login_paths = {'/api/login', '/api/auth/login'}

    for route_file in sorted(route_dir.glob('*.py')):
        tree = ast.parse(route_file.read_text(encoding='utf-8'), filename=str(route_file))
        blueprint_names = {}
        for statement in tree.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            value = statement.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == 'Blueprint'
                and value.args
            ):
                blueprint_names[target.id] = ast.literal_eval(value.args[0])
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                methods = _route_methods(decorator)
                mutation_methods = methods & {'POST', 'PUT', 'PATCH', 'DELETE'}
                if not mutation_methods:
                    continue
                path = ast.literal_eval(decorator.args[0]) if decorator.args else ''
                if path in login_paths:
                    continue
                blueprint_variable = (
                    decorator.func.value.id
                    if isinstance(decorator.func.value, ast.Name)
                    else None
                )
                blueprint_name = blueprint_names.get(blueprint_variable)
                endpoint = f'{blueprint_name}.{node.name}' if blueprint_name else None
                endpoints = [app.view_functions[endpoint]] if endpoint in app.view_functions else []
                if not endpoints or not any(
                    getattr(view, '__required_permissions__', None)
                    or getattr(view, '__admin_required__', False)
                    for view in endpoints
                ):
                    missing.append(
                        f'{route_file.name}:{node.lineno} {sorted(mutation_methods)} {path}'
                    )

    assert missing == []
