"""廠商績效計算服務測試"""
import pytest
from datetime import date
from backend.models import User, Vendor, VendorPerformance
from backend.services.vendor_performance_service import VendorPerformanceService
from backend.utils import generate_token


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
    user = User(username='vendor_history_user', password='pw', role='viewer', is_active=True)
    vendor = Vendor(name='測試廠商_月份限制')
    db_session.add_all([user, vendor])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    captured = {}

    def fake_history(vendor_id, months):
        captured['vendor_id'] = vendor_id
        captured['months'] = months
        return []

    monkeypatch.setattr(VendorPerformanceService, 'history', staticmethod(fake_history))

    response = client.get(
        f'/api/vendor-performance/{vendor.id}/history?months=9999',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert captured == {'vendor_id': vendor.id, 'months': 36}


def test_vendor_history_route_uses_default_for_invalid_months(client, db_session, monkeypatch):
    user = User(username='vendor_history_bad_months', password='pw', role='viewer', is_active=True)
    vendor = Vendor(name='測試廠商_月份格式')
    db_session.add_all([user, vendor])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    captured = {}

    def fake_history(vendor_id, months):
        captured['vendor_id'] = vendor_id
        captured['months'] = months
        return []

    monkeypatch.setattr(VendorPerformanceService, 'history', staticmethod(fake_history))

    response = client.get(
        f'/api/vendor-performance/{vendor.id}/history?months=abc',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert captured == {'vendor_id': vendor.id, 'months': 6}
