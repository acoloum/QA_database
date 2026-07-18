"""SPC 共用輸入與計算結果契約。"""

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any, Mapping, Optional, Sequence, Union


Timestamp = Optional[Union[date, datetime, str]]


@dataclass(frozen=True)
class SpcSubgroup:
    """一個合理子組及其來源追溯資料。"""

    key: str
    timestamp: Timestamp
    values: Sequence[float]
    record_ids: Sequence[int] = ()
    measurement_ids: Sequence[int] = ()

    def __post_init__(self) -> None:
        numeric_values = tuple(float(value) for value in self.values)
        if not numeric_values:
            raise ValueError("子組不可為空")
        if not all(isfinite(value) for value in numeric_values):
            raise ValueError("子組包含無效數值")
        object.__setattr__(self, "values", numeric_values)
        object.__setattr__(self, "record_ids", tuple(int(value) for value in self.record_ids))
        object.__setattr__(self, "measurement_ids", tuple(int(value) for value in self.measurement_ids))

    @property
    def n(self) -> int:
        return len(self.values)


@dataclass(frozen=True)
class SpcReason:
    """機器可讀原因碼及繁體中文說明。"""

    code: str
    message: str
    details: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class SpcStudyInput:
    """來源轉接器交給共用研究引擎的完整輸入。"""

    source: str
    filters: Mapping[str, Any]
    process_stream_key: str
    characteristic: str
    subgroups: Sequence[SpcSubgroup]
    specification: Mapping[str, Any]
    data_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source or not self.characteristic or not self.process_stream_key:
            raise ValueError("SPC 研究來源、特性與製程流鍵不可為空")
        object.__setattr__(self, "filters", dict(self.filters))
        object.__setattr__(self, "subgroups", tuple(self.subgroups))
        object.__setattr__(self, "specification", dict(self.specification))


@dataclass(frozen=True)
class SpcChartSeries:
    """管制圖的一組統計量與逐點界限。"""

    statistic: str
    values: tuple[Optional[float], ...]
    cl: tuple[float, ...]
    ucl: tuple[float, ...]
    lcl: tuple[float, ...]


@dataclass(frozen=True)
class SpcChartSet:
    """一組位置圖與變異圖。"""

    chart_type: str
    location: SpcChartSeries
    variation: SpcChartSeries
    subgroup_sizes: tuple[int, ...]
    sigma_within: float
