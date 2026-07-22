"""parse_spec_nominals 規格解析測試（三段式與四段式）"""

from backend.utils import parse_spec_nominals


def test_三段式_第二值為厚度():
    # 外徑*厚度*長度：2.2 < 31.9/2 → 視為厚度，內徑幾何回推
    assert parse_spec_nominals('31.9*2.2*589') == {
        '外徑': 31.9,
        '厚度': 2.2,
        '內徑': 31.9 - 2.2 * 2,
        '長度': 589.0,
    }


def test_三段式_第二值為內徑():
    # 外徑*內徑*長度：57.9 >= 62.5/2 → 視為內徑，厚度幾何回推
    result = parse_spec_nominals('62.5*57.9*450')
    assert result['外徑'] == 62.5
    assert result['內徑'] == 57.9
    assert result['厚度'] == (62.5 - 57.9) / 2
    assert result['長度'] == 450.0


def test_四段式_直接取用明列內徑與厚度():
    # 外徑*內徑*厚度*長度：厚度取明列的 2.0，而非幾何回推的 (33-26.5)/2=3.25
    assert parse_spec_nominals('33*26.5*2.0*244') == {
        '外徑': 33.0,
        '內徑': 26.5,
        '厚度': 2.0,
        '長度': 244.0,
    }
    assert parse_spec_nominals('22*20*1.8*4000') == {
        '外徑': 22.0,
        '內徑': 20.0,
        '厚度': 1.8,
        '長度': 4000.0,
    }


def test_四段式_相容各種分隔符與多餘分隔():
    assert parse_spec_nominals('33x26.5x2.0x244')['厚度'] == 2.0
    assert parse_spec_nominals('33*26.5**2.0*244')['厚度'] == 2.0


def test_空值與單值():
    assert parse_spec_nominals('') == {}
    assert parse_spec_nominals(None) == {}
    assert parse_spec_nominals('50') == {'外徑': 50.0}
