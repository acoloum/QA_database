"""溫度記錄器時間序列解析 — 第一欄為時間，其後每欄為一支熱電偶溫度"""
from typing import Dict, Any, BinaryIO
import pandas as pd


def parse_temperature_file(file_obj: BinaryIO, filename: str) -> Dict[str, Any]:
    """解析固定格式的 CSV/Excel：第一欄為時間，其後每欄為一通道溫度。

    回傳:
      {
        "時間": [str, ...],
        "通道": [{"名稱": str, "最高溫": float, "最低溫": float}, ...],
        "數值": {通道名稱: [float, ...]},
      }
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("僅支援 .csv / .xlsx / .xls 檔")

    if df.shape[1] < 2:
        raise ValueError("檔案需至少包含『時間』欄與一個熱電偶欄")

    time_col = df.columns[0]
    channel_cols = list(df.columns[1:])
    times = [str(v) for v in df[time_col].tolist()]

    channels, values = [], {}
    for col in channel_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        non_null = numeric.dropna()
        if non_null.empty:
            continue
        col_name = str(col)
        raw_vals = [float(v) for v in df[col].tolist()]
        values[col_name] = raw_vals
        channels.append({
            "名稱": col_name,
            "最高溫": float(non_null.max()),
            "最低溫": float(non_null.min()),
        })
    return {"時間": times, "通道": channels, "數值": values}
