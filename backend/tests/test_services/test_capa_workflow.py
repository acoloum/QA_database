import datetime

import pytest

from backend.models import AuditLog, CorrectiveAction, CustomerComplaint, NCMR, User
from backend.services.audit_service import AuditService
from backend.services.capa_service import CAPAService
from backend.services.complaint_service import ComplaintService
from backend.utils import generate_token


def test_prepare_capa_source_rejects_duplicate_complaint_capa(app, db_session):
    """已有 CAPA 關聯的客訴不可再次開立 CAPA"""
    with app.app_context():
        complaint = CustomerComplaint(
            complaint_no='CC-TEST-001',
            customer='測試客戶',
            complaint_date=datetime.date(2026, 5, 1),
            material='AL6063',
            spec='40x3',
            description='尺寸不良',
            complaint_type='quality',
            related_capa_id=99,
        )
        db_session.add(complaint)
        db_session.commit()

        with pytest.raises(ValueError, match='已開立 CAPA'):
            ComplaintService.prepare_capa_source(complaint.id)


def test_delete_ncmr_capa_clears_ncmr_link_and_status(app, db_session):
    """刪除 NCMR 來源 CAPA 時需清除 NCMR 關聯，讓 NCMR 可重新開立 CAPA"""
    with app.app_context():
        ncmr = NCMR(
            ncmr_number='NCMR-TEST-DELETE',
            date=datetime.date(2026, 5, 1),
            source='進料',
            description='外徑超差',
            status='矯正中',
        )
        db_session.add(ncmr)
        db_session.flush()

        capa = CorrectiveAction(
            eight_d_number='CAPA-TEST-DELETE',
            source_type='ncmr',
            source_id=ncmr.id,
            ncmr_id=ncmr.id,
            status='進行中',
        )
        db_session.add(capa)
        db_session.flush()
        ncmr.related_capa_id = capa.id
        ncmr.related_capa_source = 'capa'
        db_session.commit()

        CAPAService.delete(capa.id, actor_id=None)

        refreshed = db_session.get(NCMR, ncmr.id)
        assert refreshed.related_capa_id is None
        assert refreshed.related_capa_source is None
        assert refreshed.status == '待處理'


@pytest.mark.parametrize('operation', ['close', 'delete'])
@pytest.mark.parametrize('audit_fails', [True, False])
def test_capa_http_mutation_has_exact_audit_or_atomic_rollback(
    client, db_session, monkeypatch, operation, audit_fails
):
    """稽核寫入失敗時，CAPA 結案與刪除的業務資料必須一併回滾。"""
    user = User(username=f'capa_atomic_{operation}', password='pw', role='admin', is_active=True)
    capa = CorrectiveAction(
        eight_d_number=f'CAPA-ATOMIC-{operation}',
        status='進行中',
        rigor='簡化5D',
        d2_what='問題',
        d3_action='暫時對策',
        d4_root_cause='真因',
        d6_verified=True,
    )
    db_session.add_all([user, capa])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    headers = {'Authorization': f'Bearer {token}'}

    def fail_audit(**_kwargs):
        raise RuntimeError('audit unavailable')

    if audit_fails:
        monkeypatch.setattr(AuditService, 'record', fail_audit)
    if operation == 'close':
        response = client.post(
            f'/api/capas/{capa.id}/close',
            json={'D8_confirmation': '確認結案'},
            headers=headers,
        )
    else:
        response = client.delete(f'/api/capas/{capa.id}', headers=headers)

    if not audit_fails:
        assert response.status_code == 200
        logs = AuditLog.query.all()
        assert len(logs) == 1
        assert (logs[0].user_id, logs[0].action, logs[0].module, logs[0].record_id) == (
            user.id, operation, 'CAPA', capa.id,
        )
        return

    assert response.status_code == 500
    assert response.get_json()['error']['code'] == 'INTERNAL_ERROR'
    db_session.expire_all()
    persisted = db_session.get(CorrectiveAction, capa.id)
    assert persisted.status == '進行中'
    assert persisted.deleted_at is None
    assert persisted.d8_confirmation is None
    assert AuditLog.query.count() == 0
