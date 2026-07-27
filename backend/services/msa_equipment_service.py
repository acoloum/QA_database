"""MSA 量測設備主檔、校驗證據與正式研究資格服務。"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import aliased

from ..extensions import db
from ..models import (
    Attachment,
    EquipmentCalibrationRecord,
    EquipmentCorrectionPoint,
    EquipmentStatusEvent,
    MeasurementEquipment,
    MeasurementEquipmentLink,
    Recorder,
    Thermocouple,
)
from ..utils import log_audit
from .msa_contracts import EquipmentEligibility, EquipmentSnapshot
from .msa_errors import (
    MsaConflict,
    MsaNotFound,
    MsaServiceError,
    MsaValidationError,
)


_EQUIPMENT_FIELDS = {
    "equipment_no",
    "name",
    "equipment_type",
    "manufacturer",
    "model",
    "serial_no",
    "range_min",
    "range_max",
    "resolution",
    "unit",
    "department",
    "location",
    "custodian",
    "status",
    "calibration_type",
    "calibration_exemption_reason",
    "calibration_interval_months",
    "is_reference_standard",
    "affects_product_decision",
}
_EQUIPMENT_PATCH_FIELDS = _EQUIPMENT_FIELDS - {"equipment_no", "status"}
_EQUIPMENT_NUMERIC_FIELDS = {"range_min", "range_max", "resolution"}
_EQUIPMENT_BOOLEAN_FIELDS = {
    "is_reference_standard",
    "affects_product_decision",
}
_EQUIPMENT_TEXT_LIMITS = {
    "equipment_no": 80,
    "name": 160,
    "equipment_type": 80,
    "manufacturer": 120,
    "model": 120,
    "serial_no": 160,
    "unit": 40,
    "department": 120,
    "location": 200,
    "custodian": 120,
    "status": 30,
    "calibration_type": 30,
}
_EQUIPMENT_STATUS = {
    "pending_review",
    "active",
    "maintenance",
    "inactive",
    "scrapped",
}
_CALIBRATION_TYPES = {"internal", "external", "exempt"}
_CALIBRATION_RESULTS = {"pending", "pass", "fail", "limited_use"}
_CALIBRATION_SUMMARY_STATUS = {
    "valid",
    "due_soon",
    "expired",
    "failed",
    "missing",
    "exempt",
}
_CALIBRATION_TEXT_LIMITS = {
    "calibration_type": 30,
    "calibration_provider": 160,
    "certificate_no": 160,
    "result": 30,
}
_CALIBRATION_FIELDS = {
    "calibration_type",
    "calibration_date",
    "effective_date",
    "next_due_date",
    "calibration_provider",
    "certificate_no",
    "traceability_standard",
    "uncertainty_statement",
    "result",
    "applicable_modes",
    "restriction_conditions",
    "certificate_attachment_id",
    "correction_points",
}
_CORRECTION_POINT_FIELDS = {
    "measurement_mode",
    "nominal_value",
    "indicated_value",
    "error_value",
    "correction_value",
    "unit",
    "range_start",
    "range_end",
}
_CORRECTION_NUMERIC_FIELDS = {
    "nominal_value",
    "indicated_value",
    "error_value",
    "correction_value",
    "range_start",
    "range_end",
}
_CORRECTION_TEXT_LIMITS = {
    "measurement_mode": 80,
    "unit": 40,
}
_STATUS_EVENT_TYPES = {
    "calibration_overdue",
    "calibration_failed",
    "maintenance",
    "major_adjustment",
    "inactive",
    "scrapped",
    "reactivated",
    "review_completed",
}
_SOURCE_ENTITY_MODELS = {
    ("pyrometry", "Recorder"): Recorder,
    ("pyrometry", "Thermocouple"): Thermocouple,
}
_SORT_FIELDS = {
    "equipment_no": MeasurementEquipment.equipment_no,
    "name": MeasurementEquipment.name,
    "status": MeasurementEquipment.status,
    "updated_at": MeasurementEquipment.updated_at,
}


class MsaEquipmentService:
    """管理設備證據，並依固定優先序判定正式研究資格。"""

    @staticmethod
    def list(args) -> dict:
        """以受限分頁與白名單排序列出設備。"""
        page = MsaEquipmentService._parse_bounded_int(
            args.get("page", 1),
            field="page",
            minimum=1,
            maximum=10_000,
            code="MSA_PAGE_INVALID",
        )
        page_size = MsaEquipmentService._parse_bounded_int(
            args.get("page_size", 25),
            field="page_size",
            minimum=1,
            maximum=100,
            code="MSA_PAGE_SIZE_INVALID",
        )
        sort_name = args.get("sort", "equipment_no")
        sort_column = _SORT_FIELDS.get(sort_name)
        if sort_column is None and sort_name != "risk":
            raise MsaServiceError(
                "MSA_SORT_INVALID",
                "不支援的設備排序欄位",
                details={
                    "sort": sort_name,
                    "allowed": sorted([*_SORT_FIELDS, "risk"]),
                },
            )
        order = args.get("order", "asc")
        if order not in {"asc", "desc"}:
            raise MsaServiceError(
                "MSA_SORT_ORDER_INVALID",
                "排序方向只允許 asc 或 desc",
                details={"order": order},
            )

        as_of = MsaEquipmentService._parse_iso_date_argument(
            args.get("as_of"),
            field="as_of",
            default=date.today(),
            code="MSA_AS_OF_INVALID",
        )
        latest_calibration = aliased(
            EquipmentCalibrationRecord,
            name="latest_approved_calibration",
        )
        latest_calibration_id = (
            db.select(EquipmentCalibrationRecord.id)
            .where(
                EquipmentCalibrationRecord.equipment_id
                == MeasurementEquipment.id,
                EquipmentCalibrationRecord.status == "approved",
                EquipmentCalibrationRecord.calibration_date <= as_of,
                or_(
                    EquipmentCalibrationRecord.effective_date.is_(None),
                    EquipmentCalibrationRecord.effective_date <= as_of,
                ),
            )
            .order_by(
                EquipmentCalibrationRecord.calibration_date.desc(),
                EquipmentCalibrationRecord.id.desc(),
            )
            .limit(1)
            .correlate(MeasurementEquipment)
            .scalar_subquery()
        )
        exempt_condition = and_(
            MeasurementEquipment.calibration_type == "exempt",
            func.trim(
                func.coalesce(
                    MeasurementEquipment.calibration_exemption_reason,
                    "",
                )
            )
            != "",
        )
        calibration_status_expression = case(
            (exempt_condition, "exempt"),
            (latest_calibration.id.is_(None), "missing"),
            (
                latest_calibration.result.notin_(("pass", "limited_use")),
                "failed",
            ),
            (latest_calibration.next_due_date.is_(None), "missing"),
            (latest_calibration.next_due_date < as_of, "expired"),
            (
                latest_calibration.next_due_date
                <= as_of + timedelta(days=30),
                "due_soon",
            ),
            else_="valid",
        )
        query = (
            db.session.query(
                MeasurementEquipment,
                latest_calibration,
            )
            .outerjoin(
                latest_calibration,
                latest_calibration.id == latest_calibration_id,
            )
        )
        status = args.get("status")
        if status:
            if status not in _EQUIPMENT_STATUS:
                raise MsaServiceError(
                    "MSA_EQUIPMENT_STATUS_INVALID",
                    "設備狀態不在允許清單",
                    details={"status": status},
                )
            query = query.filter(MeasurementEquipment.status == status)
        calibration_status = args.get("calibration_status")
        if calibration_status:
            if calibration_status not in _CALIBRATION_SUMMARY_STATUS:
                raise MsaServiceError(
                    "MSA_CALIBRATION_STATUS_INVALID",
                    "校驗狀態不在允許清單",
                    details={
                        "calibration_status": calibration_status,
                        "allowed": sorted(_CALIBRATION_SUMMARY_STATUS),
                    },
                )
            query = query.filter(
                calibration_status_expression == calibration_status
            )
        keyword = (args.get("q") or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    MeasurementEquipment.equipment_no.ilike(pattern),
                    MeasurementEquipment.name.ilike(pattern),
                    MeasurementEquipment.serial_no.ilike(pattern),
                )
            )

        total = query.count()
        if sort_name == "risk":
            risk_expression = case(
                (calibration_status_expression == "failed", 0),
                (calibration_status_expression == "expired", 1),
                (MeasurementEquipment.status == "pending_review", 2),
                (MeasurementEquipment.status == "maintenance", 3),
                (calibration_status_expression == "due_soon", 4),
                else_=5,
            )
            ordering = (
                risk_expression.desc()
                if order == "desc"
                else risk_expression.asc()
            )
        else:
            ordering = (
                sort_column.desc()
                if order == "desc"
                else sort_column.asc()
            )
        items = (
            query.order_by(
                ordering,
                MeasurementEquipment.equipment_no.asc(),
                MeasurementEquipment.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                MsaEquipmentService._equipment_summary_to_dict(
                    equipment,
                    calibration,
                    as_of=as_of,
                )
                for equipment, calibration in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def get(equipment_id: int) -> dict:
        """取得設備主檔及其校驗、狀態事件與來源連結。"""
        equipment = MsaEquipmentService._get_equipment(equipment_id)
        as_of = date.today()
        calibration_records = (
            EquipmentCalibrationRecord.query
            .filter_by(equipment_id=equipment.id)
            .order_by(
                EquipmentCalibrationRecord.calibration_date.desc(),
                EquipmentCalibrationRecord.id.desc(),
            )
            .all()
        )
        latest_approved = next(
            (
                record
                for record in calibration_records
                if record.status == "approved"
                and record.calibration_date <= as_of
                and (
                    record.effective_date is None
                    or record.effective_date <= as_of
                )
            ),
            None,
        )
        data = MsaEquipmentService._equipment_summary_to_dict(
            equipment,
            latest_approved,
            as_of=as_of,
        )
        data["calibrations"] = [
            MsaEquipmentService._calibration_to_dict(record)
            for record in calibration_records
        ]
        data["status_events"] = [
            MsaEquipmentService._status_event_to_dict(event)
            for event in (
                EquipmentStatusEvent.query
                .filter_by(equipment_id=equipment.id)
                .order_by(
                    EquipmentStatusEvent.occurred_at.desc(),
                    EquipmentStatusEvent.id.desc(),
                )
                .all()
            )
        ]
        data["links"] = [
            MsaEquipmentService._link_to_dict(link)
            for link in (
                MeasurementEquipmentLink.query
                .filter_by(equipment_id=equipment.id)
                .order_by(
                    MeasurementEquipmentLink.is_current.desc(),
                    MeasurementEquipmentLink.id.desc(),
                )
                .all()
            )
        ]
        return data

    @staticmethod
    def create(payload, actor_id: int) -> dict:
        """建立不可重用設備編號的量測設備主檔。"""
        data = MsaEquipmentService._normalise_equipment_payload(
            payload,
            creating=True,
        )
        if MeasurementEquipment.query.filter_by(
            equipment_no=data["equipment_no"]
        ).first():
            raise MsaConflict(
                "MSA_EQUIPMENT_NO_DUPLICATE",
                "設備編號已存在，不可重複使用",
                details={"equipment_no": data["equipment_no"]},
            )
        equipment = MeasurementEquipment(
            **data,
            created_by=actor_id,
            updated_by=actor_id,
        )
        try:
            db.session.add(equipment)
            db.session.flush()
            result = MsaEquipmentService._equipment_to_dict(equipment)
            log_audit(
                actor_id,
                "create",
                "msa_equipment",
                equipment.id,
                new_val=result,
            )
            db.session.commit()
            return result
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_DATABASE_VALUE_INVALID",
                "設備欄位不符合資料庫長度或格式限制",
                details={},
            ) from error
        except IntegrityError as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_EQUIPMENT_NO_DUPLICATE",
                "設備編號已存在，不可重複使用",
                details={"equipment_no": data["equipment_no"]},
            ) from error

    @staticmethod
    def update(equipment_id: int, payload, actor_id: int) -> dict:
        """修改設備可變欄位；設備編號永遠不可改寫。"""
        if not isinstance(payload, dict):
            raise MsaValidationError(
                "MSA_EQUIPMENT_PAYLOAD_INVALID", "設備資料必須是 JSON 物件"
            )
        if "equipment_no" in payload:
            raise MsaValidationError(
                "MSA_EQUIPMENT_NO_IMMUTABLE",
                "設備編號建立後不可修改或重用",
            )
        if "status" in payload:
            raise MsaValidationError(
                "MSA_STATUS_REQUIRES_EVENT",
                "設備狀態只能透過狀態事件路由轉移",
            )
        equipment = MsaEquipmentService._get_equipment(equipment_id)
        data = MsaEquipmentService._normalise_equipment_payload(
            payload,
            creating=False,
        )
        if not data:
            raise MsaValidationError(
                "MSA_EQUIPMENT_PATCH_EMPTY", "未提供可修改的設備欄位"
            )
        MsaEquipmentService._validate_equipment_patch_invariants(
            equipment,
            data,
        )
        old_value = {
            field: MsaEquipmentService._canonical_value(
                getattr(equipment, field)
            )
            for field in data
        }
        for field, value in data.items():
            setattr(equipment, field, value)
        equipment.updated_by = actor_id
        try:
            db.session.flush()
            result = MsaEquipmentService._equipment_to_dict(equipment)
            log_audit(
                actor_id,
                "update",
                "msa_equipment",
                equipment.id,
                old_val=old_value,
                new_val={
                    field: MsaEquipmentService._canonical_value(
                        getattr(equipment, field)
                    )
                    for field in data
                },
            )
            db.session.commit()
            return result
        except (DataError, IntegrityError, ValueError) as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_EQUIPMENT_UPDATE_INVALID",
                "設備資料不符合受控限制",
                details={"reason": str(error)},
            ) from error

    @staticmethod
    def create_calibration(
        equipment_id: int,
        payload,
        actor_id: int,
    ) -> dict:
        """在單一交易建立 draft 校驗主檔及所有補正點。"""
        MsaEquipmentService._get_equipment(equipment_id)
        data, points = MsaEquipmentService._normalise_calibration_payload(
            payload
        )
        attachment_id = data.pop("certificate_attachment_id")
        certificate_attachment = None
        if attachment_id is not None:
            certificate_attachment = (
                MsaEquipmentService._lock_certificate_attachment(
                    attachment_id
                )
            )
            MsaEquipmentService._validate_staged_certificate_ownership(
                certificate_attachment,
                equipment_id=equipment_id,
                calibration_id=None,
            )
        record = EquipmentCalibrationRecord(
            equipment_id=equipment_id,
            status="draft",
            created_by=actor_id,
            certificate_attachment_id=attachment_id,
            **data,
        )
        try:
            db.session.add(record)
            db.session.flush()
            if certificate_attachment is not None:
                old_attachment = {
                    "entity_type": certificate_attachment.entity_type,
                    "entity_id": certificate_attachment.entity_id,
                }
                certificate_attachment.entity_type = "equipment_calibration"
                certificate_attachment.entity_id = record.id
                log_audit(
                    actor_id,
                    "bind_certificate",
                    "msa_attachment",
                    certificate_attachment.id,
                    old_val=old_attachment,
                    new_val={
                        "entity_type": "equipment_calibration",
                        "entity_id": record.id,
                        "calibration_id": record.id,
                    },
                )
            for point_data in points:
                db.session.add(
                    EquipmentCorrectionPoint(
                        calibration_record_id=record.id,
                        **point_data,
                    )
                )
            db.session.flush()
            result = MsaEquipmentService._calibration_to_dict(record)
            log_audit(
                actor_id,
                "create_calibration",
                "msa_equipment",
                record.id,
                new_val=result,
            )
            db.session.commit()
            return result
        except MsaServiceError:
            db.session.rollback()
            raise
        except (DataError, IntegrityError, ValueError) as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_CALIBRATION_INVALID",
                "校驗資料不符合受控限制",
                details={"reason": str(error)},
            ) from error

    @staticmethod
    def approve_calibration(
        calibration_id: int,
        payload,
        actor_id: int,
    ) -> dict:
        """以列鎖與 expected_status 核准 draft 校驗證據。"""
        payload = MsaEquipmentService._require_object(payload)
        MsaEquipmentService._reject_unknown_fields(
            set(payload)
            - {"expected_status", "reason", "certificate_attachment_id"}
        )
        expected_status = MsaEquipmentService._required_text(
            payload,
            "expected_status",
            max_length=30,
        )
        reason = MsaEquipmentService._required_text(payload, "reason")
        if expected_status not in {"draft", "approved"}:
            raise MsaValidationError(
                "MSA_EXPECTED_STATUS_INVALID",
                "expected_status 必須是 draft 或 approved",
                details={"expected_status": expected_status},
            )
        record = (
            db.session.execute(
                db.select(EquipmentCalibrationRecord)
                .where(EquipmentCalibrationRecord.id == calibration_id)
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if record is None:
            raise MsaNotFound(
                "MSA_CALIBRATION_NOT_FOUND",
                "找不到指定的設備校驗紀錄",
                details={"calibration_id": calibration_id},
            )
        if record.status != expected_status or record.status != "draft":
            raise MsaConflict(
                "MSA_CALIBRATION_STATUS_CONFLICT",
                "校驗狀態已變更，請重新載入後再核准",
                details={
                    "expected_status": expected_status,
                    "actual_status": record.status,
                },
            )
        if record.result == "pending":
            raise MsaValidationError(
                "MSA_CALIBRATION_RESULT_PENDING",
                "結果仍為 pending 的校驗紀錄不可核准",
            )
        requested_attachment_id = payload.get("certificate_attachment_id")
        if requested_attachment_id is not None:
            requested_attachment_id = MsaEquipmentService._positive_int(
                requested_attachment_id,
                field="certificate_attachment_id",
            )
        attachment_id = (
            requested_attachment_id
            if requested_attachment_id is not None
            else record.certificate_attachment_id
        )
        certificate_attachment = None
        attachment_old_value = None
        if attachment_id is not None:
            certificate_attachment = (
                MsaEquipmentService._lock_certificate_attachment(
                    attachment_id
                )
            )
            MsaEquipmentService._validate_staged_certificate_ownership(
                certificate_attachment,
                equipment_id=record.equipment_id,
                calibration_id=record.id,
            )
            attachment_old_value = {
                "entity_type": certificate_attachment.entity_type,
                "entity_id": certificate_attachment.entity_id,
            }
            certificate_attachment.entity_type = "equipment_calibration"
            certificate_attachment.entity_id = record.id
            record.certificate_attachment_id = attachment_id
        old_value = {"status": record.status}
        record.status = "approved"
        record.approval_reason = reason
        record.approved_by = actor_id
        record.approved_at = datetime.now(timezone.utc)
        try:
            db.session.flush()
            if (
                certificate_attachment is not None
                and attachment_old_value
                != {
                    "entity_type": "equipment_calibration",
                    "entity_id": record.id,
                }
            ):
                log_audit(
                    actor_id,
                    "bind_certificate",
                    "msa_attachment",
                    certificate_attachment.id,
                    old_val=attachment_old_value,
                    new_val={
                        "entity_type": "equipment_calibration",
                        "entity_id": record.id,
                        "calibration_id": record.id,
                    },
                )
            result = MsaEquipmentService._calibration_to_dict(record)
            log_audit(
                actor_id,
                "approve_calibration",
                "msa_equipment",
                record.id,
                old_val=old_value,
                new_val={
                    "status": "approved",
                    "approval_reason": reason,
                    "approved_by": actor_id,
                    "certificate_attachment_id": attachment_id,
                },
            )
            db.session.commit()
            return result
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_DATABASE_VALUE_INVALID",
                "校驗資料不符合資料庫長度或格式限制",
                details={},
            ) from error
        except (IntegrityError, ValueError) as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_CALIBRATION_STATUS_CONFLICT",
                "校驗狀態已變更，請重新載入後再核准",
                details={"reason": str(error)},
            ) from error

    @staticmethod
    def create_status_event(
        equipment_id: int,
        payload,
        actor_id: int,
    ) -> dict:
        """以 row lock 建立事件並在同一交易轉移設備狀態。"""
        payload = MsaEquipmentService._require_object(payload)
        unknown = set(payload) - {
            "event_type",
            "expected_status",
            "target_status",
            "occurred_at",
            "reason",
            "triggers_msa_restudy",
        }
        MsaEquipmentService._reject_unknown_fields(unknown)
        event_type = MsaEquipmentService._required_text(
            payload,
            "event_type",
            max_length=40,
        )
        if event_type not in _STATUS_EVENT_TYPES:
            raise MsaValidationError(
                "MSA_STATUS_EVENT_TYPE_INVALID",
                "設備狀態事件類型不在允許清單",
                details={
                    "event_type": event_type,
                    "allowed": sorted(_STATUS_EVENT_TYPES),
                },
            )
        expected_status = MsaEquipmentService._required_text(
            payload,
            "expected_status",
            max_length=30,
        )
        target_status = MsaEquipmentService._required_text(
            payload,
            "target_status",
            max_length=30,
        )
        if expected_status not in _EQUIPMENT_STATUS:
            raise MsaValidationError(
                "MSA_EXPECTED_STATUS_INVALID",
                "expected_status 不在設備狀態清單",
                details={"expected_status": expected_status},
            )
        if target_status not in _EQUIPMENT_STATUS:
            raise MsaValidationError(
                "MSA_EQUIPMENT_STATUS_INVALID",
                "target_status 不在設備狀態清單",
                details={"target_status": target_status},
            )
        if target_status == expected_status:
            raise MsaValidationError(
                "MSA_EQUIPMENT_STATUS_UNCHANGED",
                "target_status 必須與 expected_status 不同",
            )
        expected_event_type = (
            "review_completed"
            if expected_status == "pending_review"
            and target_status == "active"
            else "reactivated"
            if target_status == "active"
            else "major_adjustment"
            if target_status == "pending_review"
            else target_status
        )
        if event_type != expected_event_type:
            raise MsaValidationError(
                "MSA_STATUS_EVENT_TRANSITION_INVALID",
                "事件類型與設備狀態轉移不一致",
                details={
                    "event_type": event_type,
                    "expected_event_type": expected_event_type,
                    "expected_status": expected_status,
                    "target_status": target_status,
                },
            )
        reason = MsaEquipmentService._required_text(payload, "reason")
        triggers = payload.get("triggers_msa_restudy", False)
        if not isinstance(triggers, bool):
            raise MsaValidationError(
                "MSA_STATUS_EVENT_RESTUDY_INVALID",
                "triggers_msa_restudy 必須是布林值",
            )
        occurred_at = (
            MsaEquipmentService._parse_datetime(
                payload["occurred_at"], field="occurred_at"
            )
            if payload.get("occurred_at")
            else datetime.now(timezone.utc)
        )
        equipment = (
            db.session.execute(
                db.select(MeasurementEquipment)
                .where(MeasurementEquipment.id == equipment_id)
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if equipment is None:
            raise MsaNotFound(
                "MSA_EQUIPMENT_NOT_FOUND",
                "找不到指定的量測設備",
                details={"equipment_id": equipment_id},
            )
        if equipment.status != expected_status:
            raise MsaConflict(
                "MSA_EQUIPMENT_STATUS_CONFLICT",
                "設備狀態已變更，請重新載入後再建立事件",
                details={
                    "expected_status": expected_status,
                    "actual_status": equipment.status,
                },
            )
        event = EquipmentStatusEvent(
            equipment_id=equipment_id,
            event_type=event_type,
            occurred_at=occurred_at,
            reason=reason,
            created_by=actor_id,
            triggers_msa_restudy=triggers,
        )
        equipment.status = target_status
        equipment.updated_by = actor_id
        try:
            db.session.add(event)
            db.session.flush()
            result = MsaEquipmentService._status_event_to_dict(event)
            result["previous_status"] = expected_status
            result["target_status"] = target_status
            log_audit(
                actor_id,
                "create_status_event",
                "msa_equipment",
                event.id,
                old_val={
                    "equipment_id": equipment.id,
                    "status": expected_status,
                },
                new_val={
                    "equipment_id": equipment.id,
                    "status": target_status,
                    "event": result,
                },
            )
            db.session.commit()
            return result
        except (DataError, IntegrityError, ValueError) as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_STATUS_EVENT_INVALID",
                "設備狀態事件不符合資料庫限制",
                details={"reason": str(error)},
            ) from error

    @staticmethod
    def create_link(equipment_id: int, payload, actor_id: int) -> dict:
        """以 expected_current_link_id 受控切換 CQI-9 正式來源連結。"""
        MsaEquipmentService._get_equipment(equipment_id)
        payload = MsaEquipmentService._require_object(payload)
        unknown = set(payload) - {
            "source_module",
            "source_entity_type",
            "source_entity_id",
            "is_current",
            "expected_current_link_id",
        }
        MsaEquipmentService._reject_unknown_fields(unknown)
        source_module = MsaEquipmentService._required_text(
            payload, "source_module", max_length=50
        )
        source_entity_type = MsaEquipmentService._required_text(
            payload, "source_entity_type", max_length=80
        )
        source_entity_id = MsaEquipmentService._positive_int(
            payload.get("source_entity_id"),
            field="source_entity_id",
        )
        source_model = _SOURCE_ENTITY_MODELS.get(
            (source_module, source_entity_type)
        )
        if source_model is None:
            raise MsaValidationError(
                "MSA_SOURCE_ENTITY_TYPE_INVALID",
                "來源實體必須使用現行 CQI-9 Recorder 或 Thermocouple 名稱",
                details={
                    "source_module": source_module,
                    "source_entity_type": source_entity_type,
                },
            )
        if db.session.get(source_model, source_entity_id) is None:
            raise MsaNotFound(
                "MSA_SOURCE_ENTITY_NOT_FOUND",
                "找不到指定的 CQI-9 來源實體",
                details={
                    "source_entity_type": source_entity_type,
                    "source_entity_id": source_entity_id,
                },
            )
        is_current = payload.get("is_current", True)
        if not isinstance(is_current, bool):
            raise MsaValidationError(
                "MSA_SOURCE_LINK_STATUS_INVALID",
                "is_current 必須是布林值",
            )

        current_link = None
        previous_current_value = None
        if is_current:
            if "expected_current_link_id" not in payload:
                raise MsaValidationError(
                    "MSA_SOURCE_LINK_EXPECTED_ID_REQUIRED",
                    "建立正式連結必須提供 expected_current_link_id",
                )
            current_link = (
                db.session.execute(
                    db.select(MeasurementEquipmentLink)
                    .where(
                        MeasurementEquipmentLink.source_module
                        == source_module,
                        MeasurementEquipmentLink.source_entity_type
                        == source_entity_type,
                        MeasurementEquipmentLink.source_entity_id
                        == source_entity_id,
                        MeasurementEquipmentLink.is_current.is_(True),
                    )
                    .with_for_update()
                )
                .scalar_one_or_none()
            )
            expected_id = payload.get("expected_current_link_id")
            actual_id = current_link.id if current_link else None
            if expected_id != actual_id:
                raise MsaConflict(
                    "MSA_SOURCE_LINK_VERSION_CONFLICT",
                    "來源正式連結已變更，請重新載入後再切換",
                    details={
                        "expected_current_link_id": expected_id,
                        "actual_current_link_id": actual_id,
                    },
                )
            if current_link and current_link.equipment_id == equipment_id:
                raise MsaConflict(
                    "MSA_SOURCE_LINK_ALREADY_CURRENT",
                    "來源實體已正式連結至此設備",
                    details={"link_id": current_link.id},
                )
            if current_link:
                previous_current_value = MsaEquipmentService._link_to_dict(
                    current_link
                )
                current_link.is_current = False

        link = MeasurementEquipmentLink(
            equipment_id=equipment_id,
            source_module=source_module,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            is_current=is_current,
        )
        try:
            db.session.add(link)
            db.session.flush()
            result = MsaEquipmentService._link_to_dict(link)
            log_audit(
                actor_id,
                "create_link",
                "msa_equipment",
                link.id,
                old_val=previous_current_value,
                new_val=result,
            )
            db.session.commit()
            return result
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_DATABASE_VALUE_INVALID",
                "來源連結欄位不符合資料庫長度或格式限制",
                details={},
            ) from error
        except IntegrityError as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_SOURCE_LINK_VERSION_CONFLICT",
                "同一來源實體只能有一個目前正式連結",
                details={
                    "source_module": source_module,
                    "source_entity_type": source_entity_type,
                    "source_entity_id": source_entity_id,
                },
            ) from error

    @staticmethod
    def retire_link(
        equipment_id: int,
        link_id: int,
        payload,
        actor_id: int,
    ) -> dict:
        """以 expected id/status 將目前正式來源連結退役。"""
        payload = MsaEquipmentService._require_object(payload)
        MsaEquipmentService._reject_unknown_fields(
            set(payload) - {"expected_link_id", "expected_status"}
        )
        expected_link_id = MsaEquipmentService._positive_int(
            payload.get("expected_link_id"),
            field="expected_link_id",
        )
        expected_status = payload.get("expected_status")
        if expected_link_id != link_id or expected_status != "current":
            raise MsaConflict(
                "MSA_SOURCE_LINK_VERSION_CONFLICT",
                "來源連結識別或預期狀態不一致",
                details={
                    "path_link_id": link_id,
                    "expected_link_id": expected_link_id,
                    "expected_status": expected_status,
                },
            )
        link = (
            db.session.execute(
                db.select(MeasurementEquipmentLink)
                .where(
                    MeasurementEquipmentLink.id == link_id,
                    MeasurementEquipmentLink.equipment_id == equipment_id,
                )
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if link is None:
            raise MsaNotFound(
                "MSA_SOURCE_LINK_NOT_FOUND",
                "找不到指定的設備來源連結",
                details={
                    "equipment_id": equipment_id,
                    "link_id": link_id,
                },
            )
        if not link.is_current:
            raise MsaConflict(
                "MSA_SOURCE_LINK_VERSION_CONFLICT",
                "來源連結已不是目前正式狀態",
                details={"actual_status": "retired"},
            )
        old_value = MsaEquipmentService._link_to_dict(link)
        link.is_current = False
        try:
            db.session.flush()
            result = MsaEquipmentService._link_to_dict(link)
            log_audit(
                actor_id,
                "retire_link",
                "msa_equipment",
                link.id,
                old_val=old_value,
                new_val=result,
            )
            db.session.commit()
            return result
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_DATABASE_VALUE_INVALID",
                "來源連結欄位不符合資料庫長度或格式限制",
                details={},
            ) from error
        except IntegrityError as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_SOURCE_LINK_VERSION_CONFLICT",
                "來源連結已變更，請重新載入後再退役",
                details={"link_id": link_id},
            ) from error

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

        record = MsaEquipmentService._latest_approved_calibration(
            equipment.id, on_date
        )
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
            limitation = (record.restriction_conditions or "").strip()
            if not limitation:
                MsaEquipmentService._raise_validation(
                    "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED",
                    "受限校驗缺少完整限制條件",
                    calibration_record_id=record.id,
                )
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
        record = None
        if eligibility.calibration_record_id is not None:
            record = MsaEquipmentService._approved_calibration_by_id(
                equipment.id,
                eligibility.calibration_record_id,
                on_date,
            )
            if record is None:
                MsaEquipmentService._raise_validation(
                    "MSA_EQUIPMENT_CALIBRATION_MISSING",
                    "資格判定後校驗證據已不可用，拒絕建立快照",
                    calibration_record_id=eligibility.calibration_record_id,
                )
        return EquipmentSnapshot(
            equipment_id=equipment.id,
            equipment_no=equipment.equipment_no,
            name=equipment.name,
            status=equipment.status,
            resolution=MsaEquipmentService._canonical_value(
                equipment.resolution
            ),
            unit=equipment.unit,
            calibration=MsaEquipmentService._calibration_snapshot(
                equipment, record
            ),
        )

    @staticmethod
    def _equipment_to_dict(equipment: MeasurementEquipment) -> dict:
        return {
            "id": equipment.id,
            "equipment_no": equipment.equipment_no,
            "name": equipment.name,
            "equipment_type": equipment.equipment_type,
            "manufacturer": equipment.manufacturer,
            "model": equipment.model,
            "serial_no": equipment.serial_no,
            "range_min": MsaEquipmentService._canonical_value(
                equipment.range_min
            ),
            "range_max": MsaEquipmentService._canonical_value(
                equipment.range_max
            ),
            "resolution": MsaEquipmentService._canonical_value(
                equipment.resolution
            ),
            "unit": equipment.unit,
            "department": equipment.department,
            "location": equipment.location,
            "custodian": equipment.custodian,
            "status": equipment.status,
            "calibration_type": equipment.calibration_type,
            "calibration_exemption_reason": (
                equipment.calibration_exemption_reason
            ),
            "calibration_interval_months": (
                equipment.calibration_interval_months
            ),
            "is_reference_standard": equipment.is_reference_standard,
            "affects_product_decision": equipment.affects_product_decision,
            "created_by": equipment.created_by,
            "created_at": MsaEquipmentService._canonical_value(
                equipment.created_at
            ),
            "updated_by": equipment.updated_by,
            "updated_at": MsaEquipmentService._canonical_value(
                equipment.updated_at
            ),
        }

    @staticmethod
    def _equipment_summary_to_dict(
        equipment: MeasurementEquipment,
        calibration: EquipmentCalibrationRecord | None,
        *,
        as_of: date,
    ) -> dict:
        """輸出清單所需校驗摘要，不觸發 ORM 關聯查詢。"""
        data = MsaEquipmentService._equipment_to_dict(equipment)
        exemption_reason = (
            equipment.calibration_exemption_reason or ""
        ).strip()
        if equipment.calibration_type == "exempt" and exemption_reason:
            summary_status = "exempt"
            next_calibration_date = None
            block_reason = None
        elif calibration is None:
            summary_status = "missing"
            next_calibration_date = None
            block_reason = "尚無已核准校驗紀錄"
        else:
            next_calibration_date = MsaEquipmentService._canonical_value(
                calibration.next_due_date
            )
            if calibration.result not in {"pass", "limited_use"}:
                summary_status = "failed"
                result_label = {
                    "fail": "失敗",
                    "pending": "待確認",
                }.get(calibration.result, calibration.result)
                block_reason = f"最新已核准校驗結果為{result_label}"
            elif calibration.next_due_date is None:
                summary_status = "missing"
                block_reason = "最新已核准校驗紀錄缺少下次校驗日"
            elif (
                calibration.next_due_date < as_of
            ):
                summary_status = "expired"
                block_reason = (
                    f"校驗已於 {calibration.next_due_date.isoformat()} 到期"
                )
            elif (
                calibration.next_due_date <= as_of + timedelta(days=30)
            ):
                summary_status = "due_soon"
                block_reason = None
            else:
                summary_status = "valid"
                block_reason = None
        data.update(
            {
                "calibration_status": summary_status,
                "next_calibration_date": next_calibration_date,
                "calibration_block_reason": block_reason,
            }
        )
        return data

    @staticmethod
    def _calibration_to_dict(record: EquipmentCalibrationRecord) -> dict:
        points = (
            EquipmentCorrectionPoint.query
            .filter_by(calibration_record_id=record.id)
            .order_by(EquipmentCorrectionPoint.id.asc())
            .all()
        )
        return {
            "id": record.id,
            "equipment_id": record.equipment_id,
            "calibration_type": record.calibration_type,
            "calibration_date": MsaEquipmentService._canonical_value(
                record.calibration_date
            ),
            "effective_date": MsaEquipmentService._canonical_value(
                record.effective_date
            ),
            "next_due_date": MsaEquipmentService._canonical_value(
                record.next_due_date
            ),
            "calibration_provider": record.calibration_provider,
            "certificate_no": record.certificate_no,
            "traceability_standard": record.traceability_standard,
            "uncertainty_statement": record.uncertainty_statement,
            "result": record.result,
            "applicable_modes": list(record.applicable_modes or []),
            "restriction_conditions": record.restriction_conditions,
            "approval_reason": record.approval_reason,
            "certificate_attachment_id": record.certificate_attachment_id,
            "status": record.status,
            "created_by": record.created_by,
            "created_at": MsaEquipmentService._canonical_value(
                record.created_at
            ),
            "approved_by": record.approved_by,
            "approved_at": MsaEquipmentService._canonical_value(
                record.approved_at
            ),
            "correction_points": [
                MsaEquipmentService._correction_point_to_dict(point)
                for point in points
            ],
        }

    @staticmethod
    def _correction_point_to_dict(point: EquipmentCorrectionPoint) -> dict:
        return {
            "id": point.id,
            "measurement_mode": point.measurement_mode,
            "nominal_value": MsaEquipmentService._canonical_value(
                point.nominal_value
            ),
            "indicated_value": MsaEquipmentService._canonical_value(
                point.indicated_value
            ),
            "error_value": MsaEquipmentService._canonical_value(
                point.error_value
            ),
            "correction_value": MsaEquipmentService._canonical_value(
                point.correction_value
            ),
            "unit": point.unit,
            "range_start": MsaEquipmentService._canonical_value(
                point.range_start
            ),
            "range_end": MsaEquipmentService._canonical_value(
                point.range_end
            ),
        }

    @staticmethod
    def _status_event_to_dict(event: EquipmentStatusEvent) -> dict:
        return {
            "id": event.id,
            "equipment_id": event.equipment_id,
            "event_type": event.event_type,
            "occurred_at": MsaEquipmentService._canonical_value(
                event.occurred_at
            ),
            "reason": event.reason,
            "created_by": event.created_by,
            "triggers_msa_restudy": event.triggers_msa_restudy,
        }

    @staticmethod
    def _link_to_dict(link: MeasurementEquipmentLink) -> dict:
        return {
            "id": link.id,
            "equipment_id": link.equipment_id,
            "source_module": link.source_module,
            "source_entity_type": link.source_entity_type,
            "source_entity_id": link.source_entity_id,
            "is_current": link.is_current,
            "status": "current" if link.is_current else "retired",
        }

    @staticmethod
    def _normalise_equipment_payload(payload, *, creating: bool) -> dict:
        payload = MsaEquipmentService._require_object(payload)
        allowed = _EQUIPMENT_FIELDS if creating else _EQUIPMENT_PATCH_FIELDS
        MsaEquipmentService._reject_unknown_fields(set(payload) - allowed)
        data = {}
        if creating:
            data["equipment_no"] = MsaEquipmentService._required_text(
                payload,
                "equipment_no",
                max_length=_EQUIPMENT_TEXT_LIMITS["equipment_no"],
            )
            data["name"] = MsaEquipmentService._required_text(
                payload,
                "name",
                max_length=_EQUIPMENT_TEXT_LIMITS["name"],
            )
        elif "name" in payload:
            data["name"] = MsaEquipmentService._required_text(
                payload,
                "name",
                max_length=_EQUIPMENT_TEXT_LIMITS["name"],
            )

        for field in allowed - {"equipment_no", "name"}:
            if field not in payload:
                continue
            value = payload[field]
            if field in _EQUIPMENT_NUMERIC_FIELDS:
                data[field] = MsaEquipmentService._decimal_or_none(
                    value, field=field
                )
            elif field in _EQUIPMENT_BOOLEAN_FIELDS:
                if not isinstance(value, bool):
                    raise MsaValidationError(
                        "MSA_EQUIPMENT_FIELD_INVALID",
                        f"{field} 必須是布林值",
                        details={"field": field},
                    )
                data[field] = value
            elif field == "calibration_interval_months":
                data[field] = (
                    None
                    if value is None
                    else MsaEquipmentService._positive_int(
                        value, field=field
                    )
                )
            elif field in {
                "status",
                "calibration_type",
            }:
                data[field] = MsaEquipmentService._optional_text(
                    value,
                    field=field,
                    max_length=_EQUIPMENT_TEXT_LIMITS[field],
                )
            elif field in _EQUIPMENT_TEXT_LIMITS:
                data[field] = MsaEquipmentService._optional_text(
                    value,
                    field=field,
                    max_length=_EQUIPMENT_TEXT_LIMITS[field],
                )
            else:
                data[field] = MsaEquipmentService._optional_text(
                    value,
                    field=field,
                )

        status = data.get("status")
        if status is not None and status not in _EQUIPMENT_STATUS:
            raise MsaValidationError(
                "MSA_EQUIPMENT_STATUS_INVALID",
                "設備狀態不在允許清單",
                details={"status": status},
            )
        calibration_type = data.get("calibration_type")
        if (
            calibration_type is not None
            and calibration_type not in _CALIBRATION_TYPES
        ):
            raise MsaValidationError(
                "MSA_CALIBRATION_TYPE_INVALID",
                "校驗類別不在允許清單",
                details={"calibration_type": calibration_type},
            )
        effective_calibration_type = data.get("calibration_type")
        if creating and "calibration_type" not in data:
            effective_calibration_type = None
        if effective_calibration_type == "exempt":
            reason = data.get("calibration_exemption_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise MsaValidationError(
                    "MSA_EQUIPMENT_EXEMPTION_REASON_MISSING",
                    "校驗豁免設備必須保存完整豁免理由",
                )
        if (
            data.get("range_min") is not None
            and data.get("range_max") is not None
            and data["range_min"] > data["range_max"]
        ):
            raise MsaValidationError(
                "MSA_EQUIPMENT_RANGE_INVALID",
                "量程下限不得大於量程上限",
            )
        return data

    @staticmethod
    def _normalise_calibration_payload(payload) -> tuple[dict, list[dict]]:
        payload = MsaEquipmentService._require_object(payload)
        MsaEquipmentService._reject_unknown_fields(
            set(payload) - _CALIBRATION_FIELDS
        )
        calibration_type = MsaEquipmentService._required_text(
            payload,
            "calibration_type",
            max_length=_CALIBRATION_TEXT_LIMITS["calibration_type"],
        )
        if calibration_type not in _CALIBRATION_TYPES:
            raise MsaValidationError(
                "MSA_CALIBRATION_TYPE_INVALID",
                "校驗類型不在允許清單",
                details={"calibration_type": calibration_type},
            )
        result = MsaEquipmentService._required_text(
            payload,
            "result",
            max_length=_CALIBRATION_TEXT_LIMITS["result"],
        )
        if result not in _CALIBRATION_RESULTS:
            raise MsaValidationError(
                "MSA_CALIBRATION_RESULT_INVALID",
                "校驗結果不在允許清單",
                details={"result": result},
            )
        modes = payload.get("applicable_modes", [])
        normalised_modes = MsaEquipmentService._normalise_applicable_modes(
            modes
        )
        if modes and not normalised_modes:
            raise MsaValidationError(
                "MSA_CALIBRATION_MODES_INVALID",
                "適用量測模式必須是非空白文字陣列",
            )
        restriction = MsaEquipmentService._optional_text(
            payload.get("restriction_conditions")
        )
        if result == "limited_use" and (
            not normalised_modes or not restriction
        ):
            raise MsaValidationError(
                "MSA_CALIBRATION_LIMITED_USE_INVALID",
                "受限使用校驗必須提供適用量測模式與限制條件",
            )
        attachment_id = payload.get("certificate_attachment_id")
        if attachment_id is not None:
            attachment_id = MsaEquipmentService._positive_int(
                attachment_id,
                field="certificate_attachment_id",
            )
        data = {
            "calibration_type": calibration_type,
            "calibration_date": MsaEquipmentService._parse_date(
                payload.get("calibration_date"),
                field="calibration_date",
                required=True,
            ),
            "effective_date": MsaEquipmentService._parse_date(
                payload.get("effective_date"),
                field="effective_date",
                required=False,
            ),
            "next_due_date": MsaEquipmentService._parse_date(
                payload.get("next_due_date"),
                field="next_due_date",
                required=False,
            ),
            "calibration_provider": MsaEquipmentService._optional_text(
                payload.get("calibration_provider"),
                field="calibration_provider",
                max_length=_CALIBRATION_TEXT_LIMITS[
                    "calibration_provider"
                ],
            ),
            "certificate_no": MsaEquipmentService._optional_text(
                payload.get("certificate_no"),
                field="certificate_no",
                max_length=_CALIBRATION_TEXT_LIMITS["certificate_no"],
            ),
            "traceability_standard": MsaEquipmentService._optional_text(
                payload.get("traceability_standard")
            ),
            "uncertainty_statement": MsaEquipmentService._optional_text(
                payload.get("uncertainty_statement")
            ),
            "result": result,
            "applicable_modes": list(normalised_modes),
            "restriction_conditions": restriction,
            "certificate_attachment_id": attachment_id,
        }
        raw_points = payload.get("correction_points", [])
        if not isinstance(raw_points, list):
            raise MsaValidationError(
                "MSA_CORRECTION_POINT_INVALID",
                "correction_points 必須是陣列",
            )
        points = [
            MsaEquipmentService._normalise_correction_point(point, index)
            for index, point in enumerate(raw_points)
        ]
        return data, points

    @staticmethod
    def _normalise_correction_point(payload, index: int) -> dict:
        if not isinstance(payload, dict):
            raise MsaValidationError(
                "MSA_CORRECTION_POINT_INVALID",
                "補正點必須是 JSON 物件",
                details={"index": index},
            )
        unknown = set(payload) - _CORRECTION_POINT_FIELDS
        if unknown:
            raise MsaValidationError(
                "MSA_CORRECTION_POINT_INVALID",
                "補正點包含不支援欄位",
                details={"index": index, "fields": sorted(unknown)},
            )
        for required in ("nominal_value", "indicated_value"):
            if payload.get(required) is None:
                raise MsaValidationError(
                    "MSA_CORRECTION_POINT_INVALID",
                    "補正點缺少必要數值",
                    details={"index": index, "field": required},
                )
        result = {}
        for field in _CORRECTION_NUMERIC_FIELDS:
            result[field] = MsaEquipmentService._decimal_or_none(
                payload.get(field),
                field=field,
                error_code="MSA_CORRECTION_POINT_INVALID",
                details={"index": index},
            )
        for field in ("measurement_mode", "unit"):
            result[field] = MsaEquipmentService._optional_text(
                payload.get(field),
                field=field,
                max_length=_CORRECTION_TEXT_LIMITS[field],
            )
        if (
            result["range_start"] is not None
            and result["range_end"] is not None
            and result["range_start"] > result["range_end"]
        ):
            raise MsaValidationError(
                "MSA_CORRECTION_POINT_INVALID",
                "補正點適用量程起點不得大於終點",
                details={"index": index},
            )
        return result

    @staticmethod
    def _require_object(payload) -> dict:
        if not isinstance(payload, dict):
            raise MsaValidationError(
                "MSA_PAYLOAD_INVALID", "請求內容必須是 JSON 物件"
            )
        return payload

    @staticmethod
    def _required_text(
        payload: dict,
        field: str,
        *,
        max_length: int | None = None,
    ) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise MsaValidationError(
                "MSA_REQUIRED_FIELD_MISSING",
                f"{field} 為必填欄位",
                details={"field": field},
            )
        normalised = value.strip()
        MsaEquipmentService._validate_text_length(
            normalised,
            field=field,
            max_length=max_length,
        )
        return normalised

    @staticmethod
    def _optional_text(
        value,
        *,
        field: str = "value",
        max_length: int | None = None,
    ):
        if value is None:
            return None
        if not isinstance(value, str):
            raise MsaValidationError(
                "MSA_FIELD_INVALID",
                f"{field} 必須是文字或 null",
                details={"field": field},
            )
        normalised = value.strip() or None
        if normalised is not None:
            MsaEquipmentService._validate_text_length(
                normalised,
                field=field,
                max_length=max_length,
            )
        return normalised

    @staticmethod
    def _validate_text_length(
        value: str,
        *,
        field: str,
        max_length: int | None,
    ) -> None:
        if max_length is not None and len(value) > max_length:
            raise MsaValidationError(
                "MSA_FIELD_TOO_LONG",
                f"{field} 超過允許長度",
                details={
                    "field": field,
                    "max_length": max_length,
                },
            )

    @staticmethod
    def _validate_equipment_patch_invariants(
        equipment: MeasurementEquipment,
        data: dict,
    ) -> None:
        """以資料庫現值與 PATCH 欄位共同驗證跨欄位限制。"""
        range_min = data.get("range_min", equipment.range_min)
        range_max = data.get("range_max", equipment.range_max)
        if (
            range_min is not None
            and range_max is not None
            and range_min > range_max
        ):
            raise MsaValidationError(
                "MSA_EQUIPMENT_RANGE_INVALID",
                "量程下限不得大於量程上限",
            )
        calibration_type = data.get(
            "calibration_type",
            equipment.calibration_type,
        )
        exemption_reason = data.get(
            "calibration_exemption_reason",
            equipment.calibration_exemption_reason,
        )
        if calibration_type == "exempt" and (
            not isinstance(exemption_reason, str)
            or not exemption_reason.strip()
        ):
            raise MsaValidationError(
                "MSA_EQUIPMENT_EXEMPTION_REASON_MISSING",
                "校驗豁免設備必須保存完整豁免理由",
            )

    @staticmethod
    def _lock_certificate_attachment(
        attachment_id: int,
    ) -> Attachment:
        attachment = (
            db.session.execute(
                db.select(Attachment)
                .where(Attachment.id == attachment_id)
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if attachment is None:
            raise MsaNotFound(
                "MSA_CERTIFICATE_ATTACHMENT_NOT_FOUND",
                "找不到指定的校驗證書附件",
                details={"attachment_id": attachment_id},
            )
        return attachment

    @staticmethod
    def _validate_staged_certificate_ownership(
        attachment: Attachment,
        *,
        equipment_id: int,
        calibration_id: int | None,
    ) -> None:
        belongs_to_equipment = (
            attachment.entity_type == "measurement_equipment"
            and attachment.entity_id == equipment_id
        )
        belongs_to_calibration = (
            calibration_id is not None
            and attachment.entity_type == "equipment_calibration"
            and attachment.entity_id == calibration_id
        )
        if belongs_to_equipment or belongs_to_calibration:
            return
        raise MsaValidationError(
            "MSA_CERTIFICATE_ATTACHMENT_OWNERSHIP_INVALID",
            "校驗證書附件不屬於此設備或校驗草稿",
            details={
                "attachment_id": attachment.id,
                "actual_entity_type": attachment.entity_type,
                "actual_entity_id": attachment.entity_id,
                "expected_equipment_id": equipment_id,
                "expected_calibration_id": calibration_id,
            },
        )

    @staticmethod
    def _reject_unknown_fields(unknown: set) -> None:
        if unknown:
            raise MsaValidationError(
                "MSA_UNKNOWN_FIELDS",
                "請求包含不支援欄位",
                details={"fields": sorted(unknown)},
            )

    @staticmethod
    def _parse_bounded_int(
        value,
        *,
        field: str,
        minimum: int,
        maximum: int | None,
        code: str,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise MsaServiceError(
                code,
                f"{field} 必須是整數",
                details={"field": field, "value": value},
            ) from error
        if parsed < minimum or (maximum is not None and parsed > maximum):
            raise MsaServiceError(
                code,
                f"{field} 超出允許範圍",
                details={
                    "field": field,
                    "minimum": minimum,
                    "maximum": maximum,
                    "value": parsed,
                },
            )
        return parsed

    @staticmethod
    def _parse_iso_date_argument(
        value,
        *,
        field: str,
        default: date,
        code: str,
    ) -> date:
        if value in (None, ""):
            return default
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError) as error:
            raise MsaServiceError(
                code,
                f"{field} 必須是 ISO 日期",
                details={"field": field, "value": value},
            ) from error

    @staticmethod
    def _positive_int(value, *, field: str) -> int:
        try:
            if isinstance(value, bool):
                raise ValueError
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise MsaValidationError(
                "MSA_FIELD_INVALID",
                f"{field} 必須是正整數",
                details={"field": field},
            ) from error
        if parsed <= 0:
            raise MsaValidationError(
                "MSA_FIELD_INVALID",
                f"{field} 必須是正整數",
                details={"field": field},
            )
        return parsed

    @staticmethod
    def _decimal_or_none(
        value,
        *,
        field: str,
        error_code: str = "MSA_EQUIPMENT_FIELD_INVALID",
        details=None,
    ):
        if value is None or value == "":
            return None
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as error:
            error_details = {"field": field}
            error_details.update(details or {})
            raise MsaValidationError(
                error_code,
                f"{field} 必須是有效數值",
                details=error_details,
            ) from error
        if not decimal_value.is_finite():
            error_details = {"field": field}
            error_details.update(details or {})
            raise MsaValidationError(
                error_code,
                f"{field} 必須是有限數值",
                details=error_details,
            )
        return decimal_value

    @staticmethod
    def _parse_date(value, *, field: str, required: bool):
        if value in (None, ""):
            if required:
                raise MsaValidationError(
                    "MSA_REQUIRED_FIELD_MISSING",
                    f"{field} 為必填欄位",
                    details={"field": field},
                )
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            raise MsaValidationError(
                "MSA_DATE_INVALID",
                f"{field} 必須是 ISO 日期",
                details={"field": field},
            )
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise MsaValidationError(
                "MSA_DATE_INVALID",
                f"{field} 必須是 ISO 日期",
                details={"field": field, "value": value},
            ) from error

    @staticmethod
    def _parse_datetime(value, *, field: str):
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise MsaValidationError(
                    "MSA_DATETIME_INVALID",
                    f"{field} 必須是 ISO 日期時間",
                    details={"field": field, "value": value},
                ) from error
        else:
            raise MsaValidationError(
                "MSA_DATETIME_INVALID",
                f"{field} 必須是 ISO 日期時間",
                details={"field": field},
            )
        if parsed.tzinfo is None:
            raise MsaValidationError(
                "MSA_DATETIME_TIMEZONE_REQUIRED",
                f"{field} 必須包含時區",
                details={"field": field},
            )
        return parsed

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
        on_date: date,
    ) -> EquipmentCalibrationRecord | None:
        return (
            EquipmentCalibrationRecord.query
            .filter_by(equipment_id=equipment_id, status="approved")
            .filter(EquipmentCalibrationRecord.calibration_date <= on_date)
            .filter(
                or_(
                    EquipmentCalibrationRecord.effective_date.is_(None),
                    EquipmentCalibrationRecord.effective_date <= on_date,
                )
            )
            .order_by(
                EquipmentCalibrationRecord.calibration_date.desc(),
                EquipmentCalibrationRecord.id.desc(),
            )
            .first()
        )

    @staticmethod
    def _approved_calibration_by_id(
        equipment_id: int,
        calibration_record_id: int,
        on_date: date,
    ) -> EquipmentCalibrationRecord | None:
        return (
            db.session.execute(
                db.select(EquipmentCalibrationRecord).where(
                    EquipmentCalibrationRecord.id == calibration_record_id,
                    EquipmentCalibrationRecord.equipment_id == equipment_id,
                    EquipmentCalibrationRecord.status == "approved",
                    EquipmentCalibrationRecord.calibration_date <= on_date,
                    or_(
                        EquipmentCalibrationRecord.effective_date.is_(None),
                        EquipmentCalibrationRecord.effective_date <= on_date,
                    ),
                )
            )
            .scalar_one_or_none()
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
                "exemption_reason": (
                    equipment.calibration_exemption_reason or ""
                ).strip(),
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
            "calibration_date": MsaEquipmentService._canonical_value(
                record.calibration_date
            ),
            "effective_date": MsaEquipmentService._canonical_value(
                record.effective_date
            ),
            "next_due_date": MsaEquipmentService._canonical_value(
                record.next_due_date
            ),
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
                    "nominal_value": MsaEquipmentService._canonical_value(
                        point.nominal_value
                    ),
                    "indicated_value": MsaEquipmentService._canonical_value(
                        point.indicated_value
                    ),
                    "error_value": MsaEquipmentService._canonical_value(
                        point.error_value
                    ),
                    "correction_value": MsaEquipmentService._canonical_value(
                        point.correction_value
                    ),
                    "unit": point.unit,
                    "range_start": MsaEquipmentService._canonical_value(
                        point.range_start
                    ),
                    "range_end": MsaEquipmentService._canonical_value(
                        point.range_end
                    ),
                }
                for point in correction_points
            ],
        }

    @staticmethod
    def _canonical_value(value):
        """轉換為標準 json.dumps 可直接保存的穩定純量。"""
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, list):
            return [MsaEquipmentService._canonical_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): MsaEquipmentService._canonical_value(value[key])
                for key in sorted(value)
            }
        return value

    @staticmethod
    def _raise_validation(code: str, message: str, **details) -> None:
        raise MsaValidationError(code, message, details=details)
