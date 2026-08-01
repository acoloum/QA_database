"""Dashboard 聚合服務。"""
from datetime import date, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, case, func, or_

from ..extensions import db
from ..models import CorrectiveAction, NCMR, PatrolMain, ReworkRequest, ShippingData
from .date_range import DateWindow, month_bucket

REWORK_TERMINAL_STATUSES = {'已完成', '已結案', '已拒絕', '撤銷'}
REWORK_ACTIONABLE_STATUSES = {'待審核', '已通過', '進行中'}


def _month_expr(column: Any):
    """依資料庫方言產生 YYYY-MM 聚合欄位（委派至 date_range.month_bucket）。"""
    return month_bucket(column)


def _month_counts(model, date_column, since, *filters) -> dict[str, int]:
    month = _month_expr(date_column).label('month')
    active_filters = [model.deleted_at.is_(None)] if hasattr(model, 'deleted_at') else []
    rows = db.session.query(
        month,
        func.count().label('cnt'),
    ).filter(
        date_column >= since,
        *active_filters,
        *filters,
    ).group_by(month).all()
    return {row.month: row.cnt for row in rows}


class DashboardService:
    @staticmethod
    def get_stats(window: DateWindow, comparison: DateWindow | None = None) -> dict[str, Any]:
        """取得指定日期視窗的統計數據（含前一期間比較）。

        DateTime 欄位使用半開區間（含結束日整天），Date 欄位使用閉區間。
        """
        if comparison is None:
            prev_period_days = (window.end_date - window.start_date).days + 1
            comparison = DateWindow(
                start_date=window.start_date - timedelta(days=prev_period_days),
                end_date=window.start_date - timedelta(days=1),
            )

        # ---------- 待處理計數（點時間，無法合併，保留原本四個函式）----------

        # 注意：須與各清單頁一致，使用 active_query() 排除軟刪除紀錄

        def count_pending_ncmr():
            return NCMR.active_query().filter(
                NCMR.status.notin_(['已結案', 'CAR已完成'])
            ).count()

        def count_pending_capa():
            return CorrectiveAction.active_query().filter(
                CorrectiveAction.eight_d_number != None,
                CorrectiveAction.status.in_(['待處理', '進行中'])
            ).count()

        def count_pending_rework():
            return ReworkRequest.active_query().filter(
                ReworkRequest.status.notin_(REWORK_TERMINAL_STATUSES)
            ).count()

        # ---------- ShippingData：一次查詢同時取得 current / previous ----------
        shipping_row = db.session.query(
            func.sum(case(
                (and_(*window.date_filters(ShippingData.date)), 1),
                else_=0
            )).label('current'),
            func.sum(case(
                (and_(*comparison.date_filters(ShippingData.date)), 1),
                else_=0
            )).label('previous'),
        ).first()
        _shipping_current = int(shipping_row.current or 0)
        _shipping_previous = int(shipping_row.previous or 0)

        # ShippingData NG：只需 current 期間的 NG 數（rate 僅對當期計算）
        _shipping_ng = db.session.query(
            func.sum(case(
                (and_(*window.date_filters(ShippingData.date),
                      ShippingData.is_ng == True), 1),
                else_=0
            ))
        ).scalar() or 0
        _shipping_ng = int(_shipping_ng)

        # ---------- PatrolMain：一次查詢同時取得 current / previous ----------
        patrol_row = db.session.query(
            func.sum(case(
                (and_(*window.date_filters(PatrolMain.date)), 1),
                else_=0
            )).label('current'),
            func.sum(case(
                (and_(*comparison.date_filters(PatrolMain.date)), 1),
                else_=0
            )).label('previous'),
        ).first()
        _patrol_current = int(patrol_row.current or 0)
        _patrol_previous = int(patrol_row.previous or 0)

        _patrol_ng = db.session.query(
            func.sum(case(
                (and_(*window.date_filters(PatrolMain.date),
                      PatrolMain.is_ng == True), 1),
                else_=0
            ))
        ).scalar() or 0
        _patrol_ng = int(_patrol_ng)

        # ---------- NCMR：一次查詢同時取得 current / previous（排除軟刪除）----------
        ncmr_row = db.session.query(
            func.sum(case(
                (and_(*window.date_filters(NCMR.date)), 1),
                else_=0
            )).label('current'),
            func.sum(case(
                (and_(*comparison.date_filters(NCMR.date)), 1),
                else_=0
            )).label('previous'),
        ).filter(NCMR.deleted_at.is_(None)).first()
        _ncmr_current = int(ncmr_row.current or 0)
        _ncmr_previous = int(ncmr_row.previous or 0)

        # ---------- CorrectiveAction（CAPA / CAR）：一次查詢各取兩期 ----------
        capa_row = db.session.query(
            func.sum(case(
                (and_(*window.datetime_filters(CorrectiveAction.created_at),
                      CorrectiveAction.eight_d_number != None), 1),
                else_=0
            )).label('current'),
            func.sum(case(
                (and_(*comparison.datetime_filters(CorrectiveAction.created_at),
                      CorrectiveAction.eight_d_number != None), 1),
                else_=0
            )).label('previous'),
        ).filter(CorrectiveAction.deleted_at.is_(None)).first()
        _capa_current = int(capa_row.current or 0)
        _capa_previous = int(capa_row.previous or 0)

        # ---------- ReworkRequest：一次查詢同時取得 current / previous ----------
        rework_row = db.session.query(
            func.sum(case(
                (and_(*window.datetime_filters(ReworkRequest.created_at)), 1),
                else_=0
            )).label('current'),
            func.sum(case(
                (and_(*comparison.datetime_filters(ReworkRequest.created_at)), 1),
                else_=0
            )).label('previous'),
        ).filter(ReworkRequest.deleted_at.is_(None)).first()
        _rework_current = int(rework_row.current or 0)
        _rework_previous = int(rework_row.previous or 0)

        # ---------- 組裝回應 ----------
        stats = {
            "shipping": {
                "current": _shipping_current,
                "previous": _shipping_previous,
                "ng_count": _shipping_ng,
                "ng_rate": round((_shipping_ng / _shipping_current * 100), 1) if _shipping_current > 0 else None,
                "pending": 0
            },
            "patrol": {
                "current": _patrol_current,
                "previous": _patrol_previous,
                "ng_count": _patrol_ng,
                "ng_rate": round((_patrol_ng / _patrol_current * 100), 1) if _patrol_current > 0 else None,
                "pending": 0
            },
            "ncmr": {
                "current": _ncmr_current,
                "previous": _ncmr_previous,
                "pending": count_pending_ncmr()
            },
            "capa": {
                "current": _capa_current,
                "previous": _capa_previous,
                "pending": count_pending_capa()
            },
            "rework": {
                "current": _rework_current,
                "previous": _rework_previous,
                "pending": count_pending_rework()
            }
        }

        # 計算趨勢
        for key in stats:
            curr = stats[key]['current']
            prev = stats[key]['previous']
            if prev == 0:
                stats[key]['trend'] = 'up' if curr > 0 else 'stable'
                stats[key]['change_pct'] = 0
            else:
                change = ((curr - prev) / prev) * 100
                stats[key]['change_pct'] = round(change, 1)
                if change > 10:
                    stats[key]['trend'] = 'up'
                elif change < -10:
                    stats[key]['trend'] = 'down'
                else:
                    stats[key]['trend'] = 'stable'

        return stats

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
            ReworkRequest.status.in_(REWORK_ACTIONABLE_STATUSES),
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
