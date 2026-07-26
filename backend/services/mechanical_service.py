"""機械性質檢驗 CRUD 服務。"""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional

import openpyxl
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    MechanicalTest,
    MechanicalMeasurement,
    MechanicalTraceNumber,
    MechanicalWaivedItem,
    Vendor,
    VendorToleranceMain,
)
from ..utils import bounded_int
from .mechanical_import import build_payloads_from_workbook
from .mechanical_spec import (
    lookup_lower_limits,
    compute_measurement_ng,
    resolve_material_by_spec,
)


class MechanicalValidationError(ValueError):
    """機械性質檢驗 payload 不符合受控欄位規則。"""


class MechanicalNotFoundError(ValueError):
    """找不到指定的機械性質檢驗主檔。"""


ALLOWED_MEASUREMENT_ITEMS = {"EC值", "硬度", "抗拉強度", "降伏強度", "伸長率"}
ALLOWED_MEASUREMENT_LOCATIONS = {"爐門", "爐頂"}
ALLOWED_SAMPLE_NUMBERS = {1, 2}
# 完成判定所需的力學特性項目：每一項只要有任一量測值（不限位置／取樣序）即算完成。
# 實務上部分批次僅取單一位置（爐門或爐頂）就是完整檢驗，故不強制兩個位置都齊。
REQUIRED_MEASUREMENT_ITEMS = {"硬度", "抗拉強度", "降伏強度", "伸長率"}
# 可標記「免測」的項目：設備故障等原因無法量測時，該項目不列入完成判定。
ALLOWED_WAIVED_ITEMS = REQUIRED_MEASUREMENT_ITEMS
TRACE_TYPE_EXTRUSION = "擠製編號"
TRACE_TYPE_T4_FURNACE = "T4爐號"
NEW_TRACE_FIELDS = {
    "extrusion_numbers": TRACE_TYPE_EXTRUSION,
    "t4_furnace_numbers": TRACE_TYPE_T4_FURNACE,
}
NormalizedTraceNumbers = Dict[str, list[tuple[int, str]]]


def _trace_rows(
    test: MechanicalTest,
    trace_type: str,
) -> list[MechanicalTraceNumber]:
    """依類型與序號回傳獨立排序的追溯編號。"""
    return sorted(
        (
            row
            for row in test.trace_numbers
            if row.trace_type == trace_type
        ),
        key=lambda row: row.seq,
    )


def _serialize_trace_rows(
    test: MechanicalTest,
    trace_type: str,
) -> list[Dict[str, Any]]:
    """序列化指定類型的追溯編號，不與另一類型重新配對。"""
    return [
        {"識別碼": row.id, "序號": row.seq, "編號": row.number}
        for row in _trace_rows(test, trace_type)
    ]


def _existing_trace_signature(test: MechanicalTest) -> tuple:
    """既有檢驗的追溯編號簽章，供匯入時比對是否為重複資料。"""
    return tuple(
        tuple((row.seq, row.number) for row in _trace_rows(test, trace_type))
        for trace_type in (TRACE_TYPE_EXTRUSION, TRACE_TYPE_T4_FURNACE)
    )


def _payload_trace_signature(trace_numbers: NormalizedTraceNumbers) -> tuple:
    """匯入 payload 的追溯編號簽章，須與 `_existing_trace_signature` 同結構才能比對。"""
    return tuple(
        tuple(trace_numbers[trace_type])
        for trace_type in (TRACE_TYPE_EXTRUSION, TRACE_TYPE_T4_FURNACE)
    )


def _existing_measurement_signature(test: MechanicalTest) -> tuple:
    """既有檢驗的量測值簽章；追溯編號相同但量測值不同視為同批次二次檢驗，非重複。"""
    return tuple(sorted(
        (m.item, m.location, m.sample_no, m.value)
        for m in test.measurements
    ))


