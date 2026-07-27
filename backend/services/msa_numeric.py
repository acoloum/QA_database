"""MSA 統計輸出的數值安全層與 canonical hash。

正式結果不得包含 NaN 或 Infinity；本模組提供遞迴檢查與穩定雜湊，
讓相同資料在不同機器、不同 dict 順序下都產生相同指紋。
"""

from decimal import Decimal
import hashlib
import json
import math

import numpy as np

from .msa_errors import MsaValidationError


class MsaNumericError(MsaValidationError):
    """統計輸出出現非有限值或無法序列化的數值。"""

    def __init__(self, message: str, *, path: str | None = None, value=None):
        super().__init__(
            "MSA_NUMERIC_FAILURE",
            message,
            details={"path": path, "value": _describe(value)},
        )
        self.path = path


def _describe(value) -> str | None:
    if value is None:
        return None
    try:
        return repr(value)
    except Exception:  # pragma: no cover - repr 幾乎不會失敗
        return "<無法顯示的值>"


def _is_number(value) -> bool:
    return isinstance(value, (int, float, Decimal, np.floating, np.integer))


def _finite(value) -> bool:
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, np.integer) or isinstance(value, int):
        return True
    return math.isfinite(float(value))


def require_finite_tree(value, *, path: str = "$"):
    """遞迴確認整棵結果樹沒有 NaN、Infinity 或無法轉換的數值。

    失敗時以 JSON path 指出實際位置，讓呼叫端能直接定位問題欄位。
    回傳原輸入本身，方便串接使用。
    """
    _walk(value, path)
    return value


def _walk(value, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _walk(item, f"{path}.{key}")
        return
    if isinstance(value, np.ndarray):
        for index, item in enumerate(value.tolist()):
            _walk(item, f"{path}[{index}]")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _walk(item, f"{path}[{index}]")
        return
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if _is_number(value):
        if not _finite(value):
            raise MsaNumericError(
                "統計結果不得包含 NaN 或 Infinity",
                path=path,
                value=value,
            )
        return
    raise MsaNumericError(
        "統計結果包含無法序列化的型別",
        path=path,
        value=value,
    )


def to_float(value) -> float:
    """將 Decimal／NumPy 數值轉為有限 float，非有限值直接拒絕。"""
    if not _is_number(value):
        raise MsaNumericError("無法轉換為數值", value=value)
    if isinstance(value, Decimal) and not value.is_finite():
        raise MsaNumericError("數值必須是有限值", value=value)
    result = float(value)
    if not math.isfinite(result):
        raise MsaNumericError("數值必須是有限值", value=value)
    return result


def _json_default(value):
    if isinstance(value, Decimal):
        # 以標準化文字保留精度，避免 float 轉換造成指紋漂移
        return format(value.normalize(), "f")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise MsaNumericError("無法序列化的型別", value=value)


def canonical_hash(value: object) -> str:
    """以排序鍵、無空白的 JSON 產生穩定的 SHA-256 指紋。"""
    require_finite_tree(value)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
