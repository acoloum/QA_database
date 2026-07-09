from backend.models import ShippingData, ShippingMeasurement
from backend.services.shipping_service import ShippingService


def _base_payload(measurements):
    return {
        '檢驗日期': '2026-07-09',
        '檢驗人員姓名': 'Test Inspector',
        '廠商中文名稱': 'Test Vendor',
        '檢驗規格': '10*2',
        '材質': '6061',
        '訂單號碼': 'SO-1',
        '組數': 1,
        'measurements': measurements,
    }


def test_segmented_keys_roundtrip(db_session, setup_data):
    """分段複合鍵寫入後，DB 項目欄保持乾淨、回傳時組回複合鍵"""
    payload = _base_payload({
        '1': {
            '外徑@前段': {'value_min': 9.8, 'value_max': 10.1},
            '外徑@中段': {'value_min': 9.9, 'value_max': 10.2},
            '外徑@後段': {'value_min': 9.7, 'value_max': 10.0},
            '硬度': {'value_single': 55},
        },
    })
    ShippingService.save_data(payload)

    rows = ShippingMeasurement.query.filter_by(item='外徑').all()
    assert sorted(r.position for r in rows) == ['中段', '前段', '後段']
    hardness = ShippingMeasurement.query.filter_by(item='硬度').one()
    assert hardness.position == ''

    record = ShippingData.query.first()
    res = ShippingService._map_row_to_dict(record)
    assert set(res['measurements']['1'].keys()) == {'外徑@前段', '外徑@中段', '外徑@後段', '硬度'}
    assert res['measurements']['1']['外徑@中段']['value_max'] == 10.2


def test_invalid_position_skipped(db_session, setup_data):
    """位置不合法的鍵應整筆略過，不寫入子表"""
    payload = _base_payload({'1': {'外徑@亂段': {'value_min': 1}}})
    ShippingService.save_data(payload)
    assert ShippingMeasurement.query.count() == 0


def test_plain_keys_unchanged(db_session, setup_data):
    """未分段資料行為與現行完全相同"""
    payload = _base_payload({'1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}}})
    ShippingService.save_data(payload)

    row = ShippingMeasurement.query.one()
    assert (row.item, row.position) == ('外徑', '')

    record = ShippingData.query.first()
    res = ShippingService._map_row_to_dict(record)
    assert list(res['measurements']['1'].keys()) == ['外徑']
