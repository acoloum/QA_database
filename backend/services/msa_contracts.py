"""MSA 服務間傳遞的不可變資格與設備快照契約。"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


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
    resolution: Decimal | None
    unit: str | None
    calibration: dict