def _payload_measurement_signature(data: Dict[str, Any]) -> tuple:
    """匯入 payload 的量測值簽章，須與 `_existing_measurement_signature` 同結構才能比對。"""
    return tuple(sorted(
        (
            m.get("量測項目"),
            m.get("測量位置"),
            m.get("取樣序"),
            _to_float(m.get("量測值")),
        )
        for m in data.get("measurements", [])
    ))


def _parse_date(v: Any) -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    if not isinstance(v, str):
        raise MechanicalValidationError("測試日期格式必須為 YYYY-MM-DD")
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise MechanicalValidationError("測試日期格式必須為 YYYY-MM-DD") from exc


NUMERIC_QUANTUM = Decimal("0.0001")
NUMERIC_MAX = Decimal("99999999.9999")


def _to_float(v: Any) -> Optional[Decimal]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise MechanicalValidationError("量測值必須為空值或有限數值")
    try:
        value = Decimal(str(v).strip()).quantize(NUMERIC_QUANTUM, rounding=ROUND_HALF_UP)
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        raise MechanicalValidationError("量測值必須為空值或有限數值") from None
    if not value.is_finite() or abs(value) > NUMERIC_MAX:
        raise MechanicalValidationError("量測值必須為空值或有限數值")
    return value


def _string_field(
    value: Any, field: str, *, required: bool = False, max_length: Optional[int] = None
) -> Optional[str]:
    if value is None:
        if required:
            raise MechanicalValidationError(f"{field}為必填")
        return None
    if not isinstance(value, str):
        raise MechanicalValidationError(f"{field}必須為字串")
    normalized = value.strip() if required else value
    if required and not normalized:
        raise MechanicalValidationError(f"{field}為必填")
    if max_length is not None and len(normalized) > max_length:
        raise MechanicalValidationError(f"{field}不得超過 {max_length} 字元")
    return normalized


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


def _parse_trace_list(value: Any, field: str) -> list[tuple[int, str]]:
    if not isinstance(value, list):
        raise MechanicalValidationError(f"{field} 必須為陣列")

    parsed: list[tuple[int, str]] = []
    seen_numbers: set[str] = set()
    for expected_sequence, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            raise MechanicalValidationError(f"{field} 的項目必須為物件")
        sequence = row.get("序號")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence != expected_sequence
        ):
            raise MechanicalValidationError(f"{field} 序號必須從 1 連續排列")
        number = row.get("編號")
        if not isinstance(number, str):
            raise MechanicalValidationError(f"{field} 編號必須為字串")
        number = number.strip()
        if not number:
            raise MechanicalValidationError(f"{field} 編號不得為空")
        if len(number) > 100:
            raise MechanicalValidationError(f"{field} 編號不得超過 100 字元")
        if number in seen_numbers:
            raise MechanicalValidationError(f"{field} 編號不可重複")
        seen_numbers.add(number)
        parsed.append((sequence, number))
    return parsed


def _parse_legacy_batches(value: Any) -> NormalizedTraceNumbers:
    if not isinstance(value, list):
        raise MechanicalValidationError("batches 必須為陣列")

    ordered: list[tuple[int, int, dict[str, Any]]] = []
    seen_sequences: set[int] = set()
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise MechanicalValidationError("批次必須為物件")
        sequence = row.get("序號")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise MechanicalValidationError("批次序號必須為正整數")
        if sequence in seen_sequences:
            raise MechanicalValidationError("批次序號不可重複")
        seen_sequences.add(sequence)
        for field in ("擠製編號", "爐具編號"):
            raw = row.get(field)
            if raw is not None and not isinstance(raw, str):
                raise MechanicalValidationError(f"{field}必須為字串")
            if isinstance(raw, str) and len(raw.strip()) > 100:
                raise MechanicalValidationError(f"{field}不得超過 100 字元")
        ordered.append((sequence, index, row))

    output: NormalizedTraceNumbers = {
        TRACE_TYPE_EXTRUSION: [],
        TRACE_TYPE_T4_FURNACE: [],
    }
    for source_field, trace_type in (
        ("擠製編號", TRACE_TYPE_EXTRUSION),
        ("爐具編號", TRACE_TYPE_T4_FURNACE),
    ):
        values: list[str] = []
        seen: set[str] = set()
        for _, _, row in sorted(ordered):
            number = (row.get(source_field) or "").strip()
            if number and number not in seen:
                seen.add(number)
                values.append(number)
        output[trace_type] = [
            (sequence, number)
            for sequence, number in enumerate(values, start=1)
        ]
    return output


