"""校正草稿、模板實例化、讀值保存、送審核准工作流。"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Any, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    Attachment,
    CalibrationReferenceSnapshot,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    EquipmentCalibrationPoint,
    EquipmentCalibrationReading,
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    utc_now,
)
from ..utils import log_audit
from .calibration_calculation import (
    CALIBRATION_NUMERIC_FAILURE,
    CALCULATION_VERSION,
    CalibrationPointRule,
    CalibrationReadingInput,
    calculate_calibration,
    calculate_point,
)
from .calibration_eligibility import CalibrationEligibilityService
from .calibration_errors import (
    CalibrationConflict,
    CalibrationForbidden,
    CalibrationNotFound,
    CalibrationServiceError,
    CalibrationValidationError,
)
from .calibration_template_service import CalibrationTemplateService


_MAX_INTEGER = 2_147_483_647
_MAX_POINTS = 500
_MAX_READINGS_PER_POINT = 100
_MAX_SIGNIFICANT_DIGITS = 50
_MAX_DECIMAL_EXPONENT = 1_000
_LIST_FIELDS = {
    "page",
    "page_size",
    "sort",
    "order",
    "equipment_id",
    "status",
    "calibration_type",
    "data_level",
}
_CALIBRATION_STATUSES = {
    "draft",
    "in_progress",
    "ready_for_submission",
    "submitted",
    "rejected",
    "approved",
    "superseded",
    "voided",
}


def _rollback_on_error(function):
    """服務交易失敗時統一回滾，避免鎖定或半成品留在 scoped session。"""

    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            db.session.rollback()
            raise

    return wrapped


class CalibrationService:
    """校正記錄完整生命週期服務。"""

    @staticmethod
    def list(params: dict, actor_id: int) -> dict:
        """分頁列出校正紀錄。"""
        values = params or {}
        unknown = set(values.keys()) - _LIST_FIELDS
        if unknown:
            raise CalibrationValidationError(
                "CALIBRATION_UNKNOWN_FIELDS",
                "查詢包含未允許欄位",
                details={"unknown_fields": sorted(unknown)},
            )
        page = CalibrationService._bounded_int(
            values.get("page", 1),
            field="page",
            minimum=1,
            maximum=10_000,
            code="CALIBRATION_PAGE_INVALID",
        )
        page_size = CalibrationService._bounded_int(
            values.get("page_size", 25),
            field="page_size",
            minimum=1,
            maximum=100,
            code="CALIBRATION_PAGE_SIZE_INVALID",
        )
        sort_name = values.get("sort", "calibration_date")
        order = values.get("order", "desc")

        sort_map = {
            "id": EquipmentCalibrationRecord.id,
            "equipment_no": MeasurementEquipment.equipment_no,
            "calibration_date": EquipmentCalibrationRecord.calibration_date,
            "status": EquipmentCalibrationRecord.status,
            "result": EquipmentCalibrationRecord.result,
            "risk": case(
                (EquipmentCalibrationRecord.status == "submitted", 0),
                (EquipmentCalibrationRecord.status == "rejected", 1),
                (EquipmentCalibrationRecord.result == "fail", 2),
                (EquipmentCalibrationRecord.result == "limited_use", 3),
                (EquipmentCalibrationRecord.status == "ready_for_submission", 4),
                (EquipmentCalibrationRecord.status == "in_progress", 5),
                (EquipmentCalibrationRecord.status == "draft", 6),
                else_=7,
            ),
        }
        if sort_name not in sort_map:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "sort 欄位不受支援",
                details={"field": "sort", "value": sort_name},
            )
        if order not in {"asc", "desc"}:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "order 必須是 asc 或 desc",
                details={"field": "order", "value": order},
            )
        sort_column = sort_map[sort_name]
        ordering = sort_column.asc() if order == "asc" else sort_column.desc()

        statement = (
            select(EquipmentCalibrationRecord)
            .join(MeasurementEquipment, EquipmentCalibrationRecord.equipment_id == MeasurementEquipment.id)
        )

        # 篩選條件
        if "equipment_id" in values:
            equipment_id = CalibrationService._bounded_int(
                values["equipment_id"],
                field="equipment_id",
                minimum=1,
                maximum=_MAX_INTEGER,
                code="CALIBRATION_FIELD_INVALID",
            )
            statement = statement.where(
                EquipmentCalibrationRecord.equipment_id == equipment_id
            )
        if "status" in values:
            if values["status"] not in _CALIBRATION_STATUSES:
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "status 不受支援",
                    details={"field": "status", "value": values["status"]},
                )
            statement = statement.where(
                EquipmentCalibrationRecord.status == values["status"]
            )
        if "calibration_type" in values:
            if values["calibration_type"] not in {"internal", "external"}:
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "calibration_type 不受支援",
                    details={
                        "field": "calibration_type",
                        "value": values["calibration_type"],
                    },
                )
            statement = statement.where(
                EquipmentCalibrationRecord.calibration_type == values["calibration_type"]
            )
        if "data_level" in values:
            if values["data_level"] not in {"detailed", "summary_legacy"}:
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "data_level 不受支援",
                    details={"field": "data_level", "value": values["data_level"]},
                )
            statement = statement.where(
                EquipmentCalibrationRecord.data_level == values["data_level"]
            )

        total = db.session.execute(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ).scalar_one()

        rows = db.session.execute(
            statement.options(
                selectinload(EquipmentCalibrationRecord.equipment),
                selectinload(EquipmentCalibrationRecord.predecessors),
            )
            .order_by(ordering, EquipmentCalibrationRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()

        return {
            "items": [CalibrationService._serialize_record(r, include_points=False) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def get(calibration_id: int) -> dict:
        """取得校正紀錄完整細節（含點位與讀值）。"""
        record = db.session.execute(
            select(EquipmentCalibrationRecord)
            .where(EquipmentCalibrationRecord.id == calibration_id)
            .options(
                selectinload(EquipmentCalibrationRecord.calibration_points).selectinload(
                    EquipmentCalibrationPoint.readings
                ),
                selectinload(EquipmentCalibrationRecord.reference_snapshots),
                selectinload(EquipmentCalibrationRecord.equipment),
                selectinload(EquipmentCalibrationRecord.template_version),
            )
        ).scalar_one_or_none()

        if record is None:
            raise CalibrationNotFound(
                "CALIBRATION_RECORD_NOT_FOUND",
                "找不到校正紀錄",
                details={"calibration_id": calibration_id},
            )

        return CalibrationService._serialize_record(record, include_points=True)

    @staticmethod
    @_rollback_on_error
    def create(payload: dict, actor_id: int) -> dict:
        """
        建立校正草稿。

        - 鎖定核准模板版本
        - 存入模板快照
        - 建立 EquipmentCalibrationPoint 與預設讀值列
        """
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(
            data,
            {
                "equipment_id",
                "template_version_id",
                "calibration_type",
                "calibration_date",
                "reference_standard_equipment_id",
                "calibration_provider",
                "certificate_no",
                "traceability_standard",
                "uncertainty_statement",
                "calibration_location",
                "environment_conditions",
            },
        )

        equipment_id = CalibrationService._required_int(
            data, "equipment_id", "CALIBRATION_FIELD_INVALID"
        )
        template_version_id = CalibrationService._required_int(
            data, "template_version_id", "CALIBRATION_FIELD_INVALID"
        )
        calibration_type = CalibrationService._required_text(
            data, "calibration_type", "CALIBRATION_FIELD_INVALID"
        )
        if calibration_type not in {"internal", "external"}:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "calibration_type 必須是 internal 或 external",
                details={"field": "calibration_type"},
            )

        calibration_date = CalibrationService._required_date(
            data, "calibration_date", "CALIBRATION_FIELD_INVALID"
        )
        reference_standard_equipment_id = data.get("reference_standard_equipment_id")
        if reference_standard_equipment_id is not None:
            reference_standard_equipment_id = CalibrationService._bounded_int(
                reference_standard_equipment_id,
                field="reference_standard_equipment_id",
                minimum=1,
                maximum=_MAX_INTEGER,
                code="CALIBRATION_FIELD_INVALID",
            )

        # 驗證設備
        equipment = db.session.execute(
            select(MeasurementEquipment).where(
                MeasurementEquipment.id == equipment_id
            )
        ).scalar_one_or_none()
        if equipment is None:
            raise CalibrationNotFound(
                "CALIBRATION_EQUIPMENT_NOT_FOUND",
                "找不到受校設備",
                details={"equipment_id": equipment_id},
            )
        if equipment.status != "active":
            raise CalibrationValidationError(
                "CALIBRATION_STATUS_CONFLICT",
                "受校設備狀態非啟用",
                details={"equipment_id": equipment_id, "status": equipment.status},
            )

        # 鎖定並驗證模板版本
        template_version = CalibrationService._lock_template_version(template_version_id)
        if template_version is None:
            raise CalibrationNotFound(
                "CALIBRATION_TEMPLATE_VERSION_NOT_FOUND",
                "找不到校正模板版本",
                details={"template_version_id": template_version_id},
            )
        if template_version.status != "approved":
            raise CalibrationValidationError(
                "CALIBRATION_STATUS_CONFLICT",
                "只有核准版本可用於建立詳細校正",
                details={
                    "template_version_id": template_version_id,
                    "status": template_version.status,
                },
            )
        if equipment.equipment_type != template_version.template.equipment_type:
            raise CalibrationValidationError(
                "CALIBRATION_STATUS_CONFLICT",
                "受校設備類型與模板適用類型不符",
                details={
                    "equipment_type": equipment.equipment_type,
                    "template_equipment_type": template_version.template.equipment_type,
                },
            )

        # 內校必須提供參考標準器
        if calibration_type == "internal":
            if reference_standard_equipment_id is None:
                raise CalibrationValidationError(
                    "CALIBRATION_REFERENCE_REQUIRED",
                    "內校必須指定參考標準器",
                    details={"field": "reference_standard_equipment_id"},
                )
            # 受校設備不能同時作為自己的標準器
            if reference_standard_equipment_id == equipment_id:
                raise CalibrationValidationError(
                    "CALIBRATION_REFERENCE_INVALID",
                    "受校設備不能同時作為自己的參考標準器",
                    details={
                        "equipment_id": equipment_id,
                        "reference_standard_equipment_id": reference_standard_equipment_id,
                    },
                )
            # 驗證參考標準器資格
            CalibrationEligibilityService.assert_reference_standard_usable(
                reference_standard_equipment_id, on_date=calibration_date
            )
        else:
            # 外校可先不填證書，保留 certificate_attachment_id=None
            pass

        # 驗證環境條件（只接受模板宣告的鍵）
        environment_conditions = CalibrationService._validate_environment_conditions(
            template_version, data.get("environment_conditions", {})
        )

        try:
            # 建立草稿紀錄
            record = EquipmentCalibrationRecord(
                equipment_id=equipment_id,
                calibration_type=calibration_type,
                calibration_date=calibration_date,
                reference_standard_equipment_id=reference_standard_equipment_id,
                calibration_provider=CalibrationService._optional_text(
                    data, "calibration_provider", max_length=160
                ),
                certificate_no=CalibrationService._optional_text(
                    data, "certificate_no", max_length=160
                ),
                traceability_standard=CalibrationService._optional_text(
                    data, "traceability_standard"
                ),
                uncertainty_statement=CalibrationService._optional_text(
                    data, "uncertainty_statement"
                ),
                calibration_location=CalibrationService._optional_text(
                    data, "calibration_location", max_length=200
                ),
                result="pending",
                status="draft",
                data_level="detailed",
                template_version_id=template_version_id,
                template_snapshot=CalibrationService._build_template_snapshot(template_version),
                environment_conditions=environment_conditions,
                calculation_summary={},
                calculation_version=CALCULATION_VERSION,
                data_hash=None,
                procedure_code=template_version.procedure_code,
                procedure_name=template_version.procedure_name,
                row_version=1,
                created_by=actor_id,
            )
            db.session.add(record)
            db.session.flush()

            # 實例化校正點與讀值
            for template_point in template_version.points:
                point = EquipmentCalibrationPoint(
                    calibration_record_id=record.id,
                    template_point_id=template_point.id,
                    point_order=template_point.point_order,
                    point_code=template_point.point_code,
                    measurement_mode=template_point.measurement_mode,
                    nominal_value=template_point.nominal_value,
                    unit=template_point.unit,
                    reference_value=template_point.nominal_value,
                    reference_input_mode=template_point.reference_input_mode,
                    required_repetitions=template_point.required_repetitions,
                    error_lower_limit=template_point.error_lower_limit,
                    error_upper_limit=template_point.error_upper_limit,
                    evaluation_basis=template_point.evaluation_basis,
                    repeatability_rule=template_point.repeatability_rule,
                    repeatability_limit=template_point.repeatability_limit,
                    qualification_scope_code=template_point.qualification_scope_code,
                    qualification_range_start=template_point.qualification_range_start,
                    qualification_range_end=template_point.qualification_range_end,
                    uncertainty_required=template_point.uncertainty_required,
                    required=template_point.required,
                    result="pending",
                )
                # 建立預設讀值列
                for trial_no in range(1, template_point.required_repetitions + 1):
                    point.readings.append(
                        EquipmentCalibrationReading(
                            trial_no=trial_no,
                            result="pending",
                        )
                    )
                db.session.add(point)

            db.session.flush()

            log_audit(
                actor_id,
                "create_calibration_draft",
                "equipment_calibration",
                record.id,
                new_val=CalibrationService._serialize_record(record, include_points=True),
            )

            db.session.commit()
            return CalibrationService._serialize_record(record, include_points=True)

        except CalibrationServiceError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    @_rollback_on_error
    def update(calibration_id: int, payload: dict, actor_id: int) -> dict:
        """更新草稿一般欄位（環境條件、外校資訊等）。不允許修改已送審/核准紀錄。"""
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(
            data,
            {
                "expected_version",
                "calibration_date",
                "reference_standard_equipment_id",
                "calibration_provider",
                "certificate_no",
                "traceability_standard",
                "uncertainty_statement",
                "calibration_location",
                "environment_conditions",
                "certificate_attachment_id",
            },
        )

        expected_version = CalibrationService._required_int(
            data, "expected_version", "CALIBRATION_FIELD_INVALID"
        )

        record = CalibrationService._lock_record(calibration_id)
        CalibrationService._require_version(record, expected_version)
        CalibrationService._require_editable_status(record)

        old_snapshot = CalibrationService._serialize_record(record, include_points=False)
        new_values: dict[str, Any] = {}
        new_calibration_date = record.calibration_date
        if "calibration_date" in data:
            new_calibration_date = CalibrationService._required_date(
                data, "calibration_date", "CALIBRATION_FIELD_INVALID"
            )
            new_values["calibration_date"] = new_calibration_date

        new_reference_id = record.reference_standard_equipment_id
        if "reference_standard_equipment_id" in data:
            new_reference_id = data["reference_standard_equipment_id"]
            if new_reference_id is not None:
                new_reference_id = CalibrationService._bounded_int(
                    new_reference_id,
                    field="reference_standard_equipment_id",
                    minimum=1,
                    maximum=_MAX_INTEGER,
                    code="CALIBRATION_FIELD_INVALID",
                )
            new_values["reference_standard_equipment_id"] = new_reference_id

        if record.calibration_type == "internal":
            if new_reference_id is None:
                raise CalibrationValidationError(
                    "CALIBRATION_REFERENCE_REQUIRED",
                    "內校必須指定參考標準器",
                    details={"field": "reference_standard_equipment_id"},
                )
            if new_reference_id == record.equipment_id:
                raise CalibrationValidationError(
                    "CALIBRATION_REFERENCE_INVALID",
                    "受校設備不能同時作為自己的參考標準器",
                    details={
                        "equipment_id": record.equipment_id,
                        "reference_standard_equipment_id": new_reference_id,
                    },
                )
            if (
                "calibration_date" in data
                or "reference_standard_equipment_id" in data
            ):
                CalibrationEligibilityService.assert_reference_standard_usable(
                    new_reference_id, on_date=new_calibration_date
                )

        text_fields = {
            "calibration_provider": 160,
            "certificate_no": 160,
            "traceability_standard": 2_000,
            "uncertainty_statement": 2_000,
            "calibration_location": 200,
        }
        for field, max_length in text_fields.items():
            if field in data:
                new_values[field] = CalibrationService._optional_text(
                    data, field, max_length=max_length
                )
        if "environment_conditions" in data:
            new_values["environment_conditions"] = (
                CalibrationService._validate_environment_conditions(
                    record.template_version, data["environment_conditions"]
                )
            )
        if "certificate_attachment_id" in data:
            attachment_id = data["certificate_attachment_id"]
            if attachment_id is not None:
                attachment_id = CalibrationService._bounded_int(
                    attachment_id,
                    field="certificate_attachment_id",
                    minimum=1,
                    maximum=_MAX_INTEGER,
                    code="CALIBRATION_FIELD_INVALID",
                )
                CalibrationService._assert_certificate_attachment(
                    record, attachment_id
                )
            new_values["certificate_attachment_id"] = attachment_id
        if not new_values:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "至少必須提供一個可更新欄位",
                details={"field": "payload"},
            )

        try:
            for field, value in new_values.items():
                setattr(record, field, value)
            if record.status == "ready_for_submission":
                record.status = "in_progress"
            if record.calculation_summary:
                canonical = CalibrationService._canonical_hash_payload(
                    record,
                    [
                        (point,)
                        for point in record.calibration_points
                    ],
                )
                record.data_hash = hashlib.sha256(
                    canonical.encode("utf-8")
                ).hexdigest()
            record.row_version += 1
            db.session.flush()

            log_audit(
                actor_id,
                "update_calibration",
                "equipment_calibration",
                record.id,
                old_val=old_snapshot,
                new_val=CalibrationService._serialize_record(
                    record, include_points=False
                ),
            )

            db.session.commit()
            return CalibrationService._serialize_record(record, include_points=True)
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    @_rollback_on_error
    def save_readings(
        calibration_id: int,
        payload: dict,
        actor_id: int,
    ) -> dict:
        """
        批次保存原始讀值並由後端重算正式證據。

        - 列鎖校正紀錄
        - 驗證 expected_version 及可編輯狀態
        - 記憶體正規化全部 points/readings
        - 呼叫純計算引擎
        - 全部成功後才更新 ORM rows、摘要、結果、計算版本、row version
        - 建立 SHA-256 資料雜湊
        """
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(
            data,
            {"expected_version", "points"},
        )

        expected_version = CalibrationService._required_int(
            data, "expected_version", "CALIBRATION_FIELD_INVALID"
        )
        points_payload = data.get("points")
        if not isinstance(points_payload, list) or len(points_payload) > _MAX_POINTS:
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                f"points 必須是最多 {_MAX_POINTS} 項的陣列",
                details={
                    "step": "readings",
                    "field": "points",
                    "maximum": _MAX_POINTS,
                },
            )

        record = CalibrationService._lock_record(calibration_id)
        try:
            CalibrationService._require_version(record, expected_version)
            CalibrationService._require_editable_status(record)

            existing_points = {point.id: point for point in record.calibration_points}
            expected_point_ids = set(existing_points)
            if len(points_payload) != len(expected_point_ids):
                raise CalibrationValidationError(
                    "CALIBRATION_POINT_INVALID",
                    "points 必須包含完整校正點矩陣",
                    details={
                        "step": "readings",
                        "field": "points",
                        "expected_count": len(expected_point_ids),
                        "actual_count": len(points_payload),
                    },
                )

            normalized_points = []
            seen_point_ids: set[int] = set()
            for point_data in points_payload:
                if not isinstance(point_data, dict):
                    raise CalibrationValidationError(
                        "CALIBRATION_POINT_INVALID",
                        "每個校正點必須是 JSON 物件",
                        details={"step": "readings", "field": "points"},
                    )
                unknown_point_fields = set(point_data) - {
                    "point_id",
                    "reference_value",
                    "expanded_uncertainty",
                    "coverage_factor",
                    "readings",
                }
                if unknown_point_fields:
                    raise CalibrationValidationError(
                        "CALIBRATION_UNKNOWN_FIELDS",
                        "校正點包含未允許欄位",
                        details={
                            "step": "readings",
                            "unknown_fields": sorted(unknown_point_fields),
                        },
                    )

                point_id = CalibrationService._required_int(
                    point_data, "point_id", "CALIBRATION_POINT_INVALID"
                )
                point = existing_points.get(point_id)
                if point is None:
                    raise CalibrationValidationError(
                        "CALIBRATION_POINT_INVALID",
                        "校正點不屬於此校正紀錄",
                        details={
                            "step": "readings",
                            "field": "point_id",
                            "point_id": point_id,
                        },
                    )
                if point_id in seen_point_ids:
                    raise CalibrationValidationError(
                        "CALIBRATION_POINT_INVALID",
                        "同一校正點不可重複",
                        details={
                            "step": "readings",
                            "field": "point_id",
                            "point_code": point.point_code,
                        },
                    )
                seen_point_ids.add(point_id)

                reference_value = (
                    CalibrationService._optional_decimal(
                        point_data, "reference_value"
                    )
                    if "reference_value" in point_data
                    else point.reference_value
                )
                expanded_uncertainty = (
                    CalibrationService._optional_decimal(
                        point_data, "expanded_uncertainty"
                    )
                    if "expanded_uncertainty" in point_data
                    else point.expanded_uncertainty
                )
                coverage_factor = (
                    CalibrationService._optional_decimal(
                        point_data, "coverage_factor"
                    )
                    if "coverage_factor" in point_data
                    else point.coverage_factor
                )
                readings_payload = point_data.get("readings")
                if (
                    not isinstance(readings_payload, list)
                    or len(readings_payload) > _MAX_READINGS_PER_POINT
                ):
                    raise CalibrationValidationError(
                        "CALIBRATION_READING_INVALID",
                        f"readings 必須是最多 {_MAX_READINGS_PER_POINT} 項的陣列",
                        details={
                            "step": "readings",
                            "field": "readings",
                            "point_code": point.point_code,
                            "maximum": _MAX_READINGS_PER_POINT,
                        },
                    )

                expected_trials = set(range(1, point.required_repetitions + 1))
                if len(readings_payload) != len(expected_trials):
                    raise CalibrationValidationError(
                        "CALIBRATION_READING_INVALID",
                        "readings 必須包含完整試次矩陣",
                        details={
                            "step": "readings",
                            "field": "readings",
                            "point_code": point.point_code,
                            "expected_count": len(expected_trials),
                            "actual_count": len(readings_payload),
                        },
                    )

                reading_inputs = []
                seen_trial_nos: set[int] = set()
                for reading_data in readings_payload:
                    if not isinstance(reading_data, dict):
                        raise CalibrationValidationError(
                            "CALIBRATION_READING_INVALID",
                            "每筆讀值必須是 JSON 物件",
                            details={
                                "step": "readings",
                                "field": "readings",
                                "point_code": point.point_code,
                            },
                        )
                    unknown_reading_fields = set(reading_data) - {
                        "trial_no",
                        "indicated_value",
                        "standard_reading",
                    }
                    if unknown_reading_fields:
                        raise CalibrationValidationError(
                            "CALIBRATION_UNKNOWN_FIELDS",
                            "讀值包含未允許欄位",
                            details={
                                "step": "readings",
                                "point_code": point.point_code,
                                "unknown_fields": sorted(unknown_reading_fields),
                            },
                        )
                    trial_no = CalibrationService._required_int(
                        reading_data, "trial_no", "CALIBRATION_READING_INVALID"
                    )
                    if trial_no in seen_trial_nos or trial_no not in expected_trials:
                        raise CalibrationValidationError(
                            "CALIBRATION_READING_INVALID",
                            "trial_no 重複或超出模板範圍",
                            details={
                                "step": "readings",
                                "field": "trial_no",
                                "point_code": point.point_code,
                                "trial_no": trial_no,
                            },
                        )
                    seen_trial_nos.add(trial_no)
                    indicated_value = CalibrationService._optional_decimal(
                        reading_data, "indicated_value"
                    )
                    standard_reading = CalibrationService._optional_decimal(
                        reading_data, "standard_reading"
                    )
                    if point.required and indicated_value is None:
                        raise CalibrationValidationError(
                            "CALIBRATION_READING_INVALID",
                            "必要校正點缺少受校件器示值",
                            details={
                                "step": "readings",
                                "field": "indicated_value",
                                "point_code": point.point_code,
                                "trial_no": trial_no,
                            },
                        )
                    if (
                        point.required
                        and point.reference_input_mode == "paired_reading"
                        and standard_reading is None
                    ):
                        raise CalibrationValidationError(
                            "CALIBRATION_READING_INVALID",
                            "成對讀值模式缺少標準器讀值",
                            details={
                                "step": "readings",
                                "field": "standard_reading",
                                "point_code": point.point_code,
                                "trial_no": trial_no,
                            },
                        )
                    reading_inputs.append(
                        CalibrationReadingInput(
                            trial_no=trial_no,
                            indicated_value=indicated_value,
                            standard_reading=standard_reading,
                        )
                    )

                reading_inputs.sort(key=lambda item: item.trial_no)
                rule = CalibrationPointRule(
                    point_code=point.point_code,
                    scope_code=point.qualification_scope_code or point.point_code,
                    reference_input_mode=point.reference_input_mode,
                    reference_value=(
                        reference_value
                        if point.reference_input_mode == "certified_value"
                        else None
                    ),
                    required_repetitions=point.required_repetitions,
                    error_lower_limit=point.error_lower_limit,
                    error_upper_limit=point.error_upper_limit,
                    evaluation_basis=point.evaluation_basis,
                    repeatability_rule=point.repeatability_rule,
                    repeatability_limit=point.repeatability_limit,
                    uncertainty_required=point.uncertainty_required,
                    expanded_uncertainty=expanded_uncertainty,
                    coverage_factor=coverage_factor,
                    required=point.required,
                )
                calculation = calculate_point(rule, reading_inputs)
                normalized_points.append(
                    (
                        point,
                        calculation,
                        reference_value,
                        expanded_uncertainty,
                        coverage_factor,
                    )
                )

            if seen_point_ids != expected_point_ids:
                raise CalibrationValidationError(
                    "CALIBRATION_POINT_INVALID",
                    "points 必須包含完整校正點矩陣",
                    details={"step": "readings", "field": "points"},
                )

            calibration_calc = calculate_calibration(
                [item[1] for item in normalized_points],
                allow_limited_use=record.template_version.allow_limited_use,
            )
            request_time = utc_now()
            for (
                point,
                calculation,
                reference_value,
                expanded_uncertainty,
                coverage_factor,
            ) in normalized_points:
                readings_by_trial = {
                    reading.trial_no: reading for reading in point.readings
                }
                for reading_calc in calculation.readings:
                    orm_reading = readings_by_trial.get(reading_calc.trial_no)
                    if orm_reading is None:
                        raise CalibrationValidationError(
                            "CALIBRATION_READING_INVALID",
                            "找不到模板預建讀值列",
                            details={
                                "step": "readings",
                                "field": "trial_no",
                                "point_code": point.point_code,
                                "trial_no": reading_calc.trial_no,
                            },
                        )
                    orm_reading.indicated_value = reading_calc.indicated_value
                    orm_reading.standard_reading = reading_calc.standard_reading
                    orm_reading.effective_reference = (
                        reading_calc.effective_reference
                    )
                    orm_reading.error_value = reading_calc.error
                    orm_reading.correction_value = reading_calc.correction
                    orm_reading.result = reading_calc.result
                    if orm_reading.entered_by is None:
                        orm_reading.entered_by = actor_id
                        orm_reading.entered_at = request_time
                    orm_reading.last_modified_by = actor_id
                    orm_reading.last_modified_at = request_time

                point.reference_value = reference_value
                point.expanded_uncertainty = expanded_uncertainty
                point.coverage_factor = coverage_factor
                point.mean_error = calculation.mean_error
                point.mean_correction = calculation.mean_correction
                point.minimum_error = calculation.minimum_error
                point.maximum_error = calculation.maximum_error
                point.error_range = calculation.error_range
                point.sample_stddev = calculation.sample_stddev
                point.completed_reading_count = len(calculation.errors)
                point.result = calculation.result
                point.remarks = None

            record.calculation_summary = (
                CalibrationService._build_calculation_summary(calibration_calc)
            )
            record.calculation_version = CALCULATION_VERSION
            record.result = calibration_calc.result
            if calibration_calc.result == "limited_use":
                passed_scopes = set(calibration_calc.passed_scope_codes)
                record.applicable_modes = sorted(
                    {
                        point.measurement_mode
                        for point, *_ in normalized_points
                        if (
                            point.qualification_scope_code
                            or point.point_code
                        )
                        in passed_scopes
                    }
                )
                record.restriction_conditions = (
                    "僅限合格資格範圍："
                    + "、".join(calibration_calc.passed_scope_codes)
                    + "；不合格資格範圍："
                    + "、".join(calibration_calc.failed_scope_codes)
                )
            else:
                record.applicable_modes = []
                record.restriction_conditions = None
            record.status = "in_progress"
            record.row_version += 1

            canonical = CalibrationService._canonical_hash_payload(
                record, normalized_points
            )
            record.data_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            db.session.flush()

            log_audit(
                actor_id,
                "save_readings",
                "equipment_calibration",
                record.id,
                new_val={
                    "result": record.result,
                    "calculation_summary": record.calculation_summary,
                    "data_hash": record.data_hash,
                    "row_version": record.row_version,
                },
            )
            db.session.commit()
            return CalibrationService._serialize_record(record, include_points=True)
        except CalibrationServiceError as error:
            db.session.rollback()
            error.details.setdefault("step", "readings")
            raise
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    @_rollback_on_error
    def validate(calibration_id: int, payload: dict, actor_id: int) -> dict:
        """驗證校正紀錄是否可送審，回傳 blockers。"""
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(data, set())
        record = CalibrationService._lock_record(calibration_id)
        try:
            if record.status not in {
                "draft",
                "in_progress",
                "ready_for_submission",
            }:
                raise CalibrationConflict(
                    "CALIBRATION_STATUS_CONFLICT",
                    "只有草稿、進行中或待送審狀態可驗證",
                    details={
                        "step": "validate",
                        "calibration_id": calibration_id,
                        "status": record.status,
                    },
                )

            requirements = (
                (record.template_snapshot or {}).get(
                    "environment_requirements", {}
                )
                or {}
            )
            conditions = record.environment_conditions or {}
            for key, rule in requirements.items():
                condition = conditions.get(key)
                if (
                    rule.get("required")
                    and (
                        not isinstance(condition, dict)
                        or condition.get("value") in (None, "")
                    )
                ):
                    raise CalibrationValidationError(
                        "CALIBRATION_DATA_INCOMPLETE",
                        f"必要環境條件 {key} 尚未登錄",
                        details={
                            "step": "environment",
                            "field": f"environment_conditions.{key}",
                            "requirement": key,
                        },
                    )

            point_calculations = []
            for point in record.calibration_points:
                readings = [
                    CalibrationReadingInput(
                        trial_no=reading.trial_no,
                        indicated_value=reading.indicated_value,
                        standard_reading=reading.standard_reading,
                    )
                    for reading in point.readings
                ]
                rule = CalibrationPointRule(
                    point_code=point.point_code,
                    scope_code=point.qualification_scope_code
                    or point.point_code,
                    reference_input_mode=point.reference_input_mode,
                    reference_value=(
                        point.reference_value
                        if point.reference_input_mode == "certified_value"
                        else None
                    ),
                    required_repetitions=point.required_repetitions,
                    error_lower_limit=point.error_lower_limit,
                    error_upper_limit=point.error_upper_limit,
                    evaluation_basis=point.evaluation_basis,
                    repeatability_rule=point.repeatability_rule,
                    repeatability_limit=point.repeatability_limit,
                    uncertainty_required=point.uncertainty_required,
                    expanded_uncertainty=point.expanded_uncertainty,
                    coverage_factor=point.coverage_factor,
                    required=point.required,
                )
                point_calculations.append(calculate_point(rule, readings))

            calibration_calc = calculate_calibration(
                point_calculations,
                allow_limited_use=record.template_version.allow_limited_use,
            )
            new_status = (
                "ready_for_submission"
                if calibration_calc.result in {"pass", "limited_use"}
                and not calibration_calc.blockers
                else "in_progress"
            )
            if record.status != new_status:
                old_status = record.status
                record.status = new_status
                record.row_version += 1
                log_audit(
                    actor_id,
                    "validate_calibration",
                    "equipment_calibration",
                    record.id,
                    old_val={"status": old_status},
                    new_val={
                        "status": new_status,
                        "row_version": record.row_version,
                    },
                )
            db.session.commit()

            return {
                "result": calibration_calc.result,
                "blockers": list(calibration_calc.blockers),
                "passed_scope_codes": list(
                    calibration_calc.passed_scope_codes
                ),
                "failed_scope_codes": list(
                    calibration_calc.failed_scope_codes
                ),
                "row_version": record.row_version,
            }
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    @_rollback_on_error
    def submit(calibration_id: int, payload: dict, actor_id: int) -> dict:
        """送審：驗證完整性、重新驗證標準器、保存快照、鎖定證據。"""
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(data, {"expected_version", "reason"})

        expected_version = CalibrationService._required_int(
            data, "expected_version", "CALIBRATION_FIELD_INVALID"
        )
        reason = CalibrationService._required_text(
            data, "reason", "CALIBRATION_FIELD_INVALID", max_length=2000
        )
        record = CalibrationService._lock_record(calibration_id)
        CalibrationService._require_version(record, expected_version)

        if record.status != "ready_for_submission":
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "校正紀錄必須先通過 validate 才可送審",
                details={"calibration_id": calibration_id, "status": record.status},
            )

        if (
            not record.calculation_summary
            or record.result not in {"pass", "limited_use"}
            or not record.data_hash
        ):
            raise CalibrationValidationError(
                "CALIBRATION_DATA_INCOMPLETE",
                "缺少計算結果，請先儲存讀值",
                details={"field": "calculation_summary"},
            )
        if record.equipment is None or record.equipment.status != "active":
            raise CalibrationValidationError(
                "CALIBRATION_STATUS_CONFLICT",
                "受校設備狀態非啟用",
                details={
                    "field": "equipment_id",
                    "equipment_id": record.equipment_id,
                },
            )
        if (
            record.template_version is None
            or record.template_version.status != "approved"
        ):
            raise CalibrationValidationError(
                "CALIBRATION_STATUS_CONFLICT",
                "校正模板版本已不是目前可送審的核准版本",
                details={
                    "field": "template_version_id",
                    "template_version_id": record.template_version_id,
                },
            )

        # 內校重新驗證參考標準器並建立快照
        if record.calibration_type == "internal":
            if record.reference_standard_equipment_id is None:
                raise CalibrationValidationError(
                    "CALIBRATION_REFERENCE_REQUIRED",
                    "內校必須指定參考標準器",
                    details={"field": "reference_standard_equipment_id"},
                )
            CalibrationEligibilityService.assert_reference_standard_usable(
                record.reference_standard_equipment_id,
                on_date=record.calibration_date,
            )
        elif record.calibration_type == "external":
            if record.certificate_attachment_id is None:
                raise CalibrationValidationError(
                    "CALIBRATION_CERTIFICATE_REQUIRED",
                    "外校送審必須上傳證書附件",
                    details={"field": "certificate_attachment_id"},
                )
            CalibrationService._assert_certificate_attachment(
                record, record.certificate_attachment_id
            )

        # 以資料庫原始讀值重算並比對保存摘要
        CalibrationService._recalculate_and_compare(record)
        if record.calibration_type == "internal":
            CalibrationService._create_reference_snapshot(record)

        submitted_at = utc_now()
        record.status = "submitted"
        record.submitted_by = actor_id
        record.submitted_at = submitted_at
        record.row_version += 1

        db.session.flush()

        log_audit(
            actor_id,
            "submit_calibration",
            "equipment_calibration",
            record.id,
            new_val={
                "status": record.status,
                "submitted_by": actor_id,
                "submitted_at": submitted_at.isoformat(),
                "reason": reason,
                "data_hash": record.data_hash,
            },
        )

        db.session.commit()
        return CalibrationService._serialize_record(record, include_points=True)

    @staticmethod
    @_rollback_on_error
    def approve(calibration_id: int, payload: dict, actor_id: int) -> dict:
        """核准：職責分離、列鎖、版本檢查、建立標準器快照。"""
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(
            data,
            {"expected_version", "reason", "confirmations"},
        )

        expected_version = CalibrationService._required_int(
            data, "expected_version", "CALIBRATION_FIELD_INVALID"
        )
        reason = CalibrationService._required_text(
            data, "reason", "CALIBRATION_FIELD_INVALID", max_length=2000
        )
        confirmations = data.get("confirmations")
        if confirmations is not None:
            required_confirmations = {
                "raw_readings",
                "calculations",
                "reference_standard",
                "attachments",
                "template_version",
            }
            if (
                not isinstance(confirmations, dict)
                or set(confirmations) != required_confirmations
                or any(value is not True for value in confirmations.values())
            ):
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "核准確認項目必須完整勾選",
                    details={"field": "confirmations"},
                )

        record = CalibrationService._lock_record(calibration_id)
        CalibrationService._require_version(record, expected_version)

        if record.status != "submitted":
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "只有送審狀態可核准",
                details={"calibration_id": calibration_id, "status": record.status},
            )

        # 職責分離：建立者、讀值輸入者、送審者不可核准
        participants = {
            record.created_by,
            record.submitted_by,
        }
        for point in sorted(
            record.calibration_points, key=lambda item: item.point_order
        ):
            for reading in point.readings:
                if reading.entered_by:
                    participants.add(reading.entered_by)

        if actor_id in participants:
            raise CalibrationForbidden(
                "CALIBRATION_SELF_APPROVAL_FORBIDDEN",
                "建立、輸入或送審人員不得核准自己的校正紀錄",
                details={
                    "calibration_id": calibration_id,
                    "actor_id": actor_id,
                    "participants": list(participants),
                },
            )

        CalibrationService._recalculate_and_compare(record)

        # 核准時再次驗證標準器；送審快照保持不可變。
        if record.calibration_type == "internal":
            if record.reference_standard_equipment_id is None:
                raise CalibrationValidationError(
                    "CALIBRATION_REFERENCE_REQUIRED",
                    "內校缺少參考標準器",
                    details={"field": "reference_standard_equipment_id"},
                )
            CalibrationEligibilityService.assert_reference_standard_usable(
                record.reference_standard_equipment_id,
                on_date=record.calibration_date,
            )
        elif record.calibration_type == "external":
            if record.certificate_attachment_id is None:
                raise CalibrationValidationError(
                    "CALIBRATION_CERTIFICATE_REQUIRED",
                    "外校核准前必須保有證書附件",
                    details={"field": "certificate_attachment_id"},
                )
            CalibrationService._assert_certificate_attachment(
                record, record.certificate_attachment_id
            )

        # 更新設備下次校驗日（依校正週期）
        equipment = db.session.execute(
            select(MeasurementEquipment).where(
                MeasurementEquipment.id == record.equipment_id
            )
        ).scalar_one_or_none()
        if (
            equipment is None
            or not equipment.calibration_interval_months
            or equipment.calibration_interval_months <= 0
        ):
            raise CalibrationValidationError(
                "CALIBRATION_DATA_INCOMPLETE",
                "受校設備缺少有效校驗週期",
                details={
                    "field": "calibration_interval_months",
                    "equipment_id": record.equipment_id,
                },
            )
        from dateutil.relativedelta import relativedelta

        record.next_due_date = record.calibration_date + relativedelta(
            months=equipment.calibration_interval_months
        )

        approved_at = utc_now()
        record.effective_date = record.calibration_date
        record.status = "approved"
        record.approved_by = actor_id
        record.approved_at = approved_at
        record.approval_reason = reason
        record.row_version += 1

        db.session.flush()

        log_audit(
            actor_id,
            "approve_calibration",
            "equipment_calibration",
            record.id,
            new_val={
                "status": record.status,
                "approved_by": actor_id,
                "approved_at": approved_at.isoformat(),
                "approval_reason": reason,
                "confirmations": confirmations,
                "data_hash": record.data_hash,
                "row_version": record.row_version,
            },
        )

        db.session.commit()
        return CalibrationService._serialize_record(record, include_points=True)

    @staticmethod
    @_rollback_on_error
    def reject(calibration_id: int, payload: dict, actor_id: int) -> dict:
        """退回：保存送審證據、建立後繼草稿。"""
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(data, {"expected_version", "reason"})

        expected_version = CalibrationService._required_int(
            data, "expected_version", "CALIBRATION_FIELD_INVALID"
        )
        reason = CalibrationService._required_text(
            data, "reason", "CALIBRATION_FIELD_INVALID", max_length=2000
        )

        record = CalibrationService._lock_record(calibration_id)
        CalibrationService._require_version(record, expected_version)

        if record.status != "submitted":
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "只有送審狀態可退回",
                details={"calibration_id": calibration_id, "status": record.status},
            )

        # 建立後繼草稿
        successor = EquipmentCalibrationRecord(
            equipment_id=record.equipment_id,
            calibration_type=record.calibration_type,
            calibration_date=record.calibration_date,
            reference_standard_equipment_id=record.reference_standard_equipment_id,
            calibration_provider=record.calibration_provider,
            certificate_no=record.certificate_no,
            traceability_standard=record.traceability_standard,
            uncertainty_statement=record.uncertainty_statement,
            calibration_location=record.calibration_location,
            result="pending",
            status="draft",
            data_level=record.data_level,
            template_version_id=record.template_version_id,
            template_snapshot=record.template_snapshot,
            environment_conditions=record.environment_conditions,
            calculation_summary={},
            calculation_version=CALCULATION_VERSION,
            data_hash=None,
            procedure_code=record.procedure_code,
            procedure_name=record.procedure_name,
            row_version=1,
            created_by=actor_id,
        )
        db.session.add(successor)
        db.session.flush()

        # 複製點位與讀值到後繼草稿
        for point in record.calibration_points:
            new_point = EquipmentCalibrationPoint(
                calibration_record_id=successor.id,
                template_point_id=point.template_point_id,
                point_order=point.point_order,
                point_code=point.point_code,
                measurement_mode=point.measurement_mode,
                nominal_value=point.nominal_value,
                unit=point.unit,
                reference_value=point.reference_value,
                reference_input_mode=point.reference_input_mode,
                required_repetitions=point.required_repetitions,
                error_lower_limit=point.error_lower_limit,
                error_upper_limit=point.error_upper_limit,
                evaluation_basis=point.evaluation_basis,
                repeatability_rule=point.repeatability_rule,
                repeatability_limit=point.repeatability_limit,
                qualification_scope_code=point.qualification_scope_code,
                qualification_range_start=point.qualification_range_start,
                qualification_range_end=point.qualification_range_end,
                uncertainty_required=point.uncertainty_required,
                required=point.required,
                result="pending",
            )
            for reading in point.readings:
                new_point.readings.append(
                    EquipmentCalibrationReading(
                        trial_no=reading.trial_no,
                        standard_reading=reading.standard_reading,
                        indicated_value=reading.indicated_value,
                        effective_reference=reading.effective_reference,
                        error_value=reading.error_value,
                        correction_value=reading.correction_value,
                        result="pending",
                    )
                )
            db.session.add(new_point)

        decision_at = utc_now()
        record.status = "rejected"
        record.approved_by = actor_id
        record.approved_at = decision_at
        record.rejection_reason = reason
        record.successor_id = successor.id
        record.row_version += 1
        # 將退回理由保存到後繼草稿中供追溯
        successor.rejection_reason = reason
        db.session.flush()

        log_audit(
            actor_id,
            "reject_calibration",
            "equipment_calibration",
            record.id,
            new_val={
                "status": record.status,
                "rejection_reason": reason,
                "successor_id": successor.id,
            },
        )

        db.session.commit()
        return CalibrationService._serialize_record(successor, include_points=True)

    @staticmethod
    @_rollback_on_error
    def void(calibration_id: int, payload: dict, actor_id: int) -> dict:
        """作廢：需填寫理由，狀態轉為 voided。"""
        data = CalibrationService._object(payload)
        CalibrationService._reject_unknown(data, {"expected_version", "reason"})

        expected_version = CalibrationService._required_int(
            data, "expected_version", "CALIBRATION_FIELD_INVALID"
        )
        reason = CalibrationService._required_text(
            data, "reason", "CALIBRATION_FIELD_INVALID", max_length=2000
        )

        record = CalibrationService._lock_record(calibration_id)
        CalibrationService._require_version(record, expected_version)

        if record.status not in {
            "draft",
            "in_progress",
            "ready_for_submission",
        }:
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "只有非正式校正紀錄可作廢",
                details={"calibration_id": calibration_id, "status": record.status},
            )

        record.status = "voided"
        record.void_reason = reason
        record.row_version += 1

        db.session.flush()

        log_audit(
            actor_id,
            "void_calibration",
            "equipment_calibration",
            record.id,
            new_val={
                "status": record.status,
                "void_reason": reason,
            },
        )

        db.session.commit()
        return CalibrationService._serialize_record(record, include_points=True)

    # ============ 內部工具方法 ============

    @staticmethod
    def _assert_certificate_attachment(
        record: EquipmentCalibrationRecord,
        attachment_id: int,
    ) -> Attachment:
        """確認證書附件屬於本草稿或本設備，且格式符合校正類型。"""
        attachment = db.session.get(Attachment, attachment_id)
        if attachment is None:
            raise CalibrationNotFound(
                "CALIBRATION_ATTACHMENT_NOT_FOUND",
                "找不到指定的校正證書附件",
                details={"attachment_id": attachment_id},
            )
        belongs_to_record = (
            attachment.entity_type == "equipment_calibration"
            and attachment.entity_id == record.id
        )
        belongs_to_equipment = (
            attachment.entity_type == "measurement_equipment"
            and attachment.entity_id == record.equipment_id
        )
        if not (belongs_to_record or belongs_to_equipment):
            raise CalibrationValidationError(
                "CALIBRATION_ATTACHMENT_INVALID",
                "證書附件不屬於此設備或校正草稿",
                details={
                    "field": "certificate_attachment_id",
                    "attachment_id": attachment_id,
                },
            )
        allowed_mime_types = {
            "external": {"application/pdf", "image/jpeg", "image/png"},
            "internal": {
                "application/pdf",
                "image/jpeg",
                "image/png",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        }
        if attachment.mime_type.lower() not in allowed_mime_types.get(
            record.calibration_type, set()
        ):
            raise CalibrationValidationError(
                "CALIBRATION_ATTACHMENT_INVALID",
                "證書附件格式不符合校正類型",
                details={
                    "field": "certificate_attachment_id",
                    "attachment_id": attachment_id,
                    "mime_type": attachment.mime_type,
                    "calibration_type": record.calibration_type,
                },
            )
        if attachment.purpose != "cert":
            raise CalibrationValidationError(
                "CALIBRATION_ATTACHMENT_INVALID",
                "附件用途必須標記為 cert",
                details={
                    "field": "certificate_attachment_id",
                    "attachment_id": attachment_id,
                    "purpose": attachment.purpose,
                },
            )
        return attachment

    @staticmethod
    def _lock_record(calibration_id: int) -> EquipmentCalibrationRecord:
        record = db.session.execute(
            select(EquipmentCalibrationRecord)
            .where(EquipmentCalibrationRecord.id == calibration_id)
            .options(
                selectinload(EquipmentCalibrationRecord.calibration_points).selectinload(
                    EquipmentCalibrationPoint.readings
                )
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if record is None:
            raise CalibrationNotFound(
                "CALIBRATION_RECORD_NOT_FOUND",
                "找不到校正紀錄",
                details={"calibration_id": calibration_id},
            )
        return record

    @staticmethod
    def _lock_template_version(template_version_id: int) -> CalibrationTemplateVersion:
        return db.session.execute(
            select(CalibrationTemplateVersion)
            .where(CalibrationTemplateVersion.id == template_version_id)
            .options(selectinload(CalibrationTemplateVersion.points))
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    @staticmethod
    def _require_version(record: EquipmentCalibrationRecord, expected_version: int) -> None:
        if record.row_version != expected_version:
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "校正紀錄已被其他人更新，請重新載入",
                details={
                    "calibration_id": record.id,
                    "current_version": record.row_version,
                    "expected_version": expected_version,
                },
            )

    @staticmethod
    def _require_editable_status(record: EquipmentCalibrationRecord) -> None:
        if record.status not in {
            "draft",
            "in_progress",
            "ready_for_submission",
        }:
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "目前狀態不可編輯",
                details={"calibration_id": record.id, "status": record.status},
            )

    @staticmethod
    def _build_template_snapshot(version: CalibrationTemplateVersion) -> dict:
        snapshot = {
            "version_id": version.id,
            "version_no": version.version_no,
            "procedure_code": version.procedure_code,
            "procedure_name": version.procedure_name,
            "default_repetitions": version.default_repetitions,
            "environment_requirements": version.environment_requirements,
            "allow_limited_use": version.allow_limited_use,
            "points": [
                {
                    "point_order": p.point_order,
                    "point_code": p.point_code,
                    "measurement_mode": p.measurement_mode,
                    "nominal_value": CalibrationService._decimal_text(p.nominal_value),
                    "unit": p.unit,
                    "reference_input_mode": p.reference_input_mode,
                    "required_repetitions": p.required_repetitions,
                    "error_lower_limit": CalibrationService._decimal_text(p.error_lower_limit),
                    "error_upper_limit": CalibrationService._decimal_text(p.error_upper_limit),
                    "evaluation_basis": p.evaluation_basis,
                    "repeatability_rule": p.repeatability_rule,
                    "repeatability_limit": CalibrationService._decimal_text(p.repeatability_limit),
                    "qualification_scope_code": p.qualification_scope_code,
                    "qualification_range_start": CalibrationService._decimal_text(
                        p.qualification_range_start
                    ),
                    "qualification_range_end": CalibrationService._decimal_text(
                        p.qualification_range_end
                    ),
                    "uncertainty_required": p.uncertainty_required,
                    "required": p.required,
                    "instruction": p.instruction,
                }
                for p in sorted(version.points, key=lambda x: x.point_order)
            ],
        }
        return CalibrationService._canonical_json(snapshot)

    @staticmethod
    def _validate_environment_conditions(
        version: CalibrationTemplateVersion, conditions: dict
    ) -> dict:
        """驗證環境條件只包含模板宣告的鍵；未知鍵拒絕。"""
        if not isinstance(conditions, dict):
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "environment_conditions 必須是 JSON 物件",
                details={"field": "environment_conditions"},
            )

        template_reqs = version.environment_requirements or {}
        allowed_keys = set(template_reqs.keys())
        unknown = set(conditions.keys()) - allowed_keys
        if unknown:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "環境條件包含模板未宣告的鍵",
                details={"field": "environment_conditions", "unknown_keys": sorted(unknown)},
            )

        normalized = {}
        for key, value in conditions.items():
            if not isinstance(value, dict):
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    f"環境條件 {key} 必須是物件",
                    details={"field": "environment_conditions", "key": key},
                )
            rule = template_reqs.get(key, {})
            unknown_value_fields = set(value) - {"value", "unit", "instruction"}
            if unknown_value_fields:
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    f"環境條件 {key} 包含未允許欄位",
                    details={
                        "field": "environment_conditions",
                        "key": key,
                        "unknown_fields": sorted(unknown_value_fields),
                    },
                )
            if value.get("unit") not in (None, rule.get("unit")):
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    f"環境條件 {key} 單位與模板不符",
                    details={"field": "environment_conditions", "key": key},
                )
            if (
                value.get("instruction") is not None
                and value.get("instruction") != rule.get("instruction")
            ):
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    f"環境條件 {key} 操作提示與模板不符",
                    details={"field": "environment_conditions", "key": key},
                )
            if value.get("value") not in (None, ""):
                try:
                    decimal_value = Decimal(str(value["value"]))
                except (InvalidOperation, TypeError, ValueError):
                    raise CalibrationValidationError(
                        "CALIBRATION_FIELD_INVALID",
                        f"環境條件 {key} 數值格式錯誤",
                        details={"field": "environment_conditions", "key": key},
                    )
                if (
                    not decimal_value.is_finite()
                    or len(decimal_value.as_tuple().digits) > _MAX_SIGNIFICANT_DIGITS
                    or abs(decimal_value.adjusted()) > _MAX_DECIMAL_EXPONENT
                ):
                    raise CalibrationValidationError(
                        "CALIBRATION_FIELD_INVALID",
                        f"環境條件 {key} 數值超出允許範圍",
                        details={"field": "environment_conditions", "key": key},
                    )
            min_val = rule.get("minimum")
            max_val = rule.get("maximum")
            if min_val is not None or max_val is not None:
                val = value.get("value")
                if val not in (None, ""):
                    dec_val = Decimal(str(val))
                    if min_val is not None and dec_val < Decimal(str(min_val)):
                        raise CalibrationValidationError(
                            "CALIBRATION_FIELD_INVALID",
                            f"環境條件 {key} 低於最小值",
                            details={"field": "environment_conditions", "key": key},
                        )
                    if max_val is not None and dec_val > Decimal(str(max_val)):
                        raise CalibrationValidationError(
                            "CALIBRATION_FIELD_INVALID",
                            f"環境條件 {key} 高於最大值",
                            details={"field": "environment_conditions", "key": key},
                        )
            normalized[key] = {
                "value": value.get("value") if value.get("value") != "" else None,
                "unit": rule.get("unit"),
                "instruction": rule.get("instruction"),
            }
        return CalibrationService._canonical_json(normalized)

    @staticmethod
    def _create_reference_snapshot(
        record: EquipmentCalibrationRecord, *, is_approved: bool = False
    ) -> CalibrationReferenceSnapshot:
        """建立參考標準器快照。若已存在則更新。"""
        ref_equipment = db.session.execute(
            select(MeasurementEquipment).where(
                MeasurementEquipment.id == record.reference_standard_equipment_id
            )
        ).scalar_one()

        # 取得標準器最新核准校正
        latest_cal = CalibrationEligibilityService._latest_approved_calibration(
            ref_equipment.id
        )

        # 檢查是否已存在快照
        existing_snapshot = db.session.execute(
            select(CalibrationReferenceSnapshot).where(
                CalibrationReferenceSnapshot.calibration_record_id == record.id,
                CalibrationReferenceSnapshot.reference_standard_equipment_id == ref_equipment.id,
            )
        ).scalar_one_or_none()

        if existing_snapshot:
            # 更新現有快照
            existing_snapshot.approved_calibration_record_id = latest_cal.id if latest_cal else record.id
            existing_snapshot.equipment_no = ref_equipment.equipment_no
            existing_snapshot.name = ref_equipment.name
            existing_snapshot.model = ref_equipment.model
            existing_snapshot.serial_no = ref_equipment.serial_no
            existing_snapshot.range_min = ref_equipment.range_min
            existing_snapshot.range_max = ref_equipment.range_max
            existing_snapshot.resolution = ref_equipment.resolution
            existing_snapshot.unit = ref_equipment.unit
            existing_snapshot.calibration_date = latest_cal.calibration_date if latest_cal else record.calibration_date
            existing_snapshot.certificate_no = latest_cal.certificate_no if latest_cal else record.certificate_no
            existing_snapshot.calibration_due_date = latest_cal.next_due_date if latest_cal else record.next_due_date
            existing_snapshot.result = latest_cal.result if latest_cal else "pass"
            existing_snapshot.data_hash = latest_cal.data_hash if latest_cal else record.data_hash
            existing_snapshot.traceability_standard = latest_cal.traceability_standard if latest_cal else record.traceability_standard
            existing_snapshot.snapshot_data = {
                "equipment_id": ref_equipment.id,
                "is_reference_standard": ref_equipment.is_reference_standard,
                "calibration_type": latest_cal.calibration_type if latest_cal else record.calibration_type,
            }
            db.session.flush()
            return existing_snapshot

        snapshot = CalibrationReferenceSnapshot(
            calibration_record_id=record.id,
            reference_standard_equipment_id=ref_equipment.id,
            approved_calibration_record_id=latest_cal.id if latest_cal else record.id,
            equipment_no=ref_equipment.equipment_no,
            name=ref_equipment.name,
            model=ref_equipment.model,
            serial_no=ref_equipment.serial_no,
            range_min=ref_equipment.range_min,
            range_max=ref_equipment.range_max,
            resolution=ref_equipment.resolution,
            unit=ref_equipment.unit,
            calibration_date=latest_cal.calibration_date if latest_cal else record.calibration_date,
            certificate_no=latest_cal.certificate_no if latest_cal else record.certificate_no,
            calibration_due_date=latest_cal.next_due_date if latest_cal else record.next_due_date,
            result=latest_cal.result if latest_cal else "pass",
            data_hash=latest_cal.data_hash if latest_cal else record.data_hash,
            traceability_standard=latest_cal.traceability_standard if latest_cal else record.traceability_standard,
            snapshot_data={
                "equipment_id": ref_equipment.id,
                "is_reference_standard": ref_equipment.is_reference_standard,
                "calibration_type": latest_cal.calibration_type if latest_cal else record.calibration_type,
            },
        )
        db.session.add(snapshot)
        db.session.flush()
        return snapshot

    @staticmethod
    def _recalculate_and_compare(record: EquipmentCalibrationRecord) -> None:
        """以資料庫原始讀值重算，與保存摘要及 hash 不符時回 CALIBRATION_DATA_CHANGED。"""
        points_payload = []
        for point in record.calibration_points:
            readings = [
                CalibrationReadingInput(
                    trial_no=r.trial_no,
                    indicated_value=r.indicated_value,
                    standard_reading=r.standard_reading,
                )
                for r in sorted(point.readings, key=lambda item: item.trial_no)
            ]
            rule = CalibrationPointRule(
                point_code=point.point_code,
                scope_code=point.qualification_scope_code or point.point_code,
                reference_input_mode=point.reference_input_mode,
                reference_value=point.reference_value
                if point.reference_input_mode == "certified_value"
                else None,
                required_repetitions=point.required_repetitions,
                error_lower_limit=point.error_lower_limit,
                error_upper_limit=point.error_upper_limit,
                evaluation_basis=point.evaluation_basis,
                repeatability_rule=point.repeatability_rule,
                repeatability_limit=point.repeatability_limit,
                uncertainty_required=point.uncertainty_required,
                expanded_uncertainty=point.expanded_uncertainty,
                coverage_factor=point.coverage_factor,
                required=point.required,
            )
            calculation = calculate_point(rule, readings)
            points_payload.append(calculation)

        recalculated = calculate_calibration(
            points_payload,
            allow_limited_use=record.template_version.allow_limited_use,
        )
        # 比對結果與 hash
        if recalculated.result != record.result:
            raise CalibrationValidationError(
                "CALIBRATION_DATA_CHANGED",
                "重算結果與送審時不符",
                details={
                    "saved_result": record.result,
                    "recalculated_result": recalculated.result,
                },
            )

        sorted_points = sorted(
            record.calibration_points, key=lambda item: item.point_order
        )
        canonical = CalibrationService._canonical_hash_payload(
            record, list(zip(sorted_points, points_payload))
        )
        new_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if not record.data_hash or record.data_hash != new_hash:
            raise CalibrationValidationError(
                "CALIBRATION_DATA_CHANGED",
                "資料雜湊與送審時不符，資料可能已被竄改",
                details={
                    "saved_hash": record.data_hash,
                    "recalculated_hash": new_hash,
                },
)

    @staticmethod
    def _get_reference_value_for_hash(
        point: EquipmentCalibrationPoint,
    ) -> str | None:
        """取得用於雜湊的參考值：直接使用點位的 reference_value（已在建立/儲存讀值時設定為正確值）。"""
        return CalibrationService._decimal_text_normalized(point.reference_value)

    @staticmethod
    def _canonical_hash_payload(
        record: EquipmentCalibrationRecord,
        calculated_points: list[tuple[EquipmentCalibrationPoint, Any]],
    ) -> str:
        payload = {
            "template_snapshot": record.template_snapshot,
            "environment_conditions": record.environment_conditions,
            "reference_standard_equipment_id": record.reference_standard_equipment_id,
            "calibration_type": record.calibration_type,
            "calibration_date": record.calibration_date.isoformat()
            if record.calibration_date
            else None,
            "result": record.result,
            "calculation_version": record.calculation_version,
            "calculation_summary": record.calculation_summary,
            "points": [
                {
                    "point_code": point.point_code,
                    "reference_value": CalibrationService._get_reference_value_for_hash(point),
                    "expanded_uncertainty": CalibrationService._decimal_text_normalized(point.expanded_uncertainty),
                    "coverage_factor": CalibrationService._decimal_text_normalized(point.coverage_factor),
                    "readings": [
                        {
                            "trial_no": r.trial_no,
                            "indicated_value": CalibrationService._decimal_text_normalized(r.indicated_value),
                            "standard_reading": CalibrationService._decimal_text_normalized(r.standard_reading),
                            "error_value": CalibrationService._decimal_text_normalized(r.error_value),
                            "result": r.result,
                        }
                        for r in sorted(point.readings, key=lambda x: x.trial_no)
                    ],
                }
                for point, *_ in sorted(
                    calculated_points, key=lambda item: item[0].point_order
                )
            ],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _build_calculation_summary(calibration_calc) -> dict:
        return {
            "result": calibration_calc.result,
            "passed_scope_codes": list(calibration_calc.passed_scope_codes),
            "failed_scope_codes": list(calibration_calc.failed_scope_codes),
            "blockers": list(calibration_calc.blockers),
            "calculation_version": calibration_calc.calculation_version,
            "points": [
                {
                    "point_code": p.point_code,
                    "scope_code": p.scope_code,
                    "result": p.result,
                    "mean_error": CalibrationService._decimal_text(p.mean_error),
                    "mean_correction": CalibrationService._decimal_text(p.mean_correction),
                    "error_range": CalibrationService._decimal_text(p.error_range),
                    "sample_stddev": CalibrationService._decimal_text(p.sample_stddev),
                    "blockers": list(p.blockers),
                }
                for p in calibration_calc.points
            ],
        }

    @staticmethod
    def _serialize_record(
        record: EquipmentCalibrationRecord, *, include_points: bool
    ) -> dict:
        result = {
            "id": record.id,
            "equipment_id": record.equipment_id,
            "equipment_no": record.equipment.equipment_no if record.equipment else None,
            "equipment_name": record.equipment.name if record.equipment else None,
            "calibration_type": record.calibration_type,
            "calibration_date": record.calibration_date.isoformat()
            if record.calibration_date
            else None,
            "effective_date": record.effective_date.isoformat()
            if record.effective_date
            else None,
            "next_due_date": record.next_due_date.isoformat()
            if record.next_due_date
            else None,
            "calibration_provider": record.calibration_provider,
            "certificate_no": record.certificate_no,
            "traceability_standard": record.traceability_standard,
            "uncertainty_statement": record.uncertainty_statement,
            "result": record.result,
            "applicable_modes": record.applicable_modes,
            "restriction_conditions": record.restriction_conditions,
            "approval_reason": record.approval_reason,
            "reference_standard_no": record.reference_standard_no,
            "reference_standard_due_date": record.reference_standard_due_date.isoformat()
            if record.reference_standard_due_date
            else None,
            "template_version_id": record.template_version_id,
            "data_level": record.data_level,
            "row_version": record.row_version,
            "template_snapshot": record.template_snapshot,
            "environment_conditions": record.environment_conditions,
            "calculation_summary": record.calculation_summary,
            "calculation_version": record.calculation_version,
            "data_hash": record.data_hash,
            "procedure_code": record.procedure_code,
            "procedure_name": record.procedure_name,
            "calibration_location": record.calibration_location,
            "started_at": record.started_at.isoformat()
            if record.started_at
            else None,
            "completed_at": record.completed_at.isoformat()
            if record.completed_at
            else None,
            "reference_standard_equipment_id": record.reference_standard_equipment_id,
            "submitted_by": record.submitted_by,
            "submitted_at": record.submitted_at.isoformat()
            if record.submitted_at
            else None,
            "rejection_reason": record.rejection_reason,
            "void_reason": record.void_reason,
            "successor_id": record.successor_id,
            "predecessor_id": record.predecessors[0].id if record.predecessors else None,
            "certificate_attachment_id": record.certificate_attachment_id,
            "status": record.status,
            "created_by": record.created_by,
            "created_at": record.created_at.isoformat()
            if record.created_at
            else None,
            "approved_by": record.approved_by,
            "approved_at": record.approved_at.isoformat()
            if record.approved_at
            else None,
        }

        if include_points:
            result["points"] = [
                {
                    "id": p.id,
                    "template_point_id": p.template_point_id,
                    "point_order": p.point_order,
                    "point_code": p.point_code,
                    "measurement_mode": p.measurement_mode,
                    "nominal_value": CalibrationService._decimal_text(p.nominal_value),
                    "unit": p.unit,
                    "reference_value": CalibrationService._decimal_text(p.reference_value),
                    "error_lower_limit": CalibrationService._decimal_text(p.error_lower_limit),
                    "error_upper_limit": CalibrationService._decimal_text(p.error_upper_limit),
                    "evaluation_basis": p.evaluation_basis,
                    "repeatability_rule": p.repeatability_rule,
                    "repeatability_limit": CalibrationService._decimal_text(p.repeatability_limit),
                    "qualification_scope_code": p.qualification_scope_code,
                    "qualification_range_start": CalibrationService._decimal_text(p.qualification_range_start),
                    "qualification_range_end": CalibrationService._decimal_text(p.qualification_range_end),
                    "uncertainty_required": p.uncertainty_required,
                    "required": p.required,
                    "required_repetitions": p.required_repetitions,
                    "average_value": CalibrationService._decimal_text(p.average_value),
                    "error_value": CalibrationService._decimal_text(p.error_value),
                    "repeatability_value": CalibrationService._decimal_text(p.repeatability_value),
                    "mean_error": CalibrationService._decimal_text(p.mean_error),
                    "mean_correction": CalibrationService._decimal_text(p.mean_correction),
                    "minimum_error": CalibrationService._decimal_text(p.minimum_error),
                    "maximum_error": CalibrationService._decimal_text(p.maximum_error),
                    "error_range": CalibrationService._decimal_text(p.error_range),
                    "sample_stddev": CalibrationService._decimal_text(p.sample_stddev),
                    "expanded_uncertainty": CalibrationService._decimal_text(p.expanded_uncertainty),
                    "coverage_factor": CalibrationService._decimal_text(p.coverage_factor),
                    "completed_reading_count": p.completed_reading_count,
                    "result": p.result,
                    "remarks": p.remarks,
                    "readings": [
                        {
                            "id": r.id,
                            "trial_no": r.trial_no,
                            "standard_reading": CalibrationService._decimal_text(r.standard_reading),
                            "indicated_value": CalibrationService._decimal_text(r.indicated_value),
                            "effective_reference": CalibrationService._decimal_text(r.effective_reference),
                            "error_value": CalibrationService._decimal_text(r.error_value),
                            "correction_value": CalibrationService._decimal_text(r.correction_value),
                            "result": r.result,
                            "entered_by": r.entered_by,
                            "entered_at": r.entered_at.isoformat() if r.entered_at else None,
                            "last_modified_by": r.last_modified_by,
                            "last_modified_at": r.last_modified_at.isoformat() if r.last_modified_at else None,
                            "revision_reason": r.revision_reason,
                        }
                        for r in sorted(p.readings, key=lambda x: x.trial_no)
                    ],
                }
                for p in sorted(record.calibration_points, key=lambda x: x.point_order)
            ]
            result["reference_snapshots"] = [
                {
                    "id": s.id,
                    "reference_standard_equipment_id": s.reference_standard_equipment_id,
                    "equipment_no": s.equipment_no,
                    "name": s.name,
                    "model": s.model,
                    "serial_no": s.serial_no,
                    "range_min": CalibrationService._decimal_text(s.range_min),
                    "range_max": CalibrationService._decimal_text(s.range_max),
                    "resolution": CalibrationService._decimal_text(s.resolution),
                    "unit": s.unit,
                    "calibration_date": s.calibration_date.isoformat() if s.calibration_date else None,
                    "certificate_no": s.certificate_no,
                    "calibration_due_date": s.calibration_due_date.isoformat() if s.calibration_due_date else None,
                    "result": s.result,
                    "data_hash": s.data_hash,
                    "traceability_standard": s.traceability_standard,
                    "snapshot_data": s.snapshot_data,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in record.reference_snapshots
            ]

        return result

    @staticmethod
    def _object(payload) -> dict:
        if not isinstance(payload, dict):
            raise CalibrationValidationError(
                "CALIBRATION_PAYLOAD_INVALID",
                "請求內容必須是 JSON 物件",
                details={},
            )
        return payload

    @staticmethod
    def _reject_unknown(payload: dict, allowed: set[str]) -> None:
        unknown = set(payload) - allowed
        if unknown:
            raise CalibrationValidationError(
                "CALIBRATION_UNKNOWN_FIELDS",
                "請求包含未允許欄位",
                details={"unknown_fields": sorted(unknown)},
            )

    @staticmethod
    def _required_int(data: dict, field: str, code: str) -> int:
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise CalibrationValidationError(code, f"{field} 必須是整數", details={"field": field})
        if isinstance(value, str):
            if not value.strip():
                raise CalibrationValidationError(code, f"{field} 不可為空白", details={"field": field})
            try:
                value = int(value)
            except ValueError:
                raise CalibrationValidationError(code, f"{field} 不是合法整數", details={"field": field})
        if value <= 0 or value > _MAX_INTEGER:
            raise CalibrationValidationError(code, f"{field} 超出允許範圍", details={"field": field})
        return value

    @staticmethod
    def _required_text(data: dict, field: str, code: str, max_length: int = 2000) -> str:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CalibrationValidationError(code, f"{field} 為必填文字欄位", details={"field": field})
        if len(value) > max_length:
            raise CalibrationValidationError(code, f"{field} 超過允許長度", details={"field": field, "max_length": max_length})
        return value.strip()

    @staticmethod
    def _optional_text(data: dict, field: str, max_length: int = 2000) -> Optional[str]:
        value = data.get(field)
        if value is None:
            return None
        if not isinstance(value, str):
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                f"{field} 必須是文字",
                details={"field": field},
            )
        if len(value) > max_length:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                f"{field} 超過允許長度",
                details={"field": field, "max_length": max_length},
            )
        return value.strip() or None

    @staticmethod
    def _required_date(data: dict, field: str, code: str) -> date:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CalibrationValidationError(code, f"{field} 為必填日期欄位", details={"field": field})
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise CalibrationValidationError(code, f"{field} 日期格式錯誤 (YYYY-MM-DD)", details={"field": field})

    @staticmethod
    def _optional_decimal(data: dict, field: str) -> Optional[Decimal]:
        value = data.get(field)
        if value is None or value == "":
            return None
        if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                f"{field} 必須以十進位字串或整數提供",
                details={"field": field},
            )
        try:
            decimal_value = Decimal(str(value).strip())
        except (InvalidOperation, TypeError, ValueError):
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                f"{field} 不是合法 Decimal",
                details={"field": field},
            )
        if (
            not decimal_value.is_finite()
            or len(decimal_value.as_tuple().digits) > _MAX_SIGNIFICANT_DIGITS
            or abs(decimal_value.adjusted()) > _MAX_DECIMAL_EXPONENT
        ):
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                f"{field} 超出允許的 Decimal 範圍",
                details={"field": field},
            )
        return decimal_value

    @staticmethod
    def _decimal_text(value) -> str | None:
        """將 Decimal 格式化為標準字串，保留精度。"""
        if value is None:
            return None
        decimal_value = value if isinstance(value, Decimal) else Decimal(value)
        if decimal_value.is_zero():
            return "0"
        # 不使用 normalize()，保留尾隨零以維持精度
        return format(decimal_value, "f")

    @staticmethod
    def _decimal_text_normalized(value) -> str | None:
        """將 Decimal 格式化為正規化字串（移除尾隨零），用於雜湊計算。"""
        if value is None:
            return None
        decimal_value = value if isinstance(value, Decimal) else Decimal(value)
        if decimal_value.is_zero():
            return "0"
        # 使用 normalize 移除尾隨零，確保雜湊一致性
        normalized = decimal_value.normalize()
        # 確保科學記號不被使用
        if normalized.as_tuple().exponent < 0:
            return format(normalized, "f")
        return str(normalized)

    @staticmethod
    def _bounded_int(
        value, *, field: str, minimum: int, maximum: int, code: str
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise CalibrationValidationError(
                code, f"{field} 必須是整數", details={"field": field}
            )
        if isinstance(value, str):
            if not value.strip():
                raise CalibrationValidationError(code, f"{field} 不可為空白", details={"field": field})
            try:
                value = int(value)
            except ValueError:
                raise CalibrationValidationError(code, f"{field} 不是合法整數", details={"field": field})
        if value < minimum or value > maximum:
            raise CalibrationValidationError(
                code,
                f"{field} 超出允許範圍",
                details={"field": field, "minimum": minimum, "maximum": maximum},
            )
        return value

    @staticmethod
    def _canonical_json(value: Any) -> dict:
        try:
            encoded = json.dumps(
                value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            return json.loads(encoded)
        except (OverflowError, TypeError, ValueError) as error:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "JSON 必須可重現且僅含有限數值",
                details={},
            ) from error
