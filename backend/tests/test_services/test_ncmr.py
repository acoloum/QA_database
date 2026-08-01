import pytest
import datetime
from sqlalchemy import func, select

from backend.models import NCMR, Inspector, Role, User
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


def test_ncmr_create_loads_dates_and_accepts_existing_optional_payload(
    client,
    db_session,
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
            '產品數量': 0,
            '不良描述': None,
            '不合格數量': '',
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


@pytest.mark.parametrize(
    ('body', 'field'),
    [
        (None, None),
        ([], None),
        ({'識別碼': True, '不良描述': '不應更新'}, '識別碼'),
        ({'識別碼': 1, '日期': 'not-a-date'}, '日期'),
        ({'識別碼': 1, '不合格數量': -1}, '不合格數量'),
        ({'識別碼': 1, '未知欄位': 'x'}, '未知欄位'),
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
        },
    )

    assert response.status_code == 200
    db_session.expire_all()
    stored = db_session.get(NCMR, record.id)
    assert stored.date == datetime.date(2026, 8, 3)
    assert type(stored.date) is datetime.date
    assert stored.description == '更新內容'
    assert stored.quantity == 0


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


def test_get_capa_list_pagination(app, db_session):
    with app.app_context():
        for i in range(5):
            n = _make_ncmr(db_session, ncmr_number=f'NCMR-CAPA-{i}')
            _make_capa(db_session, n, eight_d_number=f'8D-{i:03}')
        result = NCMRService.get_capa_list(page=1, per_page=3)
        assert result['total'] == 5
        assert len(result['data']) == 3


def test_get_capa_list_filter_material(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-M1', material='6066-T6')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-M2', material='A380')
        _make_capa(db_session, n1, eight_d_number='8D-M1')
        _make_capa(db_session, n2, eight_d_number='8D-M2')
        result = NCMRService.get_capa_list(material='6066')
        assert result['total'] == 1
        assert result['data'][0]['材質'] == '6066-T6'


def test_get_capa_list_filter_date_range(app, db_session):
    with app.app_context():
        import datetime as dt
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-CD1')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-CD2')
        ca1 = _make_capa(db_session, n1, eight_d_number='8D-CD1')
        ca2 = _make_capa(db_session, n2, eight_d_number='8D-CD2')
        from backend.extensions import db
        ca1.created_at = dt.datetime(2025, 1, 10)
        ca2.created_at = dt.datetime(2025, 4, 20)
        db.session.commit()
        result = NCMRService.get_capa_list(date_from='2025-01-01', date_to='2025-01-31')
        assert result['total'] == 1
        assert result['data'][0]['8D單號'] == '8D-CD1'


def test_get_capa_list_excludes_car_only_records(app, db_session):
    """car_number 存在但 eight_d_number 為 NULL 的記錄不應出現在 CAPA 清單"""
    with app.app_context():
        n = _make_ncmr(db_session, ncmr_number='NCMR-PURE-CAR')
        ca = CorrectiveAction(ncmr_id=n.id, car_number='CAR-ONLY', status='進行中')
        db_session.add(ca)
        db_session.commit()
        result = NCMRService.get_capa_list()
        assert result['total'] == 0


def test_legacy_capa_update_cannot_close_directly(app, db_session):
    """舊 /api/capa/update 不可繞過新版 CAPA D8 gate 直接結案"""
    with app.app_context():
        n = _make_ncmr(db_session, ncmr_number='NCMR-LEGACY-CLOSE')
        ca = _make_capa(db_session, n, eight_d_number='8D-LEGACY-CLOSE')

        with pytest.raises(ValueError, match='新版 CAPA 結案流程'):
            NCMRService.update_capa({'識別碼': ca.id, '狀態': '已結案'})

        assert ca.status == '進行中'
