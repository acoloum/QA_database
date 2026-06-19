"""Dashboard 聚合服務。"""
from datetime import date
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, or_

from ..extensions import db
from ..models import CorrectiveAction, NCMR, PatrolMain, ReworkRequest, ShippingData


def _month_expr(column: Any):
    """依資料庫方言產生 YYYY-MM 聚合欄位，讓測試 SQLite 與正式 PostgreSQL 都可執行。"""
    bind = db.session.get_bind()
    dialect = bind.dialect.name if bind else ''
    if dialect == 'sqlite':
        return func.strftime('%Y-%m', column)
    return func.to_char(column, 'YYYY-MM')


def _month_counts(model, date_column, since, *filters) -> dict[str, int]:
    month = _month_expr(date_column).label('month')
    rows = db.session.query(
        month,
        func.count().label('cnt'),
    ).filter(
        date_column >= since,
        *filters,
    ).group_by(month).all()
    return {row.month: row.cnt for row in rows}


class DashboardService:
    @staticmethod
    def get_trends(today: date | None = None) -> dict[str, list[dict[str, int | str]]]:
        """取得最近六個月 Dashboard 趨勢資料。"""
        today = today or date.today()
        months = []
        for i in range(5, -1, -1):
            m = today.replace(day=1) - relativedelta(months=i)
            months.append(m.strftime('%Y-%m'))

        six_months_ago = today.replace(day=1) - relativedelta(months=5)

        ncmr_dict = _month_counts(NCMR, NCMR.date, six_months_ago)
        shipping_ok_dict = _month_counts(
            ShippingData,
            ShippingData.date,
            six_months_ago,
            or_(ShippingData.is_ng.is_(False), ShippingData.is_ng.is_(None)),
        )
        shipping_ng_dict = _month_counts(
            ShippingData,
            ShippingData.date,
            six_months_ago,
            ShippingData.is_ng.is_(True),
        )
        patrol_ok_dict = _month_counts(
            PatrolMain,
            PatrolMain.date,
            six_months_ago,
            or_(PatrolMain.is_ng.is_(False), PatrolMain.is_ng.is_(None)),
        )
        patrol_ng_dict = _month_counts(
            PatrolMain,
            PatrolMain.date,
            six_months_ago,
            PatrolMain.is_ng.is_(True),
        )
        rework_dict = _month_counts(ReworkRequest, ReworkRequest.created_at, six_months_ago)

        return {
            "ncmr_by_month": [{"month": m, "count": ncmr_dict.get(m, 0)} for m in months],
            "shipping_ok_by_month": [{"month": m, "count": shipping_ok_dict.get(m, 0)} for m in months],
            "shipping_ng_by_month": [{"month": m, "count": shipping_ng_dict.get(m, 0)} for m in months],
            "patrol_ok_by_month": [{"month": m, "count": patrol_ok_dict.get(m, 0)} for m in months],
            "patrol_ng_by_month": [{"month": m, "count": patrol_ng_dict.get(m, 0)} for m in months],
            "rework_by_month": [{"month": m, "count": rework_dict.get(m, 0)} for m in months],
        }

    @staticmethod
    def get_todos() -> list[dict[str, Any]]:
        """取得 Dashboard 待辦，集中處理各模組摘要欄位相容性。"""
        todos = []

        pending_ncmrs = NCMR.active_query().filter(NCMR.status == '待處理').order_by(NCMR.date.desc()).limit(5).all()
        for n in pending_ncmrs:
            todos.append({
                "type": "ncmr",
                "id": n.ncmr_number,
                "title": f"NCMR {n.ncmr_number} 待處理",
                "description": _truncate(n.description),
                "date": n.date.isoformat() if n.date else None,
                "priority": "high",
                "path": "/ncmr",
            })

        pending_capas = CorrectiveAction.active_query().filter(
            CorrectiveAction.eight_d_number.isnot(None),
            CorrectiveAction.status.in_(['待處理', '進行中']),
        ).order_by(CorrectiveAction.created_at.desc()).limit(5).all()
        for c in pending_capas:
            todos.append({
                "type": "capa",
                "id": c.eight_d_number,
                "title": f"CAPA {c.eight_d_number} {c.status}",
                "description": _truncate(_capa_problem_description(c)),
                "date": c.created_at.isoformat() if c.created_at else None,
                "priority": "medium",
                "path": "/capa",
            })

        pending_reworks = ReworkRequest.active_query().filter(
            ReworkRequest.status.in_(['待審核', '已通過', '進行中']),
        ).order_by(ReworkRequest.created_at.desc()).limit(5).all()
        for r in pending_reworks:
            todos.append({
                "type": "rework",
                "id": r.rework_number,
                "title": f"重工 {r.rework_number} {r.status}",
                "description": _truncate(r.reason),
                "date": r.created_at.isoformat() if r.created_at else None,
                "priority": "medium",
                "path": "/rework",
            })

        todos.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        return todos[:10]


def _truncate(value: str | None, length: int = 50) -> str | None:
    if not value:
        return value
    return value[:length] + "..." if len(value) > length else value


def _capa_problem_description(capa: CorrectiveAction) -> str | None:
    return (
        capa.d2_what
        or capa.d0_symptom
        or capa.d4_root_cause
        or getattr(capa, 'd2', None)
    )
