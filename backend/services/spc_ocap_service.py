"""持續 SPC 失控事件同步與 OCAP 處置服務。"""

from typing import Any, Dict, Mapping, Sequence

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Role, SpcEvent, SpcLimitVersion, SpcOcap, SpcStudyVersion, User
from ..utils import log_audit
from .spc_errors import SpcConflict, SpcNotFound, SpcValidationError
from .spc_study_service import _require_permission


OCAP_ASSIGNABLE_ROLE_CODES = ("qa_supervisor", "qc_manager", "admin")
OCAP_ALLOWED_STATUSES = frozenset(("open", "closed"))
OCAP_JSON_FIELDS = frozenset(("investigation_6m", "remeasurement"))
OCAP_TEXT_FIELDS = frozenset((
    "process_adjustment", "product_disposition", "effectiveness",
))
OCAP_ALLOWED_FIELDS = OCAP_JSON_FIELDS | OCAP_TEXT_FIELDS | {
    "owner_id", "status",
}


class SpcOcapService:
    """建立去重失控事件並保存可稽核的 OCAP。"""

    @staticmethod
    def list_assignable_users() -> list[dict[str, Any]]:
        """取得可指派為 OCAP 責任人的啟用使用者。"""

        rows = (
            db.session.query(User, Role)
            .join(Role, Role.code == User.role)
            .filter(
                User.is_active.is_(True),
                User.role.in_(OCAP_ASSIGNABLE_ROLE_CODES),
            )
            .order_by(Role.name, User.username, User.id)
            .all()
        )
        return [{
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "role_name": role.name,
        } for user, role in rows]

    @staticmethod
    def validate_payload(payload: Any) -> Mapping[str, Any]:
        """驗證 OCAP API 契約，避免錯型資料污染稽核紀錄。"""

        if not isinstance(payload, Mapping):
            raise SpcValidationError(
                "SPC_OCAP_PAYLOAD_INVALID", "OCAP 請求本文必須是 JSON 物件"
            )
        unknown = sorted(set(payload) - OCAP_ALLOWED_FIELDS)
        if unknown:
            raise SpcValidationError(
                "SPC_OCAP_FIELD_UNKNOWN",
                f"OCAP 包含不支援欄位：{', '.join(str(name) for name in unknown)}",
            )
        if "status" in payload and payload["status"] not in OCAP_ALLOWED_STATUSES:
            raise SpcValidationError(
                "SPC_OCAP_STATUS_INVALID", "OCAP 狀態只允許 open 或 closed"
            )
        if "owner_id" in payload:
            owner_id = payload["owner_id"]
            if owner_id is not None and type(owner_id) is not int:
                raise SpcValidationError(
                    "SPC_OCAP_OWNER_INVALID", "OCAP 責任人必須是整數使用者 ID 或 null"
                )
        for name in OCAP_JSON_FIELDS:
            if name in payload and payload[name] is not None and not isinstance(
                payload[name], Mapping
            ):
                raise SpcValidationError(
                    "SPC_OCAP_FIELD_INVALID", f"OCAP 欄位 {name} 必須是 JSON 物件或 null"
                )
        for name in OCAP_TEXT_FIELDS:
            if name in payload and payload[name] is not None and not isinstance(
                payload[name], str
            ):
                raise SpcValidationError(
                    "SPC_OCAP_FIELD_INVALID", f"OCAP 欄位 {name} 必須是文字或 null"
                )
        return payload

    @staticmethod
    def _validate_owner_change(
        current_owner_id: int | None, payload: Mapping[str, Any]
    ) -> None:
        """驗證新增或更換的 OCAP 責任人符合可指派政策。"""

        if "owner_id" not in payload:
            return
        owner_id = payload["owner_id"]
        if owner_id is None or owner_id == current_owner_id:
            return
        owner = db.session.get(User, owner_id)
        if (
            owner is None
            or not owner.is_active
            or owner.role not in OCAP_ASSIGNABLE_ROLE_CODES
        ):
            raise SpcValidationError(
                "SPC_OCAP_OWNER_NOT_ASSIGNABLE",
                "責任人必須是啟用中的 QA主管、品管經理或系統管理員",
            )

    @staticmethod
    def sync_events(
        limit_version_id: int,
        study_version_id: int,
        violations: Sequence[Mapping[str, Any]],
    ) -> list[SpcEvent]:
        """同步持續監控違規；回溯分析不建立正式事件。"""

        limit = db.session.get(SpcLimitVersion, limit_version_id)
        version = db.session.get(SpcStudyVersion, study_version_id)
        if limit is None:
            raise SpcNotFound("SPC_LIMIT_NOT_FOUND", "找不到 SPC 界限版本")
        if version is None:
            raise SpcNotFound("SPC_STUDY_VERSION_NOT_FOUND", "找不到 SPC 研究版本")
        if limit.status != "active":
            raise SpcConflict("SPC_LIMIT_NOT_ACTIVE", "只有生效中的界限可建立正式事件")
        if version.study.study_type != "ongoing":
            return []
        if (
            limit.analysis_family != version.study.analysis_family
            or limit.process_stream_key != version.study.process_stream_key
            or limit.characteristic != version.study.characteristic
            or limit.study_version.study.source != version.study.source
        ):
            raise SpcValidationError(
                "SPC_STREAM_MISMATCH", "監控研究與界限版本不屬於同一製程流"
            )

        events: list[SpcEvent] = []
        # 一次查出此界限版本下所有既有事件，避免迴圈內逐筆查詢（N+1）
        existing_events: Dict[tuple, SpcEvent] = {
            (e.source_point_key, e.chart_kind, e.rule_code): e
            for e in SpcEvent.query.filter(SpcEvent.limit_version_id == limit.id).all()
        }
        for violation in violations:
            chart_kind = str(violation.get("chart_kind") or violation.get("chart") or "")
            rule_code = str(violation.get("rule_code") or violation.get("rule") or "")
            point_index = violation.get("point_index", violation.get("index"))
            if not chart_kind or not rule_code or point_index is None:
                raise SpcValidationError(
                    "SPC_EVENT_INVALID", "失控事件缺少圖別、規則代碼或點序號"
                )
            source_point_key = str(
                violation.get("source_point_key")
                or f"version:{version.id}:point:{int(point_index)}"
            )
            event_key = (source_point_key, chart_kind, rule_code)
            event = existing_events.get(event_key)
            if event is None:
                event = SpcEvent(
                    limit_version_id=limit.id,
                    study_version_id=version.id,
                    sample_id=violation.get("sample_id"),
                    chart_kind=chart_kind,
                    rule_code=rule_code,
                    point_index=int(point_index),
                    source_point_key=source_point_key,
                    observed_value=violation.get("observed_value"),
                    status="open",
                )
                db.session.add(event)
                existing_events[event_key] = event
            events.append(event)
        # 事件、研究版本與 audit 必須由最外層應用服務在同一交易提交。
        db.session.flush()
        return events

    @staticmethod
    def save_ocap(
        event_id: int, actor_id: int, payload: Mapping[str, Any]
    ) -> SpcOcap:
        """新增或更新 OCAP，保留調查、處置、責任與有效性確認。"""

        _require_permission(actor_id, "spc.manage")
        payload = SpcOcapService.validate_payload(payload)
        event = (
            SpcEvent.query.filter_by(id=event_id)
            .with_for_update()
            .first()
        )
        if event is None:
            raise SpcNotFound("SPC_EVENT_NOT_FOUND", "找不到 SPC 失控事件")
        ocap = SpcOcap.query.filter_by(event_id=event.id).first()
        creating = ocap is None
        current_owner_id = ocap.owner_id if ocap is not None else None
        SpcOcapService._validate_owner_change(current_owner_id, payload)
        if ocap is None:
            ocap = SpcOcap(event_id=event.id, created_by=actor_id)
            db.session.add(ocap)

        def audit_snapshot(item: SpcOcap) -> dict[str, Any]:
            return {
                "event_id": item.event_id,
                "investigation_6m": item.investigation_6m,
                "remeasurement": item.remeasurement,
                "process_adjustment": item.process_adjustment,
                "product_disposition": item.product_disposition,
                "owner_id": item.owner_id,
                "effectiveness": item.effectiveness,
                "status": item.status,
                "created_by": item.created_by,
                "updated_by": item.updated_by,
            }

        old_snapshot = None if creating else audit_snapshot(ocap)

        allowed = (
            "investigation_6m", "remeasurement", "process_adjustment",
            "product_disposition", "owner_id", "effectiveness", "status",
        )
        for name in allowed:
            if name in payload:
                setattr(ocap, name, payload[name])
        ocap.updated_by = actor_id

        if ocap.status == "closed":
            if not (ocap.effectiveness or "").strip():
                raise SpcValidationError(
                    "OCAP_EFFECTIVENESS_REQUIRED", "OCAP 結案必須填寫有效性確認"
                )
            event.status = "closed"
        else:
            event.status = "investigating"

        try:
            db.session.flush()
            new_snapshot = audit_snapshot(ocap)
            log_audit(
                actor_id,
                "create_ocap" if creating else "update_ocap",
                "spc_ocap",
                ocap.id,
                old_val=old_snapshot,
                new_val=new_snapshot,
            )
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise SpcConflict(
                "SPC_OCAP_WRITE_CONFLICT",
                "同一事件的 OCAP 已被其他使用者更新，請重新整理後再試",
            ) from exc
        return ocap

    @staticmethod
    def get_event(event_id: int) -> SpcEvent:
        """取得單一 SPC 事件，供 OCAP 儲存後輕量校正。"""

        event = db.session.get(SpcEvent, event_id)
        if event is None:
            raise SpcNotFound("SPC_EVENT_NOT_FOUND", "找不到 SPC 失控事件")
        return event
