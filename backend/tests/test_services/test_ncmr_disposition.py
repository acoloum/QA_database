import datetime
import pytest
from backend.models import NCMR, NcmrDisposition, Inspector, ReworkRequest
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


# ==================================================
# 結案 Gate 測試（IATF 16949 §8.7）
# ==================================================

def _close(ncmr_id):
    return NCMRService.update_ncmr({'識別碼': ncmr_id, '狀態': '已結案'})


def test_close_blocked_without_disposition(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        with pytest.raises(ValueError, match='處置'):
            _close(n.id)


def test_close_blocked_qty_mismatch(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=100)
        NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 60}, handler_id=None)
        with pytest.raises(ValueError, match='數量'):
            _close(n.id)


def test_close_ok_scrap_full_qty(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=100)
        NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 100}, handler_id=None)
        assert _close(n.id) is True
        assert NCMR.query.get(n.id).status == '已結案'


def test_close_blocked_rework_not_closed(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=50)
        rw = ReworkRequest(ncmr_id=n.id, rework_number='RW-001', status='執行中')
        db_session.add(rw)
        db_session.commit()
        NCMRService.create_disposition(n.id, {
            '處置類型': '矯正重工', '處置數量': 50, '關聯重工單ID': rw.id,
        }, handler_id=None)
        with pytest.raises(ValueError, match='重工'):
            _close(n.id)


def test_close_ok_rework_closed(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=50)
        rw = ReworkRequest(ncmr_id=n.id, rework_number='RW-002', status='已結案')
        db_session.add(rw)
        db_session.commit()
        NCMRService.create_disposition(n.id, {
            '處置類型': '矯正重工', '處置數量': 50, '關聯重工單ID': rw.id,
        }, handler_id=None)
        assert _close(n.id) is True


def test_close_blocked_sorting_qty_mismatch(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=100)
        # 直接建立合計正確的挑選全檢，再竄改使其不一致以驗證 gate 的縱深防禦
        did = NCMRService.create_disposition(n.id, {
            '處置類型': '挑選全檢', '處置數量': 100, '合格數': 70, '不合格數': 30,
        }, handler_id=None)
        d = NcmrDisposition.query.get(did)
        d.fail_qty = 20  # 70 + 20 != 100
        db.session.commit()
        with pytest.raises(ValueError, match='挑選全檢'):
            _close(n.id)


def test_close_ok_sorting(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=100)
        NCMRService.create_disposition(n.id, {
            '處置類型': '挑選全檢', '處置數量': 100, '合格數': 70, '不合格數': 30,
        }, handler_id=None)
        assert _close(n.id) is True


def test_close_concession_within_customer_spec_ok(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=40)
        # 未超出客戶規格的內部讓步放行 → 無需授權即可結案
        NCMRService.create_disposition(n.id, {
            '處置類型': '讓步放行', '處置數量': 40, '是否超出客戶規格': False,
        }, handler_id=None)
        assert _close(n.id) is True
