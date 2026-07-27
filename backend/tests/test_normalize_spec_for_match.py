"""normalize_spec_for_match 規格正規化測試（公差比對用）。

早期公差建檔把 4.0 記成 4，出貨規格卻寫 4.0（或反之）；逐段字串比對會把
兩者視為不同規格而查不到任何公差，該筆所有項目都靜默不判定。
"""

import pytest

from backend.utils import normalize_spec_for_match as normalize


@pytest.mark.parametrize(("raw", "expected"), [
    # 尾隨 0 的小數與整數寫法須正規化為同一結果
    ("98*4.0*680", "98*4*680"),
    ("98*4*680", "98*4*680"),
    ("71*3.0*450", "71*3*450"),
    ("42*2.0*320", "42*2*320"),
    # 多餘精度一併收斂
    ("35*2.50*430", "35*2.5*430"),
    ("35*2.5*430", "35*2.5*430"),
    # 前導小數點補 0
    (".5*2*10", "0.5*2*10"),
    # 分隔符號統一
    ("80X70", "80*70"),
    ("80x70", "80*70"),
    ("54.5×46.2", "54.5*46.2"),
    ("33**26.5", "33*26.5"),
    # 空白去除
    ("33 * 26.5 * 244", "33*26.5*244"),
    # 空值與佔位字串
    ("", ""),
    (None, ""),
    ("None", ""),
    ("NULL", ""),
])
def test_正規化結果(raw, expected):
    assert normalize(raw) == expected


def test_四vs四點零正規化後相同():
    assert normalize("98*4.0*680") == normalize("98*4*680")
    assert normalize("59*3.0*520") == normalize("59*3*520")


def test_非數值段維持原樣僅大寫化():
    # Ø44 之類的非純數值段不得被誤改
    assert normalize("Ø44") == "Ø44"
    assert normalize("abc*4.0") == "ABC*4"


def test_不同數值不得被視為相同():
    assert normalize("98*4.1*680") != normalize("98*4*680")
    assert normalize("98*40*680") != normalize("98*4*680")
