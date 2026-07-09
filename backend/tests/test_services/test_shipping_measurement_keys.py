from backend.services.shipping_measurement_keys import (
    SEGMENT_POSITIONS,
    build_measurement_key,
    parse_measurement_key,
)


def test_segment_positions_order():
    assert SEGMENT_POSITIONS == ('前段', '中段', '後段')


def test_parse_plain_key_returns_empty_position():
    assert parse_measurement_key('外徑') == ('外徑', '')


def test_parse_segmented_key():
    assert parse_measurement_key('外徑@前段') == ('外徑', '前段')
    assert parse_measurement_key('外徑@中段') == ('外徑', '中段')
    assert parse_measurement_key('外徑@後段') == ('外徑', '後段')


def test_parse_invalid_position_returns_none():
    # 位置不合法時回傳 (項目, None),供呼叫端略過
    assert parse_measurement_key('外徑@亂段') == ('外徑', None)
    assert parse_measurement_key('外徑@') == ('外徑', None)


def test_build_key_roundtrip():
    assert build_measurement_key('外徑', '') == '外徑'
    assert build_measurement_key('外徑', None) == '外徑'
    assert build_measurement_key('外徑', '前段') == '外徑@前段'
    assert build_measurement_key('外徑', ' 前段 ') == '外徑@前段'