def _parse_trace_numbers(data: Dict[str, Any]) -> NormalizedTraceNumbers:
    new_present = any(field in data for field in NEW_TRACE_FIELDS)
    legacy_present = "batches" in data
    if new_present and legacy_present:
        raise MechanicalValidationError("不得同時提供新版追溯編號與 batches")
    if new_present:
        missing = [field for field in NEW_TRACE_FIELDS if field not in data]
        if missing:
            raise MechanicalValidationError("新版追溯編號兩個欄位都必須提供")
        return {
            trace_type: _parse_trace_list(data[field], field)
            for field, trace_type in NEW_TRACE_FIELDS.items()
        }
    if legacy_present:
        return _parse_legacy_batches(data["batches"])
    raise MechanicalValidationError(
        "必須提供 extrusion_numbers、t4_furnace_numbers 或 batches"
    )


def _parse_waived_items(value: Any) -> list[tuple[str, str]]:
    """解析免測項目（{項目, 原因}），驗證項目受控、不重複、原因非空且不超過 200 字。"""
    if value is None:
        return []
    if not isinstance(value, list):
        raise MechanicalValidationError("waived_items 必須為陣列")

    parsed: list[tuple[str, str]] = []
    seen_items: set[str] = set()
    for row in value:
        if not isinstance(row, dict):
            raise MechanicalValidationError("免測項目必須為物件")
        item = row.get("項目")
        if item not in ALLOWED_WAIVED_ITEMS:
            raise MechanicalValidationError("免測項目不受支援")
        if item in seen_items:
            raise MechanicalValidationError("免測項目不可重複")
        seen_items.add(item)
        reason = row.get("原因")
        if not isinstance(reason, str):
            raise MechanicalValidationError("免測原因必須為字串")
        reason = reason.strip()
        if not reason:
            raise MechanicalValidationError("免測原因不得為空")
        if len(reason) > 200:
            raise MechanicalValidationError("免測原因不得超過 200 字元")
        parsed.append((item, reason))
    return parsed


def _validate_payload(
    data: Dict[str, Any],
) -> tuple[Optional[int], NormalizedTraceNumbers]:
    if not isinstance(data, dict):
        raise MechanicalValidationError("請求內容必須為物件")
    for field in ("產品尺寸", "材質"):
        _string_field(data.get(field), field, required=True, max_length=50)
    _string_field(data.get("T4溫度時間"), "T4溫度時間", max_length=100)
    _string_field(data.get("T6溫度時間"), "T6溫度時間", max_length=100)
    _string_field(data.get("備註"), "備註")

    _parse_date(data.get("測試日期"))
    trace_numbers = _parse_trace_numbers(data)
    waived_items = _parse_waived_items(data.get("waived_items"))

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
    vendor_id = parse_vendor_id(data.get("廠商ID"))
    if vendor_id is not None and db.session.get(Vendor, vendor_id) is None:
        raise MechanicalValidationError("指定的廠商不存在")
    return vendor_id, trace_numbers, waived_items


JUDGEMENT_STATUSES = {"OK", "NG", "NO_SPEC", "INCOMPLETE"}


