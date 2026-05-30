from datetime import date, datetime, timedelta, timezone

from backend.extensions import db
from backend.models import Inspector, SPCCache, Vendor
from backend.services.shipping_service import ShippingService


def test_save_data_invalidates_spc_cache(app, db_session):
    """新增出貨資料後，SPC 快取應失效，避免圖表讀到舊統計。"""
    with app.app_context():
        inspector = Inspector(name="測試品保")
        vendor = Vendor(name="測試廠商")
        db_session.add_all([inspector, vendor])
        db_session.add(SPCCache(
            cache_key="spc|外徑|||||",
            result={"labels": ["舊資料"]},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db_session.commit()

        ShippingService.save_data({
            "檢驗日期": date(2026, 5, 30),
            "檢驗人員姓名": "測試品保",
            "廠商中文名稱": "測試廠商",
            "材質": "6061",
            "檢驗規格": "10*2*100",
            "訂單號碼": "SO-001",
            "組數": 1,
            "measurements": {
                "1": {
                    "外徑": {"value_min": 9.9, "value_max": 10.1, "is_ng": False},
                }
            },
        })

        assert db.session.query(SPCCache).count() == 0
