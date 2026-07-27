"""MSA 服務間傳遞的不可變資格與設備快照契約。"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class EquipmentEligibility:
    """指定研究日期與量測模式下的設備資格結果。"""

    equipment_id: int
    eligible: bool
    checked_on: date
    calibration_record_id: int | None
    blocking_codes: tuple[str, ...] = field(default_factory=tuple)
    limitation: str | None = None


@dataclass(frozen=True)
class EquipmentSnapshot:
    """正式研究保存的設備身分、校驗及補正證據。"""

    equipment_id: int
    equipment_no: str
    name: str
    status: str
    resolution: str | None
    unit: str | None
    calibration: dict


@dataclass(frozen=True)
class MsaMethodContext:
    """交給統計引擎的受控參數；引擎不得自行查資料庫或取用目前時間。"""

    method_code: str
    method_version: str
    alpha: float
    study_variation_multiplier: float
    tolerance: float | None
    process_sigma: float | None
    criteria: dict


@dataclass(frozen=True)
class MsaAnalysisOutput:
    """統計引擎的統一輸出；判定與門檻比較由呼叫端負責。"""

    applicability: dict
    statistics: dict
    chart_data: dict
    warnings: tuple[dict, ...] = field(default_factory=tuple)
