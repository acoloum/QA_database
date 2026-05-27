"""軟刪除與狀態機整合測試"""
from datetime import date

import pytest

from backend.models import NCMR
from backend.services.ncmr_service import NCMRService


def test_ncmr_soft_delete(app, db_session):
    """軟刪除後 active_query 查不到，但 raw query 仍可查到"""
    n = NCMR(
        ncmr_number='NCMR-SOFT-001',
        date=date.today(),
        status='待處理',
        description='測試軟刪除',
        source='進料',
    )
    db_session.add(n)
    db_session.commit()
    ncmr_id = n.id

    n.soft_delete()
    db_session.commit()

    result = NCMR.active_query().filter_by(id=ncmr_id).first()
    assert result is None

    result_raw = NCMR.query.filter_by(id=ncmr_id).first()
    assert result_raw is not None
    assert result_raw.deleted_at is not None


def test_ncmr_invalid_transition_via_service(app, db_session):
    """NCMRService.update_ncmr 對非法狀態轉移應拋出 ValueError"""
    n = NCMR(
        ncmr_number='NCMR-TRANS-001',
        date=date.today(),
        status='待處理',
        description='測試狀態機',
        source='進料',
    )
    db_session.add(n)
    db_session.commit()

    with pytest.raises(ValueError, match='非法狀態轉移'):
        NCMRService.update_ncmr({'識別碼': n.id, '狀態': '矯正完成'})
