"""設備清單 CSV 的預覽、人工確認與唯讀盤點服務。"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.exc import DataError, IntegrityError

from ..extensions import db
from ..models import (
    EquipmentImportBatch,
    EquipmentImportRow,
    MeasurementEquipment,
)
from ..utils import log_audit
from .msa_errors import MsaConflict, MsaNotFound, MsaValidationError


PARSER_VERSION = "msa-equipment-csv-1"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 50
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp950")

STATUS_MAP = {
    "使用中": "active",
    "維修": "maintenance",
    "停用": "inactive",
    "報廢": "scrapped",
}

CALIBRATION_TYPE_MAP = {
    "內校": "internal",
    "外校": "external",
    "免校": "exempt",
}

SERIAL_PATTERN = re.compile(
    r"(?:S/N|SN|序號)\s*[:：#]?\s*([A-Za-z0-9._/-]+)",
    re.IGNORECASE,
)
_SERIAL_PREFIX_PATTERN = re.compile(
    r"(?:S/N|SN|序號)\s*[:：#]?", re.IGNORECASE
)
_UNSUPPORTED_NO_PATTERN = re.compile(
    r"(?:^|[\s(（])NO\s*[:：#]", re.IGNORECASE
)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_REQUIRED_HEADERS = frozenset({"設備編號", "名稱"})
_CALIBRATION_TYPES = frozenset(CALIBRATION_TYPE_MAP.values())
_RESOLUTION_ACTIONS = frozenset({"accept", "pending_review", "reject"})
_RESOLUTION_FIELDS = frozenset(
    {
        "action",
        "calibration_type",
        "calibration_exemption_reason",
        "resolution",
        "unit",
        "model",
        "serial_no",
        "custodian",
    }
)
_UNIMPORTABLE_ISSUES = frozenset(
    {
        "MSA_IMPORT_EQUIPMENT_NO_MISSING",
        "MSA_IMPORT_EQUIPMENT_NAME_MISSING",
        "MSA_IMPORT_EQUIPMENT_NO_DUPLICATE_IN_FILE",
    }
)

_ISSUE_MESSAGES = {
    "MSA_IMPORT_EQUIPMENT_NO_MISSING": "設備編號不可空白",
    "MSA_IMPORT_EQUIPMENT_NAME_MISSING": "設備名稱不可空白",
    "MSA_IMPORT_EQUIPMENT_STATUS_INVALID": "設備狀態無法辨識",
    "MSA_IMPORT_CALIBRATION_TYPE_INVALID": "校驗類別無法辨識",
    "MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE": "「遊校」必須由人員明確映射",
    "MSA_IMPORT_CALIBRATION_INTERVAL_INVALID": "校驗週期必須是非負整數",
    "MSA_IMPORT_DATE_INVALID": "日期格式無法辨識",
    "MSA_IMPORT_QUANTITY_REQUIRES_SPLIT": "數量大於一必須拆成獨立設備",
    "MSA_IMPORT_MODEL_MISSING": "型號缺漏，必須人工確認",
    "MSA_IMPORT_CUSTODIAN_MISSING": "保管人缺漏，必須人工確認",
    "MSA_IMPORT_RESOLUTION_MISSING": "解析度缺漏，必須人工確認",
    "MSA_IMPORT_RESOLUTION_INVALID": "解析度必須是大於零的有限數值",
    "MSA_IMPORT_UNIT_MISSING": "單位缺漏，必須人工確認",
    "MSA_IMPORT_EXEMPTION_REASON_MISSING": "免校設備缺少完整豁免理由",
    "MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE": "序號前綴後沒有可擷取的序號",
    "MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX": "NO 僅列為人工候選，不自動擷取",
    "MSA_IMPORT_EQUIPMENT_NO_DUPLICATE_IN_FILE": "檔案內設備編號重複",
}


@dataclass(frozen=True)
class NormalizedEquipmentRow:
    """單列正規化結果與可稽核的人工審查標記。"""

    source_row_no: int
    data: dict
    issue_codes: tuple[str, ...]
    serial_review_candidate: bool = False
    html_cleaned: bool = False

    @property
    def issue_description(self) -> str | None:
        messages = [_ISSUE_MESSAGES.get(code, code) for code in self.issue_codes]
        return "；".join(messages) or None


@dataclass(frozen=True)
class EquipmentCsvInspection:
    """不寫資料庫的 CSV 解析結果，供 preview 與唯讀 CLI 共用。"""

    rows: tuple[tuple[dict, NormalizedEquipmentRow], ...]
    statistics: dict
    encoding: str


def _null_if_dash(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in {"", "-"} else text


def _clean_html_text(value) -> tuple[str | None, bool]:
    text = _null_if_dash(value)
    if text is None:
        return None, False
    had_html = bool(_HTML_TAG_PATTERN.search(text))
    cleaned = _HTML_TAG_PATTERN.sub(" ", text)
    cleaned = _WHITESPACE_PATTERN.sub(" ", html.unescape(cleaned)).strip()
    return cleaned or None, had_html


def _parse_source_date(value, *, issue_codes: list[str]) -> str | None:
    text = _null_if_dash(value)
    if text is None:
        return None
    for date_format in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    issue_codes.append("MSA_IMPORT_DATE_INVALID")
    return None


def _positive_decimal_text(
    value,
    *,
    issue_codes: list[str],
) -> str | None:
    text = _null_if_dash(value)
    if text is None:
        issue_codes.append("MSA_IMPORT_RESOLUTION_MISSING")
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        issue_codes.append("MSA_IMPORT_RESOLUTION_INVALID")
        return None
    if not parsed.is_finite() or parsed <= 0:
        issue_codes.append("MSA_IMPORT_RESOLUTION_INVALID")
        return None
    return format(parsed.normalize(), "f")


def _append_once(issue_codes: list[str], code: str) -> None:
    if code not in issue_codes:
        issue_codes.append(code)


def normalize_equipment_row(
    raw_row: dict,
    *,
    source_row_no: int,
    as_of: date | None = None,
) -> NormalizedEquipmentRow:
    """正規化單列；不從不明文字猜測序號、狀態或校驗類別。"""
    as_of = as_of or date.today()
    issue_codes: list[str] = []

    equipment_no = _null_if_dash(raw_row.get("設備編號"))
    name = _null_if_dash(raw_row.get("名稱"))
    if equipment_no is None:
        issue_codes.append("MSA_IMPORT_EQUIPMENT_NO_MISSING")
    if name is None:
        issue_codes.append("MSA_IMPORT_EQUIPMENT_NAME_MISSING")

    source_status = _null_if_dash(raw_row.get("狀態"))
    status = STATUS_MAP.get(source_status)
    if source_status is not None and status is None:
        issue_codes.append("MSA_IMPORT_EQUIPMENT_STATUS_INVALID")
    if status is None:
        status = "pending_review"

    calibration_source = _null_if_dash(
        raw_row.get("校驗類別", raw_row.get("類別"))
    )
    calibration_type = CALIBRATION_TYPE_MAP.get(calibration_source)
    if calibration_source == "遊校":
        issue_codes.append("MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE")
    elif calibration_source is not None and calibration_type is None:
        issue_codes.append("MSA_IMPORT_CALIBRATION_TYPE_INVALID")

    interval_source = _null_if_dash(
        raw_row.get("校驗週期月數", raw_row.get("週期"))
    )
    calibration_interval_months = None
    if interval_source is not None:
        try:
            calibration_interval_months = int(interval_source)
            if calibration_interval_months < 0:
                raise ValueError
        except ValueError:
            issue_codes.append("MSA_IMPORT_CALIBRATION_INTERVAL_INVALID")
            calibration_interval_months = None

    calibration_date = _parse_source_date(
        raw_row.get("校驗日期", raw_row.get("校驗日")),
        issue_codes=issue_codes,
    )
    effective_date = _parse_source_date(
        raw_row.get("有效日期", raw_row.get("有效日")),
        issue_codes=issue_codes,
    )
    next_due_date = _parse_source_date(
        raw_row.get("下次校驗日期", raw_row.get("下次校驗日")),
        issue_codes=issue_codes,
    )
    parsed_next_due = (
        date.fromisoformat(next_due_date) if next_due_date is not None else None
    )

    reminder_text, html_cleaned = _clean_html_text(
        raw_row.get("效準提醒", raw_row.get("校驗提醒"))
    )
    legacy_notes = _null_if_dash(raw_row.get("備註"))
    serial_match = SERIAL_PATTERN.search(legacy_notes or "")
    serial_no = serial_match.group(1) if serial_match else None
    has_supported_prefix = bool(
        _SERIAL_PREFIX_PATTERN.search(legacy_notes or "")
    )
    has_unsupported_no = bool(
        _UNSUPPORTED_NO_PATTERN.search(legacy_notes or "")
    )
    if has_supported_prefix and serial_no is None:
        issue_codes.append("MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE")
    if has_unsupported_no:
        issue_codes.append("MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX")

    model = _null_if_dash(raw_row.get("型號"))
    custodian = _null_if_dash(
        raw_row.get("保管人", raw_row.get("操作者"))
    )
    resolution = _positive_decimal_text(
        raw_row.get("解析度"),
        issue_codes=issue_codes,
    )
    unit = _null_if_dash(raw_row.get("單位"))
    if model is None:
        issue_codes.append("MSA_IMPORT_MODEL_MISSING")
    if custodian is None:
        issue_codes.append("MSA_IMPORT_CUSTODIAN_MISSING")
    if unit is None:
        issue_codes.append("MSA_IMPORT_UNIT_MISSING")
    if calibration_type == "exempt":
        issue_codes.append("MSA_IMPORT_EXEMPTION_REASON_MISSING")

    quantity_text = _null_if_dash(raw_row.get("數量"))
    quantity = None
    if quantity_text is not None:
        try:
            quantity = int(quantity_text)
            if quantity <= 0:
                raise ValueError
            if quantity > 1:
                issue_codes.append("MSA_IMPORT_QUANTITY_REQUIRES_SPLIT")
        except ValueError:
            issue_codes.append("MSA_IMPORT_QUANTITY_REQUIRES_SPLIT")
            quantity = None

    data = {
        "equipment_no": equipment_no,
        "name": name,
        "department": _null_if_dash(raw_row.get("部門")),
        "custodian": custodian,
        "quantity": quantity,
        "model": model,
        "status": status,
        "calibration_type": calibration_type,
        "calibration_interval_months": calibration_interval_months,
        "calibration_date": calibration_date,
        "effective_date": effective_date,
        "next_due_date": next_due_date,
        "is_expired": bool(parsed_next_due and parsed_next_due < as_of),
        "reminder_text": reminder_text,
        "legacy_notes": legacy_notes,
        "serial_no": serial_no,
        "resolution": resolution,
        "unit": unit,
        "calibration_exemption_reason": None,
    }
    return NormalizedEquipmentRow(
        source_row_no=source_row_no,
        data=data,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        serial_review_candidate=bool(
            serial_no or has_supported_prefix or has_unsupported_no
        ),
        html_cleaned=html_cleaned,
    )


def _decode_csv(content: bytes) -> tuple[str, str]:
    for encoding in CSV_ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise MsaValidationError(
        "MSA_IMPORT_ENCODING_INVALID",
        "CSV 編碼必須是 UTF-8、UTF-8 BOM 或 CP950",
        details={"encodings": list(CSV_ENCODINGS)},
    )


def inspect_equipment_csv(
    content: bytes,
    *,
    as_of: date | None = None,
) -> EquipmentCsvInspection:
    """在記憶體上做有界 CSV 盤點，不寫入任何設備或匯入資料。"""
    if not content:
        raise MsaValidationError(
            "MSA_IMPORT_FILE_EMPTY", "設備匯入檔案不可為空"
        )
    if len(content) > MAX_FILE_BYTES:
        raise MsaValidationError(
            "MSA_IMPORT_FILE_TOO_LARGE",
            "設備匯入檔案超過 5 MB 限制",
            details={"max_bytes": MAX_FILE_BYTES},
        )
    text, encoding = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = [str(header).strip() for header in (reader.fieldnames or [])]
    if not headers:
        raise MsaValidationError(
            "MSA_IMPORT_HEADER_INVALID", "CSV 缺少欄名"
        )
    if len(headers) > MAX_COLUMNS:
        raise MsaValidationError(
            "MSA_IMPORT_COLUMN_LIMIT_EXCEEDED",
            f"CSV 欄位數超過 {MAX_COLUMNS} 欄限制",
            details={"max_columns": MAX_COLUMNS, "columns": len(headers)},
        )
    if len(headers) != len(set(headers)) or not _REQUIRED_HEADERS.issubset(
        headers
    ):
        raise MsaValidationError(
            "MSA_IMPORT_HEADER_INVALID",
            "CSV 欄名重複或缺少設備編號、名稱",
            details={"required_headers": sorted(_REQUIRED_HEADERS)},
        )

    parsed_rows: list[tuple[dict, NormalizedEquipmentRow]] = []
    for source_row_no, source_row in enumerate(reader, start=2):
        if len(parsed_rows) >= MAX_ROWS:
            raise MsaValidationError(
                "MSA_IMPORT_ROW_LIMIT_EXCEEDED",
                f"CSV 資料列超過 {MAX_ROWS} 筆限制",
                details={"max_rows": MAX_ROWS},
            )
        if None in source_row:
            raise MsaValidationError(
                "MSA_IMPORT_ROW_SHAPE_INVALID",
                "CSV 資料列欄位數與欄名不一致",
                details={"source_row_no": source_row_no},
            )
        raw = {
            str(key).strip(): (value if value is not None else "")
            for key, value in source_row.items()
        }
        if not any(str(value).strip() for value in raw.values()):
            continue
        normalized = normalize_equipment_row(
            raw,
            source_row_no=source_row_no,
            as_of=as_of,
        )
        parsed_rows.append((raw, normalized))
    if not parsed_rows:
        raise MsaValidationError(
            "MSA_IMPORT_FILE_EMPTY", "設備匯入檔案沒有資料列"
        )

    equipment_numbers: dict[str, list[int]] = {}
    for _, normalized in parsed_rows:
        equipment_no = normalized.data["equipment_no"]
        if equipment_no is not None:
            equipment_numbers.setdefault(equipment_no, []).append(
                normalized.source_row_no
            )
    duplicate_rows = {
        row_number
        for row_numbers in equipment_numbers.values()
        if len(row_numbers) > 1
        for row_number in row_numbers
    }
    if duplicate_rows:
        rebuilt = []
        for raw, normalized in parsed_rows:
            codes = list(normalized.issue_codes)
            if normalized.source_row_no in duplicate_rows:
                _append_once(
                    codes, "MSA_IMPORT_EQUIPMENT_NO_DUPLICATE_IN_FILE"
                )
            rebuilt.append(
                (
                    raw,
                    NormalizedEquipmentRow(
                        source_row_no=normalized.source_row_no,
                        data=normalized.data,
                        issue_codes=tuple(codes),
                        serial_review_candidate=(
                            normalized.serial_review_candidate
                        ),
                        html_cleaned=normalized.html_cleaned,
                    ),
                )
            )
        parsed_rows = rebuilt

    status_counts: dict[str, int] = {}
    for _, normalized in parsed_rows:
        status = normalized.data["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    statistics = {
        "total_rows": len(parsed_rows),
        "status_counts": status_counts,
        "serial_review_candidates": sum(
            row.serial_review_candidate for _, row in parsed_rows
        ),
        "serials_auto_extracted": sum(
            bool(row.data["serial_no"]) for _, row in parsed_rows
        ),
        "html_cleaned_rows": sum(
            row.html_cleaned for _, row in parsed_rows
        ),
        "ambiguous_calibration_rows": sum(
            "MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE" in row.issue_codes
            for _, row in parsed_rows
        ),
        "active_expired_rows": sum(
            row.data["status"] == "active" and row.data["is_expired"]
            for _, row in parsed_rows
        ),
    }
    return EquipmentCsvInspection(
        rows=tuple(parsed_rows),
        statistics=statistics,
        encoding=encoding,
    )


def _open_source(source) -> tuple[BinaryIO, bool]:
    if isinstance(source, (str, Path)):
        return Path(source).open("rb"), True
    if hasattr(source, "stream"):
        return source.stream, False
    if hasattr(source, "read"):
        return source, False
    raise MsaValidationError(
        "MSA_IMPORT_FILE_MISSING", "請提供設備 CSV 檔案"
    )


def _read_bounded_source(source) -> tuple[bytes, str]:
    stream, should_close = _open_source(source)
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    size = 0
    try:
        if hasattr(stream, "seek"):
            stream.seek(0)
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise MsaValidationError(
                    "MSA_IMPORT_FILE_TOO_LARGE",
                    "設備匯入檔案超過 5 MB 限制",
                    details={"max_bytes": MAX_FILE_BYTES},
                )
            digest.update(chunk)
            chunks.append(chunk)
    finally:
        if should_close:
            stream.close()
    return b"".join(chunks), digest.hexdigest()


def _parse_iso_date(value, *, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise MsaValidationError(
            "MSA_IMPORT_DATE_INVALID",
            f"{field} 必須是 ISO 日期",
            details={"field": field, "value": value},
        ) from error


def serialize_import_batch(
    batch: EquipmentImportBatch,
    *,
    include_rows: bool = False,
) -> dict:
    """輸出穩定批次 envelope，不暴露 ORM 內部欄名。"""
    data = {
        "id": batch.id,
        "original_filename": batch.original_filename,
        "file_sha256": batch.file_sha256,
        "file_size": batch.file_size,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "success_rows": batch.success_rows,
        "pending_rows": batch.pending_rows,
        "rejected_rows": batch.rejected_rows,
        "parser_version": batch.parser_version,
        "uploaded_by": batch.uploaded_by,
        "uploaded_at": (
            batch.uploaded_at.isoformat() if batch.uploaded_at else None
        ),
    }
    if include_rows:
        rows = sorted(batch.rows, key=lambda row: (row.row_number, row.id))
        data["rows"] = [
            {
                "id": row.id,
                "source_row_no": row.row_number,
                "raw": row.raw_data,
                "normalized": row.normalized_data,
                "issue_codes": row.issue_codes or [],
                "issue_description": row.issue_description,
                "equipment_id": row.equipment_id,
                "confirmed_by": row.confirmed_by,
                "confirmed_at": (
                    row.confirmed_at.isoformat()
                    if row.confirmed_at
                    else None
                ),
            }
            for row in rows
        ]
    return data


class MsaImportService:
    """設備 CSV 預覽／確認兩階段交易服務。"""

    @staticmethod
    def preview(
        source,
        original_filename: str | None = None,
        actor_id: int | None = None,
        *,
        as_of: date | None = None,
    ) -> EquipmentImportBatch:
        filename = original_filename or getattr(source, "filename", None)
        if not isinstance(filename, str) or not filename.strip():
            raise MsaValidationError(
                "MSA_IMPORT_FILE_MISSING", "請提供設備 CSV 檔案"
            )
        filename = filename.strip()
        if Path(filename).suffix.lower() != ".csv":
            raise MsaValidationError(
                "MSA_IMPORT_FILE_TYPE_INVALID",
                "設備匯入僅接受 CSV 檔案",
                details={"filename": filename},
            )
        content, file_sha256 = _read_bounded_source(source)
        existing = EquipmentImportBatch.query.filter_by(
            file_sha256=file_sha256
        ).first()
        if existing is not None:
            return existing

        inspection = inspect_equipment_csv(content, as_of=as_of)
        batch = EquipmentImportBatch(
            original_filename=filename,
            file_sha256=file_sha256,
            file_size=len(content),
            uploaded_by=actor_id,
            status="previewed",
            total_rows=inspection.statistics["total_rows"],
            success_rows=sum(
                not normalized.issue_codes
                for _, normalized in inspection.rows
            ),
            pending_rows=sum(
                bool(normalized.issue_codes)
                for _, normalized in inspection.rows
            ),
            rejected_rows=0,
            parser_version=PARSER_VERSION,
        )
        try:
            db.session.add(batch)
            db.session.flush()
            for raw, normalized in inspection.rows:
                db.session.add(
                    EquipmentImportRow(
                        batch_id=batch.id,
                        row_number=normalized.source_row_no,
                        raw_data=raw,
                        normalized_data=normalized.data,
                        issue_codes=list(normalized.issue_codes),
                        issue_description=normalized.issue_description,
                    )
                )
            db.session.commit()
            return batch
        except IntegrityError:
            db.session.rollback()
            raced = EquipmentImportBatch.query.filter_by(
                file_sha256=file_sha256
            ).first()
            if raced is not None:
                return raced
            raise

    @staticmethod
    def confirm(
        batch_id: int,
        actor_id: int,
        *,
        resolutions,
        confirmation_date: date | None = None,
    ) -> EquipmentImportBatch:
        confirmation_date = confirmation_date or date.today()
        if not isinstance(confirmation_date, date):
            confirmation_date = _parse_iso_date(
                confirmation_date, field="confirmation_date"
            )
        if not isinstance(resolutions, dict):
            raise MsaValidationError(
                "MSA_IMPORT_RESOLUTIONS_INVALID",
                "resolutions 必須是以匯入列 ID 為鍵的物件",
            )
        try:
            batch = (
                EquipmentImportBatch.query.filter_by(id=batch_id)
                .with_for_update()
                .one_or_none()
            )
            if batch is None:
                raise MsaNotFound(
                    "MSA_IMPORT_BATCH_NOT_FOUND", "找不到設備匯入批次"
                )
            if batch.status == "confirmed":
                return batch
            if batch.status != "previewed":
                raise MsaConflict(
                    "MSA_IMPORT_BATCH_STATUS_CONFLICT",
                    "只有已預覽批次可以確認",
                    details={"status": batch.status},
                )

            rows = sorted(
                batch.rows, key=lambda row: (row.row_number, row.id)
            )
            resolution_by_id = MsaImportService._validate_resolutions(
                rows, resolutions
            )
            equipment_numbers = [
                row.normalized_data.get("equipment_no")
                for row in rows
                if row.normalized_data
                and row.normalized_data.get("equipment_no")
            ]
            duplicate = (
                MeasurementEquipment.query.filter(
                    MeasurementEquipment.equipment_no.in_(equipment_numbers)
                )
                .order_by(MeasurementEquipment.equipment_no)
                .first()
            )
            if duplicate is not None:
                raise MsaConflict(
                    "MSA_IMPORT_EQUIPMENT_NO_DUPLICATE",
                    "設備編號已存在，整批確認已取消",
                    details={"equipment_no": duplicate.equipment_no},
                )

            success_rows = 0
            pending_rows = 0
            rejected_rows = 0
            confirmed_at = datetime.now(timezone.utc)
            for row in rows:
                normalized = dict(row.normalized_data or {})
                resolution = resolution_by_id.get(row.id, {})
                action = resolution.get(
                    "action",
                    "pending_review" if row.issue_codes else "accept",
                )
                if action == "reject" or any(
                    code in _UNIMPORTABLE_ISSUES
                    for code in (row.issue_codes or [])
                ):
                    rejected_rows += 1
                    row.confirmed_by = actor_id
                    row.confirmed_at = confirmed_at
                    normalized["confirmation_resolution"] = resolution
                    row.normalized_data = normalized
                    continue

                unresolved = MsaImportService._apply_resolution(
                    normalized,
                    list(row.issue_codes or []),
                    resolution,
                )
                source_status = normalized.get("status")
                if action == "pending_review" or unresolved:
                    equipment_status = (
                        source_status
                        if source_status
                        in {"maintenance", "inactive", "scrapped"}
                        else "pending_review"
                    )
                else:
                    equipment_status = source_status or "pending_review"

                next_due_date = normalized.get("next_due_date")
                normalized["is_expired"] = bool(
                    next_due_date
                    and date.fromisoformat(next_due_date) < confirmation_date
                )
                normalized["confirmation_resolution"] = resolution
                normalized["unresolved_issue_codes"] = unresolved
                equipment = MeasurementEquipment(
                    equipment_no=normalized["equipment_no"],
                    name=normalized["name"],
                    model=normalized.get("model"),
                    serial_no=normalized.get("serial_no"),
                    resolution=(
                        Decimal(normalized["resolution"])
                        if normalized.get("resolution")
                        else None
                    ),
                    unit=normalized.get("unit"),
                    department=normalized.get("department"),
                    custodian=normalized.get("custodian"),
                    status=equipment_status,
                    calibration_type=(
                        normalized.get("calibration_type")
                        if normalized.get("calibration_type") != "exempt"
                        or normalized.get("calibration_exemption_reason")
                        else None
                    ),
                    calibration_exemption_reason=normalized.get(
                        "calibration_exemption_reason"
                    ),
                    calibration_interval_months=normalized.get(
                        "calibration_interval_months"
                    ),
                    created_by=actor_id,
                    updated_by=actor_id,
                )
                db.session.add(equipment)
                db.session.flush()
                row.equipment_id = equipment.id
                row.confirmed_by = actor_id
                row.confirmed_at = confirmed_at
                row.normalized_data = normalized
                success_rows += 1
                if equipment.status == "pending_review":
                    pending_rows += 1

            batch.status = "confirmed"
            batch.success_rows = success_rows
            batch.pending_rows = pending_rows
            batch.rejected_rows = rejected_rows
            log_audit(
                actor_id,
                "confirm",
                "msa_equipment_import",
                batch.id,
                old_val={"status": "previewed"},
                new_val={
                    "status": "confirmed",
                    "file_sha256": batch.file_sha256,
                    "parser_version": batch.parser_version,
                    "confirmation_date": confirmation_date.isoformat(),
                    "success_rows": success_rows,
                    "pending_rows": pending_rows,
                    "rejected_rows": rejected_rows,
                    "resolutions": {
                        str(row_id): resolution
                        for row_id, resolution in resolution_by_id.items()
                    },
                },
            )
            db.session.commit()
            return batch
        except (MsaConflict, MsaNotFound, MsaValidationError):
            db.session.rollback()
            raise
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_IMPORT_DATABASE_VALUE_INVALID",
                "匯入欄位不符合資料庫長度或格式限制",
            ) from error
        except IntegrityError as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_IMPORT_EQUIPMENT_NO_DUPLICATE",
                "設備編號衝突，整批確認已取消",
            ) from error

    @staticmethod
    def _validate_resolutions(
        rows: list[EquipmentImportRow],
        resolutions: dict,
    ) -> dict[int, dict]:
        valid_ids = {row.id for row in rows}
        normalized: dict[int, dict] = {}
        for raw_id, resolution in resolutions.items():
            try:
                row_id = int(raw_id)
            except (TypeError, ValueError) as error:
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    "resolution 鍵必須是匯入列 ID",
                    details={"row_id": raw_id},
                ) from error
            if row_id not in valid_ids or not isinstance(resolution, dict):
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    "resolution 不屬於此批次或格式錯誤",
                    details={"row_id": row_id},
                )
            unknown = set(resolution) - _RESOLUTION_FIELDS
            action = resolution.get("action", "accept")
            if unknown or action not in _RESOLUTION_ACTIONS:
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    "resolution 含有不支援欄位或處置",
                    details={
                        "row_id": row_id,
                        "fields": sorted(unknown),
                        "action": action,
                    },
                )
            normalized[row_id] = dict(resolution, action=action)
        return normalized

    @staticmethod
    def _apply_resolution(
        normalized: dict,
        issue_codes: list[str],
        resolution: dict,
    ) -> list[str]:
        calibration_type = resolution.get("calibration_type")
        if calibration_type is not None:
            if calibration_type not in _CALIBRATION_TYPES:
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    "人工映射的校驗類別不在允許清單",
                    details={"calibration_type": calibration_type},
                )
            normalized["calibration_type"] = calibration_type
            if calibration_type != "exempt":
                normalized["calibration_exemption_reason"] = None
            issue_codes = [
                code
                for code in issue_codes
                if code
                not in {
                    "MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE",
                    "MSA_IMPORT_CALIBRATION_TYPE_INVALID",
                }
            ]

        exemption_reason = resolution.get("calibration_exemption_reason")
        if exemption_reason is not None:
            if (
                normalized.get("calibration_type") != "exempt"
                or not isinstance(exemption_reason, str)
                or not exemption_reason.strip()
            ):
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    "校驗豁免理由僅能用於 exempt 且不可空白",
                )
            normalized["calibration_exemption_reason"] = (
                exemption_reason.strip()
            )
            issue_codes = [
                code
                for code in issue_codes
                if code != "MSA_IMPORT_EXEMPTION_REASON_MISSING"
            ]

        if "resolution" in resolution:
            resolution_issues: list[str] = []
            value = _positive_decimal_text(
                resolution["resolution"],
                issue_codes=resolution_issues,
            )
            if value is None or resolution_issues:
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    "人工確認的解析度必須是大於零的有限數值",
                )
            normalized["resolution"] = value
            issue_codes = [
                code
                for code in issue_codes
                if code
                not in {
                    "MSA_IMPORT_RESOLUTION_MISSING",
                    "MSA_IMPORT_RESOLUTION_INVALID",
                }
            ]

        text_issue_map = {
            "unit": "MSA_IMPORT_UNIT_MISSING",
            "model": "MSA_IMPORT_MODEL_MISSING",
            "custodian": "MSA_IMPORT_CUSTODIAN_MISSING",
            "serial_no": None,
        }
        for field, issue_code in text_issue_map.items():
            if field not in resolution:
                continue
            value = resolution[field]
            if not isinstance(value, str) or not value.strip():
                raise MsaValidationError(
                    "MSA_IMPORT_RESOLUTION_INVALID",
                    f"{field} 人工確認值不可空白",
                    details={"field": field},
                )
            normalized[field] = value.strip()
            if issue_code is not None:
                issue_codes = [
                    code for code in issue_codes if code != issue_code
                ]
            if field == "serial_no":
                issue_codes = [
                    code
                    for code in issue_codes
                    if code
                    not in {
                        "MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE",
                        "MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX",
                    }
                ]
        return list(dict.fromkeys(issue_codes))
