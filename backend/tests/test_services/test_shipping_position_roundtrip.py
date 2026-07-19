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
    m_after = db_session.get(ShippingMeasurement, m_id)
    assert m_after.excluded is True
    assert m_after.exclusion_reason == "校正量測誤植"

    # 解除排除
    ShippingService.set_measurement_exclusion(
        m_id, excluded=False, reason="重測確認原量測有效"
    )
    m_restored = db_session.get(ShippingMeasurement, m_id)
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


def test_measurement_exclusion_affects_get_stats(db_session, setup_data):
    """排除量測值後,SPC統計(get_stats)應反映排除,不再計入平均值計算(§6.6)"""
    payload = _base_payload({
        '1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}},  # 中點 10.0
        '2': {'外徑': {'value_min': 9.9, 'value_max': 10.1}},  # 中點 10.0
        '3': {'外徑': {'value_min': 9.0, 'value_max': 9.0}},   # 中點 9.0（離群）
    })
    payload['組數'] = 3
    ShippingService.save_data(payload)

    stats_before = ShippingService.get_stats({'field': '外徑'})
    assert stats_before['excluded_count'] == 0
    assert 9.0 in stats_before['all_values']
    assert abs(stats_before['avgs'][0] - (10.0 + 10.0 + 9.0) / 3) < 1e-9

    m3 = ShippingMeasurement.query.filter_by(item='外徑', group_num=3).one()
    ShippingService.set_measurement_exclusion(m3.id, excluded=True, reason="量測異常，設備校正誤差")

    stats_after = ShippingService.get_stats({'field': '外徑'})
    assert stats_after['excluded_count'] == 1
    assert 9.0 not in stats_after['all_values']
    assert abs(stats_after['avgs'][0] - 10.0) < 1e-9


def test_get_measurements_returns_all_details(db_session, setup_data):
    """取得單筆出貨記錄的量測明細列表,含排除狀態,供離群值管理UI使用"""
    payload = _base_payload({
        '1': {
            '外徑': {'value_min': 9.8, 'value_max': 10.2},
            '硬度': {'value_single': 55},
        },
    })
    ShippingService.save_data(payload)

    record = ShippingData.query.first()
    results = ShippingService.get_measurements(record.id)

    assert len(results) == 2
    items_by_name = {r['量測項目']: r for r in results}
    assert set(items_by_name.keys()) == {'外徑', '硬度'}

    od = items_by_name['外徑']
    assert od['量測最小值'] == 9.8
    assert od['量測最大值'] == 10.2
    assert od['排除統計'] is False
    assert od['排除原因'] is None

    hardness = items_by_name['硬度']
    assert hardness['量測值'] == 55
    assert hardness['排除統計'] is False
