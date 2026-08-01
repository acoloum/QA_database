"""客訴服務 — 客訴 CRUD、應答時效、重複客訴偵測"""
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, func
from ..extensions import db
from ..models import CustomerComplaint, Inspector
from ..errors import APIError, NotFoundError
from ..utils import acquire_number_lock
from .audit_service import AuditService

VALID_TYPES     = {'quality', 'warranty', 'field_failure'}
VALID_STATUSES  = {'待處理', '處理中', '已結案'}
VALID_SEVERITIES= {'Critical', 'Major', 'Minor'}


class ComplaintService:

    # ── 序號產生 ─────────────────────────────────────────────
    @staticmethod
    def _gen_no() -> str:
        today = date.today().strftime('%Y%m%d')
        acquire_number_lock(f'客訴紀錄.客訴單號.CC.{today}')
        count = CustomerComplaint.active_query().filter(
            CustomerComplaint.complaint_no.like(f'CC-{today}-%')
        ).count()
        return f'CC-{today}-{count + 1:03d}'

    # ── 建立客訴 ─────────────────────────────────────────────
    @staticmethod
    def create(data: Dict[str, Any], creator_id: Optional[int] = None) -> Dict[str, Any]:
        required = ('customer', 'complaint_date', 'description')
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise ValueError(f'缺少必填欄位：{missing}')

        ctype = data.get('complaint_type', 'quality')
        if ctype not in VALID_TYPES:
            raise ValueError(f'無效客訴類型：{ctype}')

        c_date = data['complaint_date']
        if isinstance(c_date, str):
            c_date = date.fromisoformat(c_date)

        complaint = CustomerComplaint(
            complaint_no   = ComplaintService._gen_no(),
            customer       = data['customer'],
            complaint_date = c_date,
            material       = data.get('material'),
            spec           = data.get('spec'),
            extrusion_nos  = data.get('extrusion_nos') or [],
            description    = data['description'],
            severity       = data.get('severity'),
            defect_category= data.get('defect_category'),
            complaint_type = ctype,
            # Warranty / Field Failure
            device_serial  = data.get('device_serial'),
            usage_env      = data.get('usage_env'),
            failure_hours  = data.get('failure_hours'),
            # 應答時效
            initial_reply_deadline = _parse_date(data.get('initial_reply_deadline')),
            final_reply_deadline   = _parse_date(data.get('final_reply_deadline')),
            status     = '待處理',
            created_by = creator_id,
        )
        db.session.add(complaint)
        db.session.flush()  # 取得 id

        # 重複客訴偵測
        ComplaintService._check_repeat(complaint)

        db.session.commit()
        return ComplaintService._to_dict(complaint)

    # ── 重複客訴偵測（12 個月內相同客戶+材質+規格+不良類別）────────
    @staticmethod
    def _check_repeat(complaint: CustomerComplaint) -> None:
        cutoff = date.today() - timedelta(days=365)
        q = CustomerComplaint.active_query().filter(
            CustomerComplaint.customer        == complaint.customer,
            CustomerComplaint.material        == complaint.material,
            CustomerComplaint.spec            == complaint.spec,
            CustomerComplaint.defect_category == complaint.defect_category,
            CustomerComplaint.complaint_date  >= cutoff,
            CustomerComplaint.id              != complaint.id,
        )
        history = q.all()
        if history:
            complaint.is_repeat   = True
            complaint.repeat_refs = [h.complaint_no for h in history]
        else:
            complaint.is_repeat   = False
            complaint.repeat_refs = []

    # ── 查詢列表 ─────────────────────────────────────────────
    @staticmethod
    def list_complaints(
        customer: Optional[str] = None,
        material: Optional[str] = None,
        spec: Optional[str] = None,
        status: Optional[str] = None,
        complaint_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        is_repeat: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        q = CustomerComplaint.active_query()
        if customer:
            q = q.filter(CustomerComplaint.customer.ilike(f'%{customer}%'))
        if material:
            q = q.filter(CustomerComplaint.material.ilike(f'%{material}%'))
        if spec:
            q = q.filter(CustomerComplaint.spec.ilike(f'%{spec}%'))
        if status:
            q = q.filter_by(status=status)
        if complaint_type:
            q = q.filter_by(complaint_type=complaint_type)
        if date_from:
            q = q.filter(CustomerComplaint.complaint_date >= date_from)
        if date_to:
            q = q.filter(CustomerComplaint.complaint_date <= date_to)
        if is_repeat is not None:
            q = q.filter_by(is_repeat=is_repeat)

        total = q.count()
        # 依開單順序排序：越新開立的單（識別碼越大）排在越上面，方便後續編輯
        items = q.order_by(CustomerComplaint.id.desc())\
                  .offset((page - 1) * per_page).limit(per_page).all()
        return {
            'data': [ComplaintService._to_dict(c) for c in items],
            'total': total,
            'page': page,
            'per_page': per_page,
        }

    # ── 取得明細 ─────────────────────────────────────────────
    @staticmethod
    def get_detail(complaint_id: int) -> Optional[Dict[str, Any]]:
        c = CustomerComplaint.active_query().filter(CustomerComplaint.id == complaint_id).first()
        return ComplaintService._to_dict(c) if c else None

    # ── 更新 ─────────────────────────────────────────────────
    @staticmethod
    def update(complaint_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        c = CustomerComplaint.active_query().filter(CustomerComplaint.id == complaint_id).first()
        if not c:
            raise ValueError('客訴不存在')

        updatable = (
            'customer', 'complaint_date', 'material', 'spec', 'extrusion_nos',
            'description', 'severity', 'defect_category', 'complaint_type',
            'device_serial', 'usage_env', 'failure_hours',
            'initial_reply_deadline', 'final_reply_deadline',
            'initial_reply', 'final_reply',
            'status',
        )
        for field in updatable:
            if field in data:
                val = data[field]
                if field in ('complaint_date', 'initial_reply_deadline', 'final_reply_deadline'):
                    val = _parse_date(val)
                setattr(c, field, val)

        # 狀態切換：填初步回覆 → 處理中
        if data.get('initial_reply') and c.status == '待處理':
            c.status = '處理中'
            c.initial_reply_date = datetime.now(timezone.utc)
        if data.get('final_reply'):
            c.final_reply_date = datetime.now(timezone.utc)

        c.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return ComplaintService._to_dict(c)

    # ── 刪除 ─────────────────────────────────────────────────
    @staticmethod
    def delete(complaint_id: int, *, actor_id: Optional[int]) -> bool:
        try:
            c = ComplaintService._locked_active(complaint_id)
            if not c:
                raise NotFoundError('客訴不存在')
            old_value = ComplaintService._audit_snapshot(c)
            c.soft_delete()
            AuditService.record(
                actor_id=actor_id,
                action='delete',
                module='客訴',
                record_id=c.id,
                old_value=old_value,
                new_value=ComplaintService._audit_snapshot(c),
            )
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise

    # ── 從客訴開立重工 ───────────────────────────────────────
    @staticmethod
    def open_rework(complaint_id: int, *, actor_id: Optional[int]) -> Dict[str, Any]:
        try:
            c = ComplaintService._locked_active(complaint_id)
            if not c:
                raise NotFoundError('客訴不存在')
            if c.related_rework_id:
                raise APIError(
                    f'此客訴已開立重工單（ID: {c.related_rework_id}）',
                    code='COMPLAINT_REWORK_EXISTS',
                    status_code=409,
                )
            old_value = ComplaintService._audit_snapshot(c)
            from ..services.rework_service import ReworkService
            result = ReworkService._create_from_complaint(c)
            c.related_rework_id = result['rework_id']
            c.status = '處理中'
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='重工',
                record_id=result['rework_id'],
                old_value={'source': old_value},
                new_value={
                    'source': ComplaintService._audit_snapshot(c),
                    'rework_id': result['rework_id'],
                },
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def open_capa(complaint_id: int, *, actor_id: Optional[int]) -> Dict[str, Any]:
        """在單一交易中建立 CAPA 並關聯客訴。"""
        try:
            c = ComplaintService._locked_active(complaint_id)
            if not c:
                raise NotFoundError('客訴不存在')
            if c.related_capa_id:
                raise APIError(
                    f'此客訴已開立 CAPA（ID: {c.related_capa_id}）',
                    code='COMPLAINT_CAPA_EXISTS',
                    status_code=409,
                )
            old_value = ComplaintService._audit_snapshot(c)
            from ..services.capa_service import CAPAService
            result = CAPAService._create_from_source(
                source_type='complaint',
                source_id=c.id,
                symptom=c.description,
                severity=c.severity or 'Major',
                creator_id=actor_id,
            )
            c.related_capa_id = result['id']
            c.status = '處理中'
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='CAPA',
                record_id=result['id'],
                old_value={'source': old_value},
                new_value={
                    'source': ComplaintService._audit_snapshot(c),
                    'capa_id': result['id'],
                },
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def _locked_active(complaint_id: int) -> Optional[CustomerComplaint]:
        return db.session.execute(
            db.select(CustomerComplaint)
            .where(
                CustomerComplaint.id == complaint_id,
                CustomerComplaint.deleted_at.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    @staticmethod
    def _audit_snapshot(c: CustomerComplaint) -> Dict[str, Any]:
        return {
            'id': c.id,
            'status': c.status,
            'related_capa_id': c.related_capa_id,
            'related_rework_id': c.related_rework_id,
            'deleted_at': c.deleted_at,
        }

    # ── 開立 CAPA（回傳 CAPA source 資訊，由 CAPA service 建立）
    @staticmethod
    def prepare_capa_source(complaint_id: int) -> Dict[str, Any]:
        c = CustomerComplaint.active_query().filter(CustomerComplaint.id == complaint_id).first()
        if not c:
            raise ValueError('客訴不存在')
        if c.related_capa_id:
            raise ValueError(f'此客訴已開立 CAPA（ID: {c.related_capa_id}）')
        return {
            'source_type': 'complaint',
            'source_id':   c.id,
            'symptom':     c.description,
            'customer':    c.customer,
            'severity':    c.severity or 'Major',
        }

    # ── 逾期待辦查詢（Dashboard 用）────────────────────────────
    @staticmethod
    def overdue_list() -> List[Dict[str, Any]]:
        today = date.today()
        items = CustomerComplaint.active_query().filter(
            CustomerComplaint.status.in_(['待處理', '處理中']),
            CustomerComplaint.initial_reply_deadline < today,
        ).order_by(CustomerComplaint.initial_reply_deadline.asc()).all()
        return [ComplaintService._to_dict(c) for c in items]

    # ── 重複客訴 Dashboard（過去 30 天警示）─────────────────────
    @staticmethod
    def recent_repeats(days: int = 30) -> List[Dict[str, Any]]:
        cutoff = date.today() - timedelta(days=days)
        items = CustomerComplaint.active_query().filter(
            CustomerComplaint.is_repeat == True,
            CustomerComplaint.complaint_date >= cutoff,
        ).order_by(CustomerComplaint.complaint_date.desc()).all()
        return [ComplaintService._to_dict(c) for c in items]

    # ── 序列化 ───────────────────────────────────────────────
    @staticmethod
    def _to_dict(c: CustomerComplaint) -> Dict[str, Any]:
        today = date.today()
        d = {
            'id':           c.id,
            'complaint_no': c.complaint_no,
            'customer':     c.customer,
            'complaint_date': c.complaint_date.isoformat() if c.complaint_date else None,
            'material':     c.material,
            'spec':         c.spec,
            'extrusion_nos': c.extrusion_nos or [],
            'description':  c.description,
            'severity':     c.severity,
            'defect_category': c.defect_category,
            'complaint_type':  c.complaint_type,
            # Warranty
            'device_serial': c.device_serial,
            'usage_env':     c.usage_env,
            'failure_hours': c.failure_hours,
            # 應答時效
            'initial_reply_deadline': c.initial_reply_deadline.isoformat() if c.initial_reply_deadline else None,
            'final_reply_deadline':   c.final_reply_deadline.isoformat() if c.final_reply_deadline else None,
            # 回覆
            'initial_reply':      c.initial_reply,
            'initial_reply_date': c.initial_reply_date.isoformat() if c.initial_reply_date else None,
            'final_reply':        c.final_reply,
            'final_reply_date':   c.final_reply_date.isoformat() if c.final_reply_date else None,
            # 重複
            'is_repeat':   c.is_repeat,
            'repeat_refs': c.repeat_refs or [],
            # 關聯
            'related_capa_id':   c.related_capa_id,
            'related_rework_id': c.related_rework_id,
            'status':            c.status,
            'created_by':      c.created_by,
            'created_at':      c.created_at.isoformat() if c.created_at else None,
        }
        # 逾期計算
        if c.initial_reply_deadline and c.status in ('待處理', '處理中'):
            d['overdue_days'] = max(0, (today - c.initial_reply_deadline).days)
            d['is_overdue']   = d['overdue_days'] > 0
        else:
            d['overdue_days'] = 0
            d['is_overdue']   = False
        return d


# ── 工具函數 ────────────────────────────────────────────────
def _parse_date(val) -> Optional[date]:
    if val is None or val == '':
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))
