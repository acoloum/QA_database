"""屬性型 SPC 的出貨與巡檢資料來源轉接器。"""

from collections import OrderedDict, defaultdict
from datetime import date
from typing import Any, Mapping

from sqlalchemy.orm import selectinload

from ...models import PatrolDetail, PatrolMain, ShippingData, ShippingMeasurement, Vendor
from ..spc_attribute_engine import AttributeSubgroup
from ..spc_contracts import SpcReason, SpcStudyInput
from .common import (
    SPC_INPUT_CONTRACT_VERSION,
    calculate_study_data_hash,
    canonical_attribute_process_stream,
    normalize_attribute_filters,
    resolve_tolerance_specification,
)


ATTRIBUTE_CHARACTERISTIC = "不符合單位"
ATTRIBUTE_INTERVALS = {"day", "week", "month"}
ATTRIBUTE_CLASSIFICATION_ALGORITHM = "attribute-measurement-v2"
MIN_MAX_CHARACTERISTICS = {"外徑", "內徑", "厚度"}


def _date_bound(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _interval_key(value: date, interval: str) -> str:
    if interval == "day":
        return value.isoformat()
    if interval == "week":
        year, week, _weekday = value.isocalendar()
        return f"{year}-W{week:02d}"
    return value.strftime("%Y-%m")


def _group_rows(rows: list[dict[str, Any]], interval: str) -> tuple[AttributeSubgroup, ...]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        grouped.setdefault(_interval_key(row["date"], interval), []).append(row)
    return tuple(
        AttributeSubgroup(
            key=f"attribute:{key}",
            timestamp=items[0]["date"],
            inspected=len(items),
            nonconforming=sum(1 for item in items if item["is_ng"]),
            record_ids=tuple(item["record_id"] for item in items),
        )
        for key, items in grouped.items()
    )


def _shipping_records(filters: Mapping[str, Any]) -> list[ShippingData]:
    query = ShippingData.query.outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)
    if filters["vendor"]:
        query = query.filter(Vendor.name.contains(filters["vendor"]))
    if filters["material"]:
        query = query.filter(ShippingData.material.contains(filters["material"]))
    if filters["spec"]:
        query = query.filter(ShippingData.spec.contains(filters["spec"]))
    if filters["start_date"]:
        query = query.filter(ShippingData.date >= _date_bound(filters["start_date"]))
    if filters["end_date"]:
        query = query.filter(ShippingData.date <= _date_bound(filters["end_date"]))
    return query.order_by(ShippingData.date.asc(), ShippingData.id.asc()).all()


