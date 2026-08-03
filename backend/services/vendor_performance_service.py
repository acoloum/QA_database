"""廠商績效計算服務

評分公式：
  - 缺陷率每 1% 扣 2 分，最多扣 40 分
  - CAPA 平均天數每天扣 1 分，最多扣 30 分
  - 客訴每件扣 5 分，最多扣 30 分
  - 最低 0 分

注意：CorrectiveAction 無直接 vendor_id，NCMR.vendor 為字串非 FK，
CustomerComplaint.customer 亦為字串無 vendor_id，因此 CAPA 與客訴
目前使用廠商名稱字串比對，若無法匹配則設為 0（簡化版）。

月份一律以嚴格 YYYY-MM 格式表示；讀取（list_by_period）為純即時計算，
不 add、不 commit；唯有 refresh_period 才把快照寫入 DB。
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, NamedTuple, Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy import case, extract, func, select
from sqlalchemy.exc import IntegrityError

from ..errors import ConflictError, ValidationError
from ..extensions import db
from ..models import (
    CorrectiveAction,
    CustomerComplaint,
    NCMR,
    ShippingData,
    Vendor,
    VendorPerformance,
)

# 嚴格月份格式：YYYY-MM（月份 01–12）
PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class PeriodWindow(NamedTuple):
    """一個完整月份的時間窗（[start, end_exclusive)）。"""
    value: str
    start: date
    end_exclusive: date


def parse_period(value: str) -> PeriodWindow:
    """解析嚴格 YYYY-MM 月份，格式不符拋 ValidationError。"""
    if not isinstance(value, str):
        raise ValidationError("period 必須為 YYYY-MM 字串")
    match = PERIOD_RE.fullmatch(value)
    if not match:
        raise ValidationError("period 必須為 YYYY-MM（例：2026-08）")
    start = date(int(match.group(1)), int(match.group(2)), 1)
    end = start + relativedelta(months=1)
    return PeriodWindow(value=value, start=start, end_exclusive=end)


class VendorPerformanceService:

    @staticmethod
    def _compute_score(
        defect_rate: float,
        avg_capa_days: float,
        complaint_count: int,
    ) -> float:
        """依缺陷率、CAPA 平均結案天數、客訴件數計算績效分數（0–100）"""
        score = 100.0
        score -= min(defect_rate * 2, 40)
        score -= min((avg_capa_days or 0) * 1, 30)
        score -= min(complaint_count * 5, 30)
        return max(round(score, 1), 0.0)

    @staticmethod
    def get_or_calculate(vendor_id: int, period: str) -> Dict[str, Any]:
        """計算（或重新計算）某廠商某月份的績效並 upsert 至 DB"""
        year = int(period[:4])
        month = int(period[5:7])

        # ── 出貨巡檢統計 ─────────────────────────────────────────
        inspections: List[ShippingData] = ShippingData.query.filter(
            ShippingData.vendor_id == vendor_id,
            extract("year",  ShippingData.date) == year,
            extract("month", ShippingData.date) == month,
        ).all()

        inspection_count = len(inspections)
        defect_count = sum(1 for i in inspections if i.is_ng)
        defect_rate = (
            round(defect_count / inspection_count * 100, 2)
            if inspection_count
            else 0.0
        )

        # ── CAPA 統計（透過廠商名稱比對 NCMR.vendor 字串）──────────
        # CorrectiveAction 無直接 vendor_id；透過 NCMR 關聯，
        # 而 NCMR.vendor 為文字欄位，與廠商名稱做字串比對。
        capa_count = 0
        avg_capa_days: Optional[float] = None

        vendor: Optional[Vendor] = db.session.get(Vendor, vendor_id)
        vendor_name = vendor.name if vendor else None

        if vendor_name:
            # 查詢本月新開的 CAPA，源頭 NCMR 廠商與本廠商相符
            ncmr_ids_for_vendor = select(NCMR.id).where(
                NCMR.vendor == vendor_name, NCMR.deleted_at.is_(None)
            )

            # 與下方客訴統計一致：績效分數不得把已軟刪除的單據算進去
            capas = CorrectiveAction.active_query().filter(
                CorrectiveAction.ncmr_id.in_(ncmr_ids_for_vendor),
                extract("year",  CorrectiveAction.created_at) == year,
                extract("month", CorrectiveAction.created_at) == month,
            ).all()

            capa_count = len(capas)

            # 計算已結案 CAPA 的平均結案天數
            closed_capas = [
                c for c in capas
                if c.d8_close_date and c.created_at
            ]
            if closed_capas:
                days_list = [
                    (c.d8_close_date - c.created_at.date()).days
                    for c in closed_capas
                ]
                avg_capa_days = round(sum(days_list) / len(days_list), 1)

        # ── 客訴統計（透過廠商名稱比對 CustomerComplaint.customer 字串）
        # CustomerComplaint.customer 為字串欄位，無直接 vendor_id。
        complaint_count = 0

        if vendor_name:
            complaint_count = CustomerComplaint.query.filter(
                CustomerComplaint.customer == vendor_name,
                extract("year",  CustomerComplaint.complaint_date) == year,
                extract("month", CustomerComplaint.complaint_date) == month,
                CustomerComplaint.deleted_at.is_(None),
            ).count()

        # ── 計算分數 ─────────────────────────────────────────────
        score = VendorPerformanceService._compute_score(
            defect_rate, avg_capa_days or 0, complaint_count
        )

        # ── Upsert VendorPerformance ──────────────────────────────
        perf: Optional[VendorPerformance] = VendorPerformance.query.filter_by(
            vendor_id=vendor_id, period=period
        ).first()

        if perf is None:
            perf = VendorPerformance(vendor_id=vendor_id, period=period)
            db.session.add(perf)

        perf.inspection_count = inspection_count
        perf.defect_count     = defect_count
        perf.defect_rate      = defect_rate
        perf.capa_count       = capa_count
        perf.avg_capa_days    = avg_capa_days
        perf.complaint_count  = complaint_count
        perf.score            = score
        perf.calculated_at    = datetime.now(timezone.utc)

        db.session.commit()

        return VendorPerformanceService._to_dict(perf)

    @staticmethod
    def calculate_period(window: PeriodWindow) -> List[Dict[str, Any]]:
        """以三個集合查詢計算所有廠商在該月份的即時績效（純讀、不寫入 DB）。

        查詢數固定、不隨廠商數成長：
          1. 出貨巡檢按 vendor_id 聚合（inspection / defect 計數）
          2. CAPA 以 NCMR join 取當月所有矯正單，於 Python 依廠商名稱分組
          3. 客訴按客戶名稱聚合
        """
        start, end = window.start, window.end_exclusive

        # 廠商名稱對應表（CAPA/客訴以名稱字串比對，無法匹配視為 0）
        vendors = db.session.query(Vendor.id, Vendor.name).all()
        vendor_names = {vid: name for vid, name in vendors}

        # 1) 出貨巡檢聚合
        shipping_rows = (
            db.session.query(
                ShippingData.vendor_id.label('vendor_id'),
                func.count(ShippingData.id).label('inspection_count'),
                func.sum(case((ShippingData.is_ng.is_(True), 1), else_=0)).label('defect_count'),
            )
            .filter(
                ShippingData.date >= start,
                ShippingData.date < end,
            )
            .group_by(ShippingData.vendor_id)
            .all()
        )
        shipping_by_vendor = {
            row.vendor_id: {
                'inspection_count': row.inspection_count,
                'defect_count': row.defect_count or 0,
            }
            for row in shipping_rows
        }

        # 2) CAPA：當月所有矯正單（join NCMR 取廠商名稱），Python 分組計數與平均天數
        capa_rows = (
            db.session.query(
                NCMR.vendor.label('vendor_name'),
                CorrectiveAction.d8_close_date,
                CorrectiveAction.created_at,
            )
            .join(CorrectiveAction, CorrectiveAction.ncmr_id == NCMR.id)
            .filter(
                CorrectiveAction.created_at >= datetime.combine(start, time.min),
                CorrectiveAction.created_at < datetime.combine(end, time.min),
                # 與下方客訴聚合一致：績效分數不得計入已軟刪除的單據
                CorrectiveAction.deleted_at.is_(None),
                NCMR.deleted_at.is_(None),
            )
            .all()
        )
        capa_by_vendor: Dict[str, Dict[str, Any]] = {}
        for row in capa_rows:
            name = row.vendor_name
            if not name:
                continue
            bucket = capa_by_vendor.setdefault(name, {'capa_count': 0, 'days': []})
            bucket['capa_count'] += 1
            if row.d8_close_date and row.created_at:
                bucket['days'].append((row.d8_close_date - row.created_at.date()).days)

        # 3) 客訴聚合（客戶名稱比對）
        complaint_rows = (
            db.session.query(
                CustomerComplaint.customer.label('customer'),
                func.count(CustomerComplaint.id).label('complaint_count'),
            )
            .filter(
                CustomerComplaint.customer.in_(
                    [name for name in vendor_names.values() if name]
                ),
                CustomerComplaint.complaint_date >= start,
                CustomerComplaint.complaint_date < end,
                CustomerComplaint.deleted_at.is_(None),
            )
            .group_by(CustomerComplaint.customer)
            .all()
        )
        complaint_by_customer = {
            row.customer: row.complaint_count for row in complaint_rows
        }

        # 組裝各廠商結果（僅對聚合 row 計分，不逐廠商查詢）
        results: List[Dict[str, Any]] = []
        for vid, name in vendor_names.items():
            shipping = shipping_by_vendor.get(
                vid, {'inspection_count': 0, 'defect_count': 0}
            )
            inspection_count = shipping['inspection_count']
            defect_count = shipping['defect_count']
            defect_rate = (
                round(defect_count / inspection_count * 100, 2)
                if inspection_count else 0.0
            )
            capa = capa_by_vendor.get(name, {'capa_count': 0, 'days': []})
            avg_capa_days = (
                round(sum(capa['days']) / len(capa['days']), 1)
                if capa['days'] else None
            )
            complaint_count = complaint_by_customer.get(name, 0)
            score = VendorPerformanceService._compute_score(
                defect_rate, avg_capa_days or 0, complaint_count
            )
            results.append({
                'id': None,
                'vendor_id': vid,
                'vendor_name': name,
                'period': window.value,
                'inspection_count': inspection_count,
                'defect_count': defect_count,
                'defect_rate': defect_rate,
                'capa_count': capa['capa_count'],
                'avg_capa_days': avg_capa_days,
                'complaint_count': complaint_count,
                'score': score,
                'calculated_at': None,
            })
        return results

    @staticmethod
    def list_by_period(period: str) -> List[Dict[str, Any]]:
        """列出所有廠商在特定月份的即時績效（純讀、不寫入 DB，按分數升序）"""
        window = parse_period(period)
        results = VendorPerformanceService.calculate_period(window)
        return sorted(results, key=lambda x: x["score"])

    @staticmethod
    def refresh_period(period: str) -> int:
        """以 (vendor_id, period) 唯一鍵將該月份所有廠商績效寫入快照。

        單一 transaction commit；競爭衝突（唯一鍵違反）rollback 後拋 ConflictError。
        """
        window = parse_period(period)
        results = VendorPerformanceService.calculate_period(window)
        existing = {
            perf.vendor_id: perf
            for perf in VendorPerformance.query.filter_by(period=window.value).all()
        }
        now = datetime.now(timezone.utc)
        for row in results:
            perf = existing.get(row['vendor_id'])
            if perf is None:
                perf = VendorPerformance(vendor_id=row['vendor_id'], period=window.value)
                db.session.add(perf)
            perf.inspection_count = row['inspection_count']
            perf.defect_count = row['defect_count']
            perf.defect_rate = row['defect_rate']
            perf.capa_count = row['capa_count']
            perf.avg_capa_days = row['avg_capa_days']
            perf.complaint_count = row['complaint_count']
            perf.score = row['score']
            perf.calculated_at = now
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ConflictError('該月份績效快照正被其他請求同時寫入，請稍後再試')
        return len(results)

    @staticmethod
    def history(vendor_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """查詢某廠商最近 N 個月的績效歷史"""
        records: List[VendorPerformance] = (
            VendorPerformance.query
            .filter_by(vendor_id=vendor_id)
            .order_by(VendorPerformance.period.desc())
            .limit(months)
            .all()
        )
        return [VendorPerformanceService._to_dict(r) for r in records]

    @staticmethod
    def _to_dict(perf: VendorPerformance) -> Dict[str, Any]:
        """將 VendorPerformance ORM 物件轉為字典"""
        return {
            "id":               perf.id,
            "vendor_id":        perf.vendor_id,
            "vendor_name":      perf.vendor.name if perf.vendor else None,
            "period":           perf.period,
            "inspection_count": perf.inspection_count,
            "defect_count":     perf.defect_count,
            "defect_rate":      perf.defect_rate,
            "capa_count":       perf.capa_count,
            "avg_capa_days":    perf.avg_capa_days,
            "complaint_count":  perf.complaint_count,
            "score":            perf.score,
            "calculated_at": (
                perf.calculated_at.isoformat()
                if perf.calculated_at
                else None
            ),
        }
