import datetime

from backend.models import Role, User, ShippingData
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
