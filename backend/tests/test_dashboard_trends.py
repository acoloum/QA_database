import datetime

from backend.models import CorrectiveAction, NCMR, PatrolMain, ReworkRequest, Role, User, ShippingData
from backend.services.dashboard_service import DashboardService
from backend.services.date_range import DateWindow
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


# ---------------------------------------------------------------------------
# 聚合查詢加上外框日期 WHERE（可走索引）後的行為回歸
# ---------------------------------------------------------------------------

def test_dashboard_stats_counts_previous_period(db_session):
    """前期資料落在外框 WHERE 範圍內，previous 與趨勢仍須正確計算。"""
    db_session.add_all([
        ShippingData(date=datetime.date(2026, 8, 10), material='6063', spec='40x3', is_ng=False),
        ShippingData(date=datetime.date(2026, 8, 20), material='6063', spec='40x3', is_ng=False),
        # 前期（7 月）
        ShippingData(date=datetime.date(2026, 7, 15), material='6063', spec='40x3', is_ng=False),
    ])
    db_session.commit()

    stats = DashboardService.get_stats(
        DateWindow(start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 31))
    )

    assert stats['shipping']['current'] == 2
    assert stats['shipping']['previous'] == 1


def test_dashboard_stats_excludes_records_outside_span(db_session):
    """外框 WHERE 之外的資料不得被計入任何一期。"""
    db_session.add_all([
        ShippingData(date=datetime.date(2026, 8, 10), material='6063', spec='40x3', is_ng=False),
        # 遠早於前期起點
        ShippingData(date=datetime.date(2020, 1, 1), material='6063', spec='40x3', is_ng=False),
        # 晚於當期結束
        ShippingData(date=datetime.date(2027, 1, 1), material='6063', spec='40x3', is_ng=False),
    ])
    db_session.commit()

    stats = DashboardService.get_stats(
        DateWindow(start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 31))
    )

    assert stats['shipping']['current'] == 1
    assert stats['shipping']['previous'] == 0


def test_dashboard_stats_ng_counts_folded_into_same_query(db_session):
    """NG 數併入主查詢後，仍只計當期且 ng_rate 正確。"""
    db_session.add_all([
        ShippingData(date=datetime.date(2026, 8, 5), material='6063', spec='40x3', is_ng=True),
        ShippingData(date=datetime.date(2026, 8, 6), material='6063', spec='40x3', is_ng=False),
        ShippingData(date=datetime.date(2026, 8, 7), material='6063', spec='40x3', is_ng=False),
        ShippingData(date=datetime.date(2026, 8, 8), material='6063', spec='40x3', is_ng=False),
        # 前期 NG 不得計入當期 ng_count
        ShippingData(date=datetime.date(2026, 7, 5), material='6063', spec='40x3', is_ng=True),
    ])
    db_session.add_all([
        PatrolMain(date=datetime.date(2026, 8, 5), material='6063', spec='40x3', is_ng=True),
        PatrolMain(date=datetime.date(2026, 8, 6), material='6063', spec='40x3', is_ng=False),
        PatrolMain(date=datetime.date(2026, 7, 6), material='6063', spec='40x3', is_ng=True),
    ])
    db_session.commit()

    stats = DashboardService.get_stats(
        DateWindow(start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 31))
    )

    assert stats['shipping']['current'] == 4
    assert stats['shipping']['ng_count'] == 1
    assert stats['shipping']['ng_rate'] == 25.0
    assert stats['patrol']['current'] == 2
    assert stats['patrol']['ng_count'] == 1
    assert stats['patrol']['ng_rate'] == 50.0


def test_dashboard_stats_supports_non_adjacent_comparison_window(db_session):
    """明確指定不相鄰的比較期時，外框仍須涵蓋兩端（spanning 取 min/max）。"""
    db_session.add_all([
        ShippingData(date=datetime.date(2026, 8, 10), material='6063', spec='40x3', is_ng=False),
        # 比較期在半年前，與當期不相鄰
        ShippingData(date=datetime.date(2026, 2, 10), material='6063', spec='40x3', is_ng=False),
        ShippingData(date=datetime.date(2026, 2, 11), material='6063', spec='40x3', is_ng=False),
        # 兩期之間的資料不屬於任何一期
        ShippingData(date=datetime.date(2026, 5, 1), material='6063', spec='40x3', is_ng=False),
    ])
    db_session.commit()

    stats = DashboardService.get_stats(
        DateWindow(start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 31)),
        comparison=DateWindow(start_date=datetime.date(2026, 2, 1), end_date=datetime.date(2026, 2, 28)),
    )

    assert stats['shipping']['current'] == 1
    assert stats['shipping']['previous'] == 2


def test_dashboard_stats_ignores_null_dates(db_session):
    """日期為 NULL 的資料在加上 WHERE 後仍應被排除（與原本 CASE else_=0 行為一致）。"""
    db_session.add_all([
        ShippingData(date=datetime.date(2026, 8, 10), material='6063', spec='40x3', is_ng=False),
        ShippingData(date=None, material='6063', spec='40x3', is_ng=True),
    ])
    db_session.commit()

    stats = DashboardService.get_stats(
        DateWindow(start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 31))
    )

    assert stats['shipping']['current'] == 1
    assert stats['shipping']['ng_count'] == 0
