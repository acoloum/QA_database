"""日期範圍 value object 與解析，供 Dashboard 等查詢共用。"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping

from sqlalchemy import func


def month_bucket(column: Any) -> Any:
    """依資料庫方言產生 YYYY-MM 聚合欄位：SQLite 用 strftime、PostgreSQL 用 to_char。"""
    from ..extensions import db

    bind = db.session.get_bind()
    dialect = bind.dialect.name if bind else ''
    if dialect == 'sqlite':
        return func.strftime('%Y-%m', column)
    return func.to_char(column, 'YYYY-MM')


@dataclass(frozen=True)
class DateWindow:
    """半開日期視窗：DateTime 欄位含結束日整天，Date 欄位閉區間含結束日。"""

    start_date: date
    end_date: date

    @classmethod
    def spanning(cls, *windows: "DateWindow") -> "DateWindow":
        """回傳涵蓋所有輸入視窗的最小外框視窗。

        用於把「當期 / 前期」兩段條件收斂成單一 WHERE 範圍，讓聚合查詢能走日期索引
        而非全表掃描；各期實際歸屬仍由 SELECT 內的 CASE 判斷，結果不變。
        """
        if not windows:
            raise ValueError("spanning() 至少需要一個 DateWindow")
        return cls(
            start_date=min(w.start_date for w in windows),
            end_date=max(w.end_date for w in windows),
        )

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start_date, time.min)

    @property
    def end_exclusive(self) -> datetime:
        return datetime.combine(self.end_date + timedelta(days=1), time.min)

    def datetime_filters(self, column: Any) -> tuple[Any, Any]:
        """DateTime 欄位用半開區間，確保結束日整天都計入。"""
        return column >= self.start_at, column < self.end_exclusive

    def date_filters(self, column: Any) -> tuple[Any, Any]:
        """Date 欄位用閉區間，包含結束日。"""
        return column >= self.start_date, column <= self.end_date


def parse_date_window(args: Mapping[str, Any], max_days: int = 366) -> DateWindow:
    """解析並驗證 start/end 日期範圍參數；格式、順序或跨度錯誤時拋出 ValueError。"""
    start_value = args.get('start')
    end_value = args.get('end')
    if not start_value or not end_value:
        raise ValueError("start 與 end 日期參數皆為必填")
    try:
        start = date.fromisoformat(str(start_value))
    except ValueError:
        raise ValueError("start 日期格式錯誤，需為 YYYY-MM-DD")
    try:
        end = date.fromisoformat(str(end_value))
    except ValueError:
        raise ValueError("end 日期格式錯誤，需為 YYYY-MM-DD")
    if start > end:
        raise ValueError("start 日期不得晚於 end 日期")
    if (end - start).days + 1 > max_days:
        raise ValueError(f"日期範圍不得超過 {max_days} 天")
    return DateWindow(start_date=start, end_date=end)
