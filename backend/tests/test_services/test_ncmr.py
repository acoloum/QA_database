import pytest
import datetime
from sqlalchemy import func, select

from backend.models import AuditLog, NCMR, Inspector, Role, User
from backend.errors import NotFoundError
from backend.services.audit_service import AuditService
from backend.services.ncmr_service import NCMRService
from backend.utils import generate_token, hash_password


def _make_ncmr(db_session, **kwargs):
    defaults = dict(
        ncmr_number='NCMR-TEST-001',
        date=datetime.date(2025, 1, 15),
        source='進料',
        vendor='TestVendor',
        material='6066-T6',
        product_info='38*3040',
        defect_quantity=5,
        status='待處理',
    )
    defaults.update(kwargs)
    n = NCMR(**defaults)
    db_session.add(n)
    db_session.commit()
    return n


def _ncmr_headers(db_session, permission, username='ncmr_contract_user'):
    role_code = f'{username}_role'
    db_session.add(Role(
        code=role_code,
        name='NCMR 契約測試角色',
        permissions={permission: True},
    ))
    user = User(
        username=username,
        password=hash_password('pw12345678'),
        role=role_code,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _all_ncmr_headers(db_session, username):
    role_code = f'{username}_role'
    db_session.add(Role(
        code=role_code,
        name='NCMR 交易測試角色',
        permissions={
            'ncmr.create': True,
            'ncmr.edit': True,
            'ncmr.delete': True,
        },
    ))
    user = User(
        username=username,
        password=hash_password('pw12345678'),
        role=role_code,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return user, {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _assert_internal_error(response):
    assert response.status_code == 500
    assert response.get_json() == {
        'success': False,
        'error': {'code': 'INTERNAL_ERROR', 'message': '伺服器內部錯誤'},
    }


def test_create_ncmr_rolls_back_when_audit_fails(client, db_session, monkeypatch):
    _, headers = _all_ncmr_headers(db_session, 'ncmr_create_atomic')
    monkeypatch.setattr(
        AuditService,
        'record',
        staticmethod(lambda **_: (_ for _ in ()).throw(RuntimeError('secret audit down'))),
    )

    response = client.post(
        '/api/ncmr/add',
        headers=headers,
        json={'日期': '2026-08-01', '來源': '進料', '不良描述': '原子建立'},
    )

    _assert_internal_error(response)
    db_session.expire_all()
    assert NCMR.query.filter_by(description='原子建立').count() == 0
    assert AuditLog.query.count() == 0


def test_update_ncmr_rolls_back_when_audit_fails(client, db_session, monkeypatch):
    record = _make_ncmr(db_session, description='更新前')
    _, headers = _all_ncmr_headers(db_session, 'ncmr_update_atomic')
    monkeypatch.setattr(
        AuditService,
        'record',
        staticmethod(lambda **_: (_ for _ in ()).throw(RuntimeError('secret audit down'))),
    )

    response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': record.id, '不良描述': '不應保存'},
    )

    _assert_internal_error(response)
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).description == '更新前'
    assert AuditLog.query.count() == 0


def test_delete_ncmr_rolls_back_when_audit_fails(client, db_session, monkeypatch):
    record = _make_ncmr(db_session)
    _, headers = _all_ncmr_headers(db_session, 'ncmr_delete_atomic')
    monkeypatch.setattr(
        AuditService,
        'record',
        staticmethod(lambda **_: (_ for _ in ()).throw(RuntimeError('secret audit down'))),
    )

    response = client.post('/api/ncmr/delete', headers=headers, json={'id': record.id})

    _assert_internal_error(response)
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).deleted_at is None
    assert AuditLog.query.count() == 0


def _assert_validation_error(response, status, field=None):
    assert response.status_code == status
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['error']['code'] == (
        'INVALID_JSON_BODY' if status == 400 else 'VALIDATION_ERROR'
    )
    if field is not None:
        assert field in payload['error']['details']


