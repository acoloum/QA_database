"""機械性質檢驗 CRUD 服務。"""
from datetime import datetime, date
from typing import Any, Dict, Optional

from ..extensions import db
from ..models import MechanicalTest, MechanicalMeasurement, MechanicalBatch
from ..utils import bounded_int, format_value
from .mechanical_spec import lookup_lower_limits, compute_measurement_ng


def _parse_date(v: Any) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, date):
        return v
    return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class MechanicalService:

    @staticmethod
    def _apply_batches(test: MechanicalTest, data: Dict[str, Any]) -> None:
        """依 payload 重建批次（擠製編號 + 爐具編號），略過整組皆空者。"""
        test.batches.clear()
        for i, b in enumerate(data.get("batches", []), start=1):
            ext = (b.get("擠製編號") or "").strip()
            fur = (b.get("爐具編號") or "").strip()
            if not ext and not fur:
                continue
            test.batches.append(MechanicalBatch(
                seq=int(b.get("序號") or i),
                extrusion_no=ext or None,
                furnace_no=fur or None,
            ))

    @staticmethod
    def _apply_measurements(test: MechanicalTest, data: Dict[str, Any]) -> None:
        """依 payload 重建量測明細並套規格判定 NG。"""
        # 清除既有明細（更新情境）
        test.measurements.clear()
        limits = lookup_lower_limits(test.material, test.product_size)

        any_ng = False
        for m in data.get("measurements", []):
            item = m.get("量測項目")
            value = _to_float(m.get("量測值"))
            lower = limits.get(item)  # EC 或查無規格 → None
            is_ng = compute_measurement_ng(value, float(lower) if lower is not None else None)
            any_ng = any_ng or is_ng
            test.measurements.append(MechanicalMeasurement(
                item=item,
                location=m.get("測量位置"),
                sample_no=int(m.get("取樣序") or 1),
                value=value,
                lower_limit=lower,
                is_ng=is_ng,
            ))
        test.is_ng = any_ng

    @staticmethod
    def create(data: Dict[str, Any], user_id: Optional[int]) -> int:
        test = MechanicalTest(
            product_size=data.get("產品尺寸"),
            material=data.get("材質"),
            vendor_id=data.get("廠商ID") or None,
            test_date=_parse_date(data.get("測試日期")),
            t4_temp_time=data.get("T4溫度時間") or None,
            t6_temp_time=data.get("T6溫度時間") or None,
            note=data.get("備註") or None,
            created_by=user_id,
        )
        MechanicalService._apply_batches(test, data)
        MechanicalService._apply_measurements(test, data)
        db.session.add(test)
        db.session.commit()
        return test.id

    @staticmethod
    def update(test_id: int, data: Dict[str, Any], user_id: Optional[int]) -> None:
        test = db.session.get(MechanicalTest, test_id)
        if not test:
            raise ValueError("找不到該筆機械性質檢驗資料")
        test.product_size = data.get("產品尺寸", test.product_size)
        test.material = data.get("材質", test.material)
        test.vendor_id = data.get("廠商ID") or None
        test.test_date = _parse_date(data.get("測試日期"))
        test.t4_temp_time = data.get("T4溫度時間") or None
        test.t6_temp_time = data.get("T6溫度時間") or None
        test.note = data.get("備註") or None
        MechanicalService._apply_batches(test, data)
        MechanicalService._apply_measurements(test, data)
        db.session.commit()

    @staticmethod
    def delete(test_id: int) -> None:
        test = db.session.get(MechanicalTest, test_id)
        if not test:
            raise ValueError("找不到該筆機械性質檢驗資料")
        db.session.delete(test)
        db.session.commit()

    @staticmethod
    def list(args: Dict[str, Any]) -> Dict[str, Any]:
        query = MechanicalTest.query
        if args.get("product_size"):
            query = query.filter(MechanicalTest.product_size.like(f"%{args['product_size']}%"))
        if args.get("material"):
            query = query.filter(MechanicalTest.material.like(f"%{args['material']}%"))
        if args.get("date_from"):
            query = query.filter(MechanicalTest.test_date >= _parse_date(args["date_from"]))
        if args.get("date_to"):
            query = query.filter(MechanicalTest.test_date <= _parse_date(args["date_to"]))
        if str(args.get("only_ng", "")).lower() in ("1", "true"):
            query = query.filter(MechanicalTest.is_ng.is_(True))

        page = bounded_int(args.get("page"), 1, 1, 1000000)
        page_size = bounded_int(args.get("page_size"), 20, 1, 100)
        total = query.count()
        # 以識別碼倒序（新→舊），避免 SQLite NULLS LAST 相容性問題（沿用擠壓公差慣例）
        pagination = query.order_by(MechanicalTest.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        data = [{
            "識別碼": t.id,
            "產品尺寸": t.product_size,
            "材質": t.material,
            "測試日期": format_value(t.test_date),
            # 多組批次以「、」串接為摘要顯示
            "擠製編號": "、".join(
                b.extrusion_no for b in sorted(t.batches, key=lambda x: x.seq) if b.extrusion_no
            ),
            "T4溫度時間": t.t4_temp_time or "",
            "T6溫度時間": t.t6_temp_time or "",
            "是否NG": t.is_ng,
            "備註": t.note or "",
        } for t in pagination.items]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": pagination.pages}

    @staticmethod
    def get_detail(test_id: int) -> Dict[str, Any]:
        t = db.session.get(MechanicalTest, test_id)
        if not t:
            raise ValueError("找不到該筆機械性質檢驗資料")
        main = {
            "識別碼": t.id,
            "產品尺寸": t.product_size,
            "材質": t.material,
            "廠商ID": t.vendor_id,
            "測試日期": format_value(t.test_date),
            "T4溫度時間": t.t4_temp_time or "",
            "T6溫度時間": t.t6_temp_time or "",
            "備註": t.note or "",
            "是否NG": t.is_ng,
        }
        batches = [{
            "識別碼": b.id,
            "序號": b.seq,
            "擠製編號": b.extrusion_no or "",
            "爐具編號": b.furnace_no or "",
        } for b in sorted(t.batches, key=lambda x: x.seq)]
        measurements = [{
            "識別碼": m.id,
            "量測項目": m.item,
            "測量位置": m.location,
            "取樣序": m.sample_no,
            "量測值": format_value(m.value),
            "下限": format_value(m.lower_limit),
            "是否超差": m.is_ng,
        } for m in sorted(t.measurements, key=lambda x: (x.item, x.location, x.sample_no))]
        return {"success": True, "main": main, "batches": batches, "measurements": measurements}
