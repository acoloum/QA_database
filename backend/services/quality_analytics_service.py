"""品質分析服務 — Pareto、趨勢、CAPA aging、重複問題與供應商排名"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, case, func

from ..extensions import db
from ..models import CorrectiveAction, CustomerComplaint, NCMR
from .date_range import month_bucket
from .vendor_performance_service import VendorPerformanceService


NCMR_DEFECT_CATEGORY_LABELS = {
    'M': 'M - 鋁材原料',
    'E': 'E - 擠型製程',
    'D': 'D - 抽管製程',
    'H': 'H - 熱處理',
    'PO': 'PO - 拋光',
    'SR': 'SR - 打直',
    'T': 'T - 模具治具',
    'S': 'S - 鋸台',
    'P': 'P - 人員操作',
    'Q': 'Q - 品管檢驗',
    'O': 'O - 其他',
}


class QualityAnalyticsService:

    @staticmethod
    def pareto(
        source: str,
        field: str = 'category',
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """回傳 NCMR 或客訴的不良 Pareto 統計（欄位級 GROUP BY 聚合）。"""
        column, filters = QualityAnalyticsService._defect_column(source, field, date_from, date_to)
        rows = db.session.query(
            column.label('bucket'),
            func.count().label('count'),
        ).filter(*filters).group_by(column).order_by(
            func.count().desc(), column.asc(),
        ).all()

        total = sum(row.count for row in rows)
        running = 0
        items = []
        for row in rows[:max(1, limit)]:
            running += row.count
            items.append({
                'label': QualityAnalyticsService._bucket_label(row.bucket, source, field),
                'count': row.count,
                'pct': round(row.count / total * 100, 1) if total else 0,
                'cumulative_pct': round(running / total * 100, 1) if total else 0,
            })
        return {'source': source, 'field': field, 'total': total, 'items': items}

    @staticmethod
    def defect_trends(
        source: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """依月份回傳 Top N 不良分類趨勢（SQL 月份分桶）。"""
        if source == 'complaint':
            date_column = CustomerComplaint.complaint_date
            category_column = CustomerComplaint.defect_category
            filters = QualityAnalyticsService._complaint_filters(date_from, date_to)
        elif source == 'ncmr':
            date_column = NCMR.date
            category_column = NCMR.defect_category
            filters = QualityAnalyticsService._ncmr_filters(date_from, date_to)
        else:
            raise ValueError('source 僅支援 ncmr 或 complaint')

        month = month_bucket(date_column).label('month')
        rows = db.session.query(
            month,
            category_column.label('bucket'),
            func.count().label('count'),
        ).filter(*filters).group_by(month, category_column).all()

        month_set = set()
        category_total: Counter[str] = Counter()
        by_month: Dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            label = QualityAnalyticsService._bucket_label(row.bucket, source, 'category')
            month_set.add(row.month)
            category_total[label] += row.count
            by_month[row.month][label] += row.count

        months = sorted(month_set)
        top_labels = [label for label, _ in category_total.most_common(max(1, top_n))]
        series = [
            {'label': label, 'data': [by_month[m].get(label, 0) for m in months]}
            for label in top_labels
        ]
        return {'source': source, 'months': months, 'series': series}

    @staticmethod
    def capa_aging(today: Optional[date] = None, overdue_limit: int = 10) -> Dict[str, Any]:
        """統計未結案 CAPA aging、逾期清單與平均結案天數（SQL 分桶與 avg 聚合）。"""
        today = today or date.today()
        raw_age = QualityAnalyticsService._age_days_expr(CorrectiveAction.created_at, today)
        # NULL created_at 視為今天（age 0）；負數（未來建立）clamp 到 0，與舊版 max(..., 0) 等價
        age_value = func.coalesce(raw_age, 0)
        safe_age = case((age_value < 0, 0), else_=age_value)
        bucket = case(
            (safe_age <= 7, '0-7'),
            (safe_age <= 14, '8-14'),
            (safe_age <= 30, '15-30'),
            else_='31+',
        ).label('bucket')

        open_filters = [
            CorrectiveAction.eight_d_number.isnot(None),
            CorrectiveAction.status != '已結案',
            CorrectiveAction.deleted_at.is_(None),
        ]
        bucket_rows = db.session.query(
            bucket,
            func.count().label('cnt'),
        ).filter(*open_filters).group_by(bucket).all()

        buckets = {'0-7': 0, '8-14': 0, '15-30': 0, '31+': 0}
        open_count = 0
        for row in bucket_rows:
            buckets[row.bucket] = row.cnt
            open_count += row.cnt

        overdue_filters = [
            *open_filters,
            CorrectiveAction.d0_deadline.isnot(None),
            CorrectiveAction.d0_deadline < today,
        ]
        overdue_count = (
            db.session.query(func.count())
            .select_from(CorrectiveAction)
            .filter(*overdue_filters)
            .scalar()
        )

        # 逾期清單只 select 顯示欄位並 limit，不載入完整 ORM 實體
        overdue_expr = QualityAnalyticsService._date_diff_days(CorrectiveAction.d0_deadline, today)
        overdue_rows = db.session.query(
            CorrectiveAction.id,
            CorrectiveAction.eight_d_number.label('number'),
            CorrectiveAction.status,
            safe_age.label('age_days'),
            CorrectiveAction.d0_deadline.label('deadline'),
            overdue_expr.label('overdue_days'),
        ).filter(*overdue_filters).order_by(overdue_expr.desc()).limit(max(1, overdue_limit)).all()

        overdue_items = [
            {
                'id': row.id,
                'number': row.number,
                'status': row.status,
                'age_days': row.age_days if row.age_days is not None else 0,
                'deadline': row.deadline.isoformat() if row.deadline else None,
                'overdue_days': row.overdue_days if row.overdue_days is not None else 0,
            }
            for row in overdue_rows
        ]

        closed_filters = [
            CorrectiveAction.eight_d_number.isnot(None),
            CorrectiveAction.status == '已結案',
            CorrectiveAction.d8_close_date.isnot(None),
            CorrectiveAction.created_at.isnot(None),
            CorrectiveAction.deleted_at.is_(None),
        ]
        avg_expr = QualityAnalyticsService._close_days_expr()
        avg_value = db.session.query(func.avg(avg_expr)).filter(*closed_filters).scalar()
        avg_close_days = round(float(avg_value), 1) if avg_value is not None else None

        return {
            'buckets': buckets,
            'open_count': open_count,
            'overdue_count': overdue_count,
            'overdue_items': overdue_items,
            'avg_close_days': avg_close_days,
        }

    @staticmethod
    def repeat_issues(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """回傳 NCMR 聚合重複問題與已標記的重複客訴（欄位級 select）。"""
        ncmr_rows = db.session.query(
            NCMR.vendor,
            NCMR.material,
            NCMR.product_info,
            NCMR.defect_category,
            NCMR.defect_detail,
            NCMR.ncmr_number,
            NCMR.date,
        ).filter(*QualityAnalyticsService._ncmr_filters(date_from, date_to)).all()

        groups: Dict[tuple, Dict[str, Any]] = {}
        for row in ncmr_rows:
            key = (
                row.vendor or '未填',
                row.material or '未填',
                row.product_info or '未填',
                row.defect_category or '未分類',
                row.defect_detail or '未分類',
            )
            entry = groups.setdefault(key, {
                'vendor': key[0],
                'material': key[1],
                'product_info': key[2],
                'defect_category': key[3],
                'defect_detail': key[4],
                'count': 0,
                'latest_date': None,
                'numbers': [],
            })
            entry['count'] += 1
            entry['numbers'].append(row.ncmr_number)
            if row.date and (entry['latest_date'] is None or row.date > entry['latest_date']):
                entry['latest_date'] = row.date

        repeated_ncmr = [
            {**entry, 'latest_date': entry['latest_date'].isoformat() if entry['latest_date'] else None}
            for entry in groups.values()
            if entry['count'] >= 2
        ]
        repeated_ncmr.sort(key=lambda x: (x['count'], x['latest_date'] or ''), reverse=True)

        complaint_filters = [
            CustomerComplaint.deleted_at.is_(None),
            CustomerComplaint.is_repeat.is_(True),
        ]
        if date_from:
            complaint_filters.append(CustomerComplaint.complaint_date >= date_from)
        if date_to:
            complaint_filters.append(CustomerComplaint.complaint_date <= date_to)

        complaint_rows = db.session.query(
            CustomerComplaint.id,
            CustomerComplaint.complaint_no,
            CustomerComplaint.customer,
            CustomerComplaint.defect_category,
            CustomerComplaint.complaint_date,
            CustomerComplaint.repeat_refs,
        ).filter(*complaint_filters).order_by(
            CustomerComplaint.complaint_date.desc()
        ).limit(limit).all()

        complaints = [
            {
                'id': row.id,
                'complaint_no': row.complaint_no,
                'customer': row.customer,
                'defect_category': row.defect_category or '未分類',
                'complaint_date': row.complaint_date.isoformat() if row.complaint_date else None,
                'repeat_refs': row.repeat_refs or [],
            }
            for row in complaint_rows
        ]

        return {'ncmr': repeated_ncmr[:limit], 'complaints': complaints}

    @staticmethod
    def vendor_ranking(period: str, limit: int = 10) -> List[Dict[str, Any]]:
        """回傳指定月份供應商績效排名，分數由低到高（委派 VendorPerformanceService）。"""
        rows = VendorPerformanceService.list_by_period(period)
        return rows[:max(1, limit)]

    # ---------------------------------------------------------------
    # SQL 聚合輔助
    # ---------------------------------------------------------------

    @staticmethod
    def _defect_column(source: str, field: str, date_from: Optional[date], date_to: Optional[date]):
        """依 source/field 選取 Pareto 聚合欄位與過濾條件。"""
        if source == 'complaint':
            return CustomerComplaint.defect_category, QualityAnalyticsService._complaint_filters(
                date_from, date_to
            )
        if source != 'ncmr':
            raise ValueError('source 僅支援 ncmr 或 complaint')
        column = NCMR.defect_detail if field == 'detail' else NCMR.defect_category
        return column, QualityAnalyticsService._ncmr_filters(date_from, date_to)

    @staticmethod
    def _bucket_label(bucket: Optional[str], source: str, field: str) -> str:
        """將聚合分桶值轉成顯示文字（含 NCMR 大類代碼翻譯）。"""
        if source == 'complaint' or field == 'detail':
            return bucket or '未分類'
        label = bucket or '未分類'
        return NCMR_DEFECT_CATEGORY_LABELS.get(label, label)

    @staticmethod
    def _ncmr_filters(date_from: Optional[date], date_to: Optional[date]):
        filters = [NCMR.deleted_at.is_(None)]
        if date_from:
            filters.append(NCMR.date >= date_from)
        if date_to:
            filters.append(NCMR.date <= date_to)
        return filters

    @staticmethod
    def _complaint_filters(date_from: Optional[date], date_to: Optional[date]):
        filters = [CustomerComplaint.deleted_at.is_(None)]
        if date_from:
            filters.append(CustomerComplaint.complaint_date >= date_from)
        if date_to:
            filters.append(CustomerComplaint.complaint_date <= date_to)
        return filters

    @staticmethod
    def _age_days_expr(column: Any, today: date):
        """產生 (today - column) 天數表達式；SQLite 用 julianday、PostgreSQL 用 date 相減。

        column 為 NULL 時結果為 NULL，由呼叫方以 coalesce 補 0（等價舊版 None → today）。
        """
        bind = db.session.get_bind()
        today_iso = today.isoformat()
        if bind and bind.dialect.name == 'sqlite':
            return func.cast(func.julianday(today_iso) - func.julianday(column), Integer)
        return func.date(today_iso) - func.date(column)

    @staticmethod
    def _date_diff_days(column: Any, today: date):
        """產生 (today - column) 天數表達式；column 為 Date 欄位（d0_deadline 等）。"""
        bind = db.session.get_bind()
        today_iso = today.isoformat()
        if bind and bind.dialect.name == 'sqlite':
            return func.cast(func.julianday(today_iso) - func.julianday(column), Integer)
        return func.date(today_iso) - func.date(column)

    @staticmethod
    def _close_days_expr():
        """(d8_close_date - created_at) 天數表達式，供已結案平均天數 AVG 使用。"""
        bind = db.session.get_bind()
        if bind and bind.dialect.name == 'sqlite':
            return func.cast(
                func.julianday(CorrectiveAction.d8_close_date)
                - func.julianday(CorrectiveAction.created_at),
                Integer,
            )
        return func.date(CorrectiveAction.d8_close_date) - func.date(CorrectiveAction.created_at)