@pytest.mark.parametrize(
    ('body', 'status', 'field'),
    [
        (None, 400, None),
        ([], 400, None),
        ({'日期': '2026-02-30', '來源': '進料'}, 422, '日期'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': -1}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '未知欄位': 'x'}, 422, '未知欄位'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': True}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': 1.0}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': 1.9}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': -0.5}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': float('nan')}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': float('inf')}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': '1.0'}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': '01'}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '產品數量': ' 1'}, 422, '產品數量'),
        ({'日期': '2026-08-01', '來源': '進料', '狀態': None}, 422, '狀態'),
        ({'日期': '2026-08-01', '來源': '進料', '狀態': ''}, 422, '狀態'),
    ],
)
def test_ncmr_create_rejects_invalid_contract(
    client,
    db_session,
    body,
    status,
    field,
):
    headers = _ncmr_headers(db_session, 'ncmr.create')
    before = db_session.scalar(select(func.count()).select_from(NCMR))

    response = client.post('/api/ncmr/add', json=body, headers=headers)

    _assert_validation_error(response, status, field)
    assert db_session.scalar(select(func.count()).select_from(NCMR)) == before


@pytest.mark.parametrize('product_quantity', [0, '0'])
@pytest.mark.parametrize('inspector_name', [None, ''])
def test_ncmr_create_loads_dates_and_accepts_existing_optional_payload(
    client,
    db_session,
    product_quantity,
    inspector_name,
):
    headers = _ncmr_headers(db_session, 'ncmr.create')

    response = client.post(
        '/api/ncmr/add',
        headers=headers,
        json={
            '日期': '2026-08-01',
            '建立日期': '2026-08-02',
            '來源': '進料',
            '廠商': None,
            '產品數量': product_quantity,
            '不良描述': None,
            '不合格數量': '',
            '發現人員姓名': inspector_name,
        },
    )

    assert response.status_code == 201
    stored = db_session.scalar(select(NCMR))
    assert stored.date == datetime.date(2026, 8, 1)
    assert type(stored.date) is datetime.date
    assert stored.create_date == datetime.date(2026, 8, 2)
    assert type(stored.create_date) is datetime.date
    assert stored.quantity == 0
    assert stored.defect_quantity is None
    assert stored.inspector_id is None
    logs = AuditLog.query.filter_by(module='NCMR', action='create').all()
    assert len(logs) == 1
    assert logs[0].record_id == stored.id


def test_ncmr_create_rejects_unknown_inspector_without_writing(
    client,
    db_session,
):
    headers = _ncmr_headers(db_session, 'ncmr.create')

    response = client.post(
        '/api/ncmr/add',
        headers=headers,
        json={
            '日期': '2026-08-01',
            '來源': '進料',
            '發現人員姓名': '不存在的人員',
        },
    )

    _assert_validation_error(response, 422, '發現人員姓名')
    assert db_session.scalar(select(func.count()).select_from(NCMR)) == 0


@pytest.mark.parametrize(
    ('body', 'field'),
    [
        (None, None),
        ([], None),
        ({'識別碼': True, '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': 1.0, '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': 1.9, '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': float('nan'), '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': float('inf'), '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': '1', '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': '01', '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': 1, '日期': 'not-a-date'}, '日期'),
        ({'識別碼': 1, '不合格數量': -1}, '不合格數量'),
        ({'識別碼': 1, '未知欄位': 'x'}, '未知欄位'),
        ({'識別碼': 1, '狀態': None}, '狀態'),
        ({'識別碼': 1, '狀態': ''}, '狀態'),
    ],
)
def test_ncmr_update_rejects_invalid_contract_without_writing(
    client,
    db_session,
    body,
    field,
):
    record = _make_ncmr(db_session, description='原始內容')
    if (
        isinstance(body, dict)
        and type(body.get('識別碼')) is int
        and body.get('識別碼') == 1
    ):
        body = {**body, '識別碼': record.id}
    headers = _ncmr_headers(
        db_session,
        'ncmr.edit',
        username='ncmr_update_contract_user',
    )

    response = client.post('/api/ncmr/update', json=body, headers=headers)

    expected_status = 400 if not isinstance(body, dict) else 422
    _assert_validation_error(response, expected_status, field)
    assert db_session().in_transaction() is False
    db_session.expire_all()
    stored = db_session.get(NCMR, record.id)
    assert stored.description == '原始內容'
    assert stored.date == datetime.date(2025, 1, 15)
    assert stored.defect_quantity == 5


