"""SPC 資料轉接器共用的正規化、製程流識別與雜湊工具。"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping, Sequence


SPC_INPUT_CONTRACT_VERSION = "2026.1"

SHIPPING_FILTERS = (
    "vendor", "material", "spec", "field", "start_date", "end_date",
)
PATROL_FILTERS = (
    "m_id", "op_id", "cust_id", "mat", "spec", "item", "pos", "s_date", "e_date",
)
ID_FILTERS = {"m_id", "op_id", "cust_id"}
DATE_FILTERS = {"start_date", "end_date", "s_date", "e_date"}


@dataclass(frozen=True)
class CanonicalProcessStream:
    """已正規化且可穩定重建的製程流識別。"""

    source: str
    filters: Mapping[str, Any]
    key: str


def _normalize_filter_value(name: str, value: Any) -> Any:
    if name in ID_FILTERS:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    if name in DATE_FILTERS:
        if value is None or str(value).strip() == "":
            return ""
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value).strip()
    if value is None:
        return ""
    return str(value).strip()


def normalize_filters(source: str, filters: Mapping[str, Any]) -> dict[str, Any]:
    """僅保留支援的篩選欄位，並將空值、ID 與日期正規化。"""

    if source == "shipping":
        names = SHIPPING_FILTERS
        defaults = {"field": "外徑"}
    elif source == "patrol":
        names = PATROL_FILTERS
        defaults = {"item": "厚度"}
    else:
        raise ValueError(f"不支援的 SPC 資料來源：{source}")

    return {
        name: _normalize_filter_value(name, filters.get(name, defaults.get(name)))
        for name in names
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def canonical_json(value: Any) -> str:
    """產生不受 dict 插入順序影響的 UTF-8 JSON。"""

    return json.dumps(
        _json_value(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def canonical_process_stream(
    source: str, filters: Mapping[str, Any]
) -> CanonicalProcessStream:
    """以來源與所有支援篩選條件建立穩定製程流鍵。"""

    normalized = normalize_filters(source, filters)
    digest = hashlib.sha256(
        canonical_json({"source": source, "filters": normalized}).encode("utf-8")
    ).hexdigest()
    return CanonicalProcessStream(source=source, filters=normalized, key=digest)


def calculate_study_data_hash(
    *, source: str, filters: Mapping[str, Any], source_rows: Sequence[Mapping[str, Any]],
    specification: Mapping[str, Any],
) -> str:
    """雜湊完整研究輸入；查詢回傳順序不同仍產生相同結果。"""

    sorted_rows = sorted(
        (dict(row) for row in source_rows), key=canonical_json,
    )
    payload = {
        "contract_version": SPC_INPUT_CONTRACT_VERSION,
        "source": source,
        "filters": dict(filters),
        "source_rows": sorted_rows,
        "specification": dict(specification),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def specification_from_measurement_limits(rows: Sequence[Any]) -> dict[str, Any]:
    """由出貨量測當時保存的規格界限建立快照，並揭露不一致狀態。"""

    lower_values = sorted({float(row.lower_limit) for row in rows if row.lower_limit is not None})
    upper_values = sorted({float(row.upper_limit) for row in rows if row.upper_limit is not None})
    return {
        "found": bool(lower_values or upper_values),
        "LSL": lower_values[0] if len(lower_values) == 1 else None,
        "USL": upper_values[0] if len(upper_values) == 1 else None,
        "lower_values": lower_values,
        "upper_values": upper_values,
        "consistent": len(lower_values) <= 1 and len(upper_values) <= 1,
        "source": "measurement_snapshot",
    }


def resolve_tolerance_specification(
    *, material: str, spec: str, characteristic: str, vendor_id: int | None,
) -> dict[str, Any]:
    """以現有公差主檔解析巡檢規格快照。找不到時明確回傳未確認。"""

    from ..tolerance_service import ToleranceService
    from ...utils import parse_spec_nominals

    result = ToleranceService.check_tolerance({
        "material": material,
        "spec": spec,
        "vendor_id": str(vendor_id) if vendor_id else "",
    })
    snapshot: dict[str, Any] = {
        "found": False, "LSL": None, "USL": None,
        "source": "vendor_tolerance",
    }
    if not result.get("found"):
        return snapshot

    aliases = {
        "硬度": {"硬度", "洛氏硬度"},
        "韋伯氏硬度": {"韋伯氏硬度", "維氏硬度"},
    }
    match_names = aliases.get(characteristic, {characteristic})
    nominal = parse_spec_nominals(spec).get(characteristic)
    for detail in result.get("tolerances", []):
        if detail.get("項目") not in match_names:
            continue
        dim_min = detail.get("尺寸下限")
        dim_max = detail.get("尺寸上限")
        tol_min = detail.get("公差下限")
        tol_max = detail.get("公差上限")
        standard = detail.get("標準值")
        standard = nominal if standard is None else standard
        lsl = dim_min
        usl = dim_max
        if lsl is None and usl is None and standard is not None:
            if tol_min is not None:
                lsl = float(standard) - abs(float(tol_min))
            if tol_max is not None:
                usl = float(standard) + abs(float(tol_max))
        snapshot.update({
            "found": lsl is not None or usl is not None,
            "LSL": float(lsl) if lsl is not None else None,
            "USL": float(usl) if usl is not None else None,
            "characteristic_class": detail.get("特性重要度") or "其他",
            "tolerance_id": result.get("tolerance_id"),
            "detail": dict(detail),
        })
        return snapshot
    return snapshot
