import datetime

from backend.models import CorrectiveAction, Role, User, ShippingData
from backend.utils import generate_token, hash_password


def _make_headers(db_session):
    db_session.add(Role(code='dashboard_viewer', name='看板檢視者', permissions={}))
    user = User(
        username='dashboard_viewer',
        password=hash_password('pw12345678'),
        role='dashboard_viewer',
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role)
    return {'Authorization': f'Bearer {token}'}


def test_dashboard_trends_runs_on_sqlite_test_database(client, db_session):
    """Dashboard 趨勢查詢不可依賴 PostgreSQL-only to_char，測試環境也應可執行。"""
    db_session.add(ShippingData(
        date=datetime.date.today().replace(day=1),
        material='6063',
        spec='40x3',
        is_ng=False,
    ))
    db_session.commit()

    resp = client.get('/api/dashboard/trends', headers=_make_headers(db_session))

    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['shipping_ok_by_month']) == 6
    assert data['shipping_ok_by_month'][-1]['count'] == 1


def test_dashboard_todos_uses_current_capa_problem_fields(client, db_session):
    """Dashboard 待辦應支援新版 CAPA D2 欄位，不可讀取已移除的 d2 屬性。"""
    db_session.add(CorrectiveAction(
        eight_d_number='CAPA-TODO-001',
        status='進行中',
        d2_what='外徑尺寸超差',
    ))
    db_session.commit()

    resp = client.get('/api/dashboard/todos', headers=_make_headers(db_session))

    assert resp.status_code == 200
    data = resp.get_json()
    capa_todo = next(item for item in data if item['type'] == 'capa')
    assert capa_todo['description'] == '外徑尺寸超差'
