"""屬性型 SPC 的出貨與巡檢資料來源轉接器。"""

from collections import OrderedDict, defaultdict
from datetime import date
from typing import Any, Mapping

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
        evidence = [
            measurement for measurement in measurements_by_record[record.id]
            if not measurement.excluded
            and (measurement.lower_limit is not None or measurement.upper_limit is not None)
        ]
        eligible = record.date is not None and record.is_ng is not None and bool(evidence)
        source_rows.append({
            "record_id": record.id,
            "date": record.date,
            "is_ng": record.is_ng,
            "eligible": eligible,
            "evidence": [{
                "measurement_id": item.id,
                "lower_limit": item.lower_limit,
                "upper_limit": item.upper_limit,
                "excluded": bool(item.excluded),
            } for item in measurements_by_record[record.id]],
        })
        if not eligible:
            snapshots.append({
                "record_id": record.id,
                "eligible": False,
                "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
            })
    return source_rows, snapshots


def _patrol_records(filters: Mapping[str, Any]) -> list[PatrolMain]:
    query = PatrolMain.query.join(PatrolDetail).filter(PatrolDetail.item == filters["item"])
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
    for record in records:
        details = [
            detail for detail in record.details
            if detail.item == filters["item"]
            and (not filters["pos"] or detail.position == filters["pos"])
        ]
        evidence = [
            detail for detail in details
            if not detail.excluded and detail.min_val is not None and detail.max_val is not None
        ]
        tolerance = resolve_tolerance_specification(
            material=str(record.material or ""),
            spec=str(record.spec or ""),
            characteristic=str(filters["item"]),
            vendor_id=record.customer_id,
        )
        eligible = (
            record.date is not None
            and record.is_ng is not None
            and bool(evidence)
            and bool(tolerance.get("found"))
        )
        source_rows.append({
            "record_id": record.id,
            "date": record.date,
            "is_ng": record.is_ng,
            "eligible": eligible,
            "tolerance": tolerance,
            "evidence": [{
                "measurement_id": item.id,
                "min_val": item.min_val,
                "max_val": item.max_val,
                "excluded": bool(item.excluded),
            } for item in details],
        })
        if not eligible:
            snapshots.append({
                "record_id": record.id,
                "eligible": False,
                "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
            })
    return source_rows, snapshots


def build_attribute_study_input(
    source: str,
    filters: Mapping[str, Any],
    interval: str,
    *,
    input_contract_version: str = SPC_INPUT_CONTRACT_VERSION,
) -> SpcStudyInput:
    """建立可追溯的 p／np 屬性研究輸入，不將未知資料視為良品。"""

    canonical_filters = normalize_attribute_filters(source, filters)
    stream = canonical_attribute_process_stream(source, canonical_filters)
    normalized_interval = str(interval).strip().lower()
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

    options = {"interval": normalized_interval}
    specification = {
        "found": bool(eligible_rows),
        "source": "saved_inspection_outcome_with_specification_evidence",
    }
    data_hash = calculate_study_data_hash(
        source=source,
        filters=canonical_filters,
        source_rows=source_rows,
        specification=specification,
        analysis_family="attribute",
        options=options,
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
        options=options,
        data_hash=data_hash,
        reasons=reasons,
        metadata={
            "classification_snapshot": snapshots,
            "eligible_record_count": len(eligible_rows),
            "excluded_record_count": len(snapshots),
        },
    )
