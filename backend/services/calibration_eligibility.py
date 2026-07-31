"""校正資格查詢服務：內校標準器驗證與設備目前校正狀態。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import or_, select

from ..extensions import db
from ..models import (
    EquipmentCalibrationRecord,
    MeasurementEquipment,
)
from .calibration_errors import (
    CalibrationNotFound,
    CalibrationValidationError,
)


@dataclass(frozen=True)
class ReferenceEligibility:
    """內校參考標準器資格檢查結果。"""

    equipment_id: int
    equipment_no: str
    name: str
    calibration_date: date
    next_due_date: date
    result: str
    data_level: str
    data_hash: Optional[str]
    calibration_record_id: int


@dataclass(frozen=True)
class EquipmentQualification:
    """設備目前校正資格（供 MSA、排程、前端顯示）。"""

    equipment_id: int
    equipment_no: str
    name: str
    calibration_type: str
    calibration_date: Optional[date]
    next_due_date: Optional[date]
    result: str
    data_level: str
    applicable_modes: list[str]
    restriction_conditions: Optional[str]
    calibration_record_id: Optional[int]
    data_hash: Optional[str]
    is_qualified: bool
    blockers: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        """提供既有 MSA 呼叫端的相容資格別名。"""
        return self.is_qualified

    @property
    def limitation(self) -> Optional[str]:
        """提供既有 MSA 呼叫端的受限校正說明欄位。"""
        return (
            self.restriction_conditions
            if self.result == "limited_use"
            else None
        )


class CalibrationEligibilityService:
    """集中處理參考標準器可用性與設備校正資格判定。"""

    @staticmethod
    def assert_reference_standard_usable(
        equipment_id: int,
        *,
        on_date: date,
    ) -> ReferenceEligibility:
        """
        驗證設備是否可作為內校參考標準器。

        條件（全部必須滿足）：
        1. is_reference_standard = True
        2. status = 'active'
        3. 最新核准校正結果為 'pass' 或 'limited_use'
        4. next_due_date 存在且 >= on_date
        """
        equipment = db.session.execute(
            select(MeasurementEquipment)
            .where(MeasurementEquipment.id == equipment_id)
        ).scalar_one_or_none()

        if equipment is None:
            raise CalibrationNotFound(
                "CALIBRATION_REFERENCE_NOT_FOUND",
                "找不到參考標準器設備",
                details={"equipment_id": equipment_id},
            )

        if not equipment.is_reference_standard:
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "設備未標記為參考標準器",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "reason": "not_marked_reference_standard",
                },
            )

        if equipment.status != "active":
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "參考標準器狀態非啟用",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "status": equipment.status,
                    "reason": "status_not_active",
                },
            )

        latest_approved = CalibrationEligibilityService._latest_approved_calibration(
            equipment_id,
            on_date=on_date,
        )

        if latest_approved is None:
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "參考標準器無核准校正紀錄",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "reason": "no_approved_calibration",
                },
            )

        if latest_approved.result not in {"pass", "limited_use"}:
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "參考標準器最新校正結果不合格",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "calibration_record_id": latest_approved.id,
                    "result": latest_approved.result,
                    "reason": "result_not_pass",
                },
            )

        if latest_approved.result == "limited_use" and (
            not latest_approved.applicable_modes
            or not latest_approved.restriction_conditions
        ):
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "參考標準器限制使用資訊不完整",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "calibration_record_id": latest_approved.id,
                    "reason": "limited_use_incomplete",
                },
            )

        if latest_approved.next_due_date is None:
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "參考標準器缺少下次校驗日",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "calibration_record_id": latest_approved.id,
                    "reason": "missing_next_due_date",
                },
            )

        if latest_approved.next_due_date < on_date:
            raise CalibrationValidationError(
                "CALIBRATION_REFERENCE_INVALID",
                "參考標準器校正已逾期",
                details={
                    "equipment_id": equipment_id,
                    "equipment_no": equipment.equipment_no,
                    "calibration_record_id": latest_approved.id,
                    "next_due_date": latest_approved.next_due_date.isoformat(),
                    "on_date": on_date.isoformat(),
                    "reason": "overdue",
                },
            )

        return ReferenceEligibility(
            equipment_id=equipment.id,
            equipment_no=equipment.equipment_no,
            name=equipment.name,
            calibration_date=latest_approved.calibration_date,
            next_due_date=latest_approved.next_due_date,
            result=latest_approved.result,
            data_level=latest_approved.data_level,
            data_hash=latest_approved.data_hash,
            calibration_record_id=latest_approved.id,
        )

    @staticmethod
    def equipment_qualification(
        equipment_id: int,
        *,
        on_date: date,
        measurement_mode: Optional[str] = None,
    ) -> EquipmentQualification:
        """
        查詢設備目前校正資格（供 MSA、前端顯示、排程檢查）。

        不拋出例外；回傳結構化資格物件含 is_qualified 與 blockers。
        """
        equipment = db.session.execute(
            select(MeasurementEquipment).where(
                MeasurementEquipment.id == equipment_id
            )
        ).scalar_one_or_none()

        if equipment is None:
            return EquipmentQualification(
                equipment_id=equipment_id,
                equipment_no="",
                name="",
                calibration_type="",
                calibration_date=None,
                next_due_date=None,
                result="",
                data_level="",
                applicable_modes=[],
                restriction_conditions=None,
                calibration_record_id=None,
                data_hash=None,
                is_qualified=False,
                blockers=("CALIBRATION_EQUIPMENT_NOT_FOUND",),
            )

        exemption_reason = (equipment.calibration_exemption_reason or "").strip()
        if equipment.calibration_type == "exempt":
            blockers = () if exemption_reason else (
                "CALIBRATION_EXEMPTION_REASON_MISSING",
            )
            return EquipmentQualification(
                equipment_id=equipment.id,
                equipment_no=equipment.equipment_no,
                name=equipment.name,
                calibration_type="exempt",
                calibration_date=None,
                next_due_date=None,
                result="exempt",
                data_level="summary_legacy",
                applicable_modes=[],
                restriction_conditions=exemption_reason or None,
                calibration_record_id=None,
                data_hash=None,
                is_qualified=not blockers and equipment.status == "active",
                blockers=(
                    blockers
                    if equipment.status == "active"
                    else (*blockers, "CALIBRATION_EQUIPMENT_INACTIVE")
                ),
            )

        latest_approved = CalibrationEligibilityService._latest_approved_calibration(
            equipment_id,
            on_date=on_date,
        )

        blockers: list[str] = []

        if equipment.status != "active":
            blockers.append("CALIBRATION_EQUIPMENT_INACTIVE")

        if latest_approved is None:
            blockers.append("CALIBRATION_NO_APPROVED_RECORD")
            return EquipmentQualification(
                equipment_id=equipment.id,
                equipment_no=equipment.equipment_no,
                name=equipment.name,
                calibration_type=equipment.calibration_type or "",
                calibration_date=None,
                next_due_date=None,
                result="",
                data_level="",
                applicable_modes=[],
                restriction_conditions=None,
                calibration_record_id=None,
                data_hash=None,
                is_qualified=False,
                blockers=tuple(blockers),
            )

        if latest_approved.result not in {"pass", "limited_use"}:
            blockers.append("CALIBRATION_RESULT_NOT_QUALIFIED")

        if latest_approved.next_due_date is None:
            blockers.append("CALIBRATION_MISSING_DUE_DATE")
        elif latest_approved.next_due_date < on_date:
            blockers.append("CALIBRATION_OVERDUE")

        applicable_modes = latest_approved.applicable_modes or []
        restriction_conditions = latest_approved.restriction_conditions

        if latest_approved.result == "limited_use":
            if not isinstance(measurement_mode, str) or not measurement_mode or (
                measurement_mode not in applicable_modes
            ):
                blockers.append("CALIBRATION_MODE_NOT_COVERED")
            if not applicable_modes or not (
                restriction_conditions and restriction_conditions.strip()
            ):
                blockers.append("CALIBRATION_LIMITED_USE_INCOMPLETE")

        return EquipmentQualification(
            equipment_id=equipment.id,
            equipment_no=equipment.equipment_no,
            name=equipment.name,
            calibration_type=equipment.calibration_type or "",
            calibration_date=latest_approved.calibration_date,
            next_due_date=latest_approved.next_due_date,
            result=latest_approved.result,
            data_level=latest_approved.data_level,
            applicable_modes=applicable_modes,
            restriction_conditions=restriction_conditions,
            calibration_record_id=latest_approved.id,
            data_hash=latest_approved.data_hash,
            is_qualified=len(blockers) == 0,
            blockers=tuple(blockers),
        )

    @staticmethod
    def _latest_approved_calibration(
        equipment_id: int,
        *,
        on_date: Optional[date] = None,
    ) -> Optional[EquipmentCalibrationRecord]:
        """取得設備最新核准校正紀錄（含 detailed 與 legacy）。"""
        statement = select(EquipmentCalibrationRecord).where(
            EquipmentCalibrationRecord.equipment_id == equipment_id,
            EquipmentCalibrationRecord.status == "approved",
        )
        if on_date is not None:
            statement = statement.where(
                EquipmentCalibrationRecord.calibration_date <= on_date,
                or_(
                    EquipmentCalibrationRecord.effective_date.is_(None),
                    EquipmentCalibrationRecord.effective_date <= on_date,
                ),
            )
        return db.session.execute(
            statement.order_by(
                EquipmentCalibrationRecord.calibration_date.desc(),
                EquipmentCalibrationRecord.id.desc(),
            ).limit(1)
        ).scalar_one_or_none()