def test_ncmr_update_loads_date_object_and_keeps_partial_update_legal(
    client,
    db_session,
):
    record = _make_ncmr(db_session, description='原始內容')
    headers = _ncmr_headers(
        db_session,
        'ncmr.edit',
        username='ncmr_update_success_user',
    )

    response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={
            '識別碼': record.id,
            '日期': '2026-08-03',
            '不良描述': '更新內容',
            '產品數量': 0,
            '狀態': '矯正中',
        },
    )

    assert response.status_code == 200
    db_session.expire_all()
    stored = db_session.get(NCMR, record.id)
    assert stored.date == datetime.date(2026, 8, 3)
    assert type(stored.date) is datetime.date
    assert stored.description == '更新內容'
    assert stored.quantity == 0
    assert stored.status == '矯正中'
    logs = AuditLog.query.filter_by(module='NCMR', action='update').all()
    assert len(logs) == 1
    assert logs[0].record_id == record.id


def test_delete_ncmr_writes_exactly_one_audit_in_successful_transaction(
    client, db_session
):
    record = _make_ncmr(db_session)
    user, headers = _all_ncmr_headers(db_session, 'ncmr_delete_success')

    response = client.post('/api/ncmr/delete', headers=headers, json={'id': record.id})

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).deleted_at is not None
    logs = AuditLog.query.filter_by(module='NCMR', action='delete').all()
    assert len(logs) == 1
    assert logs[0].record_id == record.id
    assert logs[0].user_id == user.id


def test_update_ncmr_rolls_back_when_audit_flush_fails(
    client, db_session, monkeypatch
):
    record = _make_ncmr(db_session, description='flush 前')
    _, headers = _all_ncmr_headers(db_session, 'ncmr_flush_atomic')
    monkeypatch.setattr(db_session, 'flush', lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('flush down')))

    response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': record.id, '不良描述': 'flush 後'},
    )

    _assert_internal_error(response)
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).description == 'flush 前'
    assert AuditLog.query.count() == 0


def test_delete_ncmr_rolls_back_when_commit_fails(
    client, db_session, monkeypatch
):
    record = _make_ncmr(db_session)
    _, headers = _all_ncmr_headers(db_session, 'ncmr_commit_atomic')
    original_commit = db_session.commit
    monkeypatch.setattr(
        db_session,
        'commit',
        lambda: (_ for _ in ()).throw(RuntimeError('commit down')),
    )

    response = client.post('/api/ncmr/delete', headers=headers, json={'id': record.id})

    _assert_internal_error(response)
    monkeypatch.setattr(db_session, 'commit', original_commit)
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).deleted_at is None
    assert AuditLog.query.count() == 0


@pytest.mark.parametrize('inspector_name', [None, ''])
def test_ncmr_update_explicit_empty_inspector_clears_assignment(
    client,
    db_session,
    inspector_name,
):
    original_inspector = Inspector(name='原發現人員')
    db_session.add(original_inspector)
    db_session.flush()
    record = _make_ncmr(db_session, inspector_id=original_inspector.id)
    headers = _ncmr_headers(
        db_session,
        'ncmr.edit',
        username=f'ncmr_clear_inspector_{"none" if inspector_name is None else "empty"}',
    )

    response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': record.id, '發現人員姓名': inspector_name},
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).inspector_id is None


