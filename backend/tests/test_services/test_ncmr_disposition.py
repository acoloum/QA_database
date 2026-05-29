import datetime
import pytest
from backend.models import NCMR, NcmrDisposition, Inspector
from backend.extensions import db
from backend.services.ncmr_service import NCMRService


def _make_ncmr(db_session, **kwargs):
    defaults = dict(
        ncmr_number='NCMR-DISP-001',
        date=datetime.date(2025, 1, 15),
        source='進料',
        vendor='TestVendor',
        material='6066-T6',
        product_info='38*3040',
        defect_quantity=100,
        status='待處理',
    )
    defaults.update(kwargs)
    n = NCMR(**defaults)
    db_session.add(n)
    db_session.commit()
    return n


def test_disposition_model_relationship(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        d = NcmrDisposition(ncmr_id=n.id, disposition_type='報廢', quantity=100)
        db_session.add(d)
        db_session.commit()
        fetched = NCMR.query.get(n.id)
        assert len(fetched.dispositions) == 1
        assert fetched.dispositions[0].disposition_type == '報廢'
        assert fetched.dispositions[0].quantity == 100
        assert fetched.dispositions[0].is_risk is False


def test_disposition_cascade_delete(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        db_session.add(NcmrDisposition(ncmr_id=n.id, disposition_type='報廢', quantity=100))
        db_session.commit()
        db_session.delete(n)
        db_session.commit()
        assert NcmrDisposition.query.count() == 0


def test_create_disposition_scrap(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {
            '處置類型': '報廢', '處置數量': 100,
        }, handler_id=None)
        d = NcmrDisposition.query.get(did)
        assert d.disposition_type == '報廢'
        assert d.quantity == 100


def test_create_disposition_concession_unauthorized_sets_risk(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {
            '處置類型': '讓步放行', '處置數量': 100,
            '是否超出客戶規格': True, '授權狀態': '未取得',
            '未授權放行理由': '客戶急需出貨',
        }, handler_id=None)
        d = NcmrDisposition.query.get(did)
        assert d.is_risk is True


def test_create_disposition_concession_unauthorized_requires_reason(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        with pytest.raises(ValueError, match='未授權放行理由'):
            NCMRService.create_disposition(n.id, {
                '處置類型': '讓步放行', '處置數量': 100,
                '是否超出客戶規格': True, '授權狀態': '未取得',
            }, handler_id=None)


def test_create_disposition_sorting_qty_mismatch(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        with pytest.raises(ValueError, match='合格數'):
            NCMRService.create_disposition(n.id, {
                '處置類型': '挑選全檢', '處置數量': 100,
                '合格數': 60, '不合格數': 30,
            }, handler_id=None)


def test_delete_disposition(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 100}, handler_id=None)
        NCMRService.delete_disposition(did)
        assert NcmrDisposition.query.get(did) is None


def test_update_disposition_recomputes_risk(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 100}, handler_id=None)
        # 改為超出客戶規格且未取得授權 → 應重新計算為風險項
        NCMRService.update_disposition(did, {
            '處置類型': '讓步放行', '處置數量': 100,
            '是否超出客戶規格': True, '授權狀態': '未取得', '未授權放行理由': '客戶要求',
        })
        d = NcmrDisposition.query.get(did)
        assert d.disposition_type == '讓步放行'
        assert d.is_risk is True
