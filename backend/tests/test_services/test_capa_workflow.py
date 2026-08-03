import datetime
import json

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


def test_capa_close_serialization_failure_rolls_back_before_commit(
    client, db_session, monkeypatch
):
    """回應序列化失敗必須發生在 commit 前，不可回傳500卻已結案。"""
    user = User(username='capa_result_failure', password='pw', role='admin', is_active=True)
    capa = CorrectiveAction(
        eight_d_number='CAPA-RESULT-FAIL',
        status='進行中',
        rigor='簡化5D',
        d2_what='問題',
        d3_action='對策',
        d4_root_cause='真因',
        d6_verified=True,
    )
    db_session.add_all([user, capa])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    def fail_result(_capa):
        raise RuntimeError('serialization failed')

    monkeypatch.setattr(CAPAService, '_to_dict', fail_result)
    response = client.post(
        f'/api/capas/{capa.id}/close',
        json={'D8_confirmation': '確認結案'},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 500
    assert response.get_json()['error']['code'] == 'INTERNAL_ERROR'
    db_session.expire_all()
    persisted = db_session.get(CorrectiveAction, capa.id)
    assert persisted.status == '進行中'
    assert persisted.d8_confirmation is None
    assert AuditLog.query.count() == 0


def test_capa_close_audit_contains_ncmr_source_transition_without_secret(
    client, db_session
):
    """CAPA 結案稽核需同時證明 NCMR 在同一交易的狀態轉移。"""
    user = User(username='capa_ncmr_snapshot', password='pw', role='admin', is_active=True)
    ncmr = NCMR(
        ncmr_number='NCMR-CAPA-SNAPSHOT',
        status='矯正中',
        description='password=NCMR-SOURCE-SECRET',
    )
    db_session.add_all([user, ncmr])
    db_session.flush()
    capa = CorrectiveAction(
        eight_d_number='CAPA-NCMR-SNAPSHOT',
        source_type='ncmr',
        source_id=ncmr.id,
        ncmr_id=ncmr.id,
        status='進行中',
        rigor='簡化5D',
        d2_what='問題', d3_action='對策', d4_root_cause='真因', d6_verified=True,
    )
    db_session.add(capa)
    db_session.flush()
    ncmr.related_capa_id = capa.id
    ncmr.related_capa_source = 'capa'
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.post(
        f'/api/capas/{capa.id}/close',
        json={'D8_confirmation': '完成'},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    log = AuditLog.query.one()
    assert log.old_value['capa']['status'] == '進行中'
    assert log.new_value['capa']['status'] == '已結案'
    assert log.old_value['source'] == {
        'module': 'NCMR', 'id': ncmr.id, 'status': '矯正中',
        'related_capa_id': capa.id, 'related_capa_source': 'capa', 'deleted_at': None,
    }
    assert log.new_value['source']['status'] == '矯正完成'
    assert 'NCMR-SOURCE-SECRET' not in json.dumps(
        {'old': log.old_value, 'new': log.new_value}, ensure_ascii=False
    )


def test_capa_delete_audit_contains_complaint_unlink_without_secret(
    client, db_session
):
    """CAPA 刪除稽核需證明客訴回復與清除關聯。"""
    user = User(username='capa_complaint_snapshot', password='pw', role='admin', is_active=True)
    complaint = CustomerComplaint(
        complaint_no='CC-CAPA-SNAPSHOT', customer='客戶',
        complaint_date=datetime.date(2026, 8, 1),
        description='secret=COMPLAINT-SOURCE-SECRET', complaint_type='quality',
        status='處理中',
    )
    db_session.add_all([user, complaint])
    db_session.flush()
    capa = CorrectiveAction(
        eight_d_number='CAPA-COMPLAINT-SNAPSHOT', source_type='complaint',
        source_id=complaint.id, status='進行中',
    )
    db_session.add(capa)
    db_session.flush()
    complaint.related_capa_id = capa.id
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.delete(
        f'/api/capas/{capa.id}', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    log = AuditLog.query.one()
    assert log.old_value['source']['status'] == '處理中'
    assert log.old_value['source']['related_capa_id'] == capa.id
    assert log.new_value['source']['status'] == '待處理'
    assert log.new_value['source']['related_capa_id'] is None
    assert 'COMPLAINT-SOURCE-SECRET' not in json.dumps(
        {'old': log.old_value, 'new': log.new_value}, ensure_ascii=False
    )


def test_capa_list_serializes_both_sources_with_bounded_query_count(app, db_session):
    """清單序列化：NCMR／客訴兩種來源都要帶出廠商與不良描述，
    且查詢次數不得隨筆數線性成長（避免退回 N+1）。"""
    from sqlalchemy import event

    from backend.extensions import db
    from backend.models import Inspector

    leaders = [Inspector(name=f'負責人{i}') for i in range(6)]
    db_session.add_all(leaders)
    db_session.flush()

    for i in range(3):
        ncmr = NCMR(
            ncmr_number=f'NCMR-209902-{i:03d}', date=datetime.date(2099, 2, 1),
            source='巡檢', vendor=f'廠商{i}', description=f'NCMR不良{i}', status='待處理',
        )
        db_session.add(ncmr)
        db_session.flush()
        db_session.add(CorrectiveAction(
            eight_d_number=f'CAPA-N-209902-{i:03d}', source_type='ncmr',
            source_id=ncmr.id, ncmr_id=ncmr.id, status='進行中',
            d1_leader_id=leaders[i].id,
        ))

    for i in range(3):
        complaint = CustomerComplaint(
            complaint_no=f'CC-209902-{i:03d}', customer=f'客戶{i}',
            complaint_date=datetime.date(2099, 2, 1), description=f'客訴不良{i}',
            complaint_type='quality', status='處理中',
        )
        db_session.add(complaint)
        db_session.flush()
        db_session.add(CorrectiveAction(
            eight_d_number=f'CAPA-C-209902-{i:03d}', source_type='complaint',
            source_id=complaint.id, status='進行中',
            d1_leader_id=leaders[3 + i].id,
        ))
    db_session.commit()
    db_session.expire_all()
    db_session.expunge_all()

    statements = []

    def _record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', _record)
    try:
        result = CAPAService.list_capas(per_page=20)
    finally:
        event.remove(db.engine, 'before_cursor_execute', _record)

    rows = {row['no']: row for row in result['data']}
    assert rows['CAPA-N-209902-000']['vendor'] == '廠商0'
    assert rows['CAPA-N-209902-000']['ncmr_description'] == 'NCMR不良0'
    assert rows['CAPA-N-209902-000']['owner'] == '負責人0'
    assert rows['CAPA-C-209902-002']['vendor'] == '客戶2'          # 客訴以客戶名稱對應廠商欄
    assert rows['CAPA-C-209902-002']['ncmr_description'] == '客訴不良2'
    assert rows['CAPA-C-209902-002']['owner'] == '負責人5'

    # count + 主查詢(含 joinedload) + NCMR 批次 + 客訴批次 = 4；放寬到 6 留餘裕，
    # 但遠低於「每列各查一次」的 14 次。
    assert len(statements) <= 6, f'查詢次數 {len(statements)} 過多，可能又退回 N+1：{statements}'
