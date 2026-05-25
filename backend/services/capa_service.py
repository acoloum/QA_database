"""CAPA 服務 — D0-D8 完整 8D 流程、gate 機制、D7 任務產生、AIAG 報表"""
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import CorrectiveAction, NCMR, CustomerComplaint, Inspector, ActionTask
from ..utils import generate_number
from .task_service import TaskService

# 嚴重度 → 嚴格度預設映射（可 override）
SEVERITY_RIGOR_MAP = {
    'Critical': '完整8D',
    'Major':    '完整8D',
    'Minor':    '簡化5D',
}

VALID_SOURCE_TYPES = {'ncmr', 'complaint'}

# D7 橫展類型對應任務 category
D7_TYPE_CATEGORY = {
    'pfmea':           'pfmea',
    'control_plan':    'control_plan',
    'sop':             'sop',
    'training':        'training',
    'cross_part':      'cross_part',
    'customer_notify': 'customer_notify',
    'other':           'other',
}


class CAPAService:

    # ── 序號產生 ─────────────────────────────────────────────
    @staticmethod
    def _gen_8d_number() -> str:
        return generate_number('CAPA', '異常矯正單', '8D單號')

    # ── 從源頭建立 CAPA ──────────────────────────────────────
    @staticmethod
    def create_from_source(
        source_type: str,
        source_id: int,
        symptom: Optional[str] = None,
        severity: str = 'Major',
        creator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """從 NCMR 或客訴開立新 CAPA"""
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f'CAPA 來源類型無效：{source_type}，必須為 ncmr 或 complaint')

        # 驗證來源存在
        if source_type == 'ncmr':
            source = NCMR.query.get(source_id)
            if not source:
                raise ValueError(f'NCMR #{source_id} 不存在')
            symptom = symptom or source.description
        else:
            source = CustomerComplaint.query.get(source_id)
            if not source:
                raise ValueError(f'客訴 #{source_id} 不存在')
            symptom = symptom or source.description

        # 預設嚴格度
        rigor = SEVERITY_RIGOR_MAP.get(severity, '完整8D')

        ca = CorrectiveAction(
            eight_d_number = CAPAService._gen_8d_number(),
            source_type    = source_type,
            source_id      = source_id,
            ncmr_id        = source_id if source_type == 'ncmr' else None,
            status         = '進行中',
            rigor          = rigor,
            d0_symptom     = symptom,
            d0_severity    = severity,
        )
        db.session.add(ca)

        # 更新 NCMR 狀態
        if source_type == 'ncmr' and hasattr(source, 'status'):
            source.status = '矯正中'

        db.session.commit()
        return CAPAService._to_dict(ca)

    # ── 查詢列表 ─────────────────────────────────────────────
    @staticmethod
    def list_capas(
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        customer: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        q = CorrectiveAction.query.filter(
            CorrectiveAction.eight_d_number.isnot(None)
        )
        if source_type:
            q = q.filter_by(source_type=source_type)
        if status:
            q = q.filter_by(status=status)
        if date_from:
            q = q.filter(CorrectiveAction.created_at >= date_from + 'T00:00:00')
        if date_to:
            q = q.filter(CorrectiveAction.created_at <= date_to + 'T23:59:59')

        total = q.count()
        items = q.order_by(CorrectiveAction.id.desc())\
                  .offset((page - 1) * per_page).limit(per_page).all()
        return {
            'data':     [CAPAService._to_list_dict(ca) for ca in items],
            'total':    total,
            'page':     page,
            'per_page': per_page,
        }

    # ── 取得明細 ─────────────────────────────────────────────
    @staticmethod
    def get_detail(capa_id: int) -> Optional[Dict[str, Any]]:
        ca = CorrectiveAction.query.get(capa_id)
        return CAPAService._to_dict(ca) if ca else None

    # ── 更新各 D 步驟 ────────────────────────────────────────
    @staticmethod
    def update_step(capa_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新任意 D 步驟欄位（不觸發 gate，gate 由 close 路由處理）"""
        ca = CorrectiveAction.query.get(capa_id)
        if not ca:
            raise ValueError('CAPA 不存在')
        if ca.status == '已結案':
            raise ValueError('已結案的 CAPA 不可修改')

        # D0
        _setif(ca, 'd0_symptom',   data, 'D0_symptom')
        _setif(ca, 'd0_criteria',  data, 'D0_criteria')
        _setif(ca, 'd0_deadline',  data, 'D0_deadline',  _parse_date)
        if 'D0_severity' in data:
            ca.d0_severity = data['D0_severity']
            # 聯動嚴格度（若 rigor 未被明確 override）
            if 'rigor' not in data:
                ca.rigor = SEVERITY_RIGOR_MAP.get(data['D0_severity'], ca.rigor)
        if 'rigor' in data:
            ca.rigor = data['rigor']   # 明確 override

        # D1
        _setif(ca, 'd1_champion_id', data, 'D1_champion_id')
        _setif(ca, 'd1_leader_id',   data, 'D1_leader_id')
        _setif(ca, 'd1_members',     data, 'D1_members')

        # D2 5W2H
        for fld in ('what', 'where', 'when', 'who', 'why', 'how', 'how_many'):
            _setif(ca, f'd2_{fld}', data, f'D2_{fld}')

        # D3
        _setif(ca, 'd3_action',        data, 'D3_action')
        _setif(ca, 'd3_effective_date', data, 'D3_effective_date', _parse_date)
        _setif(ca, 'd3_verification',   data, 'D3_verification')

        # D4
        _setif(ca, 'd4_tool',       data, 'D4_tool')
        _setif(ca, 'd4_five_why',   data, 'D4_five_why')
        _setif(ca, 'd4_fishbone',   data, 'D4_fishbone')
        _setif(ca, 'd4_root_cause', data, 'D4_root_cause')

        # D5
        _setif(ca, 'd5_action',       data, 'D5_action')
        _setif(ca, 'd5_planned_date', data, 'D5_planned_date', _parse_date)
        _setif(ca, 'd5_verify_plan',  data, 'D5_verify_plan')

        # D6 verified gate
        if 'D6_verified' in data:
            ca.d6_verified = bool(data['D6_verified'])
        _setif(ca, 'd6_implement_date', data, 'D6_implement_date', _parse_date)
        _setif(ca, 'd6_result',         data, 'D6_result')

        # D7 橫展（同步處理任務）
        if 'D7_actions' in data:
            CAPAService._sync_d7_tasks(ca, data['D7_actions'])

        # D8
        _setif(ca, 'd8_confirmation', data, 'D8_confirmation')
        _setif(ca, 'd8_recognition',  data, 'D8_recognition')

        db.session.commit()
        return CAPAService._to_dict(ca)

    # ── D7 任務同步 ──────────────────────────────────────────
    @staticmethod
    def _sync_d7_tasks(ca: CorrectiveAction, actions: List[Dict]) -> None:
        """依 D7_actions 清單新增/刪除橫展任務"""
        existing = {
            t.category: t
            for t in ActionTask.query.filter_by(source_type='capa', source_id=ca.id).all()
        }

        new_categories = {a['type'] for a in actions if a.get('checked')}

        # 新增尚未存在的任務
        for action in actions:
            atype = action.get('type')
            if not action.get('checked') or atype not in D7_TYPE_CATEGORY:
                continue
            if atype not in existing:
                due = _parse_date(action.get('due_date'))
                TaskService.create(
                    source_type  = 'capa',
                    source_id    = ca.id,
                    category     = D7_TYPE_CATEGORY[atype],
                    assignee_id  = action.get('assignee_id'),
                    due_date     = due,
                    description  = action.get('description'),
                    part_nos     = action.get('part_nos'),
                )

        # 取消勾選 → 依狀態決定是否刪除
        for atype, task in existing.items():
            if atype not in new_categories:
                if task.status == 'pending':
                    db.session.delete(task)
                elif task.status == 'in_progress':
                    raise ValueError(
                        f'任務「{task.title}」正在進行中，請先完成或豁免後再取消勾選'
                    )
                elif task.status in ('completed', 'waived'):
                    raise ValueError(
                        f'任務「{task.title}」已{task.status}，不可取消勾選'
                    )

        # 更新 JSON 快照
        ca.d7_actions = actions

    # ── D6 gate 檢查 ─────────────────────────────────────────
    @staticmethod
    def check_d6_gate(capa_id: int) -> bool:
        ca = CorrectiveAction.query.get(capa_id)
        return bool(ca and ca.d6_verified)

    # ── D8 結案 ──────────────────────────────────────────────
    @staticmethod
    def close(capa_id: int, confirmation: str, recognition: Optional[str] = None) -> Dict[str, Any]:
        ca = CorrectiveAction.query.get(capa_id)
        if not ca:
            raise ValueError('CAPA 不存在')
        if ca.status == '已結案':
            raise ValueError('此 CAPA 已結案')

        # D6 gate
        if not ca.d6_verified:
            raise ValueError('D6 驗證尚未通過，無法結案')

        # 任務 gate
        gate = TaskService.check_close_gate('capa', capa_id)
        if not gate['can_close']:
            blocking = [t['title'] for t in gate['blocking_tasks']]
            raise ValueError(
                f'以下橫展任務尚未完成或豁免，無法結案：{", ".join(blocking)}'
            )

        ca.status         = '已結案'
        ca.d8_confirmation= confirmation
        ca.d8_recognition = recognition
        ca.d8_close_date  = date.today()
        ca.closed_at      = datetime.utcnow()
        db.session.commit()
        return CAPAService._to_dict(ca)

    # ── 刪除 ─────────────────────────────────────────────────
    @staticmethod
    def delete(capa_id: int) -> bool:
        ca = CorrectiveAction.query.get(capa_id)
        if not ca:
            raise ValueError('CAPA 不存在')
        # 同步刪除關聯任務（pending 狀態）
        ActionTask.query.filter_by(
            source_type='capa', source_id=capa_id, status='pending'
        ).delete(synchronize_session=False)
        db.session.delete(ca)
        db.session.commit()
        return True

    # ── 進度計算 ─────────────────────────────────────────────
    @staticmethod
    def _calc_progress(ca: CorrectiveAction) -> Dict[str, Any]:
        is_full = ca.rigor == '完整8D'
        steps = (
            [0, 1, 2, 3, 4, 5, 6, 7, 8]
            if is_full
            else [2, 3, 4, 6, 8]  # 簡化 5D
        )
        completed = []
        if ca.d0_symptom or ca.d0_severity:   completed.append(0)
        if ca.d1_leader_id:                    completed.append(1)
        if ca.d2_what or ca.d2:                completed.append(2)
        if ca.d3_action or ca.d3:              completed.append(3)
        if ca.d4_root_cause or ca.d4:          completed.append(4)
        if ca.d5_action or ca.d5:              completed.append(5)
        if ca.d6_verified:                     completed.append(6)
        if ca.d7_actions:                      completed.append(7)
        if ca.d8_confirmation:                 completed.append(8)

        done_steps = [s for s in steps if s in completed]
        pct = round(len(done_steps) / len(steps) * 100) if steps else 0
        return {
            'total_steps':     len(steps),
            'completed_steps': len(done_steps),
            'percent':         pct,
            'step_status':     {str(s): (s in completed) for s in range(9)},
        }

    # ── 序列化（列表用）─────────────────────────────────────
    @staticmethod
    def _to_list_dict(ca: CorrectiveAction) -> Dict[str, Any]:
        return {
            'id':              ca.id,
            'no':              ca.eight_d_number,
            'source_type':     ca.source_type,
            'source_id':       ca.source_id,
            'rigor':           ca.rigor,
            'status':          ca.status,
            'severity':        ca.d0_severity,
            'owner':           ca.leader.name if ca.leader else (ca.owner.name if ca.owner else ''),
            'create_date':     ca.created_at.isoformat() if ca.created_at else None,
            'deadline':        ca.d0_deadline.isoformat() if ca.d0_deadline else None,
            'progress_percent': CAPAService._calc_progress(ca)['percent'],
        }

    # ── 序列化（明細用）─────────────────────────────────────
    @staticmethod
    def _to_dict(ca: CorrectiveAction) -> Dict[str, Any]:
        progress = CAPAService._calc_progress(ca)
        # 取得來源資訊
        source_info = {}
        if ca.source_type == 'ncmr' and ca.ncmr_id:
            n = NCMR.query.get(ca.source_id or ca.ncmr_id)
            if n:
                source_info = {
                    'ncmr_no':    n.ncmr_number,
                    'vendor':     n.vendor,
                    'material':   n.material,
                    'spec':       n.product_info,
                    'defect':     n.description,
                }
        elif ca.source_type == 'complaint':
            c = CustomerComplaint.query.get(ca.source_id)
            if c:
                source_info = {
                    'complaint_no': c.complaint_no,
                    'customer':     c.customer,
                    'product_no':   c.product_no,
                    'defect':       c.description,
                }

        tasks = TaskService.list_by_source('capa', ca.id)

        return {
            'id':              ca.id,
            'no':              ca.eight_d_number,
            'source_type':     ca.source_type,
            'source_id':       ca.source_id,
            'source_info':     source_info,
            'rigor':           ca.rigor,
            'status':          ca.status,
            'progress':        progress,
            # D0
            'D0_symptom':   ca.d0_symptom,
            'D0_criteria':  ca.d0_criteria,
            'D0_severity':  ca.d0_severity,
            'D0_deadline':  ca.d0_deadline.isoformat() if ca.d0_deadline else None,
            # D1
            'D1_champion_id': ca.d1_champion_id,
            'D1_leader_id':   ca.d1_leader_id,
            'D1_members':     ca.d1_members,
            'D1_leader_name': ca.leader.name if ca.leader else None,
            'D1_champion_name': ca.champion.name if ca.champion else None,
            # D2
            'D2_what':     ca.d2_what, 'D2_where': ca.d2_where,
            'D2_when':     ca.d2_when, 'D2_who':   ca.d2_who,
            'D2_why':      ca.d2_why,  'D2_how':   ca.d2_how,
            'D2_how_many': ca.d2_how_many,
            # D3
            'D3_action':        ca.d3_action,
            'D3_effective_date': ca.d3_effective_date.isoformat() if ca.d3_effective_date else None,
            'D3_verification':  ca.d3_verification,
            # D4
            'D4_tool':       ca.d4_tool,
            'D4_five_why':   ca.d4_five_why,
            'D4_fishbone':   ca.d4_fishbone,
            'D4_root_cause': ca.d4_root_cause,
            # D5
            'D5_action':       ca.d5_action,
            'D5_planned_date': ca.d5_planned_date.isoformat() if ca.d5_planned_date else None,
            'D5_verify_plan':  ca.d5_verify_plan,
            # D6
            'D6_implement_date': ca.d6_implement_date.isoformat() if ca.d6_implement_date else None,
            'D6_result':         ca.d6_result,
            'D6_verified':       ca.d6_verified,
            # D7
            'D7_actions': ca.d7_actions or [],
            'tasks':      tasks,
            # D8
            'D8_close_date':   ca.d8_close_date.isoformat() if ca.d8_close_date else None,
            'D8_confirmation': ca.d8_confirmation,
            'D8_recognition':  ca.d8_recognition,
            # 時間戳
            'created_at': ca.created_at.isoformat() if ca.created_at else None,
            'closed_at':  ca.closed_at.isoformat() if ca.closed_at else None,
        }


# ── 工具函數 ─────────────────────────────────────────────────
def _setif(obj, attr: str, data: dict, key: str, transform=None) -> None:
    if key in data:
        val = data[key]
        if transform and val is not None:
            val = transform(val)
        setattr(obj, attr, val)


def _parse_date(val) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))