def test_ncmr_update_sets_existing_inspector(client, db_session):
    original_inspector = Inspector(name='原發現人員')
    replacement_inspector = Inspector(name='新發現人員')
    db_session.add_all([original_inspector, replacement_inspector])
    db_session.flush()
    record = _make_ncmr(db_session, inspector_id=original_inspector.id)
    headers = _ncmr_headers(
        db_session,
        'ncmr.edit',
        username='ncmr_replace_inspector',
    )

    response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': record.id, '發現人員姓名': replacement_inspector.name},
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).inspector_id == replacement_inspector.id


def test_ncmr_update_rejects_unknown_inspector_without_writing(
    client,
    db_session,
):
    original_inspector = Inspector(name='原發現人員')
    db_session.add(original_inspector)
    db_session.flush()
    record = _make_ncmr(db_session, inspector_id=original_inspector.id)
    headers = _ncmr_headers(
        db_session,
        'ncmr.edit',
        username='ncmr_unknown_inspector',
    )

    response = client.post(
        '/api/ncmr/update',
        headers=headers,
        json={'識別碼': record.id, '發現人員姓名': '不存在的人員'},
    )

    _assert_validation_error(response, 422, '發現人員姓名')
    db_session.expire_all()
    assert db_session.get(NCMR, record.id).inspector_id == original_inspector.id


def test_ncmr_not_found_leaves_no_pending_transaction(app, db_session):
    with app.app_context(), pytest.raises(NotFoundError, match='找不到'):
        NCMRService.update_ncmr({'識別碼': 999999}, actor_id=None)
    assert db_session().in_transaction() is False


def test_invalid_update_id_rolls_back_an_existing_transaction(app, db_session):
    """識別碼驗證即使在既有 read transaction 後失敗，也必須清乾淨 session。"""
    with app.app_context():
        _make_ncmr(db_session)
        assert NCMR.query.first() is not None
        assert db_session().in_transaction() is True

        with pytest.raises(ValueError, match='缺少識別碼'):
            NCMRService.update_ncmr({}, actor_id=None)

        assert db_session().in_transaction() is False


def test_idempotent_delete_ncmr_leaves_no_pending_transaction(app, db_session):
    with app.app_context():
        assert NCMRService.delete_ncmr(999999, actor_id=None) is True
        assert db_session().in_transaction() is False


def test_get_ncmr_list_pagination(app, db_session):
    with app.app_context():
        for i in range(25):
            _make_ncmr(db_session, ncmr_number=f'NCMR-{i:03}')
        result = NCMRService.get_ncmr_list(page=1, per_page=20)
        assert result['total'] == 25
        assert len(result['data']) == 20
        result2 = NCMRService.get_ncmr_list(page=2, per_page=20)
        assert len(result2['data']) == 5


def test_get_ncmr_list_filter_vendor(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-A', vendor='AluCorp')
        _make_ncmr(db_session, ncmr_number='NCMR-B', vendor='SteelInc')
        result = NCMRService.get_ncmr_list(vendor='alu')
        assert result['total'] == 1
        assert result['data'][0]['廠商'] == 'AluCorp'


def test_get_ncmr_list_filter_source(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-C', source='進料')
        _make_ncmr(db_session, ncmr_number='NCMR-D', source='巡檢')
        result = NCMRService.get_ncmr_list(source='進料')
        assert result['total'] == 1
        assert result['data'][0]['來源'] == '進料'


def test_get_ncmr_list_filter_date_range(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-E', date=datetime.date(2025, 1, 10))
        _make_ncmr(db_session, ncmr_number='NCMR-F', date=datetime.date(2025, 3, 20))
        result = NCMRService.get_ncmr_list(date_from='2025-01-01', date_to='2025-02-28')
        assert result['total'] == 1
        assert result['data'][0]['日期'] == '2025-01-10'


from backend.models import CorrectiveAction


def _make_capa(db_session, ncmr, **kwargs):
    defaults = dict(
        ncmr_id=ncmr.id,
        eight_d_number='8D-TEST-001',
        status='進行中',
    )
    defaults.update(kwargs)
    ca = CorrectiveAction(**defaults)
    db_session.add(ca)
    db_session.commit()
    return ca






