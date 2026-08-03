"""製程巡檢資料轉成 SPC 共用研究輸入。"""

from collections import OrderedDict
from datetime import date
from typing import Any, Mapping

from ...models import (
    PatrolDetail, PatrolMain, VendorToleranceDetail, VendorToleranceMain,
)
from ..spc_contracts import SpcReason, SpcStudyInput, SpcSubgroup
from .common import (
    SPC_INPUT_CONTRACT_VERSION,
    assert_source_size,
    calculate_study_data_hash,
    canonical_process_stream,
    resolve_tolerance_specification,
)


def _date_bound(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _machine_detail_bounds(detail: VendorToleranceDetail) -> tuple[float | None, float | None]:
    """解析單筆已精確命中的公差明細；不使用模糊規格選擇邏輯。"""

    lower = float(detail.dim_min) if detail.dim_min is not None else None
    upper = float(detail.dim_max) if detail.dim_max is not None else None
    if lower is None and upper is None and detail.std_val is not None:
        standard = float(detail.std_val)
        if detail.tolerance_min is not None:
            lower = standard - abs(float(detail.tolerance_min))
        if detail.tolerance_max is not None:
            upper = standard + abs(float(detail.tolerance_max))
    return lower, upper


def resolve_machine_tolerance_specification(
    *, material: str, spec: str, characteristic: str, position: str,
    vendor_id: int | None,
) -> dict[str, Any]:
    """以固定機器研究的精確來源鍵解析可稽核規格快照。

    customer 已指定時只接受該 customer 的公差；未指定時只接受通用公差，
    不會把其他 customer 或模糊材質／規格候選當成核准證據。
    """

    query = (
        VendorToleranceDetail.query.join(VendorToleranceMain)
        .filter(
            VendorToleranceMain.material == material,
            VendorToleranceMain.spec == spec,
            VendorToleranceDetail.item == characteristic,
            VendorToleranceDetail.position == position,
        )
    )
    if vendor_id is None:
        query = query.filter(VendorToleranceMain.vendor_id.is_(None))
        vendor_scope = "generic_only"
    else:
        query = query.filter(VendorToleranceMain.vendor_id == vendor_id)
        vendor_scope = "exact_vendor"
    details = query.order_by(VendorToleranceMain.id.asc(), VendorToleranceDetail.id.asc()).all()
    base = {
        "found": False,
        "consistent": False,
        "LSL": None,
        "USL": None,
        "master_ids": sorted({detail.main_id for detail in details}),
        "detail_ids": [detail.id for detail in details],
        "vendor_scope": vendor_scope,
        "source": "machine_exact_vendor_tolerance",
    }
    if not details:
        return {**base, "reason_code": "SPECIFICATION_UNCONFIRMED"}

    parsed = [
        (*_machine_detail_bounds(detail), detail.characteristic_class or "其他")
        for detail in details
    ]
    valid = [
        bounds for bounds in parsed
        if (bounds[0] is not None or bounds[1] is not None)
        and not (bounds[0] is not None and bounds[1] is not None and bounds[0] >= bounds[1])
    ]
    if len(valid) != len(parsed) or len(set(valid)) != 1:
        return {**base, "reason_code": "MACHINE_SPECIFICATION_INCONSISTENT"}
    lower, upper, characteristic_class = valid[0]
    return {
        **base,
        "found": True,
        "consistent": True,
        "LSL": lower,
        "USL": upper,
        "characteristic_class": characteristic_class,
        "reason_code": None,
    }


def build_patrol_study_input(
    args: Mapping[str, Any],
    *,
    analysis_family: str = "variable",
    options: Mapping[str, Any] | None = None,
    input_contract_version: str = SPC_INPUT_CONTRACT_VERSION,
) -> SpcStudyInput:
    """依完整巡檢篩選條件建立可重現的 SPC 研究輸入。"""

    stream = canonical_process_stream("patrol", args)
    filters = stream.filters
    characteristic = str(filters["item"])

    is_machine = analysis_family == "machine"
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
        query = query.filter(
            PatrolMain.material == filters["mat"] if is_machine
            else PatrolMain.material.contains(filters["mat"])
        )
    if filters["spec"]:
        query = query.filter(
            PatrolMain.spec == filters["spec"] if is_machine
            else PatrolMain.spec.contains(filters["spec"])
        )
    assert_source_size(query.count(), "patrol")
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
    operators: set[int] = set()
    record_ids: set[int] = set()
    detail_ids: set[int] = set()
    observed_dates: list[date] = []
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
                "operator_id": main.operator_id,
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
            if detail.excluded:
                if detail.min_val is not None or detail.max_val is not None:
                    excluded_count += 1
                continue
            observations = [
                float(value) for value in (detail.min_val, detail.max_val)
                if value is not None
            ]
            if not observations:
                continue
            values.extend(observations)
            distribution_values.extend(observations)
            subgroup_distribution_values.extend(observations)
            included_measurement_ids.append(detail.id)
            record_ids.add(main_id)
            detail_ids.add(detail.id)
            if main.operator_id is not None:
                operators.add(int(main.operator_id))
            if main.date is not None:
                observed_dates.append(main.date)

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

    specification = (
        resolve_machine_tolerance_specification(
            material=str(filters["mat"]), spec=str(filters["spec"]),
            characteristic=characteristic, position=str(filters["pos"]),
            vendor_id=filters["cust_id"],
        ) if is_machine else resolve_tolerance_specification(
            material=str(filters["mat"]), spec=str(filters["spec"]),
            characteristic=characteristic, vendor_id=filters["cust_id"],
        )
    )
    reasons: list[SpcReason] = []
    if not details:
        reasons.append(SpcReason("NO_DATA", "篩選範圍內沒有可用的巡檢量測明細"))
    elif not subgroups:
        reasons.append(SpcReason("ALL_VALUES_EXCLUDED", "量測值皆無效或已排除統計"))

    data_hash = calculate_study_data_hash(
        source="patrol", filters=filters, source_rows=source_rows,
        specification=specification,
        analysis_family=analysis_family,
        options=options,
        input_contract_version=input_contract_version,
    )
    return SpcStudyInput(
        source="patrol",
        filters=filters,
        process_stream_key=stream.key,
        characteristic=characteristic,
        subgroups=subgroups,
        specification=specification,
        analysis_family=analysis_family,
        options=options,
        data_hash=data_hash,
        reasons=reasons,
        metadata={
            "excluded_count": excluded_count,
            "distribution_values": distribution_values,
            "source_semantics": (
                "patrol_min_max_observations" if is_machine else "patrol_subgroup_observations"
            ),
            "operators": sorted(operators),
            "record_ids": sorted(record_ids),
            "detail_ids": sorted(detail_ids),
            "date_span": {
                "start": min(observed_dates).isoformat() if observed_dates else None,
                "end": max(observed_dates).isoformat() if observed_dates else None,
            },
        },
    )
