"""出貨檢驗資料轉成 SPC 共用研究輸入。"""

from collections import defaultdict
from datetime import date
from typing import Any, Mapping

from ...models import ShippingData, ShippingMeasurement, Vendor
from ..spc_contracts import SpcReason, SpcStudyInput, SpcSubgroup
from .common import (
    calculate_study_data_hash,
    canonical_process_stream,
    specification_from_measurement_limits,
)


MIN_MAX_CHARACTERISTICS = {"外徑", "內徑", "厚度"}


def _date_bound(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _measurement_value(row: ShippingMeasurement, characteristic: str) -> float | None:
    if characteristic in MIN_MAX_CHARACTERISTICS:
        if row.value_min is None or row.value_max is None:
            return None
        return (float(row.value_min) + float(row.value_max)) / 2
    if row.value_single is None:
        return None
    return float(row.value_single)


def build_shipping_study_input(args: Mapping[str, Any]) -> SpcStudyInput:
    """依完整出貨篩選條件建立可重現的 SPC 研究輸入。"""

    stream = canonical_process_stream("shipping", args)
    filters = stream.filters
    characteristic = str(filters["field"])

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
    records = query.order_by(ShippingData.date.asc(), ShippingData.id.asc()).all()

    record_ids = [record.id for record in records]
    measurements: list[ShippingMeasurement] = []
    if record_ids:
        measurements = (
            ShippingMeasurement.query
            .filter(
                ShippingMeasurement.shipping_id.in_(record_ids),
                ShippingMeasurement.item == characteristic,
            )
            .order_by(
                ShippingMeasurement.shipping_id.asc(),
                ShippingMeasurement.group_num.asc(),
                ShippingMeasurement.id.asc(),
            )
            .all()
        )

    by_record: dict[int, list[ShippingMeasurement]] = defaultdict(list)
    for measurement in measurements:
        by_record[measurement.shipping_id].append(measurement)

    source_rows: list[dict[str, Any]] = []
    subgroups: list[SpcSubgroup] = []
    excluded_count = 0
    distribution_values: list[float] = []
    for record in records:
        record_measurements = by_record.get(record.id, [])
        values: list[float] = []
        subgroup_distribution_values: list[float] = []
        included_measurement_ids: list[int] = []
        exclusion_snapshot: list[dict[str, Any]] = []
        for measurement in record_measurements:
            value = _measurement_value(measurement, characteristic)
            snapshot = {
                "measurement_id": measurement.id,
                "excluded": bool(measurement.excluded),
                "reason": measurement.exclusion_reason,
                "exclusion_user_id": measurement.exclusion_user_id,
                "excluded_at": (
                    measurement.excluded_at.isoformat()
                    if measurement.excluded_at else None
                ),
            }
            exclusion_snapshot.append(snapshot)
            source_rows.append({
                "record_id": record.id,
                "date": record.date,
                "order_num": record.order_num,
                "measurement_id": measurement.id,
                "group_num": measurement.group_num,
                "position": measurement.position,
                "value_min": measurement.value_min,
                "value_max": measurement.value_max,
                "value_single": measurement.value_single,
                "lower_limit": measurement.lower_limit,
                "upper_limit": measurement.upper_limit,
                "excluded": bool(measurement.excluded),
                "exclusion_reason": measurement.exclusion_reason,
                "exclusion_user_id": measurement.exclusion_user_id,
                "excluded_at": measurement.excluded_at,
            })
            if value is None or measurement.excluded:
                if measurement.excluded:
                    excluded_count += 1
                continue
            values.append(value)
            included_measurement_ids.append(measurement.id)
            if characteristic in MIN_MAX_CHARACTERISTICS:
                distribution_values.extend((
                    float(measurement.value_min), float(measurement.value_max),
                ))
                subgroup_distribution_values.extend((
                    float(measurement.value_min), float(measurement.value_max),
                ))
            else:
                distribution_values.append(value)
                subgroup_distribution_values.append(value)

        if values:
            subgroups.append(SpcSubgroup(
                key=f"shipping:{record.id}",
                timestamp=record.date,
                values=values,
                record_ids=(record.id,),
                measurement_ids=included_measurement_ids,
                exclusion_snapshot=exclusion_snapshot,
                distribution_values=subgroup_distribution_values,
            ))

    specification = specification_from_measurement_limits(measurements)
    reasons: list[SpcReason] = []
    if not measurements:
        reasons.append(SpcReason("NO_DATA", "篩選範圍內沒有可用的出貨量測明細"))
    elif not subgroups:
        reasons.append(SpcReason("ALL_VALUES_EXCLUDED", "量測值皆無效或已排除統計"))

    data_hash = calculate_study_data_hash(
        source="shipping", filters=filters, source_rows=source_rows,
        specification=specification,
    )
    return SpcStudyInput(
        source="shipping",
        filters=filters,
        process_stream_key=stream.key,
        characteristic=characteristic,
        subgroups=subgroups,
        specification=specification,
        data_hash=data_hash,
        reasons=reasons,
        metadata={
            "excluded_count": excluded_count,
            "distribution_values": distribution_values,
        },
    )
