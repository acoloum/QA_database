import datetime

import pytest

from backend.models import AuditLog, CorrectiveAction, CustomerComplaint, ReworkRequest, Role, User
from backend.services.audit_service import AuditService
from backend.services.complaint_stats_service import ComplaintStatsService
from backend.utils import generate_token


def test_complaint_list_route_clamps_per_page(client, db_session):
    db_session.add(Role(
        code='viewer',
        name='客訴檢視者',
        permissions={'complaint.view': True},
    ))
    user = User(username='complaint_list_user', password='pw', role='viewer', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.get('/api/complaints?per_page=5000', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.get_json()['per_page'] == 100


@pytest.mark.parametrize('operation', ['delete', 'open_capa', 'open_rework'])
@pytest.mark.parametrize('audit_fails', [True, False])
def test_complaint_http_mutation_has_exact_audit_or_atomic_rollback(
    client, db_session, monkeypatch, operation, audit_fails
):
    """稽核失敗不得留下客訴狀態、關聯或孤兒 CAPA/重工單。"""
    user = User(username=f'complaint_atomic_{operation}', password='pw', role='admin', is_active=True)
    complaint = CustomerComplaint(
        complaint_no=f'CC-ATOMIC-{operation}',
        customer='測試客戶',
        complaint_date=datetime.date(2026, 8, 1),
        description='尺寸不良',
        complaint_type='quality',
        severity='Major',
        status='待處理',
    )
    db_session.add_all([user, complaint])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    headers = {'Authorization': f'Bearer {token}'}

    def fail_audit(**_kwargs):
        raise RuntimeError('audit unavailable')

    if audit_fails:
        monkeypatch.setattr(AuditService, 'record', fail_audit)
    if operation == 'delete':
        response = client.delete(f'/api/complaints/{complaint.id}', headers=headers)
    else:
        response = client.post(
            f'/api/complaints/{complaint.id}/{operation.replace("_", "-")}',
            json={},
            headers=headers,
        )

    if not audit_fails:
        assert response.status_code in {200, 201}
        logs = AuditLog.query.all()
        assert len(logs) == 1
        if operation == 'delete':
            expected = ('delete', '客訴', complaint.id)
        elif operation == 'open_capa':
            expected = ('create', 'CAPA', response.get_json()['id'])
        else:
            expected = ('create', '重工', response.get_json()['rework_id'])
        assert (logs[0].user_id, logs[0].action, logs[0].module, logs[0].record_id) == (
            user.id, *expected,
        )
        return

    assert response.status_code == 500
    assert response.get_json()['error']['code'] == 'INTERNAL_ERROR'
    db_session.expire_all()
    persisted = db_session.get(CustomerComplaint, complaint.id)
    assert persisted.deleted_at is None
    assert persisted.status == '待處理'
    assert persisted.related_capa_id is None
    assert persisted.related_rework_id is None
    assert CorrectiveAction.query.count() == 0
    assert ReworkRequest.query.count() == 0
    assert AuditLog.query.count() == 0


def test_delete_complaint_rework_unlinks_source_and_allows_reopen(
    client, db_session
):
    """刪除客訴來源重工後必須清聯，使客訴可再次開立。"""
    user = User(username='complaint_rework_reopen', password='pw', role='admin', is_active=True)
    complaint = CustomerComplaint(
        complaint_no='CC-REWORK-REOPEN',
        customer='重開客戶',
        complaint_date=datetime.date(2026, 8, 1),
        description='需重工',
        complaint_type='quality',
        status='處理中',
    )
    req = ReworkRequest(
        complaint_id=None,
        rework_number='RW-COMPLAINT-OLD',
        status='申請中',
    )
    db_session.add_all([user, complaint, req])
    db_session.flush()
    req.complaint_id = complaint.id
    complaint.related_rework_id = req.id
    db_session.commit()
    old_id = req.id
    token = generate_token(user.id, user.username, user.role, user.token_version)
    headers = {'Authorization': f'Bearer {token}'}

    deleted = client.post('/api/rework/delete', json={'rework_id': old_id}, headers=headers)

    assert deleted.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(CustomerComplaint, complaint.id)
    assert refreshed.related_rework_id is None
    assert refreshed.status == '待處理'
    assert db_session.get(ReworkRequest, old_id).deleted_at is not None

    reopened = client.post(
        f'/api/complaints/{complaint.id}/open-rework', json={}, headers=headers
    )
    assert reopened.status_code == 201
    assert reopened.get_json()['rework_id'] != old_id


@pytest.mark.parametrize('linked_type', ['capa', 'rework'])
def test_delete_complaint_rejects_active_link_without_writes(
    client, db_session, linked_type
):
    """尚有 active CAPA/重工的客訴不得軟刪除而留下孤兒。"""
    user = User(username=f'complaint_linked_{linked_type}', password='pw', role='admin', is_active=True)
    complaint = CustomerComplaint(
        complaint_no=f'CC-LINKED-{linked_type}',
        customer='關聯客戶',
        complaint_date=datetime.date(2026, 8, 1),
        description='ACTIVE-LINK-SECRET',
        complaint_type='quality',
        status='處理中',
    )
    db_session.add_all([user, complaint])
    db_session.flush()
    if linked_type == 'capa':
        linked = CorrectiveAction(
            eight_d_number='CAPA-COMPLAINT-LINKED',
            source_type='complaint',
            source_id=complaint.id,
            status='進行中',
        )
        db_session.add(linked)
        db_session.flush()
        complaint.related_capa_id = linked.id
    else:
        linked = ReworkRequest(
            complaint_id=complaint.id,
            rework_number='RW-COMPLAINT-LINKED',
            status='申請中',
        )
        db_session.add(linked)
        db_session.flush()
        complaint.related_rework_id = linked.id
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.delete(
        f'/api/complaints/{complaint.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == 'COMPLAINT_HAS_ACTIVE_LINK'
    db_session.expire_all()
    assert db_session.get(CustomerComplaint, complaint.id).deleted_at is None
    assert AuditLog.query.count() == 0


def test_complaint_stats_exclude_soft_deleted(db_session):
    """軟刪除的客訴不得出現在任何統計維度中。"""
    kept = CustomerComplaint(
        complaint_no='CC-STATS-KEEP',
        customer='保留客戶',
        complaint_date=datetime.date(2026, 6, 1),
        material='6061-F',
        spec='50*2*500',
        defect_category='尺寸不良',
        description='內徑偏小',
        complaint_type='quality',
    )
    removed = CustomerComplaint(
        complaint_no='CC-STATS-DEL',
        customer='1',
        complaint_date=datetime.date(2026, 6, 2),
        material='1',
        spec='1',
        defect_category='1',
        description='1',
        complaint_type='quality',
        deleted_at=datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc),
    )
    db_session.add_all([kept, removed])
    db_session.commit()

    assert [r['customer'] for r in ComplaintStatsService.by_customer()] == ['保留客戶']
    assert [r['material'] for r in ComplaintStatsService.by_product()] == ['6061-F']
    assert [r['defect_category'] for r in ComplaintStatsService.by_category()] == ['尺寸不良']
    assert [r['year_month'] for r in ComplaintStatsService.by_month()] == ['2026-06']
    assert [r['total'] for r in ComplaintStatsService.by_month()] == [1]
