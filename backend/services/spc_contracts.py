"""SPC 共用輸入與計算結果契約。"""

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any, Literal, Mapping, Optional, Protocol, Sequence, Union


Timestamp = Optional[Union[date, datetime, str]]
AnalysisFamily = Literal["variable", "attribute", "machine"]


@dataclass(frozen=True)
class SpcSubgroup:
    """一個合理子組及其來源追溯資料。"""

    key: str
    timestamp: Timestamp
    values: Sequence[float]
    record_ids: Sequence[int] = ()
    measurement_ids: Sequence[int] = ()
    exclusion_snapshot: Sequence[Mapping[str, Any]] = ()
    distribution_values: Sequence[float] = ()

    def __post_init__(self) -> None:
        numeric_values = tuple(float(value) for value in self.values)
        if not numeric_values:
            raise ValueError("子組不可為空")
        if not all(isfinite(value) for value in numeric_values):
            raise ValueError("子組包含無效數值")
        object.__setattr__(self, "values", numeric_values)
        object.__setattr__(self, "record_ids", tuple(int(value) for value in self.record_ids))
        object.__setattr__(self, "measurement_ids", tuple(int(value) for value in self.measurement_ids))
        object.__setattr__(
            self, "exclusion_snapshot",
            tuple(dict(value) for value in self.exclusion_snapshot),
        )
        numeric_distribution = tuple(float(value) for value in self.distribution_values)
        if not all(isfinite(value) for value in numeric_distribution):
            raise ValueError("分布分析值包含無效數值")
        object.__setattr__(self, "distribution_values", numeric_distribution)

    @property
    def n(self) -> int:
        return len(self.values)


class AttributeSubgroupContract(Protocol):
    """屬性型子組的結構契約，避免共用契約循環匯入計算引擎。"""

    key: str
    timestamp: Timestamp
    inspected: int
    nonconforming: int
    record_ids: Sequence[int]


SpcInputSubgroup = Union[SpcSubgroup, AttributeSubgroupContract]


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
    subgroups: Sequence[SpcInputSubgroup]
    specification: Mapping[str, Any]
    analysis_family: AnalysisFamily = "variable"
    options: Optional[Mapping[str, Any]] = None
    data_hash: Optional[str] = None
    reasons: Sequence[SpcReason] = ()
    metadata: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.source or not self.characteristic or not self.process_stream_key:
            raise ValueError("SPC 研究來源、特性與製程流鍵不可為空")
        object.__setattr__(self, "filters", dict(self.filters))
        object.__setattr__(self, "subgroups", tuple(self.subgroups))
        object.__setattr__(self, "specification", dict(self.specification))
        object.__setattr__(self, "options", dict(self.options or {}))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


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
    variation_source_pairs: tuple[Optional[Mapping[str, Any]], ...] = ()
