import datetime

from backend.models import CorrectiveAction, NCMR, ReworkRequest, Role, User, ShippingData
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
    token = generate_token(user.id, user.username, user.role, user.token_version)
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


def test_dashboard_trends_excludes_soft_deleted_ncmr(client, db_session):
    """Dashboard 趨勢不應計入已軟刪除的 NCMR。"""
    ncmr = NCMR(
        ncmr_number='NCMR-DELETED-TREND',
        date=datetime.date.today().replace(day=1),
        status='待處理',
    )
    db_session.add(ncmr)
    db_session.flush()
    ncmr.soft_delete()
    db_session.commit()

    resp = client.get('/api/dashboard/trends', headers=_make_headers(db_session))

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ncmr_by_month'][-1]['count'] == 0


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


def test_dashboard_stats_excludes_terminal_rework_statuses_from_pending(client, db_session):
    """Dashboard 統計的重工 pending 不應包含已結案或撤銷的終止狀態。"""
    db_session.add_all([
        ReworkRequest(rework_number='RW-PENDING', status='進行中'),
        ReworkRequest(rework_number='RW-CLOSED', status='已結案'),
        ReworkRequest(rework_number='RW-CANCELLED', status='撤銷'),
    ])
    db_session.commit()

    resp = client.get('/api/dashboard/stats?period=this_month', headers=_make_headers(db_session))

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stats']['rework']['pending'] == 1


def test_dashboard_stats_includes_datetime_on_end_date(client, db_session):
    """結束日當天中午的 DateTime 資料應計入（不可用 <= end_date 排除當日）。"""
    db_session.add(CorrectiveAction(
        eight_d_number='CAPA-ENDDATE-NOON',
        created_at=datetime.datetime(2026, 8, 31, 12, 0),
        status='進行中',
    ))
    db_session.commit()

    resp = client.get(
        '/api/dashboard/stats?start=2026-08-01&end=2026-08-31',
        headers=_make_headers(db_session),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stats']['capa']['current'] == 1


def test_dashboard_stats_includes_cross_year_datetime(client, db_session):
    """跨年日期範圍的 DateTime 資料應計入。"""
    db_session.add(CorrectiveAction(
        eight_d_number='CAPA-CROSS-YEAR',
        created_at=datetime.datetime(2025, 12, 31, 23, 30),
        status='進行中',
    ))
    db_session.commit()

    resp = client.get(
        '/api/dashboard/stats?start=2025-12-01&end=2026-01-31',
        headers=_make_headers(db_session),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stats']['capa']['current'] == 1


def test_dashboard_stats_excludes_soft_deleted_ncmr(client, db_session):
    """Dashboard 統計不應計入已軟刪除的 NCMR。"""
    ncmr = NCMR(
        ncmr_number='NCMR-SOFTDEL-STATS',
        date=datetime.date(2026, 8, 15),
        status='待處理',
    )
    db_session.add(ncmr)
    db_session.flush()
    ncmr.soft_delete()
    db_session.commit()

    resp = client.get(
        '/api/dashboard/stats?start=2026-08-01&end=2026-08-31',
        headers=_make_headers(db_session),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stats']['ncmr']['current'] == 0


def test_dashboard_stats_includes_date_column_on_end_date(client, db_session):
    """Date 欄位應包含 end_date 當天資料。"""
    db_session.add(ShippingData(
        date=datetime.date(2026, 8, 31),
        material='6063',
        spec='40x3',
        is_ng=False,
    ))
    db_session.commit()

    resp = client.get(
        '/api/dashboard/stats?start=2026-08-01&end=2026-08-31',
        headers=_make_headers(db_session),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stats']['shipping']['current'] == 1
