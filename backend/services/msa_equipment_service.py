"""MSA 正式研究使用的設備資格閘門與可追溯快照。"""

from datetime import date

from ..extensions import db
from ..models import (
    EquipmentCalibrationRecord,
    EquipmentCorrectionPoint,
    MeasurementEquipment,
)
from .msa_contracts import EquipmentEligibility, EquipmentSnapshot
from .msa_errors import MsaNotFound, MsaValidationError


class MsaEquipmentService:
    """依固定優先序判定設備是否可用於正式 MSA 研究。"""

    @staticmethod
    def assert_officially_usable(
        equipment_id: int,
        *,
        on_date: date,
        measurement_mode: str | None = None,
    ) -> EquipmentEligibility:
        """驗證正式資格，未通過時以穩定錯誤碼中止。"""
        equipment = MsaEquipmentService._get_equipment(equipment_id)

        if equipment.status == "pending_review":
            MsaEquipmentService._raise_validation(
                "MSA_EQUIPMENT_PENDING_REVIEW", "設備尚在待審核狀態"
            )
        if equipment.status in {"maintenance", "inactive", "scrapped"}:
            MsaEquipmentService._raise_validation(
                "MSA_EQUIPMENT_STATUS_BLOCKED",
                "設備目前狀態不可用於正式 MSA 研究",
                status=equipment.status,
            )
        if equipment.calibration_type == "exempt":
            reason = (equipment.calibration_exemption_reason or "").strip()
            if not reason:
                MsaEquipmentService._raise_validation(
                    "MSA_EQUIPMENT_EXEMPTION_REASON_MISSING",
                    "校驗豁免設備必須保存完整豁免理由",
                )
            return EquipmentEligibility(
                equipment_id=equipment.id,
                eligible=True,
                checked_on=on_date,
                calibration_record_id=None,
                limitation=reason,
            )

        record = MsaEquipmentService._latest_approved_calibration(equipment.id)
        if record is None:
            MsaEquipmentService._raise_validation(
                "MSA_EQUIPMENT_CALIBRATION_MISSING", "找不到核准的設備校驗紀錄"
            )
        if record.result in {"fail", "pending"}:
            MsaEquipmentService._raise_validation(
                "MSA_EQUIPMENT_CALIBRATION_FAILED",
                "最近核准校驗結果不是通過",
                calibration_record_id=record.id,
                result=record.result,
            )
        if record.next_due_date is None:
            MsaEquipmentService._raise_validation(
                "MSA_EQUIPMENT_CALIBRATION_MISSING",
                "核准校驗紀錄缺少下次校驗日",
                calibration_record_id=record.id,
            )
        if record.next_due_date < on_date:
            MsaEquipmentService._raise_validation(
                "MSA_EQUIPMENT_CALIBRATION_EXPIRED",
                "設備校驗已於研究日前到期",
                calibration_record_id=record.id,
                next_due_date=record.next_due_date.isoformat(),
            )
        if record.result == "limited_use":
            modes = MsaEquipmentService._normalise_applicable_modes(
                record.applicable_modes
            )
            normalised_measurement_mode = (
                measurement_mode.strip()
                if isinstance(measurement_mode, str)
                else ""
            )
            if (
                not modes
                or not normalised_measurement_mode
                or normalised_measurement_mode not in modes
            ):
                MsaEquipmentService._raise_validation(
                    "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED",
                    "受限校驗不適用於指定量測模式",
                    calibration_record_id=record.id,
                    applicable_modes=list(modes),
                    measurement_mode=normalised_measurement_mode or None,
                )
            limitation = record.restriction_conditions
        else:
            limitation = None

        return EquipmentEligibility(
            equipment_id=equipment.id,
            eligible=True,
            checked_on=on_date,
            calibration_record_id=record.id,
            limitation=limitation,
        )

    @staticmethod
    def build_snapshot(
        equipment_id: int,
        *,
        on_date: date,
        measurement_mode: str | None = None,
    ) -> EquipmentSnapshot:
        """驗證資格後，建立可供研究凍結保存的設備證據快照。"""
        eligibility = MsaEquipmentService.assert_officially_usable(
            equipment_id,
            on_date=on_date,
            measurement_mode=measurement_mode,
        )
        equipment = MsaEquipmentService._get_equipment(equipment_id)
        record = (
            MsaEquipmentService._latest_approved_calibration(equipment.id)
            if eligibility.calibration_record_id is not None
            else None
        )
        return EquipmentSnapshot(
            equipment_id=equipment.id,
            equipment_no=equipment.equipment_no,
            name=equipment.name,
            status=equipment.status,
            resolution=equipment.resolution,
            unit=equipment.unit,
            calibration=MsaEquipmentService._calibration_snapshot(
                equipment, record
            ),
        )

    @staticmethod
    def _get_equipment(equipment_id: int) -> MeasurementEquipment:
        equipment = db.session.get(MeasurementEquipment, equipment_id)
        if equipment is None:
            raise MsaNotFound(
                "MSA_EQUIPMENT_NOT_FOUND", "找不到指定的量測設備",
                details={"equipment_id": equipment_id},
            )
        return equipment

    @staticmethod
    def _latest_approved_calibration(
        equipment_id: int,
    ) -> EquipmentCalibrationRecord | None:
        return (
            EquipmentCalibrationRecord.query
            .filter_by(equipment_id=equipment_id, status="approved")
            .order_by(
                EquipmentCalibrationRecord.calibration_date.desc(),
                EquipmentCalibrationRecord.id.desc(),
            )
            .first()
        )

    @staticmethod
    def _normalise_applicable_modes(value) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        modes = []
        for mode in value:
            if not isinstance(mode, str) or not mode.strip():
                return ()
            modes.append(mode.strip())
        return tuple(modes)

    @staticmethod
    def _calibration_snapshot(
        equipment: MeasurementEquipment,
        record: EquipmentCalibrationRecord | None,
    ) -> dict:
        if record is None:
            return {
                "record_id": None,
                "calibration_type": equipment.calibration_type,
                "calibration_date": None,
                "effective_date": None,
                "next_due_date": None,
                "result": None,
                "status": None,
                "certificate_no": None,
                "traceability_standard": None,
                "uncertainty_statement": None,
                "applicable_modes": [],
                "restriction_conditions": None,
                "exemption_reason": equipment.calibration_exemption_reason.strip(),
                "correction_points": [],
            }

        correction_points = (
            EquipmentCorrectionPoint.query
            .filter_by(calibration_record_id=record.id)
            .order_by(EquipmentCorrectionPoint.id.asc())
            .all()
        )
        return {
            "record_id": record.id,
            "calibration_type": record.calibration_type,
            "calibration_date": record.calibration_date,
            "effective_date": record.effective_date,
            "next_due_date": record.next_due_date,
            "result": record.result,
            "status": record.status,
            "certificate_no": record.certificate_no,
            "traceability_standard": record.traceability_standard,
            "uncertainty_statement": record.uncertainty_statement,
            "applicable_modes": list(
                MsaEquipmentService._normalise_applicable_modes(
                    record.applicable_modes
                )
            ),
            "restriction_conditions": record.restriction_conditions,
            "exemption_reason": None,
            "correction_points": [
                {
                    "id": point.id,
                    "measurement_mode": point.measurement_mode,
                    "nominal_value": point.nominal_value,
                    "indicated_value": point.indicated_value,
                    "error_value": point.error_value,
                    "correction_value": point.correction_value,
                    "unit": point.unit,
                    "range_start": point.range_start,
                    "range_end": point.range_end,
                }
                for point in correction_points
            ],
        }

    @staticmethod
    def _raise_validation(code: str, message: str, **details) -> None:
        raise MsaValidationError(code, message, details=details)
