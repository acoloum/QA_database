"""機械性質檢驗 CRUD 服務。"""
from datetime import datetime, date
import math
from typing import Any, Dict, Optional

from ..extensions import db
from ..models import MechanicalTest, MechanicalMeasurement, MechanicalBatch
from ..utils import bounded_int, format_value
from .mechanical_spec import lookup_lower_limits, compute_measurement_ng


class MechanicalValidationError(ValueError):
    """機械性質檢驗 payload 不符合受控欄位規則。"""


class MechanicalNotFoundError(ValueError):
    """找不到指定的機械性質檢驗主檔。"""


ALLOWED_MEASUREMENT_ITEMS = {"EC值", "硬度", "抗拉強度", "降伏強度", "伸長率"}
ALLOWED_MEASUREMENT_LOCATIONS = {"爐門", "爐頂"}
ALLOWED_SAMPLE_NUMBERS = {1, 2}


def _parse_date(v: Any) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise MechanicalValidationError("測試日期格式必須為 YYYY-MM-DD") from exc


def _to_float(v: Any) -> Optional[float]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        value = float(v)
    except (TypeError, ValueError):
        raise MechanicalValidationError("量測值必須為空值或有限數值") from None
    if isinstance(v, bool) or not math.isfinite(value):
        raise MechanicalValidationError("量測值必須為空值或有限數值")
    return value


def parse_vendor_id(value: Any) -> Optional[int]:
    """將可選廠商識別碼轉為正整數，拒絕會退化成未指定的無效值。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise MechanicalValidationError("廠商ID必須為正整數")
    if isinstance(value, int):
        vendor_id = value
    elif isinstance(value, str):
        try:
            vendor_id = int(value)
        except ValueError:
            raise MechanicalValidationError("廠商ID必須為正整數") from None
    else:
        raise MechanicalValidationError("廠商ID必須為正整數")
    if vendor_id < 1:
        raise MechanicalValidationError("廠商ID必須為正整數")
    return vendor_id


def _validate_payload(data: Dict[str, Any]) -> Optional[int]:
    if not isinstance(data, dict):
        raise MechanicalValidationError("請求內容必須為物件")
    for field in ("產品尺寸", "材質"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise MechanicalValidationError(f"{field}為必填")

    _parse_date(data.get("測試日期"))
    measurements = data.get("measurements", [])
    if not isinstance(measurements, list):
        raise MechanicalValidationError("measurements 必須為陣列")

    seen_keys = set()
    for measurement in measurements:
        if not isinstance(measurement, dict):
            raise MechanicalValidationError("量測明細必須為物件")
        item = measurement.get("量測項目")
        location = measurement.get("測量位置")
        sample_no = measurement.get("取樣序")
        if item not in ALLOWED_MEASUREMENT_ITEMS:
            raise MechanicalValidationError("量測項目不受支援")
        if location not in ALLOWED_MEASUREMENT_LOCATIONS:
            raise MechanicalValidationError("測量位置不受支援")
        if isinstance(sample_no, bool) or sample_no not in ALLOWED_SAMPLE_NUMBERS:
            raise MechanicalValidationError("取樣序只允許 1 或 2")
        key = (item, location, sample_no)
        if key in seen_keys:
            raise MechanicalValidationError("量測明細不可重複")
        seen_keys.add(key)
        _to_float(measurement.get("量測值"))
    return parse_vendor_id(data.get("廠商ID"))


class MechanicalService:

    @staticmethod
    def _apply_batches(test: MechanicalTest, data: Dict[str, Any]) -> None:
        """依 payload 重建批次（擠製編號 + 爐具編號），略過整組皆空者。"""
        test.batches.clear()
        # 先送出孤兒刪除，避免與唯一鍵新增在同一次 flush 中排序不定。
        # 注意：此問題僅在 PostgreSQL（不可延遲的唯一鍵，逐語句檢查）會實際觸發
        # IntegrityError；SQLite 測試環境不會重現，故此行為無法單靠測試鎖定。
        db.session.flush()
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
        """依受控鍵值更新量測明細並保留既有排除追溯資訊。"""
        limits = lookup_lower_limits(test.material, test.product_size, test.vendor_id)
        existing_by_key = {
            (measurement.item, measurement.location, measurement.sample_no): measurement
            for measurement in test.measurements
        }
        submitted_keys = set()

        for m in data.get("measurements", []):
            item = m.get("量測項目")
            location = m.get("測量位置")
            sample_no = m.get("取樣序")
            value = _to_float(m.get("量測值"))
            lower = limits.get(item)  # EC 或查無規格 → None
            is_ng = compute_measurement_ng(value, float(lower) if lower is not None else None)
            key = (item, location, sample_no)
            submitted_keys.add(key)
            measurement = existing_by_key.get(key)
            if measurement is None:
                test.measurements.append(MechanicalMeasurement(
                    item=item,
                    location=location,
                    sample_no=sample_no,
                    value=value,
                    lower_limit=lower,
                    is_ng=is_ng,
                ))
                continue
            measurement.value = value
            measurement.lower_limit = lower
            measurement.is_ng = is_ng

        for key, measurement in existing_by_key.items():
            if key not in submitted_keys and not measurement.excluded:
                test.measurements.remove(measurement)
        test.is_ng = any(measurement.is_ng for measurement in test.measurements)

    @staticmethod
    def create(data: Dict[str, Any], user_id: Optional[int]) -> int:
        try:
            vendor_id = _validate_payload(data)
            test = MechanicalTest(
                product_size=data.get("產品尺寸").strip(),
                material=data.get("材質").strip(),
                vendor_id=vendor_id,
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
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def update(test_id: int, data: Dict[str, Any], user_id: Optional[int]) -> None:
        try:
            test = db.session.get(MechanicalTest, test_id)
            if not test:
                raise MechanicalNotFoundError("找不到該筆機械性質檢驗資料")
            vendor_id = _validate_payload(data)
            test.product_size = data["產品尺寸"].strip()
            test.material = data["材質"].strip()
            test.vendor_id = vendor_id
            test.test_date = _parse_date(data.get("測試日期"))
            test.t4_temp_time = data.get("T4溫度時間") or None
            test.t6_temp_time = data.get("T6溫度時間") or None
            test.note = data.get("備註") or None
            MechanicalService._apply_batches(test, data)
            MechanicalService._apply_measurements(test, data)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete(test_id: int) -> None:
        try:
            test = db.session.get(MechanicalTest, test_id)
            if not test:
                raise MechanicalNotFoundError("找不到該筆機械性質檢驗資料")
            db.session.delete(test)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

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
            raise MechanicalNotFoundError("找不到該筆機械性質檢驗資料")
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
