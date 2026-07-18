"""持續 SPC 失控事件同步與 OCAP 處置服務。"""

from typing import Any, Mapping, Sequence

from ..extensions import db
from ..models import SpcEvent, SpcLimitVersion, SpcOcap, SpcStudyVersion
from ..utils import log_audit
from .spc_errors import SpcConflict, SpcNotFound, SpcValidationError
from .spc_study_service import _require_permission


class SpcOcapService:
    """建立去重失控事件並保存可稽核的 OCAP。"""

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
            limit.process_stream_key != version.study.process_stream_key
            or limit.characteristic != version.study.characteristic
        ):
            raise SpcValidationError(
                "SPC_STREAM_MISMATCH", "監控研究與界限版本不屬於同一製程流"
            )

        events: list[SpcEvent] = []
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
            event = SpcEvent.query.filter_by(
                limit_version_id=limit.id,
                source_point_key=source_point_key,
                chart_kind=chart_kind,
                rule_code=rule_code,
            ).first()
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
                db.session.flush()
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
        event = db.session.get(SpcEvent, event_id)
        if event is None:
            raise SpcNotFound("SPC_EVENT_NOT_FOUND", "找不到 SPC 失控事件")
        ocap = SpcOcap.query.filter_by(event_id=event.id).first()
        creating = ocap is None
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
        return ocap