def _shipping_input(filters: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = _shipping_records(filters)
    record_ids = [record.id for record in records]
    measurements_by_record: dict[int, list[ShippingMeasurement]] = defaultdict(list)
    if record_ids:
        measurements = ShippingMeasurement.query.filter(
            ShippingMeasurement.shipping_id.in_(record_ids),
            ShippingMeasurement.item == filters["field"],
        ).order_by(ShippingMeasurement.shipping_id.asc(), ShippingMeasurement.id.asc()).all()
        for measurement in measurements:
            measurements_by_record[measurement.shipping_id].append(measurement)

    source_rows: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    for record in records:
        measurements_for_record = measurements_by_record[record.id]
        eligible, calculated_is_ng, evidence = _classify_shipping_record(
            measurements_for_record, str(filters["field"])
        )
        eligible = record.date is not None and eligible
        source_rows.append({
            "record_id": record.id,
            "date": record.date,
            "is_ng": calculated_is_ng,
            "main_is_ng": record.is_ng,
            "eligible": eligible,
            "classification_source": "shipping_measurement_snapshot",
            "classification_algorithm": ATTRIBUTE_CLASSIFICATION_ALGORITHM,
            "evidence": evidence,
        })
        if not eligible:
            snapshots.append({
                "record_id": record.id,
                "eligible": False,
                "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
            })
    return source_rows, snapshots


def _shipping_measurement_values(
    measurement: ShippingMeasurement, characteristic: str
) -> tuple[float, ...] | None:
    if characteristic in MIN_MAX_CHARACTERISTICS:
        if measurement.value_min is None or measurement.value_max is None:
            return None
        return float(measurement.value_min), float(measurement.value_max)
    if measurement.value_single is None:
        return None
    return (float(measurement.value_single),)


def _outside_limits(values: tuple[float, ...], lsl: Any, usl: Any) -> bool:
    return any(
        (lsl is not None and value < float(lsl))
        or (usl is not None and value > float(usl))
        for value in values
    )


def _classify_shipping_record(
    measurements: list[ShippingMeasurement], characteristic: str
) -> tuple[bool, bool | None, list[dict[str, Any]]]:
    """僅以選定特性量測與當時規格快照判定出貨不符合單位。"""

    applicable = [item for item in measurements if not item.excluded]
    evidence: list[dict[str, Any]] = []
    if not applicable:
        return False, None, evidence
    classifications: list[bool] = []
    for item in applicable:
        values = _shipping_measurement_values(item, characteristic)
        complete = values is not None and (
            item.lower_limit is not None or item.upper_limit is not None
        )
        is_ng = _outside_limits(values, item.lower_limit, item.upper_limit) if complete else None
        evidence.append({
            "measurement_id": item.id,
            "values": list(values) if values is not None else None,
            "lower_limit": item.lower_limit,
            "upper_limit": item.upper_limit,
            "excluded": False,
            "is_ng": is_ng,
        })
        if is_ng is None:
            return False, None, evidence
        classifications.append(is_ng)
    return True, any(classifications), evidence


def _patrol_records(filters: Mapping[str, Any]) -> list[PatrolMain]:
    query = PatrolMain.query.options(selectinload(PatrolMain.details)).join(PatrolDetail).filter(
        PatrolDetail.item == filters["item"]
    )
    if filters["pos"]:
        query = query.filter(PatrolDetail.position == filters["pos"])
    if filters["s_date"]:
        query = query.filter(PatrolMain.date >= _date_bound(filters["s_date"]))
    if filters["e_date"]:
        query = query.filter(PatrolMain.date <= _date_bound(filters["e_date"]))
    if filters["m_id"] is not None:
        query = query.filter(PatrolMain.machine_id == filters["m_id"])
    if filters["op_id"] is not None:
        query = query.filter(PatrolMain.operator_id == filters["op_id"])
    if filters["cust_id"] is not None:
        query = query.filter(PatrolMain.customer_id == filters["cust_id"])
    if filters["mat"]:
        query = query.filter(PatrolMain.material.contains(filters["mat"]))
    if filters["spec"]:
        query = query.filter(PatrolMain.spec.contains(filters["spec"]))
    return query.distinct().order_by(PatrolMain.date.asc(), PatrolMain.id.asc()).all()


def _patrol_input(filters: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = _patrol_records(filters)
    source_rows: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    tolerance_cache: dict[tuple[str, str, int | None, str, str], dict[str, Any]] = {}
    for record in records:
        details = sorted((
            detail for detail in record.details
            if detail.item == filters["item"]
            and (not filters["pos"] or detail.position == filters["pos"])
        ), key=lambda detail: detail.id)
        eligible, calculated_is_ng, evidence = _classify_patrol_record(
            record, details, str(filters["item"]), tolerance_cache
        )
        eligible = record.date is not None and eligible
        source_rows.append({
            "record_id": record.id,
            "date": record.date,
            "is_ng": calculated_is_ng,
            "main_is_ng": record.is_ng,
            "eligible": eligible,
            "classification_source": "patrol_measurement_with_position_tolerance",
            "classification_algorithm": ATTRIBUTE_CLASSIFICATION_ALGORITHM,
            "evidence": evidence,
        })
        if not eligible:
            snapshots.append({
                "record_id": record.id,
                "eligible": False,
                "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
            })
    return source_rows, snapshots


def _patrol_tolerance(
    record: PatrolMain,
    characteristic: str,
    position: str,
    cache: dict[tuple[str, str, int | None, str, str], dict[str, Any]],
) -> dict[str, Any]:
    key = (
        str(record.material or ""), str(record.spec or ""), record.customer_id,
        characteristic, position,
    )
    if key not in cache:
        cache[key] = resolve_tolerance_specification(
            material=key[0], spec=key[1], characteristic=characteristic,
            vendor_id=record.customer_id, position=position,
        )
    return cache[key]


def _classify_patrol_record(
    record: PatrolMain,
    details: list[PatrolDetail],
    characteristic: str,
    tolerance_cache: dict[tuple[str, str, int | None, str, str], dict[str, Any]],
) -> tuple[bool, bool | None, list[dict[str, Any]]]:
    """按每筆巡檢位置的公差快照重算不符合單位。"""

    applicable = [item for item in details if not item.excluded]
    evidence: list[dict[str, Any]] = []
    if not applicable:
        return False, None, evidence
    classifications: list[bool] = []
    for item in applicable:
        position = str(item.position or "")
        tolerance = _patrol_tolerance(record, characteristic, position, tolerance_cache)
        values = (
            (float(item.min_val), float(item.max_val))
            if item.min_val is not None and item.max_val is not None else None
        )
        complete = values is not None and bool(tolerance.get("found"))
        is_ng = _outside_limits(values, tolerance.get("LSL"), tolerance.get("USL")) if complete else None
        evidence.append({
            "measurement_id": item.id,
            "position": position,
            "values": list(values) if values is not None else None,
            "tolerance_id": tolerance.get("tolerance_id"),
            "LSL": tolerance.get("LSL"),
            "USL": tolerance.get("USL"),
            "excluded": False,
            "is_ng": is_ng,
        })
        if is_ng is None:
            return False, None, evidence
        classifications.append(is_ng)
    return True, any(classifications), evidence


def build_attribute_study_input(
    source: str,
    filters: Mapping[str, Any],
    interval: str | None = None,
    *,
    options: Mapping[str, Any] | None = None,
    input_contract_version: str = SPC_INPUT_CONTRACT_VERSION,
) -> SpcStudyInput:
    """建立可追溯的 p／np 屬性研究輸入，不將未知資料視為良品。"""

    canonical_filters = normalize_attribute_filters(source, filters)
    stream = canonical_attribute_process_stream(source, canonical_filters)
    canonical_options = dict(options or {"interval": interval or "day"})
    normalized_interval = str(canonical_options["interval"]).strip().lower()
    if normalized_interval not in ATTRIBUTE_INTERVALS:
        raise ValueError("屬性資料分組僅支援 day、week、month")

    if source == "shipping":
        source_rows, snapshots = _shipping_input(canonical_filters)
    elif source == "patrol":
        source_rows, snapshots = _patrol_input(canonical_filters)
    else:
        raise ValueError(f"不支援的屬性 SPC 資料來源：{source}")

    eligible_rows = [row for row in source_rows if row["eligible"]]
    subgroups = _group_rows(eligible_rows, normalized_interval)
    reasons: list[SpcReason] = []
    if not source_rows:
        reasons.append(SpcReason("NO_DATA", "篩選範圍內沒有可用檢驗紀錄"))
    elif not eligible_rows:
        reasons.append(SpcReason("ALL_CLASSIFICATIONS_UNKNOWN", "沒有可判定的不符合單位資料"))

    specification = {
        "found": bool(eligible_rows),
        "source": "measurement_and_specification_snapshot",
    }
    data_hash = calculate_study_data_hash(
        source=source,
        filters=canonical_filters,
        source_rows=source_rows,
        specification=specification,
        analysis_family="attribute",
        options=canonical_options,
        input_contract_version=input_contract_version,
    )
    return SpcStudyInput(
        source=source,
        filters=canonical_filters,
        process_stream_key=stream.key,
        characteristic=ATTRIBUTE_CHARACTERISTIC,
        subgroups=subgroups,
        specification=specification,
        analysis_family="attribute",
        options=canonical_options,
        data_hash=data_hash,
        reasons=reasons,
        metadata={
            "classification_source": "measurement_and_specification_snapshot",
            "classification_algorithm": ATTRIBUTE_CLASSIFICATION_ALGORITHM,
            "classification_snapshot": snapshots,
            "classification_evidence": [{
                "record_id": row["record_id"],
                "eligible": row["eligible"],
                "calculated_is_ng": row["is_ng"],
                "measurement_ids": [item["measurement_id"] for item in row["evidence"]],
            } for row in source_rows],
            "main_is_ng_mismatch_record_ids": [
                row["record_id"] for row in source_rows
                if row["eligible"] and row["main_is_ng"] is not None
                and bool(row["main_is_ng"]) != bool(row["is_ng"])
            ],
            "eligible_record_count": len(eligible_rows),
            "excluded_record_count": len(snapshots),
        },
    )
