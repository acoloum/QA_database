"""廠商績效計算服務

評分公式：
  - 缺陷率每 1% 扣 2 分，最多扣 40 分
  - CAPA 平均天數每天扣 1 分，最多扣 30 分
  - 客訴每件扣 5 分，最多扣 30 分
  - 最低 0 分

注意：CorrectiveAction 無直接 vendor_id，NCMR.vendor 為字串非 FK，
CustomerComplaint.customer 亦為字串無 vendor_id，因此 CAPA 與客訴
目前使用廠商名稱字串比對，若無法匹配則設為 0（簡化版）。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import extract, select

from ..extensions import db
from ..models import (
    CorrectiveAction,
    CustomerComplaint,
    NCMR,
    ShippingData,
    Vendor,
    VendorPerformance,
)


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
            ncmr_ids_for_vendor = select(NCMR.id).where(NCMR.vendor == vendor_name)

            capas = CorrectiveAction.query.filter(
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
    def list_by_period(period: str) -> List[Dict[str, Any]]:
        """列出所有廠商在特定月份的績效（按分數升序）"""
        vendors: List[Vendor] = Vendor.query.all()
        results = [
            VendorPerformanceService.get_or_calculate(v.id, period)
            for v in vendors
        ]
        return sorted(results, key=lambda x: x["score"])

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