def _judgement_status(test: MechanicalTest) -> str:
    """依有效判定量測回傳清單與明細共用的明確判定狀態。"""
    judged = [
        measurement for measurement in test.measurements
        if measurement.item != "EC值" and measurement.value is not None
    ]
    if any(measurement.is_ng for measurement in judged):
        return "NG"
    measured_items = {measurement.item for measurement in judged}
    # 免測項目（設備故障等原因無法量測）不列入完成要求
    waived_items = {waived.item for waived in test.waived_items}
    required = REQUIRED_MEASUREMENT_ITEMS - waived_items
    if not required.issubset(measured_items):
        return "INCOMPLETE"
    if any(measurement.lower_limit is None for measurement in judged):
        return "NO_SPEC"
    return "OK"


class MechanicalService:

    @staticmethod
    def options(vendor_id: Optional[int]) -> Dict[str, list[str]]:
        """回傳指定廠商公差中可用的材質與產品尺寸建議。"""
        if vendor_id is None:
            return {"materials": [], "product_sizes": []}
        mains = VendorToleranceMain.query.filter_by(vendor_id=vendor_id).all()
        materials = sorted({
            main.material.strip() for main in mains if main.material and main.material.strip()
        })
        product_sizes = sorted({
            main.spec.strip() for main in mains if main.spec and main.spec.strip()
        })
        return {"materials": materials, "product_sizes": product_sizes}

    @staticmethod
    def _apply_trace_numbers(
        test: MechanicalTest,
        values: NormalizedTraceNumbers,
    ) -> None:
        """依正規化結果重建兩類各自排序的追溯編號。"""
        test.trace_numbers.clear()
        # 先送出孤兒刪除，避免與唯一鍵新增在同一次 flush 中排序不定。
        # 注意：此問題僅在 PostgreSQL（不可延遲的唯一鍵，逐語句檢查）會實際觸發
        # IntegrityError；SQLite 測試環境不會重現，故此行為無法單靠測試鎖定。
        db.session.flush()
        for trace_type in (TRACE_TYPE_EXTRUSION, TRACE_TYPE_T4_FURNACE):
            for sequence, number in values[trace_type]:
                test.trace_numbers.append(
                    MechanicalTraceNumber(
                        trace_type=trace_type,
                        seq=sequence,
                        number=number,
                    )
                )

    @staticmethod
    def _apply_waived_items(
        test: MechanicalTest,
        values: list[tuple[str, str]],
        user_id: Optional[int],
    ) -> None:
        """依正規化結果重建免測項目；先送出孤兒刪除避免唯一鍵衝突。"""
        test.waived_items.clear()
        db.session.flush()
        for item, reason in values:
            test.waived_items.append(
                MechanicalWaivedItem(item=item, reason=reason, created_by=user_id)
            )

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
            if not measurement.excluded:
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
            vendor_id, trace_numbers, waived_items = _validate_payload(data)
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
            MechanicalService._apply_trace_numbers(test, trace_numbers)
            MechanicalService._apply_waived_items(test, waived_items, user_id)
            MechanicalService._apply_measurements(test, data)
            db.session.add(test)
            db.session.commit()
            return test.id
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def get_stats(args: Dict[str, Any]) -> Dict[str, Any]:
        """使用 2026 共用 SPC 引擎產生機械性質即時預覽（與出貨/巡檢同一引擎）。"""
        from .spc_study_service import SpcStudyService

        return SpcStudyService.preview("mechanical", args)

    @staticmethod
    def _is_duplicate(data: Dict[str, Any]) -> bool:
        """依產品尺寸/材質/測試日期/追溯編號**與量測值**判斷是否已存在完全相同的檢驗紀錄。

        追溯編號相同但硬度/抗拉強度/降伏強度/伸長率等量測值不同時，視為同批次的
        二次檢驗（例如重新取樣覆測），仍應允許匯入為新紀錄，不得因追溯編號相同而略過。
        用於匯入時避免同一批（或跨檔重疊的）Excel 資料重複上傳造成重複建檔；
        驗證失敗的 payload 一律視為非重複，交由 create() 走正常流程回報錯誤。
        """
        try:
            test_date = _parse_date(data.get("測試日期"))
            trace_numbers = _parse_trace_numbers(data)
            measurement_signature = _payload_measurement_signature(data)
        except MechanicalValidationError:
            return False
        product_size = (data.get("產品尺寸") or "").strip()
        material = (data.get("材質") or "").strip()
        if not product_size or not material:
            return False
        incoming_trace_signature = _payload_trace_signature(trace_numbers)
        candidates = MechanicalTest.query.filter_by(
            product_size=product_size, material=material, test_date=test_date
        ).all()
        return any(
            _existing_trace_signature(candidate) == incoming_trace_signature
            and _existing_measurement_signature(candidate) == measurement_signature
            for candidate in candidates
        )

    @staticmethod
    def import_data(
        file: Any,
        default_material: Optional[str],
        vendor_id: Optional[int],
        user_id: Optional[int],
    ) -> Dict[str, Any]:
        """解析必榮機械性質 Excel（轉置表格式）並逐欄建立檢驗紀錄。

        來源 Excel 沒有材質欄位，且同一廠商不同規格常是不同材質；故逐工作表
        （＝逐產品尺寸）反查廠商公差主檔的材質自動填入，查無時才退回
        default_material。未指定廠商時無從反查，整批沿用 default_material。

        每一欄各自呼叫 create() 獨立驗證與提交，單欄失敗僅記錄錯誤，
        不影響同批次其他已成功匯入的紀錄（歷史資料量大，避免一筆錯誤拖累全部）。
        已存在相同產品尺寸/材質/測試日期/追溯編號的紀錄視為重複，略過不重複建檔，
        讓同一份（或跨年度重疊的）Excel 可重複上傳而只新增真正新增的部分。
        """
        try:
            wb = openpyxl.load_workbook(file, data_only=True)
        except Exception as exc:
            raise MechanicalValidationError("無法讀取 Excel 檔案，請確認檔案格式") from exc

        resolver = (
            (lambda product_size: resolve_material_by_spec(product_size, vendor_id))
            if vendor_id is not None
            else None
        )
        plan = build_payloads_from_workbook(
            wb, default_material, vendor_id, resolve_material=resolver
        )
        created = 0
        skipped = 0
        errors: list[Dict[str, Any]] = list(plan.errors)
        for sheet_name, col_idx, data in plan.payloads:
            try:
                if MechanicalService._is_duplicate(data):
                    skipped += 1
                    continue
                MechanicalService.create(data, user_id)
                created += 1
            except MechanicalValidationError as exc:
                errors.append({"工作表": sheet_name, "欄位": col_idx, "錯誤": str(exc)})
        return {
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "material_sources": plan.resolutions,
        }

    @staticmethod
    def update(test_id: int, data: Dict[str, Any], user_id: Optional[int]) -> None:
        try:
            test = db.session.get(MechanicalTest, test_id)
            if not test:
                raise MechanicalNotFoundError("找不到該筆機械性質檢驗資料")
            vendor_id, trace_numbers, waived_items = _validate_payload(data)
            test.product_size = data["產品尺寸"].strip()
            test.material = data["材質"].strip()
            test.vendor_id = vendor_id
            test.test_date = _parse_date(data.get("測試日期"))
            test.t4_temp_time = data.get("T4溫度時間") or None
            test.t6_temp_time = data.get("T6溫度時間") or None
            test.note = data.get("備註") or None
            MechanicalService._apply_trace_numbers(test, trace_numbers)
            MechanicalService._apply_waived_items(test, waived_items, user_id)
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
        if args.get("vendor_id"):
            vendor_id = parse_vendor_id(args.get("vendor_id"))
            if vendor_id is not None:
                query = query.filter(MechanicalTest.vendor_id == vendor_id)
        if args.get("date_from"):
            query = query.filter(MechanicalTest.test_date >= _parse_date(args["date_from"]))
        if args.get("date_to"):
            query = query.filter(MechanicalTest.test_date <= _parse_date(args["date_to"]))
        if str(args.get("only_ng", "")).lower() in ("1", "true"):
            query = query.filter(MechanicalTest.is_ng.is_(True))

        page = bounded_int(args.get("page"), 1, 1, 1000000)
        page_size = bounded_int(args.get("page_size"), 20, 1, 100)
        query = query.order_by(MechanicalTest.id.desc())

        status_filter = str(args.get("judgement_status") or "").strip().upper()
        if status_filter in JUDGEMENT_STATUSES:
            # 判定狀態是跨量測明細聚合出的衍生值，資料庫沒有對應欄位可直接 filter；
            # 先套用其餘條件縮小候選集合，一次撈出量測明細後在 Python 端篩選、手動分頁。
            candidates = query.options(
                selectinload(MechanicalTest.measurements),
                selectinload(MechanicalTest.waived_items),
            ).all()
            filtered = [t for t in candidates if _judgement_status(t) == status_filter]
            total = len(filtered)
            start = (page - 1) * page_size
            items = filtered[start:start + page_size]
            total_pages = max((total + page_size - 1) // page_size, 1)
        else:
            total = query.count()
            # 以識別碼倒序（新→舊），避免 SQLite NULLS LAST 相容性問題（沿用擠壓公差慣例）
            pagination = query.paginate(page=page, per_page=page_size, error_out=False)
            items = pagination.items
            total_pages = pagination.pages

        data = [{
            "識別碼": t.id,
            "產品尺寸": t.product_size,
            "材質": t.material,
            "測試日期": t.test_date.isoformat() if t.test_date else None,
            "擠製編號": "、".join(
                row.number for row in _trace_rows(t, TRACE_TYPE_EXTRUSION)
            ),
            "T4爐號": "、".join(
                row.number for row in _trace_rows(t, TRACE_TYPE_T4_FURNACE)
            ),
            "T4溫度時間": t.t4_temp_time,
            "T6溫度時間": t.t6_temp_time,
            "是否NG": t.is_ng,
            "判定狀態": _judgement_status(t),
            "免測": "、".join(waived.item for waived in t.waived_items),
            "備註": t.note,
        } for t in items]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": total_pages}

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
            "測試日期": t.test_date.isoformat() if t.test_date else None,
            "T4溫度時間": t.t4_temp_time,
            "T6溫度時間": t.t6_temp_time,
            "備註": t.note,
            "是否NG": t.is_ng,
            "判定狀態": _judgement_status(t),
        }
        extrusion_numbers = _serialize_trace_rows(
            t, TRACE_TYPE_EXTRUSION
        )
        t4_furnace_numbers = _serialize_trace_rows(
            t, TRACE_TYPE_T4_FURNACE
        )
        batches = []
        for row in extrusion_numbers:
            batches.append({
                "序號": len(batches) + 1,
                "擠製編號": row["編號"],
                "爐具編號": None,
            })
        for row in t4_furnace_numbers:
            batches.append({
                "序號": len(batches) + 1,
                "擠製編號": None,
                "爐具編號": row["編號"],
            })
        measurements = [{
            "識別碼": m.id,
            "量測項目": m.item,
            "測量位置": m.location,
            "取樣序": m.sample_no,
            "量測值": float(m.value) if m.value is not None else None,
            "下限": float(m.lower_limit) if m.lower_limit is not None else None,
            "是否超差": m.is_ng,
            "排除統計": m.excluded,
            "排除原因": m.exclusion_reason,
            "排除者ID": m.exclusion_user_id,
            "排除時間": m.excluded_at.isoformat() if m.excluded_at else None,
        } for m in sorted(t.measurements, key=lambda x: (x.item, x.location, x.sample_no))]
        waived_items = [
            {"項目": w.item, "原因": w.reason}
            for w in sorted(t.waived_items, key=lambda x: x.item)
        ]
        return {
            "success": True,
            "main": main,
            "extrusion_numbers": extrusion_numbers,
            "t4_furnace_numbers": t4_furnace_numbers,
            "batches": batches,
            "measurements": measurements,
            "waived_items": waived_items,
        }
