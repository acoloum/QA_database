"""MSA 再研究要求：由週期或設備／方法事件觸發，並保持冪等。

同一個來源事件重放多次只會產生一筆要求，讓觸發可以安全地由排程、
補跑或事後回填重複執行。
"""

from datetime import date

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    EquipmentStatusEvent,
    MsaRestudyRequest,
    MsaStudy,
    MsaStudyEquipment,
)
from ..utils import log_audit
from .msa_errors import MsaConflict, MsaNotFound, MsaValidationError
from .msa_payload import reject_unknown_fields


TRIGGER_TYPES = {
    "equipment_maintenance",
    "equipment_major_adjustment",
    "calibration_failed",
    "calibration_expired",
    "correction_changed",
    "measurement_method_changed",
    "fixture_changed",
    "software_changed",
    "appraiser_population_changed",
    "product_or_spec_changed",
    "conditional_action_due",
    "periodic_due",
}

# 設備狀態事件類型對應的再研究觸發類型
_EVENT_TRIGGERS = {
    "maintenance": "equipment_maintenance",
    "major_adjustment": "equipment_major_adjustment",
}

# 這些研究狀態代表結論仍在生效，設備變動才需要重新確認
_ACTIVE_STUDY_STATUSES = {"approved"}

_LIST_QUERY_FIELDS = {"page", "page_size", "status", "trigger_type"}


