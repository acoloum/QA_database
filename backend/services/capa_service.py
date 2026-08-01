"""CAPA 服務 — D0-D8 完整 8D 流程、gate 機制、D7 任務產生、AIAG 報表"""
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import CorrectiveAction, NCMR, CustomerComplaint, Inspector, ActionTask
from ..utils import generate_number, validate_status_transition
from .task_service import TaskService
from .audit_service import AuditService

# 嚴重度 → 嚴格度預設映射（可 override）
SEVERITY_RIGOR_MAP = {
    'Critical': '完整8D',
    'Major':    '完整8D',
    'Minor':    '簡化5D',
}

VALID_SOURCE_TYPES = {'ncmr', 'complaint'}

# 各 D 步驟顯示名稱（結案檢查訊息用）
D_STEP_LABELS = {
    0: 'D0 緊急應對', 1: 'D1 成立團隊', 2: 'D2 問題描述',
    3: 'D3 暫時對策', 4: 'D4 根本原因', 5: 'D5 永久對策',
    6: 'D6 實施驗證', 7: 'D7 橫向展開', 8: 'D8 結案確認',
}

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
    def _create_from_source(
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
        d2_what = d2_who = d2_where = d2_how = d2_how_many = None
        if source_type == 'ncmr':
            source = NCMR.active_query().filter_by(id=source_id).first()
            if not source:
                raise ValueError(f'NCMR #{source_id} 不存在')
            symptom = symptom or source.description
            # 從 NCMR 預填 D2 5W2H
            d2_what     = source.description
            d2_who      = source.vendor
            d2_where    = source.source
            d2_how      = source.defect_detail
            qty_str     = f"{source.defect_quantity or '?'} / {source.quantity or '?'} 支"
            d2_how_many = qty_str
        else:
            source = CustomerComplaint.active_query().filter_by(id=source_id).first()
            if not source:
                raise ValueError(f'客訴 #{source_id} 不存在')
            symptom = symptom or source.description
            d2_what = source.description

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
            # D2 從來源預填
            d2_what        = d2_what,
            d2_who         = d2_who,
            d2_where       = d2_where,
            d2_how         = d2_how,
            d2_how_many    = d2_how_many,
        )
        db.session.add(ca)
        db.session.flush()

        # 更新 NCMR 狀態
        if source_type == 'ncmr' and hasattr(source, 'status'):
            source.status = '矯正中'

        return CAPAService._to_dict(ca)

    @staticmethod
    def create_from_source(
        source_type: str,
        source_id: int,
        symptom: Optional[str] = None,
        severity: str = 'Major',
        creator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """相容既有客訴流程；來源 route 的全面交易遷移由 Task 8 完成。"""
        try:
            result = CAPAService._create_from_source(
                source_type,
                source_id,
                symptom,
                severity,
                creator_id,
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def open_from_ncmr(
        ncmr_id: int,
        *,
        symptom: Optional[str] = None,
        severity: str = 'Major',
        actor_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """在單一交易內開立 CAPA、更新 NCMR 並寫入一筆稽核。"""
        try:
            ncmr = NCMR.active_query().filter_by(id=ncmr_id).with_for_update().first()
            if not ncmr:
                raise ValueError(f'NCMR #{ncmr_id} 不存在')
            if ncmr.related_capa_id:
                raise ValueError('此 NCMR 已開立 CAPA，不可重複開立')

            old_source = {
                'status': ncmr.status,
                'related_capa_id': ncmr.related_capa_id,
                'related_capa_source': ncmr.related_capa_source,
            }
            result = CAPAService._create_from_source(
                'ncmr',
                ncmr_id,
                symptom or ncmr.description,
                severity,
                actor_id,
            )
            ncmr.related_capa_id = result['id']
            ncmr.related_capa_source = 'capa'
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='CAPA',
                record_id=result['id'],
                old_value={'source': old_source},
                new_value={
                    'eight_d_number': result.get('no'),
                    'source_type': 'ncmr',
                    'source_id': ncmr_id,
                    'source': {
                        'status': ncmr.status,
                        'related_capa_id': ncmr.related_capa_id,
                        'related_capa_source': ncmr.related_capa_source,
                    },
                },
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    # ── 查詢列表 ─────────────────────────────────────────────
    @staticmethod
    def list_capas(
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date | str] = None,
        date_to: Optional[date | str] = None,
        customer: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        q = CorrectiveAction.active_query().filter(
            CorrectiveAction.eight_d_number.isnot(None)
        )
        if source_type:
            q = q.filter_by(source_type=source_type)
        if status:
            q = q.filter_by(status=status)
        if date_from:
            q = q.filter(CorrectiveAction.created_at >= datetime.combine(_coerce_date(date_from), datetime.min.time()))
        if date_to:
            q = q.filter(CorrectiveAction.created_at <= datetime.combine(_coerce_date(date_to), datetime.max.time()))

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
        ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
        return CAPAService._to_dict(ca) if ca else None

    # ── 更新各 D 步驟 ────────────────────────────────────────
    @staticmethod
    def update_step(capa_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新任意 D 步驟欄位（不觸發 gate，gate 由 close 路由處理）"""
        ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
        if not ca:
            raise ValueError('CAPA 不存在')
        if ca.status == '已結案':
            raise ValueError('已結案的 CAPA 不可修改')

        # 狀態轉移驗證
        new_status = data.get('status') or data.get('狀態')
        if new_status and new_status != ca.status:
            validate_status_transition('CAPA', ca.status, new_status)
            ca.status = new_status

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

        # 新增尚未存在的任務；已存在者同步更新指派人/期限/說明
        for action in actions:
            atype = action.get('type')
            if not action.get('checked') or atype not in D7_TYPE_CATEGORY:
                continue
            due = _parse_date(action.get('due_date'))
            if atype not in existing:
                TaskService.create(
                    source_type  = 'capa',
                    source_id    = ca.id,
                    category     = D7_TYPE_CATEGORY[atype],
                    assignee_id  = action.get('assignee_id'),
                    due_date     = due,
                    description  = action.get('description'),
                    part_nos     = action.get('part_nos'),
                )
            else:
                task = existing[atype]
                # 已完成/豁免的任務視為定案，不再回寫
                if task.status in ('pending', 'in_progress'):
                    task.assignee_id = action.get('assignee_id')
                    task.due_date    = due
                    task.description = action.get('description')
                    if action.get('part_nos') is not None:
                        task.part_nos = action.get('part_nos')

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
        ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
        return bool(ca and ca.d6_verified)

    # ── 步驟完成度檢查 ────────────────────────────────────────
    @staticmethod
    def _missing_steps(ca: CorrectiveAction) -> List[int]:
        """回傳該嚴格度下尚未完成的步驟編號。
        不含 D6（另有專屬 gate）與 D8（於結案動作時填寫）。"""
        progress = CAPAService._calc_progress(ca)
        steps = [0, 1, 2, 3, 4, 5, 6, 7, 8] if ca.rigor == '完整8D' else [2, 3, 4, 6, 8]
        return [s for s in steps if s not in (6, 8) and not progress['step_status'][str(s)]]

    @staticmethod
    def get_missing_step_labels(capa_id: int) -> List[str]:
        ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
        if not ca:
            return []
        return [D_STEP_LABELS[s] for s in CAPAService._missing_steps(ca)]

    # ── D8 結案 ──────────────────────────────────────────────
    @staticmethod
    def close(capa_id: int, confirmation: str, recognition: Optional[str] = None) -> Dict[str, Any]:
        ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
        if not ca:
            raise ValueError('CAPA 不存在')
        if ca.status == '已結案':
            raise ValueError('此 CAPA 已結案')

        # D6 gate
        if not ca.d6_verified:
            raise ValueError('D6 驗證尚未通過，無法結案')

        # 步驟完成度 gate：所有步驟（依嚴格度）皆須完成，避免結案後進度未達 100%
        missing = CAPAService._missing_steps(ca)
        if missing:
            labels = '、'.join(D_STEP_LABELS[s] for s in missing)
            raise ValueError(f'以下步驟尚未完成，無法結案：{labels}')

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
        ca.closed_at      = datetime.now(timezone.utc)

        # CAPA 結案時，若來源為 NCMR，自動更新 NCMR 狀態為「矯正完成」
        if ca.ncmr_id:
            ncmr = NCMR.active_query().filter_by(id=ca.ncmr_id).first()
            if ncmr and ncmr.status == '矯正中':
                ncmr.status = '矯正完成'

        # 若來源為客訴，同步將客訴狀態設為已結案
        if ca.source_type == 'complaint' and ca.source_id:
            complaint = CustomerComplaint.active_query().filter_by(id=ca.source_id).first()
            if complaint:
                complaint.status = '已結案'

        db.session.commit()
        return CAPAService._to_dict(ca)

    # ── 刪除 ─────────────────────────────────────────────────
    @staticmethod
    def delete(capa_id: int) -> bool:
        ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
        if not ca:
            raise ValueError('CAPA 不存在')
        # 若來源為客訴，將客訴狀態回退為待處理並清空 related_capa_id
        if ca.source_type == 'complaint' and ca.source_id:
            complaint = CustomerComplaint.active_query().filter_by(id=ca.source_id).first()
            if complaint:
                complaint.status = '待處理'
                complaint.related_capa_id = None
        if ca.source_type == 'ncmr' and (ca.source_id or ca.ncmr_id):
            ncmr = NCMR.active_query().filter_by(id=ca.source_id or ca.ncmr_id).first()
            if ncmr and ncmr.related_capa_id == ca.id:
                ncmr.related_capa_id = None
                ncmr.related_capa_source = None
                ncmr.status = '待處理'

        # 同步刪除關聯任務（pending 狀態）
        ActionTask.query.filter_by(
            source_type='capa', source_id=capa_id, status='pending'
        ).delete(synchronize_session=False)
        # 軟刪除：設定 deleted_at 時間戳，而非真正 DELETE
        ca.soft_delete()
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
        # D4 視為完成：彙整欄位、舊欄位、或分析工具（5Why／魚骨圖）任一有內容
        d4_tool_filled = (
            any(
                (w.get('why') or w.get('answer'))
                for w in (ca.d4_five_why or []) if isinstance(w, dict)
            )
            or any(v for v in (ca.d4_fishbone or {}).values() if v)
        )
        completed = []
        if ca.d0_symptom or ca.d0_severity:   completed.append(0)
        if ca.d1_leader_id:                    completed.append(1)
        if ca.d2_what or ca.d2:                completed.append(2)
        if ca.d3_action or ca.d3:              completed.append(3)
        if ca.d4_root_cause or ca.d4 or d4_tool_filled: completed.append(4)
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
        # 依來源類型取得「廠商/客戶」與「不良描述」，供清單顯示
        vendor = None
        description = None
        if ca.source_type == 'ncmr' or ca.ncmr_id:
            ncmr = NCMR.active_query().filter_by(id=ca.source_id or ca.ncmr_id).first()
            if ncmr:
                vendor      = ncmr.vendor
                description = ncmr.description
        elif ca.source_type == 'complaint':
            c = CustomerComplaint.active_query().filter_by(id=ca.source_id).first()
            if c:
                vendor      = c.customer       # 客訴以客戶名稱對應「廠商」欄
                description = c.description
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
            'vendor':          vendor,
            'ncmr_description': description,
        }

    # ── 序列化（明細用）─────────────────────────────────────
    @staticmethod
    def _to_dict(ca: CorrectiveAction) -> Dict[str, Any]:
        progress = CAPAService._calc_progress(ca)
        # 取得來源資訊
        source_info = {}
        if ca.source_type == 'ncmr' and ca.ncmr_id:
            n = NCMR.active_query().filter_by(id=ca.source_id or ca.ncmr_id).first()
            if n:
                source_info = {
                    'ncmr_no':       n.ncmr_number,
                    'vendor':        n.vendor,
                    'material':      n.material,
                    'spec':          n.product_info,
                    'defect':        n.description,
                    'defect_detail': n.defect_detail,
                    'source':        n.source,
                    'total_qty':     n.quantity,
                    'defect_qty':    n.defect_quantity,
                    'ncmr_date':     n.date.isoformat() if n.date else None,
                }
        elif ca.source_type == 'complaint':
            c = CustomerComplaint.active_query().filter_by(id=ca.source_id).first()
            if c:
                source_info = {
                    'complaint_no': c.complaint_no,
                    'customer':     c.customer,
                    'material':     c.material,
                    'spec':         c.spec,
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


def _coerce_date(val) -> date:
    """相容 route 已解析的 date 與舊呼叫端傳入的 YYYY-MM-DD 字串。"""
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))
