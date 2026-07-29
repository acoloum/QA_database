"""MSA 設備相容入口：委派校正資格，保留既有錯誤契約與快照。"""

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import EquipmentCalibrationPoint, EquipmentCalibrationRecord

from .calibration_eligibility import (
    CalibrationEligibilityService,
    EquipmentQualification,
)
from .calibration_errors import CalibrationServiceError
from .measurement_equipment_service import MeasurementEquipmentService
from .msa_contracts import EquipmentSnapshot
from .msa_errors import MsaNotFound, MsaValidationError


def map_calibration_error_to_msa(error: CalibrationServiceError) -> MsaValidationError:
    """將校正服務例外轉換為既有 MSA 程式錯誤契約。"""
    mapping = {
        "CALIBRATION_EQUIPMENT_NOT_FOUND": (
            MsaNotFound,
            "MSA_EQUIPMENT_NOT_FOUND",
            "找不到指定的量測設備",
        ),
    }
    error_type, code, message = mapping.get(
        error.code,
        (MsaValidationError, "MSA_EQUIPMENT_CALIBRATION_MISSING", error.message),
    )
    return error_type(code, message, details=error.details)


class MsaEquipmentService(MeasurementEquipmentService):
    """保留 MSA 既有匯出，正式資格一律委派校正資格服務。"""

    @staticmethod
    def assert_officially_usable(
        equipment_id: int,
        *,
        on_date: date,
        measurement_mode: str | None = None,
    ) -> EquipmentQualification:
        """驗證 MSA 正式資格並映射為既有 MSA 穩定錯誤碼。"""
        try:
            qualification = CalibrationEligibilityService.equipment_qualification(
                equipment_id,
                on_date=on_date,
                measurement_mode=measurement_mode,
            )
        except CalibrationServiceError as error:
            raise map_calibration_error_to_msa(error) from error

        if qualification.is_qualified:
            return qualification

        equipment = MeasurementEquipmentService._get_equipment(equipment_id)
        blockers = set(qualification.blockers)
        details = {
            "calibration_record_id": qualification.calibration_record_id,
        }
        if "CALIBRATION_EQUIPMENT_NOT_FOUND" in blockers:
            raise MsaNotFound(
                "MSA_EQUIPMENT_NOT_FOUND",
                "找不到指定的量測設備",
                details={"equipment_id": equipment_id},
            )
        if equipment.status == "pending_review":
            raise MsaValidationError(
                "MSA_EQUIPMENT_PENDING_REVIEW",
                "設備尚在待審核狀態",
                details={},
            )
        if equipment.status in {"maintenance", "inactive", "scrapped"}:
            raise MsaValidationError(
                "MSA_EQUIPMENT_STATUS_BLOCKED",
                "設備目前狀態不可用於正式 MSA 研究",
                details={"status": equipment.status},
            )
        if "CALIBRATION_EXEMPTION_REASON_MISSING" in blockers:
            raise MsaValidationError(
                "MSA_EQUIPMENT_EXEMPTION_REASON_MISSING",
                "校驗豁免設備必須保存完整豁免理由",
                details={},
            )
        if "CALIBRATION_NO_APPROVED_RECORD" in blockers:
            raise MsaValidationError(
                "MSA_EQUIPMENT_CALIBRATION_MISSING",
                "找不到核准的設備校驗紀錄",
                details={},
            )
        if "CALIBRATION_RESULT_NOT_QUALIFIED" in blockers:
            details["result"] = qualification.result
            raise MsaValidationError(
                "MSA_EQUIPMENT_CALIBRATION_FAILED",
                "最近核准校驗結果不是通過",
                details=details,
            )
        if "CALIBRATION_MISSING_DUE_DATE" in blockers:
            raise MsaValidationError(
                "MSA_EQUIPMENT_CALIBRATION_MISSING",
                "核准校驗紀錄缺少下次校驗日",
                details=details,
            )
        if "CALIBRATION_OVERDUE" in blockers:
            details["next_due_date"] = qualification.next_due_date.isoformat()
            raise MsaValidationError(
                "MSA_EQUIPMENT_CALIBRATION_EXPIRED",
                "設備校驗已於研究日前到期",
                details=details,
            )
        if "CALIBRATION_LIMITED_USE_INCOMPLETE" in blockers:
            details.update({
                "applicable_modes": qualification.applicable_modes,
                "restriction_conditions": qualification.restriction_conditions,
            })
            raise MsaValidationError(
                "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED",
                "受限校驗限制資訊不完整",
                details=details,
            )
        if "CALIBRATION_MODE_NOT_COVERED" in blockers:
            details["applicable_modes"] = qualification.applicable_modes
            details["measurement_mode"] = measurement_mode
            raise MsaValidationError(
                "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED",
                "受限校驗不適用於指定量測模式",
                details=details,
            )
        raise MsaValidationError(
            "MSA_EQUIPMENT_CALIBRATION_MISSING",
            "設備校正資格不完整",
            details=details,
        )

    @staticmethod
    def build_snapshot(
        equipment_id: int,
        *,
        on_date: date,
        measurement_mode: str | None = None,
    ) -> EquipmentSnapshot:
        """建立 MSA 凍結快照，不將舊摘要偽裝為詳細原始證據。"""
        qualification = MsaEquipmentService.assert_officially_usable(
            equipment_id,
            on_date=on_date,
            measurement_mode=measurement_mode,
        )
        equipment = MeasurementEquipmentService._get_equipment(equipment_id)
        record = None
        if qualification.calibration_record_id is not None:
            record = MsaEquipmentService._approved_calibration_by_id(
                equipment.id,
                qualification.calibration_record_id,
                on_date,
            )
            if record is None:
                raise MsaValidationError(
                    "MSA_EQUIPMENT_CALIBRATION_MISSING",
                    "資格判定後校驗證據已不可用，拒絕建立快照",
                    details={
                        "calibration_record_id": qualification.calibration_record_id,
                    },
                )
        calibration = MsaEquipmentService._calibration_snapshot(
            equipment,
            record,
        )
        calibration.update({
            "data_level": qualification.data_level,
            "data_hash": qualification.data_hash,
        })
        if qualification.data_level == "summary_legacy":
            calibration["correction_points"] = []
        return EquipmentSnapshot(
            equipment_id=equipment.id,
            equipment_no=equipment.equipment_no,
            name=equipment.name,
            status=equipment.status,
            resolution=MeasurementEquipmentService._canonical_value(
                equipment.resolution,
            ),
            unit=equipment.unit,
            calibration=calibration,
        )

    @staticmethod
    def _approved_calibration_by_id(
        equipment_id: int,
        calibration_record_id: int,
        on_date: date,
    ) -> EquipmentCalibrationRecord | None:
        """只取得研究日期當日有效的已核准校正紀錄。"""
        return db.session.execute(
            db.select(EquipmentCalibrationRecord).options(
                selectinload(EquipmentCalibrationRecord.calibration_points)
                .selectinload(EquipmentCalibrationPoint.readings),
            ).where(
                EquipmentCalibrationRecord.id == calibration_record_id,
                EquipmentCalibrationRecord.equipment_id == equipment_id,
                EquipmentCalibrationRecord.status == "approved",
                EquipmentCalibrationRecord.calibration_date <= on_date,
                or_(
                    EquipmentCalibrationRecord.effective_date.is_(None),
                    EquipmentCalibrationRecord.effective_date <= on_date,
                ),
            )
        ).scalar_one_or_none()

    @staticmethod
    def _calibration_snapshot(equipment, record) -> dict:
        """封裝 MSA 快照；唯有 detailed 紀錄可附帶逐點校正證據。"""
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
                "exemption_reason": (
                    equipment.calibration_exemption_reason or ""
                ).strip(),
                "correction_points": [],
            }

        points = (
            [MsaEquipmentService._detailed_point_to_snapshot(point)
             for point in sorted(
                 record.calibration_points,
                 key=lambda item: item.point_order,
             )]
            if record.data_level == "detailed"
            else []
        )
        return {
            "record_id": record.id,
            "calibration_type": record.calibration_type,
            "calibration_date": MeasurementEquipmentService._canonical_value(
                record.calibration_date,
            ),
            "effective_date": MeasurementEquipmentService._canonical_value(
                record.effective_date,
            ),
            "next_due_date": MeasurementEquipmentService._canonical_value(
                record.next_due_date,
            ),
            "result": record.result,
            "status": record.status,
            "certificate_no": record.certificate_no,
            "traceability_standard": record.traceability_standard,
            "uncertainty_statement": record.uncertainty_statement,
            "applicable_modes": list(record.applicable_modes or []),
            "restriction_conditions": record.restriction_conditions,
            "exemption_reason": None,
            "correction_points": points,
        }

    @staticmethod
    def _detailed_point_to_snapshot(point: EquipmentCalibrationPoint) -> dict:
        """序列化已保存的詳細點位摘要與原始讀值，不重新計算。"""
        canonical = MeasurementEquipmentService._canonical_value
        return {
            "id": point.id,
            "point_order": point.point_order,
            "point_code": point.point_code,
            "measurement_mode": point.measurement_mode,
            "nominal_value": canonical(point.nominal_value),
            "unit": point.unit,
            "reference_value": canonical(point.reference_value),
            "evaluation_basis": point.evaluation_basis,
            "repeatability_rule": point.repeatability_rule,
            "required_repetitions": point.required_repetitions,
            "completed_reading_count": point.completed_reading_count,
            "average_value": canonical(point.average_value),
            "error_value": canonical(point.error_value),
            "mean_error": canonical(point.mean_error),
            "mean_correction": canonical(point.mean_correction),
            "result": point.result,
            "summary": {
                "minimum_error": canonical(point.minimum_error),
                "maximum_error": canonical(point.maximum_error),
                "error_range": canonical(point.error_range),
                "sample_stddev": canonical(point.sample_stddev),
                "repeatability_value": canonical(point.repeatability_value),
                "expanded_uncertainty": canonical(point.expanded_uncertainty),
                "coverage_factor": canonical(point.coverage_factor),
                "remarks": point.remarks,
            },
            "readings": [
                {
                    "id": reading.id,
                    "trial_no": reading.trial_no,
                    "standard_reading": canonical(reading.standard_reading),
                    "indicated_value": canonical(reading.indicated_value),
                    "effective_reference": canonical(reading.effective_reference),
                    "error_value": canonical(reading.error_value),
                    "correction_value": canonical(reading.correction_value),
                    "result": reading.result,
                }
                for reading in sorted(
                    point.readings,
                    key=lambda item: item.trial_no,
                )
            ],
        }
