"""MSA 服務共用的請求內容形狀驗證。

各 MSA 服務原本各自複製一份 text/int/decimal 欄位驗證，邏輯相同、只有錯誤碼不同；
統一收在此處並以 code 參數區分，避免同一規則在多處各自漂移。
"""

import json
from decimal import Decimal, InvalidOperation
import math

from .msa_errors import MsaValidationError


def require_object(payload) -> dict:
    if not isinstance(payload, dict):
        raise MsaValidationError(
            "MSA_PAYLOAD_INVALID", "請求內容必須是 JSON 物件", details={},
        )
    return payload


def reject_unknown_fields(payload: dict, allowed: set) -> None:
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise MsaValidationError(
            "MSA_UNKNOWN_FIELDS",
            "請求包含未允許欄位",
            details={"unknown_fields": unknown},
        )


def optional_text(value, *, field: str, max_length: int, code: str) -> str | None:
    """可選文字欄位：None/空白一律收斂為 None，超長則以指定 code 拋出。"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise MsaValidationError(
            code, f"{field} 必須是文字", details={"field": field},
        )
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise MsaValidationError(
            code,
            f"{field} 超過允許長度",
            details={"field": field, "max_length": max_length},
        )
    return normalized


def required_text(value, *, field: str, max_length: int, code: str) -> str:
    """必填文字欄位：沿用 optional_text 的規則，僅在結果為空時額外拋出。"""
    normalized = optional_text(value, field=field, max_length=max_length, code=code)
    if normalized is None:
        raise MsaValidationError(
            code, f"{field} 為必填欄位", details={"field": field},
        )
    return normalized


def bounded_int(value, *, field: str, minimum: int, maximum: int, code: str) -> int:
    """有界整數欄位。bool 不視為整數（避免 True 被當成 1）。"""
    if isinstance(value, bool):
        raise MsaValidationError(
            code, f"{field} 必須是整數", details={"field": field},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise MsaValidationError(
            code, f"{field} 必須是整數", details={"field": field},
        ) from error
    if parsed < minimum or parsed > maximum:
        raise MsaValidationError(
            code,
            f"{field} 超出允許範圍",
            details={"field": field, "minimum": minimum, "maximum": maximum},
        )
    return parsed


def optional_decimal(value, *, field: str, code: str) -> Decimal | None:
    """可選數值欄位；拒絕 bool、NaN 與 Infinity。"""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise MsaValidationError(
            code, f"{field} 必須是數值", details={"field": field},
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise MsaValidationError(
            code, f"{field} 必須是有限數值", details={"field": field},
        )
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise MsaValidationError(
            code, f"{field} 必須是數值", details={"field": field},
        ) from error
    if not parsed.is_finite():
        raise MsaValidationError(
            code, f"{field} 必須是有限數值", details={"field": field},
        )
    return parsed


def decimal_text(value) -> str | None:
    """Decimal 轉存字串（None 直通），供快照與雜湊使用。"""
    return str(value) if value is not None else None


def canonical_json(value, *, field: str, code: str):
    """正規化 JSON：排序鍵、拒絕 NaN/Infinity，確保可重現雜湊。"""
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return json.loads(encoded)
    except (OverflowError, TypeError, ValueError) as error:
        raise MsaValidationError(
            code,
            f"{field} 必須是可重現且僅含有限數值的 JSON",
            details={"field": field},
        ) from error
