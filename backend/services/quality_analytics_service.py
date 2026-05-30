"""品質分析服務 — Pareto、趨勢、CAPA aging、重複問題與供應商排名"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, List, Optional

from ..models import CorrectiveAction, CustomerComplaint, NCMR
from .vendor_performance_service import VendorPerformanceService


class QualityAnalyticsService:
    @staticmethod
    def pareto(
        source: str,
        field: str = 'category',
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """回傳 NCMR 或客訴的不良 Pareto 統計。"""
        records = QualityAnalyticsService._records_for_source(source, date_from, date_to)
        counter: Counter[str] = Counter()

        for record in records:
            label = QualityAnalyticsService._defect_label(record, source, field)
            counter[label or '未分類'] += 1

        total = sum(counter.values())
        running = 0
        items = []
        for label, count in counter.most_common(max(1, limit)):
            running += count
            items.append({
                'label': label,
                'count': count,
                'pct': round(count / total * 100, 1) if total else 0,
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
        """依月份回傳 Top N 不良分類趨勢。"""
        records = QualityAnalyticsService._records_for_source(source, date_from, date_to)
        month_set = set()
        category_total: Counter[str] = Counter()
        by_month: Dict[str, Counter[str]] = defaultdict(Counter)

        for record in records:
            record_date = QualityAnalyticsService._record_date(record, source)
            if not record_date:
                continue
            month = record_date.strftime('%Y-%m')
            label = QualityAnalyticsService._defect_label(record, source, 'category') or '未分類'
            month_set.add(month)
            category_total[label] += 1
            by_month[month][label] += 1

        months = sorted(month_set)
        top_labels = [label for label, _ in category_total.most_common(max(1, top_n))]
        series = [
            {'label': label, 'data': [by_month[m].get(label, 0) for m in months]}
            for label in top_labels
        ]
        return {'source': source, 'months': months, 'series': series}

    @staticmethod
    def capa_aging(today: Optional[date] = None) -> Dict[str, Any]:
        """統計未結案 CAPA aging、逾期清單與平均結案天數。"""
        today = today or date.today()
        open_capas = CorrectiveAction.query.filter(
            CorrectiveAction.eight_d_number.isnot(None),
            CorrectiveAction.status != '已結案',
            CorrectiveAction.deleted_at.is_(None),
        ).all()

        buckets = {'0-7': 0, '8-14': 0, '15-30': 0, '31+': 0}
        overdue_items = []
        for capa in open_capas:
            created_date = capa.created_at.date() if capa.created_at else today
            age_days = max((today - created_date).days, 0)
            buckets[QualityAnalyticsService._aging_bucket(age_days)] += 1
            if capa.d0_deadline and capa.d0_deadline < today:
                overdue_items.append({
                    'id': capa.id,
                    'number': capa.eight_d_number,
                    'status': capa.status,
                    'age_days': age_days,
                    'deadline': capa.d0_deadline.isoformat(),
                    'overdue_days': (today - capa.d0_deadline).days,
                })

        closed_capas = CorrectiveAction.query.filter(
            CorrectiveAction.eight_d_number.isnot(None),
            CorrectiveAction.status == '已結案',
            CorrectiveAction.d8_close_date.isnot(None),
            CorrectiveAction.created_at.isnot(None),
            CorrectiveAction.deleted_at.is_(None),
        ).all()
        close_days = [
            (capa.d8_close_date - capa.created_at.date()).days
            for capa in closed_capas
            if capa.d8_close_date and capa.created_at
        ]
        avg_close_days = round(sum(close_days) / len(close_days), 1) if close_days else None

        overdue_items.sort(key=lambda x: x['overdue_days'], reverse=True)
        return {
            'buckets': buckets,
            'open_count': len(open_capas),
            'overdue_count': len(overdue_items),
            'overdue_items': overdue_items,
            'avg_close_days': avg_close_days,
        }

    @staticmethod
    def repeat_issues(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """回傳 NCMR 聚合重複問題與已標記的重複客訴。"""
        ncmrs = QualityAnalyticsService._filter_ncmr(date_from, date_to).all()
        groups: Dict[tuple, Dict[str, Any]] = {}
        for ncmr in ncmrs:
            key = (
                ncmr.vendor or '未填',
                ncmr.material or '未填',
                ncmr.product_info or '未填',
                ncmr.defect_category or '未分類',
                ncmr.defect_detail or '未分類',
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
            entry['numbers'].append(ncmr.ncmr_number)
            if ncmr.date and (entry['latest_date'] is None or ncmr.date > entry['latest_date']):
                entry['latest_date'] = ncmr.date

        repeated_ncmr = [
            {**entry, 'latest_date': entry['latest_date'].isoformat() if entry['latest_date'] else None}
            for entry in groups.values()
            if entry['count'] >= 2
        ]
        repeated_ncmr.sort(key=lambda x: (x['count'], x['latest_date'] or ''), reverse=True)

        complaint_query = CustomerComplaint.query.filter(
            CustomerComplaint.deleted_at.is_(None),
            CustomerComplaint.is_repeat.is_(True),
        )
        if date_from:
            complaint_query = complaint_query.filter(CustomerComplaint.complaint_date >= date_from)
        if date_to:
            complaint_query = complaint_query.filter(CustomerComplaint.complaint_date <= date_to)

        complaints = [
            {
                'id': c.id,
                'complaint_no': c.complaint_no,
                'customer': c.customer,
                'defect_category': c.defect_category or '未分類',
                'complaint_date': c.complaint_date.isoformat() if c.complaint_date else None,
                'repeat_refs': c.repeat_refs or [],
            }
            for c in complaint_query.order_by(CustomerComplaint.complaint_date.desc()).limit(limit).all()
        ]

        return {'ncmr': repeated_ncmr[:limit], 'complaints': complaints}

    @staticmethod
    def vendor_ranking(period: str, limit: int = 10) -> List[Dict[str, Any]]:
        """回傳指定月份供應商績效排名，分數由低到高。"""
        rows = VendorPerformanceService.list_by_period(period)
        return rows[:max(1, limit)]

    @staticmethod
    def _records_for_source(source: str, date_from: Optional[date], date_to: Optional[date]):
        if source == 'complaint':
            return QualityAnalyticsService._filter_complaints(date_from, date_to).all()
        if source == 'ncmr':
            return QualityAnalyticsService._filter_ncmr(date_from, date_to).all()
        raise ValueError('source 僅支援 ncmr 或 complaint')

    @staticmethod
    def _filter_ncmr(date_from: Optional[date], date_to: Optional[date]):
        query = NCMR.active_query()
        if date_from:
            query = query.filter(NCMR.date >= date_from)
        if date_to:
            query = query.filter(NCMR.date <= date_to)
        return query

    @staticmethod
    def _filter_complaints(date_from: Optional[date], date_to: Optional[date]):
        query = CustomerComplaint.active_query()
        if date_from:
            query = query.filter(CustomerComplaint.complaint_date >= date_from)
        if date_to:
            query = query.filter(CustomerComplaint.complaint_date <= date_to)
        return query

    @staticmethod
    def _record_date(record: Any, source: str) -> Optional[date]:
        return record.complaint_date if source == 'complaint' else record.date

    @staticmethod
    def _defect_label(record: Any, source: str, field: str) -> str:
        if source == 'complaint':
            return record.defect_category or '未分類'
        if field == 'detail':
            return record.defect_detail or '未分類'
        return record.defect_category or '未分類'

    @staticmethod
    def _aging_bucket(age_days: int) -> str:
        if age_days <= 7:
            return '0-7'
        if age_days <= 14:
            return '8-14'
        if age_days <= 30:
            return '15-30'
        return '31+'
