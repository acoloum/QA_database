import datetime
import pytest
from backend.models import NCMR, NcmrDisposition, Inspector
from backend.extensions import db


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
