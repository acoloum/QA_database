"""交易內稽核寫入服務。"""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
import math
import re
from typing import Any

from ..extensions import db
from ..models import AuditLog


_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|token|secret|credential|authorization|cookie|api[_-]?key)",
    re.IGNORECASE,
)


def _json_value(value: Any, *, key: str | None = None) -> Any:
    """建立可安全寫入 JSON 欄位的快照，不保留憑證值。"""
    if key is not None and _SENSITIVE_KEY_PATTERN.search(key):
        return "[REDACTED]"
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            marker = 'NaN'
        else:
            marker = 'Infinity' if value > 0 else '-Infinity'
        return f'[NON_FINITE_FLOAT:{marker}]'
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): _json_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    # 不將未知物件字串化，以免 __repr__ 意外帶出憑證或個資。
    return f"[UNSUPPORTED:{type(value).__name__}]"


class AuditService:
    """由業務 service 在同一交易內呼叫的稽核介面。"""

    @staticmethod
    def record(
        *,
        actor_id: int | None,
        action: str,
        module: str,
        record_id: int | None,
        old_value: Mapping | None = None,
        new_value: Mapping | None = None,
    ) -> AuditLog:
        if not isinstance(action, str) or not action or len(action) > 20:
            raise ValueError("稽核操作類型必須為 1 到 20 個字元")
        if not isinstance(module, str) or not module or len(module) > 30:
            raise ValueError("稽核模組必須為 1 到 30 個字元")
        entry = AuditLog(
            user_id=actor_id,
            action=action,
            module=module,
            record_id=record_id,
            old_value=_json_value(old_value),
            new_value=_json_value(new_value),
        )
        db.session.add(entry)
        db.session.flush()
        return entry
