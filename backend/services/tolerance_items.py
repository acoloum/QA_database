# -*- coding: utf-8 -*-
"""量測項目與廠商公差項目名稱的對應。

量測明細以固定的項目名存放（硬度／韋伯氏硬度），但廠商公差主檔的硬度項目
存在多種寫法：未指明標度的「硬度」與明確標度的「洛氏硬度」並存。公差比對
是以項目名稱相等來配對，兩邊寫法不同就會整項配對失敗而**靜默不判定**，
因此需要一份共用的別名對應，避免各處各自硬編碼而漏掉某一種寫法。

注意標度不可混用：
  洛氏硬度 Rockwell HRB（約 50~90）— 與未指明標度的「硬度」視為同一項
  韋伯氏硬度 Webster HW（約 3~20）— 另一種標度，不與洛氏互為別名
  維氏硬度 Vickers HV — 第三種標度，同樣不得混用
"""

# 量測項目 → 廠商公差主檔可能使用的項目名稱（依優先序）
MEASUREMENT_TOLERANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "硬度": ("洛氏硬度", "硬度"),
    "韋伯氏硬度": ("韋伯氏硬度",),
}


def tolerance_names_for(measurement_item: str) -> tuple[str, ...]:
    """回傳某量測項目可接受的公差項目名稱；無別名者即其本身。"""
    return MEASUREMENT_TOLERANCE_ALIASES.get(measurement_item, (measurement_item,))


def measurement_items_for(tolerance_item: str) -> tuple[str, ...]:
    """反查某公差項目名稱應套用到哪些量測項目；無別名者即其本身。

    用於以公差項目名為鍵建立界限表時，一併掛上對應的量測項目名，
    使後續以量測項目名查表不會落空。
    """
    matched = tuple(
        measurement
        for measurement, names in MEASUREMENT_TOLERANCE_ALIASES.items()
        if tolerance_item in names
    )
    return matched or (tolerance_item,)
