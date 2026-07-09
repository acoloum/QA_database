"""出貨檢驗量測複合鍵處理 — 「項目@位置」字串與 (項目, 位置) 之間互轉。

未分段資料的鍵即項目名(位置為空字串);分段資料鍵為「項目@位置」,
位置僅允許 前段/中段/後段(與巡檢子檔用語一致)。
"""

SEGMENT_POSITIONS = ('前段', '中段', '後段')


def parse_measurement_key(key):
    """拆解複合鍵,回傳 (項目, 位置)。

    無 @ 的鍵位置為空字串;位置不合法時回傳 (項目, None) 供呼叫端略過。
    """
    item, sep, position = str(key).partition('@')
    if not sep:
        return item, ''
    position = position.strip()
    if position in SEGMENT_POSITIONS:
        return item, position
    return item, None


def build_measurement_key(item, position):
    """由項目與位置組回複合鍵;位置為空(或 None)時只回項目名。"""
    position = (position or '').strip()
    return f"{item}@{position}" if position else item
