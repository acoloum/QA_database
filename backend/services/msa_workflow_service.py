"""MSA 結果版本的送審、核准、退回與作廢。

職責分離是硬性規則：建立研究、擔任主要執行者、產生結果或輸入過
任何一筆有效觀測的人，都不得核准同一份研究。這個檢查不因 admin
角色而略過。
"""

from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    MsaObservation,
    MsaResultVersion,
    MsaStudy,
    MsaWorkflowDecision,
)
from ..utils import log_audit
from .msa_errors import (
    MsaConflict,
    MsaForbidden,
    MsaNotFound,
    MsaValidationError,
)


# 明確列出允許的狀態轉移；不在表內的一律視為衝突。
ALLOWED_TRANSITIONS = {
    "submit": {("analyzed", "submitted")},
    "approve": {("submitted", "approved")},
    "reject": {("submitted", "rejected")},
    "void": {("approved", "voided")},
}

# 這些角色與研究結果有直接利害關係，不得核准同一份研究
SEPARATION_ROLES = ("creator", "primary_executor", "result_author", "data_entry")

MAX_REASON_LENGTH = 1000


class MsaWorkflowService:
    """以列鎖與 expected_status 完成結果版本的狀態推進。"""

    @staticmethod
    def submit(result_id: int, payload, *, actor_id: int) -> MsaResultVersion:
        data = _require_object(payload)
        _reject_unknown_fields(
            data, {"expected_status", "reason", "actions", "due_date"},
        )
        reason = _required_reason(data.get("reason"))
        return MsaWorkflowService._transition(
            result_id,
            action="submit",
            expected_status=data.get("expected_status"),
            reason=reason,
            actor_id=actor_id,
            extra_validator=lambda result: (
                MsaWorkflowService._validate_conditional_submission(
                    result, data,
                )
            ),
        )

    @staticmethod
    def approve(result_id: int, payload, *, actor_id: int) -> MsaResultVersion:
        data = _require_object(payload)
        _reject_unknown_fields(data, {"expected_status", "reason"})
        reason = _required_reason(data.get("reason"))
        return MsaWorkflowService._transition(
            result_id,
            action="approve",
            expected_status=data.get("expected_status"),
            reason=reason,
            actor_id=actor_id,
            separation_required=True,
        )

    @staticmethod
    def reject(result_id: int, payload, *, actor_id: int) -> MsaResultVersion:
        data = _require_object(payload)
        _reject_unknown_fields(data, {"expected_status", "reason"})
        reason = _required_reason(data.get("reason"))
        return MsaWorkflowService._transition(
            result_id,
            action="reject",
            expected_status=data.get("expected_status"),
            reason=reason,
            actor_id=actor_id,
            separation_required=True,
        )

    @staticmethod
    def void(result_id: int, payload, *, actor_id: int) -> MsaResultVersion:
        data = _require_object(payload)
        _reject_unknown_fields(data, {"expected_status", "reason"})
        reason = _required_reason(data.get("reason"))
        return MsaWorkflowService._transition(
            result_id,
            action="void",
            expected_status=data.get("expected_status"),
            reason=reason,
            actor_id=actor_id,
            separation_required=True,
        )

    # ------------------------------------------------------------------
    # 職責分離
    # ------------------------------------------------------------------

    @staticmethod
    def disallowed_approver_ids(result: MsaResultVersion) -> dict:
        """列出因參與研究而不得核准的人員，並標明各自的角色。"""
        study = result.study
        roles = {}

        def add(user_id, role):
            if user_id is None:
                return
            roles.setdefault(user_id, []).append(role)

        add(study.created_by_id, "creator")
        add(study.primary_executor_id, "primary_executor")
        add(result.created_by_id, "result_author")
        entered_by = db.session.execute(
            db.select(MsaObservation.entered_by_id)
            .where(
                MsaObservation.plan_version_id == result.plan_version_id,
                MsaObservation.is_effective.is_(True),
            )
            .distinct()
        ).scalars().all()
        for user_id in entered_by:
            add(user_id, "data_entry")
        return roles

    @staticmethod
    def assert_can_approve(result: MsaResultVersion, actor_id: int) -> dict:
        """核准前的職責分離檢查；admin 角色同樣適用。"""
        disallowed = MsaWorkflowService.disallowed_approver_ids(result)
        if actor_id in disallowed:
            raise MsaForbidden(
                "MSA_SELF_APPROVAL_FORBIDDEN",
                "建立、執行或輸入本研究資料的人員不得核准本研究",
                details={
                    "actor_id": actor_id,
                    "conflicting_roles": sorted(set(disallowed[actor_id])),
                },
            )
        return {
            "passed": True,
            "checked_actor_id": actor_id,
            "disallowed_roles_checked": list(SEPARATION_ROLES),
            "disallowed_actor_count": len(disallowed),
        }

    # ------------------------------------------------------------------
    # 內部
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_conditional_submission(result, data) -> dict:
        """條件接受的結果必須帶處置措施與期限才能送審。"""
        disposition = (result.conclusion or {}).get("system_disposition")
        if disposition != "conditionally_acceptable":
            return {}

        actions = data.get("actions")
        if (
            not isinstance(actions, list)
            or not actions
            or any(
                not isinstance(item, str) or not item.strip()
                for item in actions
            )
        ):
            raise MsaValidationError(
                "MSA_CONDITIONAL_ACTIONS_REQUIRED",
                "條件接受的結果必須列出具體處置措施才能送審",
                details={"field": "actions"},
            )
        due_date = data.get("due_date")
        if not due_date:
            raise MsaValidationError(
                "MSA_CONDITIONAL_DUE_DATE_REQUIRED",
                "條件接受的結果必須訂定處置期限才能送審",
                details={"field": "due_date"},
            )
        try:
            parsed_due = date.fromisoformat(str(due_date))
        except ValueError as error:
            raise MsaValidationError(
                "MSA_CONDITIONAL_DUE_DATE_REQUIRED",
                "處置期限必須是 ISO 日期",
                details={"field": "due_date", "value": str(due_date)[:40]},
            ) from error
        return {
            "actions": [item.strip() for item in actions],
            "due_date": parsed_due.isoformat(),
        }

    @staticmethod
    def _transition(
        result_id: int,
        *,
        action: str,
        expected_status,
        reason: str,
        actor_id: int,
        separation_required: bool = False,
        extra_validator=None,
    ) -> MsaResultVersion:
        try:
            result = (
                MsaResultVersion.query
                .filter_by(id=result_id)
                .with_for_update()
                .one_or_none()
            )
            if result is None:
                raise MsaNotFound(
                    "MSA_RESULT_NOT_FOUND",
                    "找不到 MSA 結果版本",
                    details={"result_id": result_id},
                )

            transitions = ALLOWED_TRANSITIONS[action]
            target_status = next(
                (
                    to_status for from_status, to_status in transitions
                    if from_status == result.status
                ),
                None,
            )
            if target_status is None or expected_status != result.status:
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "結果版本狀態已變更或不允許此動作",
                    details={
                        "action": action,
                        "expected_status": expected_status,
                        "actual_status": result.status,
                        "allowed": sorted(
                            f"{a}->{b}" for a, b in transitions
                        ),
                    },
                )

            extra_data = {}
            if extra_validator is not None:
                extra_data = extra_validator(result) or {}

            separation_check = {"passed": True, "checked_actor_id": actor_id}
            if separation_required:
                separation_check = MsaWorkflowService.assert_can_approve(
                    result, actor_id,
                )

            study = (
                MsaStudy.query
                .filter_by(id=result.study_id)
                .with_for_update()
                .one()
            )
            old_status = result.status
            result.status = target_status
            try:
                db.session.flush()
            except IntegrityError as error:
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "同一研究已有其他送審中的結果版本",
                    details={"study_id": result.study_id},
                ) from error

            old_study_status = study.status
            study.status = target_status
            if target_status == "approved":
                study.current_result_version_id = result.id
            study.updated_by_id = actor_id
            study.updated_at = datetime.now(timezone.utc)

            db.session.add(MsaWorkflowDecision(
                study_id=result.study_id,
                result_version_id=result.id,
                action=action,
                from_status=old_status,
                to_status=target_status,
                reason=reason,
                actor_id=actor_id,
                separation_check=separation_check,
                extra_data=extra_data,
            ))
            log_audit(
                actor_id,
                action,
                "msa_result",
                result.id,
                old_val={
                    "result_status": old_status,
                    "study_status": old_study_status,
                },
                new_val={
                    "result_status": target_status,
                    "study_status": target_status,
                    "reason": reason,
                    **({"conditional": extra_data} if extra_data else {}),
                },
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise


def _require_object(payload) -> dict:
    if not isinstance(payload, dict):
        raise MsaValidationError(
            "MSA_PAYLOAD_INVALID", "請求內容必須是 JSON 物件", details={},
        )
    return payload


def _reject_unknown_fields(payload: dict, allowed: set) -> None:
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise MsaValidationError(
            "MSA_UNKNOWN_FIELDS",
            "請求包含未允許欄位",
            details={"unknown_fields": unknown},
        )


def _required_reason(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MsaValidationError(
            "MSA_WORKFLOW_REASON_REQUIRED",
            "工作流動作必須說明理由",
            details={"field": "reason"},
        )
    reason = value.strip()
    if len(reason) > MAX_REASON_LENGTH:
        raise MsaValidationError(
            "MSA_WORKFLOW_REASON_REQUIRED",
            "理由超過允許長度",
            details={"field": "reason", "max_length": MAX_REASON_LENGTH},
        )
    return reason
