"""廠商績效計算服務測試"""
import pytest
from datetime import date
from backend.models import Vendor, VendorPerformance
from backend.services.vendor_performance_service import VendorPerformanceService


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
