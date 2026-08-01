import datetime

import pytest

from backend.models import AuditLog, CorrectiveAction, CustomerComplaint, ReworkRequest, Role, User
from backend.services.audit_service import AuditService
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
