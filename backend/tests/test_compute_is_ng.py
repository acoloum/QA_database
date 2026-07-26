# -*- coding: utf-8 -*-
"""ShippingData.compute_is_ng 判定測試，聚焦「尺寸 0 視為未量測」缺陷修正。"""

from backend.models import ShippingData, ShippingMeasurement


def _make(spec, measurements, group_count=5):
    s = ShippingData(spec=spec, group_count=group_count)
    for m in measurements:
        s.measurements.append(ShippingMeasurement(**m))
    return s


# 規格 33*26.5*2.0*244 → 外徑33 內徑26.5 厚度2.0；各項 ±0.1
TOL = [
    {'項目': '外徑', '公差下限': -0.1, '公差上限': 0.1, '標準值': None, '尺寸下限': None, '尺寸上限': None},
    {'項目': '內徑', '公差下限': -0.1, '公差上限': 0.1, '標準值': None, '尺寸下限': None, '尺寸上限': None},
    {'項目': '厚度', '公差下限': -0.1, '公差上限': 0.1, '標準值': None, '尺寸下限': None, '尺寸上限': None},
]


def test_尺寸為0視為未量測_不判超差():
    # 內徑 min/max 為 0（空白存成 0），厚度在公差內 → 不應超差
    s = _make('33*26.5*2.0*244', [
        {'group_num': 1, 'item': '內徑', 'value_min': 0, 'value_max': 0},
        {'group_num': 1, 'item': '厚度', 'value_min': 2.0, 'value_max': 2.05},
    ])
    assert s.compute_is_ng(TOL) is False


def test_尺寸真實出界仍判超差():
    # 厚度 2.30 > 上限 2.1 → 超差
    s = _make('33*26.5*2.0*244', [
        {'group_num': 1, 'item': '厚度', 'value_min': 2.0, 'value_max': 2.30},
    ])
    assert s.compute_is_ng(TOL) is True


def test_硬度為0視為未量測_不判超差():
    # 硬度未量測存成 0，視窗 8~12；0 不應被判超差（0 為未量測哨兵值）
    tol = [{'項目': '硬度', '公差下限': None, '公差上限': None,
            '標準值': None, '尺寸下限': 8, '尺寸上限': 12}]
    s = _make('32*4.1*900', [
        {'group_num': 1, 'item': '硬度', 'value_single': 0},
    ])
    assert s.compute_is_ng(tol) is False
    # 但硬度 13 > 12 仍應超差
    s2 = _make('32*4.1*900', [
        {'group_num': 1, 'item': '硬度', 'value_single': 13},
    ])
    assert s2.compute_is_ng(tol) is True


def test_非尺寸項目的0不跳過():
    # 真圓度 0 是理想值，不屬「未量測跳過」；給一個下限>0 的視窗以證明 0 仍被評估
    tol = [{'項目': '真圓度', '公差下限': None, '公差上限': None,
            '標準值': None, '尺寸下限': 0.5, '尺寸上限': 2.0}]
    s = _make('33*26.5*2.0*244', [
        {'group_num': 1, 'item': '真圓度', 'value_single': 0},
    ])
    # 0 < 尺寸下限 0.5 → 超差（未被當成未量測跳過）
    assert s.compute_is_ng(tol) is True


def test_公差寫洛氏硬度時硬度量測仍須判定():
    """公差項目寫「洛氏硬度」而量測明細以「硬度」存放，兩邊名稱不同仍須配對。

    原本以公差項目名為鍵、卻以量測項目名查表，導致安泰（公差已正名為
    洛氏硬度）的硬度從未被判定而靜默放行。
    """
    tol = [{'項目': '洛氏硬度', '公差下限': None, '公差上限': None,
            '標準值': None, '尺寸下限': 58, '尺寸上限': None}]
    # 51.9 < 下限 58 → 必須判超差
    ng = _make('80*70*2955', [
        {'group_num': 1, 'item': '硬度', 'value_single': 51.9},
    ])
    assert ng.compute_is_ng(tol) is True
    # 60 ≥ 58 → 合格
    ok = _make('80*70*2955', [
        {'group_num': 1, 'item': '硬度', 'value_single': 60},
    ])
    assert ok.compute_is_ng(tol) is False


def test_公差寫未指明標度的硬度時仍須判定():
    """正名前的舊寫法「硬度」不得因加入別名而失效。"""
    tol = [{'項目': '硬度', '公差下限': None, '公差上限': None,
            '標準值': None, '尺寸下限': 58, '尺寸上限': None}]
    s = _make('80*70*2955', [
        {'group_num': 1, 'item': '硬度', 'value_single': 51.9},
    ])
    assert s.compute_is_ng(tol) is True


def test_韋伯氏硬度不得被當成洛氏硬度的別名():
    """韋伯(HW 約3~20)與洛氏(HRB 約50~90)標度不同，混用會製造假合格。

    韋伯下限 15 不得套用到「硬度」量測值 51.9 上（51.9 > 15 會誤判合格）。
    """
    tol = [{'項目': '韋伯氏硬度', '公差下限': None, '公差上限': None,
            '標準值': None, '尺寸下限': 15, '尺寸上限': None}]
    s = _make('80*70*2955', [
        {'group_num': 1, 'item': '硬度', 'value_single': 51.9},
    ])
    # 沒有可用的洛氏/硬度公差 → 該項不判定，不得因韋伯公差而判為合格或超差
    assert s.compute_is_ng(tol) is False
