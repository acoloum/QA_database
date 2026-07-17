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


def test_get_stats_includes_all_segments(db_session, setup_data):
    """SPC 統計：分段資料三段皆納入計算，不互相覆蓋"""
    payload = _base_payload({
        '1': {
            '外徑@前段': {'value_min': 9.8, 'value_max': 10.1},
            '外徑@中段': {'value_min': 9.9, 'value_max': 10.2},
            '外徑@後段': {'value_min': 9.7, 'value_max': 10.0},
        },
        '2': {'外徑': {'value_min': 9.5, 'value_max': 10.5}},
    })
    payload['組數'] = 2
    ShippingService.save_data(payload)

    stats = ShippingService.get_stats({'field': '外徑'})

    # 4 筆中點：9.95, 10.05, 9.85, 10.0 → 平均 9.9625；全距 10.05-9.85=0.2
    assert stats['avgs'] == [9.9625]
    assert abs(stats['ranges'][0] - 0.2) < 1e-9


def test_plain_keys_unchanged(db_session, setup_data):
    """未分段資料行為與現行完全相同"""
    payload = _base_payload({'1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}}})
    ShippingService.save_data(payload)

    row = ShippingMeasurement.query.one()
    assert (row.item, row.position) == ('外徑', '')

    record = ShippingData.query.first()
    res = ShippingService._map_row_to_dict(record)
    assert list(res['measurements']['1'].keys()) == ['外徑']


def test_set_measurement_exclusion_and_stats_skip(db_session, setup_data):
    """標示量測值為離群後,應排除於SPC統計計算,但保留於資料庫供追溯(§6.6)"""
    payload = _base_payload({'1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}}})
    payload['組數'] = 1
    ShippingService.save_data(payload)

    m = ShippingMeasurement.query.filter_by(item='外徑').one()
    m_id = m.id

    ShippingService.set_measurement_exclusion(m_id, excluded=True, reason="校正量測誤植")
    m_after = ShippingMeasurement.query.get(m_id)
    assert m_after.excluded is True
    assert m_after.exclusion_reason == "校正量測誤植"

    # 解除排除
    ShippingService.set_measurement_exclusion(m_id, excluded=False, reason=None)
    m_restored = ShippingMeasurement.query.get(m_id)
    assert m_restored.excluded is False
    assert m_restored.exclusion_reason is None


def test_excluding_measurement_requires_reason(db_session, setup_data):
    """標示離群值時必須填寫原因(§6.6),否則拒絕"""
    payload = _base_payload({'1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}}})
    ShippingService.save_data(payload)
    m = ShippingMeasurement.query.filter_by(item='外徑').one()

    import pytest
    with pytest.raises(ValueError):
        ShippingService.set_measurement_exclusion(m.id, excluded=True, reason="")
