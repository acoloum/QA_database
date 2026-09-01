"""客訴統計服務 — 客戶、材質規格、不良類別、月份、Warranty 維度"""
from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy import func, extract
from ..extensions import db
from ..models import CustomerComplaint


class ComplaintStatsService:

    @staticmethod
    def by_customer(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """依客戶維度統計件數與重複率"""
        q = db.session.query(
            CustomerComplaint.customer,
            func.count(CustomerComplaint.id).label('total'),
            func.sum(
                func.cast(CustomerComplaint.is_repeat, db.Integer)
            ).label('repeat_count'),
        ).group_by(CustomerComplaint.customer)
        q = _apply_filters(q, date_from, date_to)
        rows = q.order_by(func.count(CustomerComplaint.id).desc()).all()
        return [
            {
                'customer':      r.customer,
                'total':         r.total,
                'repeat_count':  int(r.repeat_count or 0),
                'repeat_rate':   round(int(r.repeat_count or 0) / r.total * 100, 1) if r.total else 0,
            }
            for r in rows
        ]

    @staticmethod
    def by_product(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """依材質+規格維度統計件數與重複率"""
        q = db.session.query(
            CustomerComplaint.material,
            CustomerComplaint.spec,
            func.count(CustomerComplaint.id).label('total'),
            func.sum(
                func.cast(CustomerComplaint.is_repeat, db.Integer)
            ).label('repeat_count'),
        ).group_by(CustomerComplaint.material, CustomerComplaint.spec)
        q = _apply_filters(q, date_from, date_to)
        rows = q.order_by(func.count(CustomerComplaint.id).desc()).all()
        return [
            {
                'material':     r.material or '—',
                'spec':         r.spec or '—',
                'total':        r.total,
                'repeat_count': int(r.repeat_count or 0),
                'repeat_rate':  round(int(r.repeat_count or 0) / r.total * 100, 1) if r.total else 0,
            }
            for r in rows
        ]

    @staticmethod
    def by_category(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """依不良類別維度統計"""
        q = db.session.query(
            CustomerComplaint.defect_category,
            func.count(CustomerComplaint.id).label('total'),
        ).group_by(CustomerComplaint.defect_category)
        q = _apply_filters(q, date_from, date_to)
        rows = q.order_by(func.count(CustomerComplaint.id).desc()).all()
        return [
            {'defect_category': r.defect_category or '未分類', 'total': r.total}
            for r in rows
        ]

    @staticmethod
    def by_month(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """依月份維度統計趨勢"""
        q = db.session.query(
            extract('year',  CustomerComplaint.complaint_date).label('year'),
            extract('month', CustomerComplaint.complaint_date).label('month'),
            func.count(CustomerComplaint.id).label('total'),
        ).group_by('year', 'month')
        q = _apply_filters(q, date_from, date_to)
        rows = q.order_by('year', 'month').all()
        return [
            {
                'year_month': f'{int(r.year)}-{int(r.month):02d}',
                'total':      r.total,
            }
            for r in rows
        ]

    @staticmethod
    def warranty_stats(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Warranty / Field Failure 獨立統計"""
        # 統計不得計入已軟刪除的客訴
        q = CustomerComplaint.active_query().filter(
            CustomerComplaint.complaint_type.in_(['warranty', 'field_failure'])
        )
        if date_from:
            q = q.filter(CustomerComplaint.complaint_date >= date_from)
        if date_to:
            q = q.filter(CustomerComplaint.complaint_date <= date_to)

        items = q.all()
        if not items:
            return {
                'total': 0, 'warranty_count': 0, 'field_failure_count': 0,
                'avg_failure_hours': None, 'by_product': [],
            }

        warranty_count      = sum(1 for i in items if i.complaint_type == 'warranty')
        field_failure_count = sum(1 for i in items if i.complaint_type == 'field_failure')
        hours = [i.failure_hours for i in items if i.failure_hours is not None]
        avg_hours = round(sum(hours) / len(hours), 1) if hours else None

        # 依材質統計
        material_map: Dict[str, int] = {}
        for i in items:
            key = i.material or '未填'
            material_map[key] = material_map.get(key, 0) + 1
        by_material = sorted(
            [{'material': k, 'total': v} for k, v in material_map.items()],
            key=lambda x: -x['total'],
        )

        return {
            'total':               len(items),
            'warranty_count':      warranty_count,
            'field_failure_count': field_failure_count,
            'avg_failure_hours':   avg_hours,
            'by_material':         by_material,
        }


# ── 工具函數 ─────────────────────────────────────────────────
def _apply_filters(q, date_from, date_to):
    """統計一律排除已軟刪除的客訴，再套用日期區間。"""
    q = q.filter(CustomerComplaint.deleted_at.is_(None))
    if date_from:
        q = q.filter(CustomerComplaint.complaint_date >= date_from)
    if date_to:
        q = q.filter(CustomerComplaint.complaint_date <= date_to)
    return q
