"""廠商績效計算服務測試"""
import pytest
from contextlib import contextmanager
from sqlalchemy import event
from backend.extensions import db
from backend.models import Role, User, Vendor, VendorPerformance
from backend.services.vendor_performance_service import VendorPerformanceService
from backend.utils import generate_token


def _make_user(db_session, username, role_code):
    """建立具指定 role 的啟用使用者並回傳。"""
    user = User(username=username, password='pw', role=role_code, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user):
    """為使用者產生 Bearer token headers。"""
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}'}


def _vendor_viewer_role(db_session):
    """建立具 vendor.view 權限的角色（vendor.view 為 GET 讀取所需）。"""
    db_session.add(Role(
        code='vendor_viewer', name='廠商績效檢視者',
        permissions={'vendor.view': True},
    ))
    db_session.commit()


@pytest.fixture
def viewer_headers(db_session):
    """具 vendor.view 權限使用者的 Bearer headers。"""
    _vendor_viewer_role(db_session)
    user = _make_user(db_session, 'vendor_viewer_user', 'vendor_viewer')
    return _headers(user)


@pytest.fixture
def vendors(db_session):
    """建立一間基準廠商，供 query count 測試使用。"""
    vendor = Vendor(name='測試廠商_績效基線')
    db_session.add(vendor)
    db_session.commit()
    return [vendor]


def create_more_vendors(count, db_session):
    """額外建立 count 間廠商，模擬廠商數成長。"""
    for i in range(count):
        db_session.add(Vendor(name=f'測試廠商_額外_{i}'))
    db_session.commit()


@contextmanager
def count_sql(app):
    """計算區塊內執行的 SQL 語句數。"""
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _executemany):
        statements.append(statement)
    event.listen(db.session.get_bind(), 'before_cursor_execute', capture)
    try:
        yield lambda: len(statements)
    finally:
        event.remove(db.session.get_bind(), 'before_cursor_execute', capture)


def test_compute_score_perfect(app):
    """零缺陷、零CAPA天數、零客訴 → 滿分100"""
    with app.app_context():
        score = VendorPerformanceService._compute_score(
            defect_rate=0, avg_capa_days=0, complaint_count=0
        )
        assert score == 100.0


def test_compute_score_deductions(app):
    """缺陷率10% → 扣20分；客訴2件 → 扣10分 → 70分"""
    with app.app_context():
        score = VendorPerformanceService._compute_score(
            defect_rate=10.0, avg_capa_days=0, complaint_count=2
        )
        assert score == 70.0


def test_compute_score_minimum_zero(app):
    """扣超過100分時最低為0"""
    with app.app_context():
        score = VendorPerformanceService._compute_score(
            defect_rate=50.0, avg_capa_days=100, complaint_count=10
        )
        assert score == 0.0


def test_get_or_calculate_creates_record(app, db_session):
    """get_or_calculate 應建立 VendorPerformance 記錄"""
    with app.app_context():
        # 建立測試廠商
        v = Vendor(name='測試廠商_績效測試')
        db_session.add(v)
        db_session.commit()

        result = VendorPerformanceService.get_or_calculate(v.id, '2026-05')
        assert result['vendor_id'] == v.id
        assert result['period'] == '2026-05'
        assert 'score' in result
        assert 0 <= result['score'] <= 100

        # 確認已存入 DB
        perf = VendorPerformance.query.filter_by(vendor_id=v.id, period='2026-05').first()
        assert perf is not None


def test_vendor_history_route_clamps_months(client, db_session, monkeypatch):
    _vendor_viewer_role(db_session)
    user = _make_user(db_session, 'vendor_history_user', 'vendor_viewer')
    vendor = Vendor(name='測試廠商_月份限制')
    db_session.add(vendor)
    db_session.commit()
    captured = {}

    def fake_history(vendor_id, months):
        captured['vendor_id'] = vendor_id
        captured['months'] = months
        return []

    monkeypatch.setattr(VendorPerformanceService, 'history', staticmethod(fake_history))

    response = client.get(
        f'/api/vendor-performance/{vendor.id}/history?months=9999',
        headers=_headers(user),
    )

    assert response.status_code == 200
    assert captured == {'vendor_id': vendor.id, 'months': 36}


def test_vendor_history_route_uses_default_for_invalid_months(client, db_session, monkeypatch):
    _vendor_viewer_role(db_session)
    user = _make_user(db_session, 'vendor_history_bad_months', 'vendor_viewer')
    vendor = Vendor(name='測試廠商_月份格式')
    db_session.add(vendor)
    db_session.commit()
    captured = {}

    def fake_history(vendor_id, months):
        captured['vendor_id'] = vendor_id
        captured['months'] = months
        return []

    monkeypatch.setattr(VendorPerformanceService, 'history', staticmethod(fake_history))

    response = client.get(
        f'/api/vendor-performance/{vendor.id}/history?months=abc',
        headers=_headers(user),
    )

    assert response.status_code == 200
    assert captured == {'vendor_id': vendor.id, 'months': 6}


@pytest.mark.parametrize("period", ["abc", "2026-00", "2026-13", "2026-1", "26-01"])
def test_invalid_period_returns_400_without_write(client, period, db_session, viewer_headers):
    """無效月份格式應回 400，且不得寫入任何 VendorPerformance。"""
    before = VendorPerformance.query.count()
    response = client.get(f"/api/vendor-performance?period={period}", headers=viewer_headers)
    assert response.status_code == 400
    assert VendorPerformance.query.count() == before


def test_list_query_count_is_constant(app, vendors, db_session):
    """廠商數增加時，集合式計算的 SQL 語句數不得隨之成長。"""
    from backend.services.vendor_performance_service import parse_period
    with count_sql(app) as small:
        VendorPerformanceService.calculate_period(parse_period("2026-08"))
    create_more_vendors(20, db_session)
    with count_sql(app) as large:
        VendorPerformanceService.calculate_period(parse_period("2026-08"))
    assert large() <= small() + 1


def test_list_period_get_is_read_only(client, db_session, viewer_headers, monkeypatch):
    """GET 列表為純讀：commit 被替換成拋錯時仍須回 200。"""
    db_session.add(Vendor(name='測試廠商_純讀'))
    db_session.commit()

    def boom(*args, **kwargs):
        raise RuntimeError('GET 不應 commit')
    monkeypatch.setattr(db.session, 'commit', boom)
    response = client.get('/api/vendor-performance?period=2026-08', headers=viewer_headers)
    assert response.status_code == 200
