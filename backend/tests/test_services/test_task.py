from backend.models import ActionTask, Inspector, User
from backend.services.task_service import TaskService
from backend.utils import generate_token


def test_my_tasks_for_user_uses_linked_inspector_id(app, db_session):
    """我的待辦需以使用者綁定的品管人員 ID 查詢，而不是使用者 ID"""
    with app.app_context():
        user = User(username='task_user', password='pw', inspector_id=None)
        inspector = Inspector(name='任務負責人')
        other_inspector = Inspector(name='其他人員')
        db_session.add_all([user, inspector, other_inspector])
        db_session.flush()

        user.inspector_id = inspector.id
        own_task = ActionTask(
            task_no='TASK-OWN',
            source_type='capa',
            source_id=1,
            category='pfmea',
            title='更新 PFMEA',
            assignee_id=inspector.id,
            status='pending',
        )
        other_task = ActionTask(
            task_no='TASK-OTHER',
            source_type='capa',
            source_id=1,
            category='sop',
            title='更新 SOP',
            assignee_id=other_inspector.id,
            status='pending',
        )
        db_session.add_all([own_task, other_task])
        db_session.commit()

        tasks = TaskService.my_tasks_for_user(user)

        assert [t['task_no'] for t in tasks] == ['TASK-OWN']


def test_task_list_route_clamps_per_page(client, db_session):
    # 測試目的為「分頁上限」，非權限；admin 為內建全權限角色，不需 DB Role
    user = User(username='task_list_user', password='pw', role='admin', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.get('/api/tasks?per_page=5000', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.get_json()['per_page'] == 100


def test_task_list_route_uses_default_for_invalid_page(client, db_session):
    # 測試目的為「無效頁碼回退」，非權限；admin 為內建全權限角色，不需 DB Role
    user = User(username='task_list_bad_page', password='pw', role='admin', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.get('/api/tasks?page=abc', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.get_json()['page'] == 1


def test_list_tasks_eager_loads_assignee(app, db_session):
    """清單序列化會讀 assignee.name；查詢次數不得隨承辦人數量成長。"""
    from sqlalchemy import event

    from backend.extensions import db

    inspectors = [Inspector(name=f'承辦{i}') for i in range(8)]
    db_session.add_all(inspectors)
    db_session.flush()
    for i, inspector in enumerate(inspectors):
        db_session.add(ActionTask(
            task_no=f'TASK-EAGER-{i:03d}',
            source_type='capa',
            source_id=i + 1,
            category='pfmea',
            title=f'任務{i}',
            assignee_id=inspector.id,
            status='pending',
        ))
    db_session.commit()
    db_session.expire_all()
    db_session.expunge_all()

    statements = []

    def _record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', _record)
    try:
        result = TaskService.list_tasks(per_page=20)
    finally:
        event.remove(db.engine, 'before_cursor_execute', _record)

    names = {row['task_no']: row['assignee_name'] for row in result['data']}
    assert names['TASK-EAGER-000'] == '承辦0'
    assert names['TASK-EAGER-007'] == '承辦7'
    # count + 主查詢(joinedload) = 2；放寬到 4，仍遠低於逐列查詢的 10 次。
    assert len(statements) <= 4, f'查詢次數 {len(statements)} 過多，可能又退回 N+1：{statements}'
