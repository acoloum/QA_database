"""MSA 盲測觀測的收集、append-only 修正與完整性驗證。

觀測一旦寫入即不可改值；修正一律以「原紀錄作廢 + 新增後繼紀錄」
表達，讓原始讀值永遠留在證據軌上。
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    MsaObservation,
    MsaPlanVersion,
    MsaStudy,
)
from ..utils import log_audit
from .msa_errors import (
    MsaConflict,
    MsaForbidden,
    MsaNotFound,
    MsaValidationError,
)
from .msa_payload import (
    reject_unknown_fields as _reject_unknown_fields,
    require_object as _require_object,
)


_RECORD_FIELDS = {
    "task_order", "numeric_value", "attribute_value", "measured_at",
}
_CORRECT_FIELDS = {"numeric_value", "attribute_value", "reason"}

MAX_CORRECTION_REASON = 1000

# 只接受明確的小數表示；千分位、科學記號等模糊格式一律拒絕。
_ALLOWED_NUMERIC_CHARS = set("0123456789.+-")


class MsaObservationService:
    """以受控盲測任務為單位收集讀值，並維持單一有效紀錄。"""

    # ------------------------------------------------------------------
    # 收集
    # ------------------------------------------------------------------

    @staticmethod
    def record(
        plan_id: int, payload, *, actor_id: int, can_manage: bool = False,
    ) -> MsaObservation:
        data = _require_object(payload)
        _reject_unknown_fields(data, _RECORD_FIELDS)

        try:
            plan = MsaObservationService._locked_frozen_plan(plan_id)
            task = MsaObservationService._resolve_task(
                plan, data.get("task_order")
            )
            appraiser = next(
                row for row in plan.appraisers
                if row.id == task["appraiser_id"]
            )
            source = MsaObservationService._resolve_source(
                appraiser, actor_id=actor_id, can_manage=can_manage,
            )
            numeric_value, attribute_value = (
                MsaObservationService._resolve_value(plan, data)
            )

            observation = MsaObservation(
                plan_version_id=plan.id,
                part_id=task["part_id"],
                appraiser_id=task["appraiser_id"],
                trial_no=task["trial_no"],
                requested_order=task["requested_order"],
                actual_entry_order=(
                    MsaObservationService._next_entry_order(plan.id)
                ),
                numeric_value=numeric_value,
                attribute_value=attribute_value,
                measured_at=_optional_timestamp(data.get("measured_at")),
                source=source,
                entered_by_id=actor_id,
                is_effective=True,
            )
            db.session.add(observation)
            try:
                db.session.flush()
            except IntegrityError as error:
                raise MsaConflict(
                    "MSA_OBSERVATION_ALREADY_RECORDED",
                    "這個盲測任務已有有效讀值；如需更正請建立修正紀錄",
                    details={"task_order": task["requested_order"]},
                ) from error

            MsaObservationService._advance_study_to_collecting(
                plan.study_id, actor_id,
            )
            log_audit(
                actor_id,
                "record_observation",
                "msa_observation",
                observation.id,
                new_val={
                    "plan_version_id": plan.id,
                    "requested_order": task["requested_order"],
                    "actual_entry_order": observation.actual_entry_order,
                    "source": source,
                },
            )
            db.session.commit()
            return observation
        except Exception:
            db.session.rollback()
            raise

    # ------------------------------------------------------------------
    # 修正
    # ------------------------------------------------------------------

    @staticmethod
    def correct(
        observation_id: int, payload, *, actor_id: int,
    ) -> MsaObservation:
        data = _require_object(payload)
        _reject_unknown_fields(data, _CORRECT_FIELDS)
        reason = _optional_text(
            data.get("reason"),
            field="reason",
            max_length=MAX_CORRECTION_REASON,
        )
        if not reason:
            raise MsaValidationError(
                "MSA_CORRECTION_REASON_REQUIRED",
                "修正觀測必須說明原因",
                details={"field": "reason"},
            )

        try:
            original = (
                MsaObservation.query
                .filter_by(id=observation_id)
                .with_for_update()
                .one_or_none()
            )
            if original is None:
                raise MsaNotFound(
                    "MSA_OBSERVATION_NOT_FOUND",
                    "找不到 MSA 觀測",
                    details={"observation_id": observation_id},
                )
            if not original.is_effective:
                raise MsaConflict(
                    "MSA_OBSERVATION_ALREADY_SUPERSEDED",
                    "這筆觀測已被後續修正取代，請修正目前有效的紀錄",
                    details={"observation_id": observation_id},
                )

            plan = db.session.get(MsaPlanVersion, original.plan_version_id)
            numeric_value, attribute_value = (
                MsaObservationService._resolve_value(plan, data)
            )

            # 先作廢原紀錄，才不會撞到「單一有效觀測」的唯一索引
            original.is_effective = False
            db.session.flush()

            successor = MsaObservation(
                plan_version_id=original.plan_version_id,
                part_id=original.part_id,
                appraiser_id=original.appraiser_id,
                trial_no=original.trial_no,
                requested_order=original.requested_order,
                actual_entry_order=(
                    MsaObservationService._next_entry_order(
                        original.plan_version_id
                    )
                ),
                numeric_value=numeric_value,
                attribute_value=attribute_value,
                measured_at=original.measured_at,
                source=original.source,
                entered_by_id=actor_id,
                is_effective=True,
                supersedes_id=original.id,
                correction_reason=reason,
            )
            db.session.add(successor)
            db.session.flush()
            log_audit(
                actor_id,
                "correct_observation",
                "msa_observation",
                successor.id,
                old_val={
                    "observation_id": original.id,
                    "numeric_value": _decimal_text(original.numeric_value),
                    "attribute_value": original.attribute_value,
                },
                new_val={
                    "observation_id": successor.id,
                    "numeric_value": _decimal_text(successor.numeric_value),
                    "attribute_value": successor.attribute_value,
                    "reason": reason,
                },
            )
            db.session.commit()
            return successor
        except Exception:
            db.session.rollback()
            raise

    # ------------------------------------------------------------------
    # 完整性
    # ------------------------------------------------------------------

    @staticmethod
    def list_for_plan(plan_id: int) -> list[dict]:
        """列出計畫的所有觀測（含已作廢），供管理矩陣呈現修正歷程。

        這個視圖只給具管理權限者使用；盲測任務 DTO 仍不含這些資訊。
        """
        plan = db.session.get(
            MsaPlanVersion,
            plan_id,
            options=[
                selectinload(MsaPlanVersion.parts),
                selectinload(MsaPlanVersion.appraisers),
            ],
        )
        if plan is None:
            raise MsaNotFound(
                "MSA_PLAN_NOT_FOUND",
                "找不到 MSA 計畫版本",
                details={"plan_id": plan_id},
            )

        part_codes = {part.id: part.blind_code for part in plan.parts}
        appraiser_codes = {
            row.id: row.blind_code for row in plan.appraisers
        }
        rows = (
            MsaObservation.query
            .filter_by(plan_version_id=plan.id)
            .order_by(MsaObservation.actual_entry_order.asc())
            .all()
        )
        return [
            {
                "id": row.id,
                "requested_order": row.requested_order,
                "actual_entry_order": row.actual_entry_order,
                "part_blind_code": part_codes.get(row.part_id),
                "appraiser_blind_code": appraiser_codes.get(row.appraiser_id),
                "trial_no": row.trial_no,
                "numeric_value": (
                    str(row.numeric_value)
                    if row.numeric_value is not None else None
                ),
                "attribute_value": row.attribute_value,
                "measured_at": (
                    row.measured_at.isoformat() if row.measured_at else None
                ),
                "source": row.source,
                "entered_by_id": row.entered_by_id,
                "created_at": (
                    row.created_at.isoformat() if row.created_at else None
                ),
                "is_effective": row.is_effective,
                "supersedes_id": row.supersedes_id,
                "correction_reason": row.correction_reason,
            }
            for row in rows
        ]

    @staticmethod
    def completeness(plan_id: int) -> dict:
        """唯讀比對盲測矩陣與有效讀值；不改狀態、不 commit。

        分析交易需要在自己的交易內判斷完整性，因此與會推進狀態的
        validate() 分開，避免在交易中途提交而提早釋放列鎖。
        """
        plan = db.session.get(MsaPlanVersion, plan_id)
        if plan is None:
            raise MsaNotFound(
                "MSA_PLAN_NOT_FOUND",
                "找不到 MSA 計畫版本",
                details={"plan_id": plan_id},
            )
        if plan.frozen_at is None:
            raise MsaConflict(
                "MSA_PLAN_NOT_FROZEN",
                "計畫尚未凍結，無法驗證資料完整性",
                details={"plan_id": plan_id},
            )

        recorded = {
            (row.part_id, row.appraiser_id, row.trial_no)
            for row in MsaObservation.query.filter_by(
                plan_version_id=plan.id, is_effective=True,
            ).all()
        }
        missing = [
            {
                "requested_order": item["requested_order"],
                "trial_no": item["trial_no"],
            }
            for item in plan.randomized_order
            if (
                item["part_id"], item["appraiser_id"], item["trial_no"],
            ) not in recorded
        ]
        return {
            "plan_version_id": plan.id,
            "plan_hash": plan.plan_hash,
            "expected": len(plan.randomized_order),
            "recorded": len(recorded),
            "missing": missing,
            "complete": not missing,
        }

    @staticmethod
    def validate(plan_id: int, *, actor_id: int | None = None) -> dict:
        """驗證完整性；資料齊全時把研究推進到可分析。"""
        report = MsaObservationService.completeness(plan_id)
        if not report["complete"]:
            return report

        plan = db.session.get(MsaPlanVersion, plan_id)
        study = (
            MsaStudy.query
            .filter_by(id=plan.study_id)
            .with_for_update()
            .one()
        )
        if study.status in {"ready", "collecting"}:
            study.status = "ready_for_analysis"
            study.updated_at = datetime.now(timezone.utc)
            if actor_id is not None:
                study.updated_by_id = actor_id
            db.session.commit()
        return report

    # ------------------------------------------------------------------
    # 內部
    # ------------------------------------------------------------------

    @staticmethod
    def _locked_frozen_plan(plan_id: int) -> MsaPlanVersion:
        plan = (
            MsaPlanVersion.query
            .filter_by(id=plan_id)
            .options(selectinload(MsaPlanVersion.appraisers))
            .with_for_update()
            .one_or_none()
        )
        if plan is None:
            raise MsaNotFound(
                "MSA_PLAN_NOT_FOUND",
                "找不到 MSA 計畫版本",
                details={"plan_id": plan_id},
            )
        if plan.frozen_at is None:
            raise MsaConflict(
                "MSA_PLAN_NOT_FROZEN",
                "計畫尚未凍結，不可收集正式讀值",
                details={"plan_id": plan_id},
            )
        return plan

    @staticmethod
    def _resolve_task(plan: MsaPlanVersion, task_order) -> dict:
        if isinstance(task_order, bool) or not isinstance(task_order, int):
            raise MsaValidationError(
                "MSA_OBSERVATION_TASK_UNKNOWN",
                "task_order 必須是整數",
                details={"task_order": task_order},
            )
        task = next(
            (
                item for item in plan.randomized_order
                if item["requested_order"] == task_order
            ),
            None,
        )
        if task is None:
            raise MsaValidationError(
                "MSA_OBSERVATION_TASK_UNKNOWN",
                "指定的盲測任務不存在於這個計畫版本",
                details={"task_order": task_order},
            )
        return task

    @staticmethod
    def _resolve_source(appraiser, *, actor_id: int, can_manage: bool) -> str:
        """評價人只能輸入自己的任務；具管理權限者可代輸入並標記來源。"""
        if appraiser.user_id == actor_id:
            return "page_single"
        if can_manage:
            return "page_matrix"
        raise MsaForbidden(
            "MSA_OBSERVATION_TASK_NOT_ASSIGNED",
            "只有被指派的評價人或具管理權限者可以輸入這筆讀值",
            details={"appraiser_id": appraiser.id},
        )

    @staticmethod
    def _resolve_value(plan: MsaPlanVersion, data: dict):
        numeric_raw = data.get("numeric_value")
        attribute_raw = data.get("attribute_value")
        has_numeric = numeric_raw is not None
        has_attribute = attribute_raw is not None
        if has_numeric == has_attribute:
            raise MsaValidationError(
                "MSA_OBSERVATION_INVALID",
                "每筆觀測必須且只能有一種讀值（計量或計數）",
                details={
                    "numeric_value": _describe(numeric_raw),
                    "attribute_value": _describe(attribute_raw),
                },
            )
        if has_numeric:
            return _strict_decimal(numeric_raw), None

        category = _optional_text(
            attribute_raw, field="attribute_value", max_length=80,
        )
        allowed = list(plan.category_set or [])
        if not allowed:
            raise MsaValidationError(
                "MSA_OBSERVATION_CATEGORY_UNKNOWN",
                "計畫凍結時未保存計數類別集合，無法接受計數讀值",
                details={"plan_version_id": plan.id},
            )
        if category not in allowed:
            raise MsaValidationError(
                "MSA_OBSERVATION_CATEGORY_UNKNOWN",
                "計數分類不在計畫凍結時保存的類別集合內",
                details={"attribute_value": category, "allowed": allowed},
            )
        return None, category

    @staticmethod
    def _next_entry_order(plan_version_id: int) -> int:
        """由資料庫取得同計畫的下一個實際輸入順序。"""
        current = db.session.execute(
            db.select(db.func.max(MsaObservation.actual_entry_order))
            .where(MsaObservation.plan_version_id == plan_version_id)
        ).scalar_one_or_none()
        return (current or 0) + 1

    @staticmethod
    def _advance_study_to_collecting(study_id: int, actor_id: int) -> None:
        # 絕大多數觀測寫入時研究早已離開 ready 狀態；先用不加鎖的讀取
        # 判斷，避免每筆觀測都對研究列取得排他鎖造成不必要的鎖競爭。
        study = MsaStudy.query.filter_by(id=study_id).one()
        if study.status != "ready":
            return
        study = (
            MsaStudy.query
            .filter_by(id=study_id)
            .with_for_update()
            .one()
        )
        if study.status == "ready":
            study.status = "collecting"
            study.updated_by_id = actor_id
            study.updated_at = datetime.now(timezone.utc)


# ----------------------------------------------------------------------
# 共用輸入處理
# ----------------------------------------------------------------------


def _describe(value):
    return None if value is None else str(value)[:80]


def _strict_decimal(value) -> Decimal:
    """只接受明確小數字面值，拒絕千分位、科學記號與非有限值。"""
    if isinstance(value, bool):
        _raise_observation_invalid(value)
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, float):
        parsed = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        if not text or not set(text) <= _ALLOWED_NUMERIC_CHARS:
            _raise_observation_invalid(value)
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            _raise_observation_invalid(value)
    else:
        _raise_observation_invalid(value)

    if not parsed.is_finite():
        _raise_observation_invalid(value)
    return parsed


def _raise_observation_invalid(value):
    raise MsaValidationError(
        "MSA_OBSERVATION_INVALID",
        "讀值必須是明確且有限的小數，不接受千分位或科學記號",
        details={"numeric_value": _describe(value)},
    )


def _optional_text(value, *, field: str, max_length: int):
    if value is None:
        return None
    if not isinstance(value, str):
        raise MsaValidationError(
            "MSA_OBSERVATION_INVALID",
            f"{field} 必須是文字",
            details={"field": field},
        )
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise MsaValidationError(
            "MSA_OBSERVATION_INVALID",
            f"{field} 超過允許長度",
            details={"field": field, "max_length": max_length},
        )
    return normalized


def _optional_timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise MsaValidationError(
            "MSA_OBSERVATION_INVALID",
            "measured_at 必須是 ISO 時間字串",
            details={"field": "measured_at"},
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise MsaValidationError(
            "MSA_OBSERVATION_INVALID",
            "measured_at 必須是 ISO 時間字串",
            details={"field": "measured_at", "value": value[:40]},
        ) from error
    return (
        parsed if parsed.tzinfo is not None
        else parsed.replace(tzinfo=timezone.utc)
    )


def _decimal_text(value):
    return str(value) if value is not None else None
