import pytest
import datetime
from backend.models import NCMR, Inspector
from backend.services.ncmr_service import NCMRService


def _make_ncmr(db_session, **kwargs):
    defaults = dict(
        ncmr_number='NCMR-TEST-001',
        date=datetime.date(2025, 1, 15),
        source='進料',
        vendor='TestVendor',
        material='6066-T6',
        product_info='38*3040',
        defect_quantity=5,
        status='待處理',
    )
    defaults.update(kwargs)
    n = NCMR(**defaults)
    db_session.add(n)
    db_session.commit()
    return n


def test_get_ncmr_list_pagination(app, db_session):
    with app.app_context():
        for i in range(25):
            _make_ncmr(db_session, ncmr_number=f'NCMR-{i:03}')
        result = NCMRService.get_ncmr_list(page=1, per_page=20)
        assert result['total'] == 25
        assert len(result['data']) == 20
        result2 = NCMRService.get_ncmr_list(page=2, per_page=20)
        assert len(result2['data']) == 5


def test_get_ncmr_list_filter_vendor(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-A', vendor='AluCorp')
        _make_ncmr(db_session, ncmr_number='NCMR-B', vendor='SteelInc')
        result = NCMRService.get_ncmr_list(vendor='alu')
        assert result['total'] == 1
        assert result['data'][0]['廠商'] == 'AluCorp'


def test_get_ncmr_list_filter_source(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-C', source='進料')
        _make_ncmr(db_session, ncmr_number='NCMR-D', source='巡檢')
        result = NCMRService.get_ncmr_list(source='進料')
        assert result['total'] == 1
        assert result['data'][0]['來源'] == '進料'


def test_get_ncmr_list_filter_date_range(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-E', date=datetime.date(2025, 1, 10))
        _make_ncmr(db_session, ncmr_number='NCMR-F', date=datetime.date(2025, 3, 20))
        result = NCMRService.get_ncmr_list(date_from='2025-01-01', date_to='2025-02-28')
        assert result['total'] == 1
        assert result['data'][0]['日期'] == '2025-01-10'


from backend.models import CorrectiveAction


def _make_car(db_session, ncmr, **kwargs):
    defaults = dict(
        ncmr_id=ncmr.id,
        car_number='CAR-TEST-001',
        status='進行中',
    )
    defaults.update(kwargs)
    ca = CorrectiveAction(**defaults)
    db_session.add(ca)
    db_session.commit()
    return ca


def test_get_cara_list_pagination(app, db_session):
    with app.app_context():
        for i in range(5):
            n = _make_ncmr(db_session, ncmr_number=f'NCMR-CAR-{i}')
            _make_car(db_session, n, car_number=f'CAR-{i:03}')
        result = NCMRService.get_cara_list(page=1, per_page=3)
        assert result['total'] == 5
        assert len(result['data']) == 3


def test_get_cara_list_filter_vendor(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-V1', vendor='VendorAlpha')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-V2', vendor='VendorBeta')
        _make_car(db_session, n1, car_number='CAR-V1')
        _make_car(db_session, n2, car_number='CAR-V2')
        result = NCMRService.get_cara_list(vendor='alpha')
        assert result['total'] == 1
        assert result['data'][0]['ncmr_vendor'] == 'VendorAlpha'


def test_get_cara_list_filter_status(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-S1')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-S2')
        _make_car(db_session, n1, car_number='CAR-S1', status='進行中')
        _make_car(db_session, n2, car_number='CAR-S2', status='已結案')
        result = NCMRService.get_cara_list(status='已結案')
        assert result['total'] == 1
        assert result['data'][0]['狀態'] == '已結案'
