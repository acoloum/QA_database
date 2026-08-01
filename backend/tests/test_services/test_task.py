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
    user = User(username='task_list_user', password='pw', role='viewer', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.get('/api/tasks?per_page=5000', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.get_json()['per_page'] == 100


def test_task_list_route_uses_default_for_invalid_page(client, db_session):
    user = User(username='task_list_bad_page', password='pw', role='viewer', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.get('/api/tasks?page=abc', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.get_json()['page'] == 1