class MsaRestudyService:
    """建立與追蹤再研究要求。"""

    # ------------------------------------------------------------------
    # 事件觸發
    # ------------------------------------------------------------------

    @staticmethod
    def _active_study_ids(equipment_id: int) -> list[int]:
        return db.session.execute(
            db.select(MsaStudyEquipment.study_id)
            .join(MsaStudy, MsaStudy.id == MsaStudyEquipment.study_id)
            .where(
                MsaStudyEquipment.equipment_id == equipment_id,
                MsaStudy.status.in_(_ACTIVE_STUDY_STATUSES),
            )
            .distinct()
        ).scalars().all()

    @staticmethod
    def from_equipment_event(event_id: int, *, actor_id=None):
        """由設備狀態事件建立再研究要求；重放同一事件不會重複建立。"""
        event = db.session.get(EquipmentStatusEvent, event_id)
        if event is None:
            raise MsaNotFound(
                "MSA_STATUS_EVENT_NOT_FOUND",
                "找不到設備狀態事件",
                details={"event_id": event_id},
            )

        trigger_type = _EVENT_TRIGGERS.get(event.event_type)
        if trigger_type is None or not event.triggers_msa_restudy:
            return None

        study_ids = MsaRestudyService._active_study_ids(event.equipment_id)

        created = [
            MsaRestudyService._ensure_request(
                source_study_id=study_id,
                trigger_type=trigger_type,
                source_entity_type="equipment_status_event",
                source_entity_id=event.id,
                payload={
                    "equipment_id": event.equipment_id,
                    "event_type": event.event_type,
                    "reason": event.reason,
                    "occurred_at": (
                        event.occurred_at.isoformat()
                        if event.occurred_at else None
                    ),
                },
                actor_id=actor_id or event.created_by,
            )
            for study_id in study_ids
        ]
        db.session.commit()
        return created[0] if len(created) == 1 else created

    @staticmethod
    def from_calibration_outcome(
        equipment_id: int, calibration_record_id: int, outcome: str,
        *, actor_id=None,
    ):
        """校驗失敗或逾期時，為引用該設備的有效研究建立再研究要求。"""
        trigger_type = {
            "fail": "calibration_failed",
            "expired": "calibration_expired",
        }.get(outcome)
        if trigger_type is None:
            raise MsaValidationError(
                "MSA_RESTUDY_TRIGGER_INVALID",
                "不支援的校驗結果觸發",
                details={"outcome": outcome},
            )

        study_ids = MsaRestudyService._active_study_ids(equipment_id)
        created = [
            MsaRestudyService._ensure_request(
                source_study_id=study_id,
                trigger_type=trigger_type,
                source_entity_type="equipment_calibration",
                source_entity_id=calibration_record_id,
                payload={"equipment_id": equipment_id, "outcome": outcome},
                actor_id=actor_id,
            )
            for study_id in study_ids
        ]
        db.session.commit()
        return created

    @staticmethod
    def create_manual(payload, *, actor_id: int) -> MsaRestudyRequest:
        """人工登錄方法、夾治具、軟體、人員或規格改變等觸發。"""
        data = payload if isinstance(payload, dict) else {}
        trigger_type = data.get("trigger_type")
        if trigger_type not in TRIGGER_TYPES:
            raise MsaValidationError(
                "MSA_RESTUDY_TRIGGER_INVALID",
                "不支援的再研究觸發類型",
                details={
                    "trigger_type": trigger_type,
                    "allowed": sorted(TRIGGER_TYPES),
                },
            )
        study_id = data.get("source_study_id")
        study = db.session.get(MsaStudy, study_id) if study_id else None
        if study is None:
            raise MsaNotFound(
                "MSA_STUDY_NOT_FOUND",
                "找不到來源研究",
                details={"source_study_id": study_id},
            )
        request = MsaRestudyService._ensure_request(
            source_study_id=study.id,
            trigger_type=trigger_type,
            source_entity_type=data.get("source_entity_type") or "manual",
            source_entity_id=data.get("source_entity_id"),
            payload=data.get("trigger_payload") or {},
            due_date=_parse_date(data.get("due_date")),
            actor_id=actor_id,
        )
        db.session.commit()
        return request

    @staticmethod
    def create_periodic_due(as_of: date, *, actor_id=None) -> list:
        """為已到期的核准研究建立週期再研究要求；可安全重複執行。"""
        studies = MsaStudy.query.filter(
            MsaStudy.status.in_(_ACTIVE_STUDY_STATUSES),
            MsaStudy.next_due_date.isnot(None),
            MsaStudy.next_due_date <= as_of,
        ).all()
        created = [
            MsaRestudyService._ensure_request(
                source_study_id=study.id,
                trigger_type="periodic_due",
                source_entity_type="study_due_date",
                source_entity_id=study.id,
                payload={"next_due_date": study.next_due_date.isoformat()},
                due_date=study.next_due_date,
                actor_id=actor_id,
            )
            for study in studies
        ]
        db.session.commit()
        return created

    # ------------------------------------------------------------------
    # 查詢與承接
    # ------------------------------------------------------------------

    @staticmethod
    def get_list(args) -> dict:
        values = dict(args or {})
        reject_unknown_fields(values, _LIST_QUERY_FIELDS)
        page = _bounded_int(values.get("page", 1), minimum=1, maximum=10_000)
        page_size = _bounded_int(
            values.get("page_size", 25), minimum=1, maximum=100,
        )
        query = MsaRestudyRequest.query
        if values.get("status"):
            query = query.filter(MsaRestudyRequest.status == values["status"])
        if values.get("trigger_type"):
            query = query.filter(
                MsaRestudyRequest.trigger_type == values["trigger_type"]
            )
        total = query.count()
        items = (
            query
            .order_by(
                MsaRestudyRequest.due_date.is_(None),
                MsaRestudyRequest.due_date.asc(),
                MsaRestudyRequest.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [MsaRestudyService.serialize(item) for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def start(request_id: int, *, actor_id: int) -> MsaRestudyRequest:
        """由再研究要求建立新的 draft 研究；只複製設計意圖，不複製觀測。"""
        try:
            request = (
                MsaRestudyRequest.query
                .filter_by(id=request_id)
                .with_for_update()
                .one_or_none()
            )
            if request is None:
                raise MsaNotFound(
                    "MSA_RESTUDY_REQUEST_NOT_FOUND",
                    "找不到再研究要求",
                    details={"request_id": request_id},
                )
            if request.new_study_id is not None:
                raise MsaConflict(
                    "MSA_RESTUDY_ALREADY_STARTED",
                    "這筆再研究要求已建立過新研究",
                    details={"new_study_id": request.new_study_id},
                )

            source = db.session.get(MsaStudy, request.source_study_id)
            # 延後匯入避免服務之間循環相依
            from .msa_study_service import MsaStudyService

            new_study = MsaStudyService.create(
                {
                    "study_type": source.study_type,
                    "measurement_purpose": source.measurement_purpose,
                    "characteristic": source.characteristic,
                    "unit": source.unit,
                    "lsl": source.lsl,
                    "usl": source.usl,
                    "no_tolerance_reason": source.no_tolerance_reason,
                    "process_sigma": source.process_sigma,
                    "criteria_profile_id": source.criteria_profile_id,
                    "responsible_user_id": source.responsible_user_id,
                    "primary_executor_id": source.primary_executor_id,
                },
                actor_id=actor_id,
            )
            new_study.previous_approved_study_id = source.id
            request.new_study_id = new_study.id
            request.status = "in_progress"
            db.session.flush()
            log_audit(
                actor_id,
                "start_restudy",
                "msa_restudy",
                request.id,
                new_val={
                    "source_study_id": source.id,
                    "new_study_id": new_study.id,
                    "trigger_type": request.trigger_type,
                },
            )
            db.session.commit()
            return request
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def serialize(request: MsaRestudyRequest) -> dict:
        return {
            "id": request.id,
            "source_study_id": request.source_study_id,
            "trigger_type": request.trigger_type,
            "source_entity_type": request.source_entity_type,
            "source_entity_id": request.source_entity_id,
            "trigger_payload": request.trigger_payload,
            "due_date": (
                request.due_date.isoformat() if request.due_date else None
            ),
            "status": request.status,
            "new_study_id": request.new_study_id,
            "created_by_id": request.created_by_id,
            "created_at": (
                request.created_at.isoformat() if request.created_at else None
            ),
        }

    # ------------------------------------------------------------------
    # 內部
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_request(
        *, source_study_id, trigger_type, source_entity_type,
        source_entity_id, payload, due_date=None, actor_id=None,
    ) -> MsaRestudyRequest:
        """同一來源事件只建立一次；已存在時直接回傳既有要求。"""
        existing = MsaRestudyRequest.query.filter_by(
            source_study_id=source_study_id,
            trigger_type=trigger_type,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
        ).one_or_none()
        if existing is not None:
            return existing

        request = MsaRestudyRequest(
            source_study_id=source_study_id,
            trigger_type=trigger_type,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            trigger_payload=payload or {},
            due_date=due_date,
            status="open",
            created_by_id=actor_id,
        )
        db.session.add(request)
        try:
            with db.session.begin_nested():
                db.session.flush()
        except IntegrityError:
            # 併發下另一個交易先建立了相同來源的要求，改用既有那筆
            db.session.expunge(request)
            return MsaRestudyRequest.query.filter_by(
                source_study_id=source_study_id,
                trigger_type=trigger_type,
                source_entity_type=source_entity_type,
                source_entity_id=source_entity_id,
            ).one()
        log_audit(
            actor_id,
            "create_restudy_request",
            "msa_restudy",
            request.id,
            new_val={
                "source_study_id": source_study_id,
                "trigger_type": trigger_type,
                "source_entity_type": source_entity_type,
                "source_entity_id": source_entity_id,
            },
        )
        return request


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise MsaValidationError(
            "MSA_RESTUDY_DUE_DATE_INVALID",
            "到期日必須是 ISO 日期",
            details={"due_date": str(value)[:40]},
        ) from error


def _bounded_int(value, *, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise MsaValidationError(
            "MSA_RESTUDY_QUERY_INVALID", "分頁參數必須是整數", details={},
        ) from error
    if parsed < minimum or parsed > maximum:
        raise MsaValidationError(
            "MSA_RESTUDY_QUERY_INVALID",
            "分頁參數超出允許範圍",
            details={"minimum": minimum, "maximum": maximum},
        )
    return parsed
