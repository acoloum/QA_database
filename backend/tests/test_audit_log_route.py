from sqlalchemy import event

from backend.extensions import db
from backend.models import AuditLog, Role, User
from backend.utils import generate_token, hash_password


def _make_admin_headers(db_session):
    db_session.add(Role(code='audit_admin', name='審計管理者', permissions={'user.manage': True}))
    user = User(
        username='audit_admin',
        password=hash_password('pw12345678'),
        role='audit_admin',
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}'}


def _seed_logs(db_session, count):
    """每筆日誌各屬於不同使用者，讓延遲載入時每列都得多查一次。"""
    for i in range(count):
        user = User(username=f'auditor_{i}', password='x', role='audit_admin', is_active=True)
        db_session.add(user)
        db_session.flush()
        db_session.add(AuditLog(user_id=user.id, action='UPDATE', module='ncmr', record_id=i))
    # 另加一筆使用者已刪除（user_id 為空）的日誌
    db_session.add(AuditLog(user_id=None, action='DELETE', module='ncmr', record_id=999))
    db_session.commit()
    db_session.expunge_all()


def _count_selects(client, url, headers):
    statements = []

    def _on_execute(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    engine = db.engine
    event.listen(engine, 'before_cursor_execute', _on_execute)
    try:
        resp = client.get(url, headers=headers)
    finally:
        event.remove(engine, 'before_cursor_execute', _on_execute)
    return resp, statements


def test_audit_logs_lists_usernames(client, db_session):
    headers = _make_admin_headers(db_session)
    _seed_logs(db_session, 3)

    resp = client.get('/api/audit-logs?module=ncmr', headers=headers)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total'] == 4
    usernames = {item['username'] for item in body['data']}
    assert usernames == {'auditor_0', 'auditor_1', 'auditor_2', '(已刪除)'}


def test_audit_logs_query_count_does_not_grow_with_rows(client, db_session):
    """使用者名稱須隨日誌一次載入，查詢次數不可隨筆數成長（避免 N+1）。"""
    headers = _make_admin_headers(db_session)
    _seed_logs(db_session, 2)
    _, few = _count_selects(client, '/api/audit-logs', headers)

    for i in range(15):
        user = User(username=f'extra_{i}', password='x', role='audit_admin', is_active=True)
        db_session.add(user)
        db_session.flush()
        db_session.add(AuditLog(user_id=user.id, action='CREATE', module='capa', record_id=i))
    db_session.commit()
    db_session.expunge_all()

    resp, many = _count_selects(client, '/api/audit-logs', headers)

    assert resp.status_code == 200
    assert len(resp.get_json()['data']) == 18
    assert len(many) == len(few)
