"""任務服務 — 橫展任務 CRUD、狀態機、「我的待辦」查詢"""
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import ActionTask, Inspector, User
from ..utils import acquire_number_lock

VALID_CATEGORIES = {
    'pfmea', 'control_plan', 'sop', 'training',
    'cross_part', 'customer_notify', 'other',
}

# 狀態機合法轉換
VALID_TRANSITIONS = {
    'pending':     {'in_progress', 'waived'},
    'in_progress': {'completed', 'waived'},
    'completed':   set(),   # 終態
    'waived':      set(),   # 終態
}

CATEGORY_TITLES = {
    'pfmea':           '更新 PFMEA',
    'control_plan':    '更新控制計畫',
    'sop':             '更新 SOP',
    'training':        '教育訓練',
    'cross_part':      '橫展其他料號',
    'customer_notify': '通知客戶',
    'other':           '其他橫展事項',
}


class TaskService:

    # ── 序號產生 ─────────────────────────────────────────────
    @staticmethod
    def _gen_task_no() -> str:
        today = date.today().strftime('%Y%m%d')
        acquire_number_lock(f'橫展任務.任務單號.TASK.{today}')
        count = ActionTask.query.filter(
            ActionTask.task_no.like(f'TASK-{today}-%')
        ).count()
        return f'TASK-{today}-{count + 1:03d}'

    # ── 建立任務 ─────────────────────────────────────────────
    @staticmethod
    def _create_without_commit(
        source_type: str,
        source_id: int,
        category: str,
        assignee_id: Optional[int] = None,
        due_date: Optional[date] = None,
        description: Optional[str] = None,
        part_nos: Optional[List[str]] = None,
    ) -> ActionTask:
        """建立並 flush 任務，讓外層服務可以與其他異動共用交易。"""
        if category not in VALID_CATEGORIES:
            raise ValueError(f'無效類別：{category}，合法值：{VALID_CATEGORIES}')

        title = CATEGORY_TITLES.get(category, category)
        task = ActionTask(
            task_no=TaskService._gen_task_no(),
            source_type=source_type,
            source_id=source_id,
            category=category,
            title=title,
            description=description,
            assignee_id=assignee_id,
            due_date=due_date,
            part_nos=part_nos,
            status='pending',
        )
        db.session.add(task)
        db.session.flush()
        return task

    @staticmethod
    def create(
        source_type: str,
        source_id: int,
        category: str,
        assignee_id: Optional[int] = None,
        due_date: Optional[date] = None,
        description: Optional[str] = None,
        part_nos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """建立任務並提交；跨服務流程應使用不提交的內部建構器。"""
        task = TaskService._create_without_commit(
            source_type=source_type,
            source_id=source_id,
            category=category,
            assignee_id=assignee_id,
            due_date=due_date,
            description=description,
            part_nos=part_nos,
        )
        db.session.commit()
        return TaskService._to_dict(task)

    # ── 狀態更新（含狀態機驗證）────────────────────────────
    @staticmethod
    def update_status(
        task_id: int,
        new_status: str,
        completion_proof: Optional[str] = None,
        waiver_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        task = db.session.get(ActionTask, task_id)
        if not task:
            raise ValueError('任務不存在')

        allowed = VALID_TRANSITIONS.get(task.status, set())
        if new_status not in allowed:
            raise ValueError(
                f'狀態 {task.status} 不可轉換至 {new_status}，'
                f'合法目標：{allowed if allowed else "（終態）"}'
            )

        # 完成需要證明
        if new_status == 'completed':
            if not completion_proof and not task.completion_proof:
                raise ValueError('標記完成需提供完成證明')
            task.completion_proof = completion_proof or task.completion_proof
            task.completed_at = datetime.now(timezone.utc)

        # 豁免需要理由
        if new_status == 'waived':
            if not waiver_reason:
                raise ValueError('豁免需填寫豁免理由')
            task.waiver_reason = waiver_reason
            task.completed_at = datetime.now(timezone.utc)

        task.status = new_status
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return TaskService._to_dict(task)

    # ── 查詢列表 ─────────────────────────────────────────────
    @staticmethod
    def list_tasks(
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        due_from: Optional[date] = None,
        due_to: Optional[date] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        q = ActionTask.query
        if source_type:
            q = q.filter_by(source_type=source_type)
        if source_id:
            q = q.filter_by(source_id=source_id)
        if assignee_id:
            q = q.filter_by(assignee_id=assignee_id)
        if status:
            q = q.filter_by(status=status)
        if category:
            q = q.filter_by(category=category)
        if due_from:
            q = q.filter(ActionTask.due_date >= due_from)
        if due_to:
            q = q.filter(ActionTask.due_date <= due_to)

        total = q.count()
        # _to_dict 會讀 assignee.name，先 eager load 避免每列各查一次
        tasks = q.options(joinedload(ActionTask.assignee))\
                  .order_by(ActionTask.due_date.asc().nullslast(), ActionTask.created_at.desc())\
                  .offset((page - 1) * per_page).limit(per_page).all()
        return {
            'data': [TaskService._to_dict(t) for t in tasks],
            'total': total,
            'page': page,
            'per_page': per_page,
        }

    # ── 我的待辦 ─────────────────────────────────────────────
    @staticmethod
    def my_tasks(assignee_id: int) -> List[Dict[str, Any]]:
        """回傳指定人員的未完成任務，依期限排序，逾期優先"""
        tasks = ActionTask.query.options(joinedload(ActionTask.assignee)).filter(
            ActionTask.assignee_id == assignee_id,
            ActionTask.status.in_(['pending', 'in_progress']),
        ).order_by(ActionTask.due_date.asc().nullslast()).all()

        today = date.today()
        result = []
        for t in tasks:
            d = TaskService._to_dict(t)
            d['is_overdue'] = bool(t.due_date and t.due_date < today)
            d['overdue_days'] = (today - t.due_date).days if d['is_overdue'] else 0
            result.append(d)
        return result

    @staticmethod
    def my_tasks_for_user(user: User) -> List[Dict[str, Any]]:
        """依登入使用者找到對應品管人員，再回傳該品管人員的待辦。"""
        inspector_id = getattr(user, 'inspector_id', None)
        if not inspector_id and getattr(user, 'username', None):
            inspector = Inspector.query.filter_by(name=user.username).first()
            inspector_id = inspector.id if inspector else None
        if not inspector_id:
            return []
        return TaskService.my_tasks(inspector_id)

    # ── 依來源查詢（用於 CAPA D7 顯示）────────────────────────
    @staticmethod
    def list_by_source(source_type: str, source_id: int) -> List[Dict[str, Any]]:
        tasks = ActionTask.query.options(joinedload(ActionTask.assignee)).filter_by(
            source_type=source_type, source_id=source_id
        ).order_by(ActionTask.created_at.asc()).all()
        return [TaskService._to_dict(t) for t in tasks]

    # ── 刪除（僅 pending 狀態可刪）────────────────────────────
    @staticmethod
    def delete(task_id: int) -> bool:
        task = db.session.get(ActionTask, task_id)
        if not task:
            raise ValueError('任務不存在')
        if task.status not in ('pending',):
            raise ValueError(f'狀態為 {task.status} 的任務不可刪除，請改用豁免')
        db.session.delete(task)
        db.session.commit()
        return True

    # ── D8 結案前 gate 檢查 ────────────────────────────────────
    @staticmethod
    def check_close_gate(source_type: str, source_id: int) -> Dict[str, Any]:
        """確認所有關聯任務皆為 completed 或 waived"""
        tasks = ActionTask.query.filter_by(
            source_type=source_type, source_id=source_id
        ).all()
        blocking = [
            t for t in tasks if t.status in ('pending', 'in_progress')
        ]
        return {
            'can_close': len(blocking) == 0,
            'blocking_tasks': [TaskService._to_dict(t) for t in blocking],
        }

    # ── 序列化 ────────────────────────────────────────────────
    @staticmethod
    def _to_dict(t: ActionTask) -> Dict[str, Any]:
        return {
            'id':               t.id,
            'task_no':          t.task_no,
            'source_type':      t.source_type,
            'source_id':        t.source_id,
            'category':         t.category,
            'title':            t.title,
            'description':      t.description,
            'part_nos':         t.part_nos,
            'assignee_id':      t.assignee_id,
            'assignee_name':    t.assignee.name if t.assignee else None,
            'due_date':         t.due_date.isoformat() if t.due_date else None,
            'status':           t.status,
            'completion_proof': t.completion_proof,
            'waiver_reason':    t.waiver_reason,
            'completed_at':     t.completed_at.isoformat() if t.completed_at else None,
            'created_at':       t.created_at.isoformat() if t.created_at else None,
        }
