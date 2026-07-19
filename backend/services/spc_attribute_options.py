"""屬性 SPC 選項的共用 canonicalization，供 adapter 與生命週期服務使用。"""

import math
from typing import Any, Mapping

from .spc_errors import SpcValidationError


ATTRIBUTE_OPTION_DEFAULTS = {"interval": "day", "chart_type": "p", "alpha": 0.0027}
ATTRIBUTE_OPTION_KEYS = frozenset(ATTRIBUTE_OPTION_DEFAULTS)


def canonical_attribute_options(
    options: Mapping[str, Any] | None = None, *, legacy_interval: str | None = None
) -> dict[str, Any]:
    """補齊並嚴格驗證屬性圖選項，避免 adapter 與服務層契約分歧。"""

    if options is None:
        raw: Mapping[str, Any] = ({"interval": legacy_interval} if legacy_interval is not None else {})
    elif not isinstance(options, Mapping):
        raise SpcValidationError("SPC_ANALYSIS_OPTIONS_INVALID", "分析選項必須是物件")
    else:
        raw = options
    unknown = sorted(set(raw) - ATTRIBUTE_OPTION_KEYS)
    if unknown:
        raise SpcValidationError("SPC_ATTRIBUTE_OPTION_UNKNOWN", "屬性分析選項包含未知欄位")
    result = dict(ATTRIBUTE_OPTION_DEFAULTS)
    result.update(raw)
    if type(result["interval"]) is not str or result["interval"] not in {"day", "week", "month"}:
        raise SpcValidationError("SPC_ATTRIBUTE_INTERVAL_INVALID", "interval 僅支援 day、week、month")
    if type(result["chart_type"]) is not str or result["chart_type"] not in {"p", "np"}:
        raise SpcValidationError("SPC_ATTRIBUTE_CHART_TYPE_INVALID", "chart_type 僅支援 p、np")
    alpha = result["alpha"]
    if type(alpha) not in {int, float} or not math.isfinite(alpha) or not 0 < alpha < 1:
        raise SpcValidationError("SPC_ATTRIBUTE_ALPHA_INVALID", "alpha 必須是介於 0 與 1 的有限數值")
    result["alpha"] = float(alpha)
    return result
