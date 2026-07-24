"""機械性質 Excel 匯入解析工具測試。"""

import pytest

from backend.services.mechanical_import import normalize_product_size


@pytest.mark.parametrize(("raw", "expected"), [
    ("80X70", "80*70"),
    ("66.7X59", "66.7*59"),
    ("44.5x36.7", "44.5*36.7"),
    ("90X80.2", "90*80.2"),
    ("36x25.2", "36*25.2"),
    ("54.5×46.2", "54.5*46.2"),
    # 已是 * 或無分隔者維持原樣
    ("82.5*70.15", "82.5*70.15"),
    ("65.5", "65.5"),
    ("", ""),
])
def test_normalize_product_size_unifies_separator(raw, expected):
    assert normalize_product_size(raw) == expected
