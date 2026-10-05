"""客訴關聯既有 CAPA：多張客訴共用一份 8D。"""
import datetime

import pytest

from backend.models import AuditLog, CorrectiveAction, CustomerComplaint, Role, User
from backend.utils import generate_token


def _headers(user):
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}'}


def _complaint(no, **overrides):
    values = dict(
        complaint_no=no,
        customer='測試客戶',
        complaint_date=datetime.date(2026, 10, 1),
        description='表面刮傷',
        complaint_type='quality',
        severity='Major',
        status='待處理',
    )
    values.update(overrides)
    return CustomerComplaint(**values)


@pytest.fixture
def admin(db_session):
    user = User(username='link_capa_admin', password='pw', role='admin', is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def shared_capa(db_session):
    """由第一張客訴開立、可結案的 CAPA，第二張客訴尚未關聯。"""
    first = _complaint('CC-LINK-001', material='6063', spec='Φ20')
    second = _complaint('CC-LINK-002', material='6061', spec='Φ30')
    db_session.add_all([first, second])
    db_session.flush()
    capa = CorrectiveAction(
        eight_d_number='CAPA-LINK-001',
        status='進行中',
        source_type='complaint',
        source_id=first.id,
        rigor='簡化5D',
        d2_what='問題',
        d3_action='暫時對策',
        d4_root_cause='真因',
        d6_verified=True,
    )
    db_session.add(capa)
    db_session.flush()
    first.related_capa_id = capa.id
    first.status = '處理中'
    db_session.commit()
    return first, second, capa


def test_link_existing_capa_sets_relation_status_and_audit(client, db_session, admin, shared_capa):
    _first, second, capa = shared_capa

    response = client.post(
        f'/api/complaints/{second.id}/link-capa',
        json={'capa_id': capa.id},
        headers=_headers(admin),
    )

    assert response.status_code == 200
    assert response.get_json()['related_capa_id'] == capa.id
    db_session.expire_all()
    persisted = db_session.get(CustomerComplaint, second.id)
    assert persisted.related_capa_id == capa.id
    assert persisted.status == '處理中'
    logs = AuditLog.query.all()
    assert [(log.action, log.module, log.record_id) for log in logs] == [
        ('link_capa', '客訴', second.id),
    ]


def test_link_rejects_complaint_that_already_has_capa(client, admin, shared_capa):
    first, _second, capa = shared_capa

    response = client.post(
        f'/api/complaints/{first.id}/link-capa',
        json={'capa_id': capa.id},
        headers=_headers(admin),
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == 'COMPLAINT_CAPA_EXISTS'


def test_link_rejects_closed_capa(client, db_session, admin, shared_capa):
    _first, second, capa = shared_capa
    capa.status = '已結案'
    db_session.commit()

    response = client.post(
        f'/api/complaints/{second.id}/link-capa',
        json={'capa_id': capa.id},
        headers=_headers(admin),
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == 'INVALID_STATE'
    db_session.expire_all()
    assert db_session.get(CustomerComplaint, second.id).related_capa_id is None


@pytest.mark.parametrize(('payload', 'status_code'), [({}, 400), ({'capa_id': 'abc'}, 400), ({'capa_id': 999999}, 404)])
def test_link_rejects_missing_or_unknown_capa(client, admin, shared_capa, payload, status_code):
    _first, second, _capa = shared_capa

    response = client.post(
        f'/api/complaints/{second.id}/link-capa',
        json=payload,
        headers=_headers(admin),
    )

    assert response.status_code == status_code


def test_capa_detail_lists_all_linked_complaints(client, admin, shared_capa):
    first, second, capa = shared_capa
    client.post(f'/api/complaints/{second.id}/link-capa', json={'capa_id': capa.id}, headers=_headers(admin))

    response = client.get(f'/api/capas/{capa.id}', headers=_headers(admin))

    linked = response.get_json()['linked_complaints']
    assert [(c['id'], c['complaint_no'], c['spec']) for c in linked] == [
        (first.id, 'CC-LINK-001', 'Φ20'),
        (second.id, 'CC-LINK-002', 'Φ30'),
    ]


def test_closing_capa_closes_every_linked_complaint(client, db_session, admin, shared_capa):
    first, second, capa = shared_capa
    client.post(f'/api/complaints/{second.id}/link-capa', json={'capa_id': capa.id}, headers=_headers(admin))

    response = client.post(
        f'/api/capas/{capa.id}/close',
        json={'D8_confirmation': '確認結案'},
        headers=_headers(admin),
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(CustomerComplaint, first.id).status == '已結案'
    assert db_session.get(CustomerComplaint, second.id).status == '已結案'


def test_deleting_capa_unlinks_every_linked_complaint(client, db_session, admin, shared_capa):
    first, second, capa = shared_capa
    client.post(f'/api/complaints/{second.id}/link-capa', json={'capa_id': capa.id}, headers=_headers(admin))

    response = client.delete(f'/api/capas/{capa.id}', headers=_headers(admin))

    assert response.status_code == 200
    db_session.expire_all()
    for complaint_id in (first.id, second.id):
        persisted = db_session.get(CustomerComplaint, complaint_id)
        assert persisted.related_capa_id is None
        assert persisted.status == '待處理'


@pytest.mark.parametrize('permissions', [{'complaint.edit': True}, {'capa.edit': True}])
def test_link_requires_both_complaint_and_capa_edit(client, db_session, shared_capa, permissions):
    _first, second, capa = shared_capa
    role_code = 'link_' + '_'.join(key.replace('.', '_') for key in permissions)
    db_session.add(Role(code=role_code, name='單側權限', permissions=permissions))
    user = User(username=f'{role_code}_user', password='pw', role=role_code, is_active=True)
    db_session.add(user)
    db_session.commit()

    response = client.post(
        f'/api/complaints/{second.id}/link-capa',
        json={'capa_id': capa.id},
        headers=_headers(user),
    )

    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(CustomerComplaint, second.id).related_capa_id is None
