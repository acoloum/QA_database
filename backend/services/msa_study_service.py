"""MSA 研究的識別資料、受控編號與樂觀鎖更新服務。"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import MsaStudy
from ..utils import log_audit
from .msa_errors import (
    MsaConflict,
    MsaNotFound,
    MsaValidationError,
)
from .msa_payload import (
    bounded_int as _bounded_int,
    decimal_text as _decimal_text,
    optional_decimal as _optional_decimal,
    optional_text as _optional_text,
    required_text as _required_text,
    reject_unknown_fields as _reject_unknown_fields,
    require_object as _require_object,
)


# 研究類型對應第四版受控方法；新增類型必須同時擴充 method registry。
STUDY_TYPES = {
    "grr_range",
    "grr_xbar_r",
    "grr_anova",
    "bias",
    "linearity",
    "stability",
    "attribute",
    "nonreplicable",
}

MEASUREMENT_PURPOSES = {"product_control", "process_control"}

# 建立時可指定的欄位；狀態與各種目前版本指標只能由流程推進。
_CREATE_FIELDS = {
    "study_type",
    "measurement_purpose",
    "characteristic",
    "unit",
    "lsl",
    "usl",
    "no_tolerance_reason",
    "process_sigma",
    "criteria_profile_id",
    "responsible_user_id",
    "primary_executor_id",
}

# 只有 draft 階段可修正的識別資料；凍結計畫後這些值即為正式證據。
_IDENTITY_FIELDS = {
    "study_type",
    "measurement_purpose",
    "characteristic",
    "unit",
    "lsl",
    "usl",
    "no_tolerance_reason",
    "process_sigma",
}

_UPDATE_FIELDS = _CREATE_FIELDS

_TEXT_LIMITS = {
    "characteristic": 200,
    "unit": 40,
    "no_tolerance_reason": 2000,
}

_LIST_QUERY_FIELDS = {"page", "page_size", "sort", "order", "status"}

_SORT_FIELDS = {
    "id": MsaStudy.id,
    "study_no": MsaStudy.study_no,
    "updated_at": MsaStudy.updated_at,
}

MAX_STUDY_PAGE = 1_000_000
_NUMBER_RETRY_LIMIT = 5


class MsaStudyService:
    """維護研究識別資料，並以 updated_at 作為畫面樂觀鎖。"""

    # ------------------------------------------------------------------
    # 查詢
    # ------------------------------------------------------------------

    @staticmethod
    def get(study_id: int) -> MsaStudy:
        study = db.session.get(MsaStudy, study_id)
        if study is None:
            raise MsaNotFound(
                "MSA_STUDY_NOT_FOUND",
                "找不到 MSA 研究",
                details={"study_id": study_id},
            )
        return study

    @staticmethod
    def get_list(args) -> dict:
        """以有界分頁及白名單排序列出研究。"""
        values = dict(args or {})
        unknown = sorted(set(values) - _LIST_QUERY_FIELDS)
        if unknown:
            raise MsaValidationError(
                "MSA_UNKNOWN_FIELDS",
                "請求包含未允許欄位",
                details={"unknown_fields": unknown},
            )
        page = _bounded_int(
            values.get("page", 1),
            field="page",
            minimum=1,
            maximum=MAX_STUDY_PAGE,
            code="MSA_STUDY_PAGE_INVALID",
        )
        page_size = _bounded_int(
            values.get("page_size", 25),
            field="page_size",
            minimum=1,
            maximum=100,
            code="MSA_STUDY_PAGE_SIZE_INVALID",
        )
        sort_name = values.get("sort", "study_no")
        sort_column = _SORT_FIELDS.get(sort_name)
        if sort_column is None:
            raise MsaValidationError(
                "MSA_STUDY_SORT_INVALID",
                "不支援的研究排序欄位",
                details={"sort": sort_name, "allowed": sorted(_SORT_FIELDS)},
            )
        order = values.get("order", "asc")
        if order not in {"asc", "desc"}:
            raise MsaValidationError(
                "MSA_STUDY_SORT_ORDER_INVALID",
                "排序方向只允許 asc 或 desc",
                details={"order": order},
            )

        query = MsaStudy.query
        status = values.get("status")
        if status is not None:
            query = query.filter(MsaStudy.status == status)

        ordering = sort_column.asc() if order == "asc" else sort_column.desc()
        total = query.count()
        items = (
            query
            .order_by(ordering, MsaStudy.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [MsaStudyService.serialize(item) for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def serialize(study: MsaStudy) -> dict:
        return {
            "id": study.id,
            "study_no": study.study_no,
            "study_type": study.study_type,
            "measurement_purpose": study.measurement_purpose,
            "characteristic": study.characteristic,
            "unit": study.unit,
            "lsl": _decimal_text(study.lsl),
            "usl": _decimal_text(study.usl),
            "no_tolerance_reason": study.no_tolerance_reason,
            "process_sigma": _decimal_text(study.process_sigma),
            "criteria_profile_id": study.criteria_profile_id,
            "responsible_user_id": study.responsible_user_id,
            "primary_executor_id": study.primary_executor_id,
            "status": study.status,
            "current_plan_version_id": study.current_plan_version_id,
            "current_result_version_id": study.current_result_version_id,
            "previous_approved_study_id": study.previous_approved_study_id,
            "next_due_date": (
                study.next_due_date.isoformat() if study.next_due_date else None
            ),
            "created_by_id": study.created_by_id,
            "created_at": _timestamp_text(study.created_at),
            "updated_by_id": study.updated_by_id,
            "updated_at": _timestamp_text(study.updated_at),
        }

    # ------------------------------------------------------------------
    # 建立與更新
    # ------------------------------------------------------------------

    @staticmethod
    def create(payload, actor_id: int) -> MsaStudy:
        data = _require_object(payload)
        _reject_unknown_fields(data, _CREATE_FIELDS)
        values = MsaStudyService._validated_identity(data, defaults=None)

        try:
            study = MsaStudyService._insert_with_number(values, actor_id)
            log_audit(
                actor_id,
                "create_study",
                "msa_study",
                study.id,
                new_val={
                    "study_no": study.study_no,
                    "study_type": study.study_type,
                    "characteristic": study.characteristic,
                },
            )
            db.session.commit()
            return study
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def update(
        study_id: int,
        payload,
        actor_id: int,
        expected_updated_at=None,
    ) -> MsaStudy:
        data = _require_object(payload)
        _reject_unknown_fields(data, _UPDATE_FIELDS)
        if not expected_updated_at:
            raise MsaValidationError(
                "MSA_EXPECTED_UPDATED_AT_REQUIRED",
                "更新研究必須提供畫面上的 expected_updated_at",
                details={"field": "expected_updated_at"},
            )

        try:
            study = (
                MsaStudy.query
                .filter_by(id=study_id)
                .with_for_update()
                .one_or_none()
            )
            if study is None:
                raise MsaNotFound(
                    "MSA_STUDY_NOT_FOUND",
                    "找不到 MSA 研究",
                    details={"study_id": study_id},
                )
            if not _same_instant(study.updated_at, expected_updated_at):
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "研究已被其他人更新，請重新載入",
                    details={
                        "expected_updated_at": expected_updated_at,
                        "actual_updated_at": _timestamp_text(study.updated_at),
                    },
                )
            touched_identity = sorted(set(data) & _IDENTITY_FIELDS)
            if touched_identity and study.status != "draft":
                raise MsaConflict(
                    "MSA_STUDY_IDENTITY_LOCKED",
                    "研究離開草稿後不得改寫識別資料；請建立新研究",
                    details={
                        "status": study.status,
                        "fields": touched_identity,
                    },
                )

            values = MsaStudyService._validated_identity(data, defaults=study)
            before = {
                field: getattr(study, field) for field in sorted(data)
            }
            for field, value in values.items():
                setattr(study, field, value)
            study.updated_by_id = actor_id
            study.updated_at = datetime.now(timezone.utc)
            db.session.flush()
            log_audit(
                actor_id,
                "update_study",
                "msa_study",
                study.id,
                old_val={key: _plain(value) for key, value in before.items()},
                new_val={
                    key: _plain(getattr(study, key)) for key in sorted(data)
                },
            )
            db.session.commit()
            return study
        except Exception:
            db.session.rollback()
            raise

    # ------------------------------------------------------------------
    # 內部
    # ------------------------------------------------------------------

    @staticmethod
    def _insert_with_number(values: dict, actor_id: int) -> MsaStudy:
        """以受控序號建立研究；併發碰撞時重試，不使用 count()+1。"""
        last_error = None
        for _ in range(_NUMBER_RETRY_LIMIT):
            study = MsaStudy(
                study_no=_next_study_no(datetime.now(timezone.utc)),
                status="draft",
                created_by_id=actor_id,
                updated_by_id=actor_id,
                **values,
            )
            db.session.add(study)
            try:
                with db.session.begin_nested():
                    db.session.flush()
                return study
            except IntegrityError as error:
                last_error = error
                db.session.expunge(study)
        raise MsaConflict(
            "MSA_STUDY_NUMBER_CONFLICT",
            "研究編號連續碰撞，請稍後再試",
            details={"error": str(last_error)},
        )

    @staticmethod
    def _validated_identity(data: dict, defaults) -> dict:
        """驗證識別資料；defaults 為 None 表示建立情境。"""
        values = {}

        def current(field, fallback=None):
            if field in data:
                return values.get(field, fallback)
            if defaults is not None:
                return getattr(defaults, field)
            return fallback

        if "study_type" in data or defaults is None:
            study_type = data.get("study_type")
            if study_type not in STUDY_TYPES:
                raise MsaValidationError(
                    "MSA_STUDY_TYPE_INVALID",
                    "不支援的 MSA 研究類型",
                    details={
                        "study_type": study_type,
                        "allowed": sorted(STUDY_TYPES),
                    },
                )
            values["study_type"] = study_type

        if "measurement_purpose" in data or defaults is None:
            purpose = data.get("measurement_purpose")
            if purpose not in MEASUREMENT_PURPOSES:
                raise MsaValidationError(
                    "MSA_STUDY_PURPOSE_INVALID",
                    "量測目的只允許 product_control 或 process_control",
                    details={"measurement_purpose": purpose},
                )
            values["measurement_purpose"] = purpose

        for field in ("characteristic", "unit"):
            if field in data or defaults is None:
                values[field] = _required_text(
                    data.get(field),
                    field=field,
                    max_length=_TEXT_LIMITS[field],
                    code="MSA_STUDY_TEXT_INVALID",
                )

        if "no_tolerance_reason" in data or defaults is None:
            values["no_tolerance_reason"] = _optional_text(
                data.get("no_tolerance_reason"),
                field="no_tolerance_reason",
                max_length=_TEXT_LIMITS["no_tolerance_reason"],
                code="MSA_STUDY_TEXT_INVALID",
            )

        for field in ("lsl", "usl"):
            if field in data or defaults is None:
                values[field] = _optional_decimal(
                    data.get(field),
                    field=field,
                    code="MSA_STUDY_SPEC_INVALID",
                )

        if "process_sigma" in data or defaults is None:
            sigma = _optional_decimal(
                data.get("process_sigma"),
                field="process_sigma",
                code="MSA_STUDY_PROCESS_SIGMA_INVALID",
            )
            if sigma is not None and sigma <= 0:
                raise MsaValidationError(
                    "MSA_STUDY_PROCESS_SIGMA_INVALID",
                    "製程標準差必須大於 0",
                    details={"process_sigma": str(sigma)},
                )
            values["process_sigma"] = sigma

        for field in (
            "criteria_profile_id", "responsible_user_id", "primary_executor_id",
        ):
            if field in data or defaults is None:
                values[field] = _optional_int(
                    data.get(field),
                    field=field,
                    code="MSA_STUDY_REFERENCE_INVALID",
                )

        lsl = values.get("lsl", current("lsl"))
        usl = values.get("usl", current("usl"))
        if lsl is not None and usl is not None and lsl >= usl:
            raise MsaValidationError(
                "MSA_STUDY_SPEC_INVALID",
                "規格下限必須小於規格上限",
                details={"lsl": str(lsl), "usl": str(usl)},
            )

        purpose = values.get(
            "measurement_purpose", current("measurement_purpose")
        )
        reason = values.get(
            "no_tolerance_reason", current("no_tolerance_reason")
        )
        if (
            purpose == "product_control"
            and lsl is None
            and usl is None
            and not reason
        ):
            raise MsaValidationError(
                "MSA_STUDY_TOLERANCE_REQUIRED",
                "產品判定用研究必須有規格或明確記錄無公差原因",
                details={"measurement_purpose": purpose},
            )

        return values


# ----------------------------------------------------------------------
# 共用輸入處理
# ----------------------------------------------------------------------


def _optional_int(value, *, field: str, code: str):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MsaValidationError(
            code, f"{field} 必須是整數", details={"field": field},
        )
    if value <= 0:
        raise MsaValidationError(
            code, f"{field} 必須是正整數", details={"field": field},
        )
    return value


def _next_study_no(now: datetime) -> str:
    """PostgreSQL 以 sequence 取號；SQLite 測試以目前最大號推進。"""
    bind = db.session.get_bind()
    if bind.dialect.name == "postgresql":
        next_value = db.session.execute(
            db.text("SELECT nextval('msa_study_number_seq')")
        ).scalar_one()
    else:
        next_value = (
            db.session.execute(
                db.select(db.func.count(MsaStudy.id))
            ).scalar_one()
            + 1
        )
        while MsaStudy.query.filter_by(
            study_no=f"MSA-{now.year}-{next_value:04d}"
        ).first() is not None:
            next_value += 1
    return f"MSA-{now.year}-{next_value:04d}"


def _timestamp_text(value):
    return value.isoformat() if value is not None else None


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _same_instant(actual, expected_text) -> bool:
    """比較實際 updated_at 與畫面帶回的字串是否為同一瞬間。"""
    if actual is None:
        return False
    try:
        expected = datetime.fromisoformat(str(expected_text))
    except ValueError:
        return False
    if expected.tzinfo is None:
        expected = expected.replace(tzinfo=timezone.utc)
    actual_aware = (
        actual if actual.tzinfo is not None
        else actual.replace(tzinfo=timezone.utc)
    )
    return abs((actual_aware - expected).total_seconds()) < 0.000_001
