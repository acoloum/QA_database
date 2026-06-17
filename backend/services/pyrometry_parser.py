"""溫度記錄器時間序列解析

支援兩種格式（自動偵測，且不依賴欄名）：
  A. 單時間欄：第一欄為時間，其後每欄為一通道溫度
  B. 雙時間欄：第一欄日期、第二欄時刻，其後為通道溫度
時間標籤一律輸出為分鐘級（單日 HH:MM；跨日 MM/DD HH:MM），
方便在前端以分鐘為單位選取恆溫穩定期。並自動略過文字副標題列。
"""
from typing import Dict, Any, BinaryIO, List
import datetime
import pandas as pd

_TIME_KEYWORDS = ('時間', 'time', '日期', 'date', '時刻')


def _name_is_time(name) -> bool:
    s = str(name).lower()
    return any(k in s for k in _TIME_KEYWORDS)


def _is_numeric_series(s: pd.Series) -> bool:
    """該欄是否為數值欄（通道資料）。日期/時刻欄會回傳 False。"""
    num = pd.to_numeric(s, errors="coerce")
    return num.notna().sum() > 0


def _norm_colon_ms(s: str) -> str:
    """將 HH:MM:SS:fff（毫秒以冒號分隔）正規化為 HH:MM:SS.fff，供 to_datetime 解析。
    日期部分不含冒號，故整串以冒號切成 4 段即代表含毫秒。"""
    parts = s.split(':')
    if len(parts) == 4:
        return ':'.join(parts[:3]) + '.' + parts[3]
    return s


def _to_timestamp(item):
    """將單一時間值（或 (日期,時刻) tuple）轉為 pandas Timestamp；無法轉換則丟出。"""
    if isinstance(item, tuple):
        d, t = item
        if isinstance(d, (int, float, bool)) or isinstance(t, (int, float, bool)):
            raise ValueError("數值非時間")
        return pd.to_datetime(_norm_colon_ms(f"{d} {t}"))
    v = item
    if isinstance(v, bool) or isinstance(v, (int, float)):
        # 純數值（如 0,1,2 索引）不視為時間，保留原樣
        raise ValueError("數值非時間")
    if isinstance(v, datetime.datetime):
        return pd.Timestamp(v)
    if isinstance(v, datetime.time):
        return pd.Timestamp.combine(datetime.date(2000, 1, 1), v)
    return pd.to_datetime(_norm_colon_ms(str(v)))


def _build_time_labels(time_raw: List) -> List[str]:
    """輸出分鐘級時間標籤；若任一值無法解析為時間則整體後備為原字串。"""
    try:
        ts = [_to_timestamp(x) for x in time_raw]
    except Exception:
        return [
            f"{x[0]} {x[1]}" if isinstance(x, tuple) else str(x)
            for x in time_raw
        ]
    multi_day = len({t.date() for t in ts}) > 1
    fmt = "%m/%d %H:%M" if multi_day else "%H:%M"
    return [t.strftime(fmt) for t in ts]


def parse_temperature_file(file_obj: BinaryIO, filename: str) -> Dict[str, Any]:
    """解析溫度記錄器 CSV/Excel。

    回傳:
      {
        "時間": [str, ...],                                   # 分鐘級
        "通道": [{"名稱", "最高溫", "最低溫"}, ...],
        "數值": {通道名稱: [float | None, ...]},
      }
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        raw = pd.read_csv(file_obj, header=0)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        raw = pd.read_excel(file_obj, header=0)
    else:
        raise ValueError("僅支援 .csv / .xlsx / .xls 檔")

    if raw.shape[1] < 2:
        raise ValueError("檔案需至少包含時間欄與一個熱電偶欄")

    cols = list(raw.columns)

    # 第二欄是否也是時間欄（日期+時刻雙欄）：欄名含關鍵字、或內容非數值
    second_is_time = raw.shape[1] >= 3 and (
        _name_is_time(cols[1]) or not _is_numeric_series(raw.iloc[:, 1])
    )

    if second_is_time:
        time_raw = list(zip(raw.iloc[:, 0], raw.iloc[:, 1]))
        channel_cols = cols[2:]
        channel_df = raw.iloc[:, 2:].copy()
    else:
        time_raw = list(raw.iloc[:, 0])
        channel_cols = cols[1:]
        channel_df = raw.iloc[:, 1:].copy()

    # 略過副標題列：該列所有通道欄均為非數值（文字或空）
    numeric_mask = channel_df.apply(pd.to_numeric, errors="coerce").notna().any(axis=1)
    time_raw = [t for t, keep in zip(time_raw, numeric_mask) if keep]
    channel_df = channel_df[numeric_mask].reset_index(drop=True)

    time_strs = _build_time_labels(time_raw)

    channels, values = [], {}
    for col in channel_cols:
        numeric = pd.to_numeric(channel_df[col], errors="coerce")
        non_null = numeric.dropna()
        if non_null.empty:
            continue
        col_name = str(col)
        values[col_name] = [None if pd.isna(v) else float(v) for v in numeric]
        channels.append({
            "名稱": col_name,
            "最高溫": float(non_null.max()),
            "最低溫": float(non_null.min()),
        })

    if not channels:
        raise ValueError("未找到有效的溫度通道數值")

    return {"時間": time_strs, "通道": channels, "數值": values}
