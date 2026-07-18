"""製程巡檢資料轉成 SPC 共用研究輸入。"""

from collections import OrderedDict
from datetime import date
from typing import Any, Mapping

from ...models import PatrolDetail, PatrolMain
from ..spc_contracts import SpcReason, SpcStudyInput, SpcSubgroup
from .common import (
    calculate_study_data_hash,
    canonical_process_stream,
    resolve_tolerance_specification,
)


def _date_bound(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def build_patrol_study_input(args: Mapping[str, Any]) -> SpcStudyInput:
    """依完整巡檢篩選條件建立可重現的 SPC 研究輸入。"""

    stream = canonical_process_stream("patrol", args)
    filters = stream.filters
    characteristic = str(filters["item"])

    query = PatrolDetail.query.join(PatrolMain).filter(PatrolDetail.item == characteristic)
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
    details = query.order_by(
        PatrolMain.date.asc(), PatrolDetail.main_id.asc(), PatrolDetail.group.asc(),
        PatrolDetail.id.asc(),
    ).all()

    grouped: OrderedDict[tuple[int, int | None], list[PatrolDetail]] = OrderedDict()
    for detail in details:
        grouped.setdefault((detail.main_id, detail.group), []).append(detail)

    source_rows: list[dict[str, Any]] = []
    subgroups: list[SpcSubgroup] = []
    excluded_count = 0
    distribution_values: list[float] = []
    for (main_id, group_no), group_details in grouped.items():
        main = group_details[0].main
        values: list[float] = []
        subgroup_distribution_values: list[float] = []
        included_measurement_ids: list[int] = []
        exclusion_snapshot: list[dict[str, Any]] = []
        for detail in group_details:
            snapshot = {
                "measurement_id": detail.id,
                "excluded": bool(detail.excluded),
                "reason": detail.exclusion_reason,
                "exclusion_user_id": detail.exclusion_user_id,
                "excluded_at": (
                    detail.excluded_at.isoformat() if detail.excluded_at else None
                ),
            }
            exclusion_snapshot.append(snapshot)
            source_rows.append({
                "record_id": main_id,
                "date": main.date,
                "measurement_id": detail.id,
                "group_num": group_no,
                "position": detail.position,
                "value_min": detail.min_val,
                "value_max": detail.max_val,
                "excluded": bool(detail.excluded),
                "exclusion_reason": detail.exclusion_reason,
                "exclusion_user_id": detail.exclusion_user_id,
                "excluded_at": detail.excluded_at,
            })
            if detail.min_val is None or detail.max_val is None or detail.excluded:
                if (
                    detail.min_val is not None and detail.max_val is not None
                    and detail.excluded
                ):
                    excluded_count += 1
                continue
            values.extend((float(detail.min_val), float(detail.max_val)))
            distribution_values.extend((float(detail.min_val), float(detail.max_val)))
            subgroup_distribution_values.extend((float(detail.min_val), float(detail.max_val)))
            included_measurement_ids.append(detail.id)

        if values:
            subgroups.append(SpcSubgroup(
                key=f"patrol:{main_id}:group:{group_no}",
                timestamp=main.date,
                values=values,
                record_ids=(main_id,),
                measurement_ids=included_measurement_ids,
                exclusion_snapshot=exclusion_snapshot,
                distribution_values=subgroup_distribution_values,
            ))

    specification = resolve_tolerance_specification(
        material=str(filters["mat"]), spec=str(filters["spec"]),
        characteristic=characteristic, vendor_id=filters["cust_id"],
    )
    reasons: list[SpcReason] = []
    if not details:
        reasons.append(SpcReason("NO_DATA", "篩選範圍內沒有可用的巡檢量測明細"))
    elif not subgroups:
        reasons.append(SpcReason("ALL_VALUES_EXCLUDED", "量測值皆無效或已排除統計"))

    data_hash = calculate_study_data_hash(
        source="patrol", filters=filters, source_rows=source_rows,
        specification=specification,
    )
    return SpcStudyInput(
        source="patrol",
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
