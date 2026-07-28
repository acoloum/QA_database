"""受控校正模板、逐點規則與版本核准工作流。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re

from sqlalchemy import func
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    utc_now,
)
from ..utils import log_audit
from .calibration_errors import (
    CalibrationConflict,
    CalibrationForbidden,
    CalibrationNotFound,
    CalibrationServiceError,
    CalibrationValidationError,
)


VERSION_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"approved", "rejected"},
    "approved": {"superseded"},
    "rejected": set(),
    "superseded": set(),
}

REFERENCE_INPUT_MODES = {"certified_value", "paired_reading"}
EVALUATION_BASES = {"all_readings", "mean_error"}
REPEATABILITY_RULES = {"none", "range", "stddev"}

_MAX_PAGE = 10_000
_MAX_PAGE_SIZE = 100
_MAX_POINTS = 500
_MAX_POINT_ORDER = 10_000
_MAX_REPETITIONS = 100
_MAX_INTEGER = 2_147_483_647
_MAX_SIGNIFICANT_DIGITS = 50
_MAX_DECIMAL_EXPONENT = 1_000

_TEMPLATE_FIELDS = {
    "template_code",
    "name",
    "equipment_type",
    "description",
}
_VERSION_FIELDS = {
    "procedure_code",
    "procedure_name",
    "procedure_description",
    "default_repetitions",
    "environment_requirements",
    "allow_limited_use",
    "revision_reason",
    "points",
}
_UPDATE_VERSION_FIELDS = _VERSION_FIELDS | {"expected_version"}
_DECISION_FIELDS = {"expected_version", "reason"}
_POINT_FIELDS = {
    "point_order",
    "point_code",
    "measurement_mode",
    "nominal_value",
    "unit",
    "reference_input_mode",
    "required_repetitions",
    "error_lower_limit",
    "error_upper_limit",
    "evaluation_basis",
    "repeatability_rule",
    "repeatability_limit",
    "qualification_scope_code",
    "qualification_range_start",
    "qualification_range_end",
    "uncertainty_required",
    "required",
    "instruction",
}
_LIST_FIELDS = {
    "page",
    "page_size",
    "sort",
    "order",
    "status",
    "equipment_type",
}
_SORT_FIELDS = {
    "id": CalibrationTemplate.id,
    "template_code": CalibrationTemplate.template_code,
    "name": CalibrationTemplate.name,
    "equipment_type": CalibrationTemplate.equipment_type,
}
_TEMPLATE_TEXT_LIMITS = {
    "template_code": 80,
    "name": 160,
    "equipment_type": 80,
    "description": 10_000,
}
_VERSION_TEXT_LIMITS = {
    "procedure_code": 80,
    "procedure_name": 160,
    "procedure_description": 10_000,
    "revision_reason": 2_000,
}
_POINT_TEXT_LIMITS = {
    "point_code": 80,
    "measurement_mode": 80,
    "unit": 40,
    "qualification_scope_code": 80,
    "instruction": 10_000,
}
_ENVIRONMENT_RULE_FIELDS = {
    "required",
    "minimum",
    "maximum",
    "unit",
    "instruction",
}
_STATUS_FILTERS = {"active", "inactive"}
_INTEGER_PATTERN = re.compile(r"[+-]?\d+\Z")


class CalibrationTemplateService:
    """集中處理模板驗證、交易、鎖定與穩定序列化。"""

    @staticmethod
    def list(params) -> dict:
        """以白名單排序與有界分頁列出模板。"""
        values = params or {}
        unknown = set(values.keys()) - _LIST_FIELDS
        if unknown:
            CalibrationTemplateService._unknown_fields(unknown)
        page = CalibrationTemplateService._bounded_int(
            values.get("page", 1),
            field="page",
            minimum=1,
            maximum=_MAX_PAGE,
            code="CALIBRATION_PAGE_INVALID",
        )
        page_size = CalibrationTemplateService._bounded_int(
            values.get("page_size", 25),
            field="page_size",
            minimum=1,
            maximum=_MAX_PAGE_SIZE,
            code="CALIBRATION_PAGE_SIZE_INVALID",
        )
        sort_name = values.get("sort", "template_code")
        sort_column = _SORT_FIELDS.get(sort_name)
        if sort_column is None:
            raise CalibrationValidationError(
                "CALIBRATION_SORT_INVALID",
                "不支援的模板排序欄位",
                details={
                    "sort": sort_name,
                    "allowed": sorted(_SORT_FIELDS),
                },
            )
        order = values.get("order", "asc")
        if order not in {"asc", "desc"}:
            raise CalibrationValidationError(
                "CALIBRATION_SORT_ORDER_INVALID",
                "排序方向只允許 asc 或 desc",
                details={"order": order},
            )

        statement = db.select(CalibrationTemplate)
        status = values.get("status")
        if status is not None:
            if status not in _STATUS_FILTERS:
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "status 不在允許清單",
                    details={
                        "field": "status",
                        "allowed": sorted(_STATUS_FILTERS),
                    },
                )
            statement = statement.where(CalibrationTemplate.status == status)
        equipment_type = values.get("equipment_type")
        if equipment_type is not None:
            equipment_type = CalibrationTemplateService._text(
                equipment_type,
                field="equipment_type",
                max_length=_TEMPLATE_TEXT_LIMITS["equipment_type"],
                required=True,
            )
            statement = statement.where(
                CalibrationTemplate.equipment_type == equipment_type
            )

        total = db.session.execute(
            db.select(func.count()).select_from(statement.subquery())
        ).scalar_one()
        ordering = (
            sort_column.asc() if order == "asc" else sort_column.desc()
        )
        tie_breaker = (
            CalibrationTemplate.id.asc()
            if order == "asc"
            else CalibrationTemplate.id.desc()
        )
        templates = (
            db.session.execute(
                statement.options(
                    selectinload(CalibrationTemplate.versions).selectinload(
                        CalibrationTemplateVersion.points
                    )
                )
                .order_by(ordering, tie_breaker)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return {
            "items": [
                CalibrationTemplateService.serialize_template(template)
                for template in templates
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def get(template_id: int) -> dict:
        """取得模板及所有歷史版本。"""
        template = db.session.execute(
            db.select(CalibrationTemplate)
            .where(CalibrationTemplate.id == template_id)
            .options(
                selectinload(CalibrationTemplate.versions).selectinload(
                    CalibrationTemplateVersion.points
                )
            )
        ).scalar_one_or_none()
        if template is None:
            raise CalibrationNotFound(
                "CALIBRATION_TEMPLATE_NOT_FOUND",
                "找不到校正模板",
                details={"template_id": template_id},
            )
        return CalibrationTemplateService.serialize_template(template)

    @staticmethod
    def create(payload: dict, actor_id: int) -> dict:
        """建立模板穩定識別，不允許呼叫端指定工作流欄位。"""
        data = CalibrationTemplateService._object(payload)
        CalibrationTemplateService._reject_unknown(data, _TEMPLATE_FIELDS)
        normalized = {
            field: CalibrationTemplateService._text(
                data.get(field),
                field=field,
                max_length=limit,
                required=field != "description",
            )
            for field, limit in _TEMPLATE_TEXT_LIMITS.items()
        }
        template = CalibrationTemplate(
            **normalized,
            status="active",
        )
        try:
            db.session.add(template)
            db.session.flush()
            snapshot = CalibrationTemplateService.serialize_template(
                template,
                include_versions=False,
            )
            log_audit(
                actor_id,
                "create_template",
                "calibration_template",
                template.id,
                new_val=snapshot,
            )
            db.session.commit()
            return CalibrationTemplateService.serialize_template(
                template,
                include_versions=False,
            )
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except IntegrityError as error:
            db.session.rollback()
            raise CalibrationConflict(
                "CALIBRATION_TEMPLATE_CONFLICT",
                "模板代碼已存在或資料與既有模板衝突",
                details={"template_code": normalized["template_code"]},
            ) from error
        except DataError as error:
            db.session.rollback()
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "模板欄位超過資料庫限制",
                details={},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def create_version(
        template_id: int,
        payload: dict,
        actor_id: int,
    ) -> dict:
        """鎖定模板後配置下一版號並原子保存逐點規則。"""
        data = CalibrationTemplateService._object(payload)
        CalibrationTemplateService._reject_unknown(data, _VERSION_FIELDS)
        normalized = CalibrationTemplateService._normalize_version(
            data,
            partial=False,
        )
        points = normalized.pop("points")
        try:
            template = CalibrationTemplateService._lock_template(template_id)
            if template is None:
                raise CalibrationNotFound(
                    "CALIBRATION_TEMPLATE_NOT_FOUND",
                    "找不到校正模板",
                    details={"template_id": template_id},
                )
            if template.status != "active":
                raise CalibrationConflict(
                    "CALIBRATION_STATUS_CONFLICT",
                    "停用模板不可建立新版本",
                    details={
                        "template_id": template_id,
                        "status": template.status,
                    },
                )
            latest_version = db.session.execute(
                db.select(func.max(CalibrationTemplateVersion.version_no))
                .where(CalibrationTemplateVersion.template_id == template_id)
            ).scalar_one()
            version = CalibrationTemplateVersion(
                template_id=template_id,
                version_no=(latest_version or 0) + 1,
                status="draft",
                row_version=1,
                created_by=actor_id,
                **normalized,
            )
            db.session.add(version)
            db.session.flush()
            for point_data in points:
                db.session.add(
                    CalibrationTemplatePoint(
                        template_version_id=version.id,
                        **point_data,
                    )
                )
            db.session.flush()
            snapshot = CalibrationTemplateService.serialize_version(version)
            log_audit(
                actor_id,
                "create_version",
                "calibration_template",
                version.id,
                new_val=snapshot,
            )
            db.session.commit()
            return CalibrationTemplateService.serialize_version(version)
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except IntegrityError as error:
            db.session.rollback()
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "模板版號或校正點已被其他交易建立",
                details={"template_id": template_id},
            ) from error
        except DataError as error:
            db.session.rollback()
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "模板版本欄位超過資料庫限制",
                details={},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def update_version(
        version_id: int,
        payload: dict,
        actor_id: int,
    ) -> dict:
        """以列鎖與 expected_version 原子更新 draft 版本。"""
        data = CalibrationTemplateService._object(payload)
        CalibrationTemplateService._reject_unknown(
            data,
            _UPDATE_VERSION_FIELDS,
        )
        expected_version = CalibrationTemplateService._expected_version(data)
        changes = CalibrationTemplateService._normalize_version(
            {
                key: value
                for key, value in data.items()
                if key != "expected_version"
            },
            partial=True,
        )
        replacement_points = changes.pop("points", None)
        try:
            version = CalibrationTemplateService._lock_version(version_id)
            CalibrationTemplateService._require_version(version, version_id)
            CalibrationTemplateService._check_expected_version(
                version,
                expected_version,
            )
            CalibrationTemplateService._require_status(version, "draft")
            old_snapshot = CalibrationTemplateService.serialize_version(version)
            for field, value in changes.items():
                setattr(version, field, value)
            if replacement_points is not None:
                for point in list(version.points):
                    db.session.delete(point)
                db.session.flush()
                for point_data in replacement_points:
                    db.session.add(
                        CalibrationTemplatePoint(
                            template_version_id=version.id,
                            **point_data,
                        )
                    )
                db.session.flush()
            version.row_version += 1
            db.session.flush()
            snapshot = CalibrationTemplateService.serialize_version(version)
            log_audit(
                actor_id,
                "update_version",
                "calibration_template",
                version.id,
                old_val=old_snapshot,
                new_val=snapshot,
            )
            db.session.commit()
            return CalibrationTemplateService.serialize_version(version)
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except (IntegrityError, ValueError) as error:
            db.session.rollback()
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "模板版本已被更新或校正點與既有資料衝突",
                details={"version_id": version_id},
            ) from error
        except DataError as error:
            db.session.rollback()
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "模板版本欄位超過資料庫限制",
                details={},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def submit_version(
        version_id: int,
        payload: dict,
        actor_id: int,
    ) -> dict:
        """重新驗證完整逐點證據後送審 draft。"""
        expected_version, reason = (
            CalibrationTemplateService._decision_payload(payload)
        )
        try:
            version = CalibrationTemplateService._lock_version(version_id)
            CalibrationTemplateService._require_version(version, version_id)
            CalibrationTemplateService._check_expected_version(
                version,
                expected_version,
            )
            CalibrationTemplateService._require_transition(
                version,
                "submitted",
            )
            CalibrationTemplateService._validate_persisted_points(
                version.points,
                require_required_point=True,
            )
            version.status = "submitted"
            version.submitted_by = actor_id
            version.submitted_at = utc_now()
            version.row_version += 1
            db.session.flush()
            snapshot = CalibrationTemplateService.serialize_version(version)
            audit_value = dict(snapshot)
            audit_value["reason"] = reason
            log_audit(
                actor_id,
                "submit_version",
                "calibration_template",
                version.id,
                new_val=audit_value,
            )
            db.session.commit()
            return CalibrationTemplateService.serialize_version(version)
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except (IntegrityError, ValueError) as error:
            db.session.rollback()
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "模板版本送審時已被其他交易更新",
                details={"version_id": version_id},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def approve_version(
        version_id: int,
        payload: dict,
        actor_id: int,
    ) -> dict:
        """核准 submitted 版本並在同交易受控取代舊核准版。"""
        expected_version, reason = (
            CalibrationTemplateService._decision_payload(payload)
        )
        try:
            version = CalibrationTemplateService._lock_version(version_id)
            CalibrationTemplateService._require_version(version, version_id)
            CalibrationTemplateService._check_expected_version(
                version,
                expected_version,
            )
            CalibrationTemplateService._require_transition(
                version,
                "approved",
            )
            if actor_id in {version.created_by, version.submitted_by}:
                raise CalibrationForbidden(
                    "CALIBRATION_SELF_APPROVAL_FORBIDDEN",
                    "建立或送審模板版次的人員不得核准同一版次",
                    details={
                        "version_id": version.id,
                        "created_by": version.created_by,
                        "submitted_by": version.submitted_by,
                    },
                )
            template = CalibrationTemplateService._lock_template(
                version.template_id
            )
            if template is None:
                raise CalibrationNotFound(
                    "CALIBRATION_TEMPLATE_NOT_FOUND",
                    "找不到校正模板",
                    details={"template_id": version.template_id},
                )
            old_approved = None
            if template.current_approved_version_id is not None:
                old_approved = CalibrationTemplateService._lock_version(
                    template.current_approved_version_id
                )
                if (
                    old_approved is None
                    or old_approved.template_id != template.id
                    or old_approved.status != "approved"
                ):
                    raise CalibrationConflict(
                        "CALIBRATION_STATUS_CONFLICT",
                        "模板目前核准版本指標不一致",
                        details={"template_id": template.id},
                    )

            if old_approved is not None:
                CalibrationTemplateService._require_transition(
                    old_approved,
                    "superseded",
                )
                old_approved.successor_version = version
                old_approved.status = "superseded"
                old_approved.row_version += 1
                # partial unique 要求先釋放舊 approved；仍維持同一交易，
                # 此 flush 不會讓其他交易看到半套狀態。
                db.session.flush()

            version.status = "approved"
            version.approved_by = actor_id
            version.approved_at = utc_now()
            version.approval_reason = reason
            version.rejection_reason = None
            version.row_version += 1
            template.current_approved_version_id = version.id
            db.session.flush()

            if old_approved is not None:
                log_audit(
                    actor_id,
                    "supersede_version",
                    "calibration_template",
                    old_approved.id,
                    new_val={
                        "status": old_approved.status,
                        "row_version": old_approved.row_version,
                        "successor_version_id": version.id,
                    },
                )
            snapshot = CalibrationTemplateService.serialize_version(version)
            log_audit(
                actor_id,
                "approve_version",
                "calibration_template",
                version.id,
                new_val=snapshot,
            )
            db.session.commit()
            return CalibrationTemplateService.serialize_version(version)
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except (IntegrityError, ValueError) as error:
            db.session.rollback()
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "模板版本核准時已被其他交易更新",
                details={"version_id": version_id},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def reject_version(
        version_id: int,
        payload: dict,
        actor_id: int,
    ) -> dict:
        """退回 submitted 版本並保存受控理由。"""
        expected_version, reason = (
            CalibrationTemplateService._decision_payload(payload)
        )
        try:
            version = CalibrationTemplateService._lock_version(version_id)
            CalibrationTemplateService._require_version(version, version_id)
            CalibrationTemplateService._check_expected_version(
                version,
                expected_version,
            )
            CalibrationTemplateService._require_transition(
                version,
                "rejected",
            )
            version.status = "rejected"
            version.approved_by = actor_id
            version.approved_at = utc_now()
            version.approval_reason = None
            version.rejection_reason = reason
            version.row_version += 1
            db.session.flush()
            snapshot = CalibrationTemplateService.serialize_version(version)
            log_audit(
                actor_id,
                "reject_version",
                "calibration_template",
                version.id,
                new_val=snapshot,
            )
            db.session.commit()
            return CalibrationTemplateService.serialize_version(version)
        except CalibrationServiceError:
            db.session.rollback()
            raise
        except (IntegrityError, ValueError) as error:
            db.session.rollback()
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "模板版本退回時已被其他交易更新",
                details={"version_id": version_id},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def serialize_template(
        template: CalibrationTemplate,
        *,
        include_versions: bool = True,
    ) -> dict:
        """序列化模板；Decimal 僅由版本校正點輸出穩定字串。"""
        result = {
            "id": template.id,
            "template_code": template.template_code,
            "name": template.name,
            "equipment_type": template.equipment_type,
            "description": template.description,
            "status": template.status,
            "current_approved_version_id": (
                template.current_approved_version_id
            ),
        }
        if include_versions:
            result["versions"] = [
                CalibrationTemplateService.serialize_version(version)
                for version in sorted(
                    template.versions,
                    key=lambda item: (item.version_no, item.id or 0),
                    reverse=True,
                )
            ]
        return result

    @staticmethod
    def serialize_version(version: CalibrationTemplateVersion) -> dict:
        """輸出 deterministic 版本與逐點證據。"""
        return {
            "id": version.id,
            "template_id": version.template_id,
            "version_no": version.version_no,
            "procedure_code": version.procedure_code,
            "procedure_name": version.procedure_name,
            "procedure_description": version.procedure_description,
            "default_repetitions": version.default_repetitions,
            "environment_requirements": (
                CalibrationTemplateService._canonical_json(
                    version.environment_requirements or {},
                    field="environment_requirements",
                )
            ),
            "allow_limited_use": bool(version.allow_limited_use),
            "status": version.status,
            "row_version": version.row_version,
            "revision_reason": version.revision_reason,
            "created_by": version.created_by,
            "created_at": (
                version.created_at.isoformat() if version.created_at else None
            ),
            "submitted_by": version.submitted_by,
            "submitted_at": (
                version.submitted_at.isoformat()
                if version.submitted_at
                else None
            ),
            "approved_by": version.approved_by,
            "approved_at": (
                version.approved_at.isoformat()
                if version.approved_at
                else None
            ),
            "approval_reason": version.approval_reason,
            "rejection_reason": version.rejection_reason,
            "successor_version_id": version.successor_version_id,
            "points": [
                CalibrationTemplateService.serialize_point(point)
                for point in sorted(
                    version.points,
                    key=lambda item: (item.point_order, item.id or 0),
                )
            ],
        }

    @staticmethod
    def serialize_point(point: CalibrationTemplatePoint) -> dict:
        """Decimal 不轉 float，避免正式證據出現二進位誤差。"""
        return {
            "id": point.id,
            "template_version_id": point.template_version_id,
            "point_order": point.point_order,
            "point_code": point.point_code,
            "measurement_mode": point.measurement_mode,
            "nominal_value": CalibrationTemplateService._decimal_text(
                point.nominal_value
            ),
            "unit": point.unit,
            "reference_input_mode": point.reference_input_mode,
            "required_repetitions": point.required_repetitions,
            "error_lower_limit": CalibrationTemplateService._decimal_text(
                point.error_lower_limit
            ),
            "error_upper_limit": CalibrationTemplateService._decimal_text(
                point.error_upper_limit
            ),
            "evaluation_basis": point.evaluation_basis,
            "repeatability_rule": point.repeatability_rule,
            "repeatability_limit": CalibrationTemplateService._decimal_text(
                point.repeatability_limit
            ),
            "qualification_scope_code": point.qualification_scope_code,
            "qualification_range_start": (
                CalibrationTemplateService._decimal_text(
                    point.qualification_range_start
                )
            ),
            "qualification_range_end": (
                CalibrationTemplateService._decimal_text(
                    point.qualification_range_end
                )
            ),
            "uncertainty_required": bool(point.uncertainty_required),
            "required": bool(point.required),
            "instruction": point.instruction,
        }

    @staticmethod
    def _lock_template(template_id: int) -> CalibrationTemplate | None:
        return (
            db.session.execute(
                db.select(CalibrationTemplate)
                .where(CalibrationTemplate.id == template_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            .scalar_one_or_none()
        )

    @staticmethod
    def _lock_version(
        version_id: int,
    ) -> CalibrationTemplateVersion | None:
        return (
            db.session.execute(
                db.select(CalibrationTemplateVersion)
                .where(CalibrationTemplateVersion.id == version_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            .scalar_one_or_none()
        )

    @staticmethod
    def _require_version(version, version_id: int) -> None:
        if version is None:
            raise CalibrationNotFound(
                "CALIBRATION_TEMPLATE_VERSION_NOT_FOUND",
                "找不到校正模板版本",
                details={"version_id": version_id},
            )

    @staticmethod
    def _require_status(version, expected_status: str) -> None:
        if version.status != expected_status:
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "目前模板版本狀態不允許此操作",
                details={
                    "version_id": version.id,
                    "status": version.status,
                    "expected_status": expected_status,
                },
            )

    @staticmethod
    def _require_transition(version, target_status: str) -> None:
        if target_status not in VERSION_TRANSITIONS.get(version.status, set()):
            raise CalibrationConflict(
                "CALIBRATION_STATUS_CONFLICT",
                "目前模板版本狀態不允許此轉換",
                details={
                    "version_id": version.id,
                    "status": version.status,
                    "target_status": target_status,
                },
            )

    @staticmethod
    def _check_expected_version(version, expected_version: int) -> None:
        if version.row_version != expected_version:
            raise CalibrationConflict(
                "CALIBRATION_VERSION_CONFLICT",
                "模板版本已被其他人更新，請重新載入",
                details={
                    "version_id": version.id,
                    "current_version": version.row_version,
                    "expected_version": expected_version,
                },
            )

    @staticmethod
    def _normalize_version(payload: dict, *, partial: bool) -> dict:
        result = {}
        for field, limit in _VERSION_TEXT_LIMITS.items():
            if partial and field not in payload:
                continue
            result[field] = CalibrationTemplateService._text(
                payload.get(field),
                field=field,
                max_length=limit,
                required=field in {
                    "procedure_code",
                    "procedure_name",
                    "revision_reason",
                },
            )
        if not partial or "default_repetitions" in payload:
            result["default_repetitions"] = (
                CalibrationTemplateService._bounded_int(
                    payload.get("default_repetitions"),
                    field="default_repetitions",
                    minimum=1,
                    maximum=_MAX_REPETITIONS,
                    code="CALIBRATION_FIELD_INVALID",
                )
            )
        if not partial or "environment_requirements" in payload:
            result["environment_requirements"] = (
                CalibrationTemplateService._environment_requirements(
                    payload.get("environment_requirements", {})
                )
            )
        if not partial or "allow_limited_use" in payload:
            result["allow_limited_use"] = CalibrationTemplateService._boolean(
                payload.get("allow_limited_use", False),
                field="allow_limited_use",
            )
        if not partial or "points" in payload:
            result["points"] = CalibrationTemplateService._points(
                payload.get("points", [])
            )
        return result

    @staticmethod
    def _points(value) -> list[dict]:
        if not isinstance(value, list) or len(value) > _MAX_POINTS:
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                f"points 必須是最多 {_MAX_POINTS} 項的陣列",
                details={"field": "points", "maximum": _MAX_POINTS},
            )
        normalized = [
            CalibrationTemplateService._point(point, index=index)
            for index, point in enumerate(value)
        ]
        codes = [point["point_code"] for point in normalized]
        orders = [point["point_order"] for point in normalized]
        if len(set(codes)) != len(codes):
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                "同一版本的 point_code 不可重複",
                details={"field": "point_code"},
            )
        if len(set(orders)) != len(orders):
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                "同一版本的 point_order 不可重複",
                details={"field": "point_order"},
            )
        return normalized

    @staticmethod
    def _point(value, *, index: int) -> dict:
        if not isinstance(value, dict):
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                "每個校正點必須是 JSON 物件",
                details={"field": "points", "index": index},
            )
        unknown = set(value) - _POINT_FIELDS
        if unknown:
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                "校正點包含未允許欄位",
                details={
                    "field": "points",
                    "index": index,
                    "unknown_fields": sorted(unknown),
                },
            )
        result = {
            "point_order": CalibrationTemplateService._bounded_int(
                value.get("point_order"),
                field="point_order",
                minimum=1,
                maximum=_MAX_POINT_ORDER,
                code="CALIBRATION_POINT_INVALID",
                index=index,
            ),
            "required_repetitions": (
                CalibrationTemplateService._bounded_int(
                    value.get("required_repetitions"),
                    field="required_repetitions",
                    minimum=1,
                    maximum=_MAX_REPETITIONS,
                    code="CALIBRATION_POINT_INVALID",
                    index=index,
                )
            ),
        }
        for field, limit in _POINT_TEXT_LIMITS.items():
            result[field] = CalibrationTemplateService._text(
                value.get(field),
                field=field,
                max_length=limit,
                required=field != "instruction",
                code="CALIBRATION_POINT_INVALID",
                index=index,
            )
        for field in (
            "nominal_value",
            "error_lower_limit",
            "error_upper_limit",
            "repeatability_limit",
            "qualification_range_start",
            "qualification_range_end",
        ):
            result[field] = CalibrationTemplateService._decimal(
                value.get(field),
                field=field,
                required=field == "nominal_value",
                code="CALIBRATION_POINT_INVALID",
                index=index,
            )
        result["reference_input_mode"] = (
            CalibrationTemplateService._choice(
                value.get("reference_input_mode"),
                field="reference_input_mode",
                allowed=REFERENCE_INPUT_MODES,
                index=index,
            )
        )
        result["evaluation_basis"] = CalibrationTemplateService._choice(
            value.get("evaluation_basis"),
            field="evaluation_basis",
            allowed=EVALUATION_BASES,
            index=index,
        )
        result["repeatability_rule"] = CalibrationTemplateService._choice(
            value.get("repeatability_rule"),
            field="repeatability_rule",
            allowed=REPEATABILITY_RULES,
            index=index,
        )
        result["uncertainty_required"] = (
            CalibrationTemplateService._boolean(
                value.get("uncertainty_required", False),
                field="uncertainty_required",
                code="CALIBRATION_POINT_INVALID",
                index=index,
            )
        )
        result["required"] = CalibrationTemplateService._boolean(
            value.get("required", True),
            field="required",
            code="CALIBRATION_POINT_INVALID",
            index=index,
        )
        lower = result["error_lower_limit"]
        upper = result["error_upper_limit"]
        if lower is None and upper is None:
            CalibrationTemplateService._point_error(
                "error_lower_limit",
                index,
                "校正點至少需要一個誤差界限",
            )
        if lower is not None and upper is not None and lower > upper:
            CalibrationTemplateService._point_error(
                "error_lower_limit",
                index,
                "誤差下限不得大於上限",
            )
        range_start = result["qualification_range_start"]
        range_end = result["qualification_range_end"]
        if range_start is None and range_end is not None:
            CalibrationTemplateService._point_error(
                "qualification_range_start",
                index,
                "資格範圍起點與終點必須同時提供",
            )
        if range_start is not None and range_end is None:
            CalibrationTemplateService._point_error(
                "qualification_range_end",
                index,
                "資格範圍起點與終點必須同時提供",
            )
        if (
            range_start is not None
            and range_end is not None
            and range_start > range_end
        ):
            CalibrationTemplateService._point_error(
                "qualification_range_start",
                index,
                "資格範圍起點不得大於終點",
            )
        rule = result["repeatability_rule"]
        limit = result["repeatability_limit"]
        if rule == "none" and limit is not None:
            CalibrationTemplateService._point_error(
                "repeatability_limit",
                index,
                "重複性規則為 none 時不得設定上限",
            )
        if rule in {"range", "stddev"} and (
            limit is None or limit < 0
        ):
            CalibrationTemplateService._point_error(
                "repeatability_limit",
                index,
                "range/stddev 必須搭配非負重複性上限",
            )
        if rule == "stddev" and result["required_repetitions"] < 2:
            CalibrationTemplateService._point_error(
                "required_repetitions",
                index,
                "stddev 至少需要兩次讀值",
            )
        return result

    @staticmethod
    def _validate_persisted_points(
        points,
        *,
        require_required_point: bool,
    ) -> None:
        normalized = CalibrationTemplateService._points(
            [
                {
                    field: getattr(point, field)
                    for field in _POINT_FIELDS
                }
                for point in points
            ]
        )
        if require_required_point and not any(
            point["required"] for point in normalized
        ):
            raise CalibrationValidationError(
                "CALIBRATION_REQUIRED_POINT_MISSING",
                "送審版本至少需要一個必要校正點",
                details={"field": "points"},
            )

    @staticmethod
    def _environment_requirements(value) -> dict:
        if not isinstance(value, dict) or len(value) > 20:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                "environment_requirements 必須是最多 20 項的 JSON 物件",
                details={"field": "environment_requirements"},
            )
        normalized = {}
        for raw_name, raw_rule in value.items():
            name = CalibrationTemplateService._text(
                raw_name,
                field="environment_requirements",
                max_length=80,
                required=True,
            )
            if not isinstance(raw_rule, dict):
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "每個環境要求必須是 JSON 物件",
                    details={
                        "field": "environment_requirements",
                        "requirement": name,
                    },
                )
            unknown = set(raw_rule) - _ENVIRONMENT_RULE_FIELDS
            if unknown:
                raise CalibrationValidationError(
                    "CALIBRATION_UNKNOWN_FIELDS",
                    "環境要求包含未允許欄位",
                    details={
                        "requirement": name,
                        "unknown_fields": sorted(unknown),
                    },
                )
            minimum = CalibrationTemplateService._decimal(
                raw_rule.get("minimum"),
                field="minimum",
                required=False,
            )
            maximum = CalibrationTemplateService._decimal(
                raw_rule.get("maximum"),
                field="maximum",
                required=False,
            )
            if (
                minimum is not None
                and maximum is not None
                and minimum > maximum
            ):
                raise CalibrationValidationError(
                    "CALIBRATION_FIELD_INVALID",
                    "環境要求下限不得大於上限",
                    details={
                        "field": "environment_requirements",
                        "requirement": name,
                    },
                )
            rule = {
                "required": CalibrationTemplateService._boolean(
                    raw_rule.get("required", False),
                    field="required",
                ),
                "minimum": CalibrationTemplateService._decimal_text(minimum),
                "maximum": CalibrationTemplateService._decimal_text(maximum),
                "unit": CalibrationTemplateService._text(
                    raw_rule.get("unit"),
                    field="unit",
                    max_length=40,
                    required=False,
                ),
                "instruction": CalibrationTemplateService._text(
                    raw_rule.get("instruction"),
                    field="instruction",
                    max_length=2_000,
                    required=False,
                ),
            }
            normalized[name] = rule
        return CalibrationTemplateService._canonical_json(
            normalized,
            field="environment_requirements",
        )

    @staticmethod
    def _decision_payload(payload) -> tuple[int, str]:
        data = CalibrationTemplateService._object(payload)
        CalibrationTemplateService._reject_unknown(data, _DECISION_FIELDS)
        return (
            CalibrationTemplateService._expected_version(data),
            CalibrationTemplateService._text(
                data.get("reason"),
                field="reason",
                max_length=2_000,
                required=True,
            ),
        )

    @staticmethod
    def _expected_version(payload: dict) -> int:
        return CalibrationTemplateService._bounded_int(
            payload.get("expected_version"),
            field="expected_version",
            minimum=1,
            maximum=_MAX_INTEGER,
            code="CALIBRATION_FIELD_INVALID",
        )

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
            CalibrationTemplateService._unknown_fields(unknown)

    @staticmethod
    def _unknown_fields(unknown) -> None:
        raise CalibrationValidationError(
            "CALIBRATION_UNKNOWN_FIELDS",
            "請求包含未允許欄位",
            details={"unknown_fields": sorted(unknown)},
        )

    @staticmethod
    def _text(
        value,
        *,
        field: str,
        max_length: int,
        required: bool,
        code: str = "CALIBRATION_FIELD_INVALID",
        index: int | None = None,
    ) -> str | None:
        details = {"field": field}
        if index is not None:
            details["index"] = index
        if value is None:
            if required:
                raise CalibrationValidationError(
                    code,
                    f"{field} 為必填文字欄位",
                    details=details,
                )
            return None
        if not isinstance(value, str):
            raise CalibrationValidationError(
                code,
                f"{field} 必須是文字",
                details=details,
            )
        normalized = value.strip()
        if not normalized:
            if required:
                raise CalibrationValidationError(
                    code,
                    f"{field} 不可為空白",
                    details=details,
                )
            return None
        if len(normalized) > max_length:
            details["max_length"] = max_length
            raise CalibrationValidationError(
                code,
                f"{field} 超過允許長度",
                details=details,
            )
        return normalized

    @staticmethod
    def _bounded_int(
        value,
        *,
        field: str,
        minimum: int,
        maximum: int,
        code: str,
        index: int | None = None,
    ) -> int:
        details = {
            "field": field,
            "minimum": minimum,
            "maximum": maximum,
        }
        if index is not None:
            details["index"] = index
        if isinstance(value, bool):
            raise CalibrationValidationError(
                code,
                f"{field} 必須是整數",
                details=details,
            )
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str):
            normalized = value.strip()
            if (
                len(normalized) > 20
                or _INTEGER_PATTERN.fullmatch(normalized) is None
            ):
                raise CalibrationValidationError(
                    code,
                    f"{field} 必須是有界整數",
                    details=details,
                )
            parsed = int(normalized)
        else:
            raise CalibrationValidationError(
                code,
                f"{field} 必須是整數",
                details=details,
            )
        if parsed < minimum or parsed > maximum:
            raise CalibrationValidationError(
                code,
                f"{field} 超出允許範圍",
                details=details,
            )
        return parsed

    @staticmethod
    def _decimal(
        value,
        *,
        field: str,
        required: bool,
        code: str = "CALIBRATION_FIELD_INVALID",
        index: int | None = None,
    ) -> Decimal | None:
        details = {"field": field}
        if index is not None:
            details["index"] = index
        if value is None:
            if required:
                raise CalibrationValidationError(
                    code,
                    f"{field} 為必填 Decimal 欄位",
                    details=details,
                )
            return None
        if isinstance(value, (bool, float)) or not isinstance(
            value,
            (str, int, Decimal),
        ):
            raise CalibrationValidationError(
                code,
                f"{field} 必須以十進位字串或整數提供",
                details=details,
            )
        try:
            decimal_value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as error:
            raise CalibrationValidationError(
                code,
                f"{field} 不是合法 Decimal",
                details=details,
            ) from error
        if (
            not decimal_value.is_finite()
            or len(decimal_value.as_tuple().digits)
            > _MAX_SIGNIFICANT_DIGITS
            or abs(decimal_value.adjusted()) > _MAX_DECIMAL_EXPONENT
        ):
            raise CalibrationValidationError(
                code,
                f"{field} 超出 Decimal 證據範圍",
                details=details,
            )
        return decimal_value

    @staticmethod
    def _decimal_text(value) -> str | None:
        if value is None:
            return None
        decimal_value = value if isinstance(value, Decimal) else Decimal(value)
        if decimal_value.is_zero():
            return "0"
        return format(decimal_value.normalize(), "f")

    @staticmethod
    def _boolean(
        value,
        *,
        field: str,
        code: str = "CALIBRATION_FIELD_INVALID",
        index: int | None = None,
    ) -> bool:
        if not isinstance(value, bool):
            details = {"field": field}
            if index is not None:
                details["index"] = index
            raise CalibrationValidationError(
                code,
                f"{field} 必須是 boolean",
                details=details,
            )
        return value

    @staticmethod
    def _choice(value, *, field: str, allowed: set[str], index: int) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise CalibrationValidationError(
                "CALIBRATION_POINT_INVALID",
                f"{field} 不在允許清單",
                details={
                    "field": field,
                    "index": index,
                    "allowed": sorted(allowed),
                },
            )
        return value

    @staticmethod
    def _point_error(field: str, index: int, message: str) -> None:
        raise CalibrationValidationError(
            "CALIBRATION_POINT_INVALID",
            message,
            details={"field": field, "index": index},
        )

    @staticmethod
    def _canonical_json(value, *, field: str):
        try:
            encoded = json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            return json.loads(encoded)
        except (OverflowError, TypeError, ValueError) as error:
            raise CalibrationValidationError(
                "CALIBRATION_FIELD_INVALID",
                f"{field} 必須是可重現且僅含有限數值的 JSON",
                details={"field": field},
            ) from error
