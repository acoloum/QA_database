"""MSA 服務共用的請求內容形狀驗證。"""

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
