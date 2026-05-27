from backend.models import ActionTask, Inspector, User
from backend.services.task_service import TaskService


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
