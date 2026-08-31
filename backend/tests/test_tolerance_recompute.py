# -*- coding: utf-8 -*-
"""公差異動後自動重判「是否超差」的測試。

重點在於：公差是在紀錄存檔之後才建立／修改的情境——那正是造成全庫 41 筆判定
與現行公差不一致的原因，也是這個機制要根治的問題。
"""
import pytest

from backend.extensions import db
from backend.models import (ShippingData, ShippingMeasurement, Vendor,
                            VendorToleranceMain, VendorToleranceDetail, AuditLog)
from backend.services.tolerance_service import ToleranceService


@pytest.fixture
def vendor(db_session):
    v = Vendor(name='測試廠商')
    db_session.add(v)
    db_session.flush()
    return v


def _make_shipping(db_session, vendor, material='6061-T6', spec='50*2*300',
                   od_value=50.0, is_ng=False):
    """建立一筆已存檔的出貨紀錄，外徑量測值可指定，is_ng 預設凍結為合格。"""
    record = ShippingData(material=material, spec=spec,
                          vendor_id=vendor.id, group_count=1, is_ng=is_ng)
    db_session.add(record)
    db_session.flush()
    db_session.add(ShippingMeasurement(
        shipping_id=record.id, group_num=1, item='外徑', position='',
        value_min=od_value, value_max=od_value))
    db_session.flush()
    return record


def _tolerance_payload(vendor_id, material='6061-T6', spec='50*2*300',
                       tol_min=-0.1, tol_max=0.1):
    return {
        '材質': material,
        '規格': spec,
        '廠商ID': vendor_id,
        'details': [{'測量項目': '外徑', '公差下限': tol_min, '公差上限': tol_max}],
    }


def test_新增公差會補判存檔時查無公差的舊紀錄(db_session, vendor):
    # 存檔當下沒有任何公差 → is_ng 被凍結為 False（未判定，不是合格）
    record = _make_shipping(db_session, vendor, od_value=50.5)

    ToleranceService.add_tolerance(_tolerance_payload(vendor.id))

    # 外徑 50.5 超出 50±0.1
    assert db.session.get(ShippingData, record.id).is_ng is True


def test_新增公差不會誤動合格紀錄(db_session, vendor):
    record = _make_shipping(db_session, vendor, od_value=50.05)

    ToleranceService.add_tolerance(_tolerance_payload(vendor.id))

    assert db.session.get(ShippingData, record.id).is_ng is False


def test_放寬公差會把原本的超差改回合格(db_session, vendor):
    record = _make_shipping(db_session, vendor, od_value=50.15)
    tol_id = ToleranceService.add_tolerance(_tolerance_payload(vendor.id))
    assert db.session.get(ShippingData, record.id).is_ng is True

    ToleranceService.update_tolerance(
        tol_id, _tolerance_payload(vendor.id, tol_min=-0.2, tol_max=0.2))

    assert db.session.get(ShippingData, record.id).is_ng is False


def test_更新公差改廠商時舊廠商的紀錄也要重判(db_session, vendor):
    """只算異動後的範圍會漏掉「原本吃這筆公差、改完不再吃」的紀錄。"""
    other = Vendor(name='另一家廠商')
    db_session.add(other)
    db_session.flush()

    record = _make_shipping(db_session, vendor, od_value=50.5)
    tol_id = ToleranceService.add_tolerance(_tolerance_payload(vendor.id))
    assert db.session.get(ShippingData, record.id).is_ng is True

    # 公差改掛到另一家廠商後，原廠商的紀錄已無公差可用 → 回到未判定
    ToleranceService.update_tolerance(tol_id, _tolerance_payload(other.id))

    assert db.session.get(ShippingData, record.id).is_ng is False


def test_刪除公差後紀錄回到未判定(db_session, vendor):
    record = _make_shipping(db_session, vendor, od_value=50.5)
    tol_id = ToleranceService.add_tolerance(_tolerance_payload(vendor.id))
    assert db.session.get(ShippingData, record.id).is_ng is True

    ToleranceService.delete_tolerance(tol_id)

    assert db.session.get(ShippingData, record.id).is_ng is False


def test_他廠紀錄不受本廠公差影響(db_session, vendor):
    other = Vendor(name='不相干廠商')
    db_session.add(other)
    db_session.flush()
    outsider = _make_shipping(db_session, other, od_value=50.5)

    ToleranceService.add_tolerance(_tolerance_payload(vendor.id))

    assert db.session.get(ShippingData, outsider.id).is_ng is False


def test_材質不相符的紀錄不在重判範圍(db_session, vendor):
    # 公差材質為 6061-T6，紀錄材質 7075-T6 不被它包含
    outsider = _make_shipping(db_session, vendor, material='7075-T6', od_value=50.5)

    ToleranceService.add_tolerance(_tolerance_payload(vendor.id))

    assert db.session.get(ShippingData, outsider.id).is_ng is False


def test_有紀錄被翻動時寫入稽核日誌(db_session, vendor):
    _make_shipping(db_session, vendor, od_value=50.5)

    ToleranceService.add_tolerance(_tolerance_payload(vendor.id), user_id=None)

    logs = AuditLog.query.filter_by(action='公差異動重判是否超差').all()
    assert len(logs) == 1
    assert '出貨 1 筆' in logs[0].new_value


def test_沒有紀錄被翻動時不留稽核日誌(db_session, vendor):
    _make_shipping(db_session, vendor, od_value=50.05)

    ToleranceService.add_tolerance(_tolerance_payload(vendor.id))

    assert AuditLog.query.filter_by(action='公差異動重判是否超差').count() == 0
