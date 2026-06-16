"""溫度記錄器時間序列解析

支援兩種格式：
  A. 單時間欄：第一欄為時間，其後每欄為一通道溫度（測試儀器格式）
  B. 雙時間欄：第一欄日期、第二欄時間，其後為通道溫度（爐體記錄格式）
兩種格式自動偵測，並略過副標題文字列。
"""
from typing import Dict, Any, BinaryIO
import pandas as pd


def _is_time_col(col_name: str) -> bool:
    s = str(col_name).lower()
    return any(k in s for k in ('時間', 'time', '日期', 'date'))


def parse_temperature_file(file_obj: BinaryIO, filename: str) -> Dict[str, Any]:
    """解析溫度記錄器 CSV/Excel。

    回傳:
      {
        "時間": [str, ...],
        "通道": [{"名稱": str, "最高溫": float, "最低溫": float}, ...],
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

    # 偵測雙時間欄格式（日期欄 + 時間欄）
    dual_time = (
        raw.shape[1] >= 3
        and _is_time_col(cols[0])
        and _is_time_col(cols[1])
    )

    if dual_time:
        time_strs = [
            f"{str(d)} {str(t)}" if pd.notna(d) and pd.notna(t) else ""
            for d, t in zip(raw.iloc[:, 0], raw.iloc[:, 1])
        ]
        channel_cols = cols[2:]
        channel_df = raw.iloc[:, 2:].copy()
    else:
        time_strs = [str(v) for v in raw.iloc[:, 0]]
        channel_cols = cols[1:]
        channel_df = raw.iloc[:, 1:].copy()

    # 略過副標題列：該列所有通道欄均為非數值（文字或空）
    numeric_mask = channel_df.apply(pd.to_numeric, errors="coerce").notna().any(axis=1)
    time_strs_filtered = [t for t, keep in zip(time_strs, numeric_mask) if keep]
    channel_df_filtered = channel_df[numeric_mask].reset_index(drop=True)

    channels, values = [], {}
    for col in channel_cols:
        numeric = pd.to_numeric(channel_df_filtered[col], errors="coerce")
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

    return {"時間": time_strs_filtered, "通道": channels, "數值": values}
