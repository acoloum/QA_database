"""SPC 資料轉接器共用的正規化、製程流識別與雜湊工具。"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping, Sequence


SPC_INPUT_CONTRACT_VERSION = "2026.2"

SHIPPING_FILTERS = (
    "vendor", "material", "spec", "field", "start_date", "end_date",
)
PATROL_FILTERS = (
    "m_id", "op_id", "cust_id", "mat", "spec", "item", "pos", "s_date", "e_date",
)
MECHANICAL_FILTERS = (
    "vendor_id", "material", "product_size", "item", "position", "start_date", "end_date",
)
ATTRIBUTE_SHIPPING_FILTERS = SHIPPING_FILTERS
ATTRIBUTE_PATROL_FILTERS = PATROL_FILTERS
ID_FILTERS = {"m_id", "op_id", "cust_id", "vendor_id"}
DATE_FILTERS = {"start_date", "end_date", "s_date", "e_date"}

# 單次研究可載入的來源主檔上限。
# adapter 的篩選條件全部是可選的，載入後還要把量測明細一起讀進記憶體做計算；
# 沒有上界時一次請求就可能把整張表拉進來。管制圖本來就不會用到數千個子組，
# 因此超過上限時明確要求縮小範圍，而不是默默截斷資料——截斷會讓管制界限失真。
MAX_SOURCE_RECORDS = 5000


def assert_source_size(record_count: int, source: str) -> None:
    """來源資料筆數超過上限時中止，並告訴使用者該怎麼縮小範圍。"""

    if record_count > MAX_SOURCE_RECORDS:
        from ..spc_errors import SpcValidationError

        raise SpcValidationError(
            "SPC_SOURCE_TOO_LARGE",
            f"符合條件的資料有 {record_count} 筆，超過單次分析上限 "
            f"{MAX_SOURCE_RECORDS} 筆，請縮小日期範圍或增加篩選條件。",
            details={
                "source": source,
                "record_count": record_count,
                "max_records": MAX_SOURCE_RECORDS,
            },
        )


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
    elif source == "mechanical":
        names = MECHANICAL_FILTERS
        defaults = {"item": "抗拉強度", "position": "爐門"}
    else:
        raise ValueError(f"不支援的 SPC 資料來源：{source}")

    return {
        name: _normalize_filter_value(name, filters.get(name, defaults.get(name)))
        for name in names
    }


def normalize_attribute_filters(source: str, filters: Mapping[str, Any]) -> dict[str, Any]:
    """正規化屬性研究來源篩選，避免控制選項混入製程流識別。"""

    if source == "shipping":
        names = ATTRIBUTE_SHIPPING_FILTERS
        defaults = {"field": "外徑"}
    elif source == "patrol":
        names = ATTRIBUTE_PATROL_FILTERS
        defaults = {"item": "厚度"}
    else:
        raise ValueError(f"不支援的屬性 SPC 資料來源：{source}")
    return {
        name: _normalize_filter_value(name, filters.get(name, defaults.get(name)))
        for name in names
    }


def canonical_attribute_process_stream(
    source: str, filters: Mapping[str, Any]
) -> CanonicalProcessStream:
    """以屬性研究專用篩選建立穩定製程流鍵。"""

    normalized = normalize_attribute_filters(source, filters)
    digest = hashlib.sha256(canonical_json({
        "source": source,
        "analysis_family": "attribute",
        "filters": normalized,
    }).encode("utf-8")).hexdigest()
    return CanonicalProcessStream(source=source, filters=normalized, key=digest)


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
    specification: Mapping[str, Any], analysis_family: str = "variable",
    options: Mapping[str, Any] | None = None,
    input_contract_version: str = SPC_INPUT_CONTRACT_VERSION,
) -> str:
    """雜湊完整研究輸入；依指定契約保留歷史版本相容性。"""

    sorted_rows = sorted(
        (dict(row) for row in source_rows), key=canonical_json,
    )
    payload = {
        "contract_version": input_contract_version,
        "source": source,
        "filters": dict(filters),
        "source_rows": sorted_rows,
        "specification": dict(specification),
    }
    if input_contract_version != "2026.1":
        payload["analysis_family"] = analysis_family
        payload["options"] = dict(options or {})
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


def specification_from_mechanical_limits(rows: Sequence[Any]) -> dict[str, Any]:
    """由機械性質量測保存的下限建立單邊規格快照。

    機械性質為單邊下限（量測值 < 下限 → 超差），量測明細沒有上限欄位，
    故只讀 lower_limit，並標記 one_sided="lower" 讓能力分析走單邊計算。
    """

    lower_values = sorted({float(row.lower_limit) for row in rows if row.lower_limit is not None})
    return {
        "found": bool(lower_values),
        "LSL": lower_values[0] if len(lower_values) == 1 else None,
        "USL": None,
        "one_sided": "lower",
        "lower_values": lower_values,
        "consistent": len(lower_values) <= 1,
        "source": "measurement_snapshot",
    }


def resolve_tolerance_specification(
    *, material: str, spec: str, characteristic: str, vendor_id: int | None,
    position: str | None = None,
) -> dict[str, Any]:
    """以現有公差主檔解析巡檢規格快照。找不到時明確回傳未確認。"""

    from ..tolerance_service import ToleranceService
    from ..tolerance_items import tolerance_names_for
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

    # 硬度的標度寫法並存（未指明標度的「硬度」與「洛氏硬度」），兩者都要接受，
    # 否則對不上就整項不判定；別名定義集中於 tolerance_items 共用。
    match_names = set(tolerance_names_for(characteristic))
    nominal = parse_spec_nominals(spec).get(characteristic)
    normalized_position = None if position is None else str(position)
    for detail in result.get("tolerances", []):
        if detail.get("項目") not in match_names:
            continue
        if normalized_position is not None and str(detail.get("位置") or "") != normalized_position:
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
