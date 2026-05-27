import datetime

import pytest

from backend.models import CorrectiveAction, CustomerComplaint, NCMR
from backend.services.capa_service import CAPAService
from backend.services.complaint_service import ComplaintService


def test_prepare_capa_source_rejects_duplicate_complaint_capa(app, db_session):
    """已有 CAPA 關聯的客訴不可再次開立 CAPA"""
    with app.app_context():
        complaint = CustomerComplaint(
            complaint_no='CC-TEST-001',
            customer='測試客戶',
            complaint_date=datetime.date(2026, 5, 1),
            product_no='P-001',
            description='尺寸不良',
            complaint_type='quality',
            related_capa_id=99,
        )
        db_session.add(complaint)
        db_session.commit()

        with pytest.raises(ValueError, match='已開立 CAPA'):
            ComplaintService.prepare_capa_source(complaint.id)


def test_delete_ncmr_capa_clears_ncmr_link_and_status(app, db_session):
    """刪除 NCMR 來源 CAPA 時需清除 NCMR 關聯，讓 NCMR 可重新開立 CAPA"""
    with app.app_context():
        ncmr = NCMR(
            ncmr_number='NCMR-TEST-DELETE',
            date=datetime.date(2026, 5, 1),
            source='進料',
            description='外徑超差',
            status='矯正中',
        )
        db_session.add(ncmr)
        db_session.flush()

        capa = CorrectiveAction(
            eight_d_number='CAPA-TEST-DELETE',
            source_type='ncmr',
            source_id=ncmr.id,
            ncmr_id=ncmr.id,
            status='進行中',
        )
        db_session.add(capa)
        db_session.flush()
        ncmr.related_capa_id = capa.id
        ncmr.related_capa_source = 'capa'
        db_session.commit()

        CAPAService.delete(capa.id)

        refreshed = NCMR.query.get(ncmr.id)
        assert refreshed.related_capa_id is None
        assert refreshed.related_capa_source is None
        assert refreshed.status == '待處理'
