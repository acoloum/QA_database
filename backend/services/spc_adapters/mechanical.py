"""機械性質檢驗資料轉成 SPC 共用研究輸入。

依 AIAG-VDA SPC 2026 方法，機械性質以「每爐次一個個別值」建立 I-MR 研究：
一筆 MechanicalTest 對應一個子組（n=1），個別值為該爐次某（項目,位置）
所有未排除樣本的平均；爐門/爐頂視為不同製程流分別監控。
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping

from ...models import MechanicalTest, MechanicalMeasurement
from ..spc_contracts import SpcReason, SpcStudyInput, SpcSubgroup
from .common import (
    SPC_INPUT_CONTRACT_VERSION,
    assert_source_size,
    calculate_study_data_hash,
    canonical_process_stream,
    specification_from_mechanical_limits,
)


def _date_bound(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _sequence_timestamp(test_date: date | None, intra_day_index: int) -> datetime | None:
    """為 I-MR 產生嚴格遞增的序列時間戳。

    I-MR 管制圖的 x 軸本質是觀測（生產）順序；同一天多個爐次以爐次建檔順序
    （已依 test_date, id 排序）在當日內遞增秒數區分，保留正確日期供顯示，
    且相同查詢必得相同順序，維持研究可重現性。爐次無測試日期則無法排入時間序。
    """
    if test_date is None:
        return None
    return datetime.combine(test_date, time.min) + timedelta(seconds=intra_day_index)


def build_mechanical_study_input(
    args: Mapping[str, Any],
    *,
    analysis_family: str = "variable",
    options: Mapping[str, Any] | None = None,
    input_contract_version: str = SPC_INPUT_CONTRACT_VERSION,
) -> SpcStudyInput:
    """依完整機械性質篩選條件建立可重現的 SPC 研究輸入。"""

    stream = canonical_process_stream("mechanical", args)
    filters = stream.filters
    characteristic = str(filters["item"])
    position = str(filters["position"])

    query = MechanicalTest.query
    if filters["vendor_id"] is not None:
        query = query.filter(MechanicalTest.vendor_id == filters["vendor_id"])
    if filters["material"]:
        query = query.filter(MechanicalTest.material.contains(filters["material"]))
    if filters["product_size"]:
        query = query.filter(MechanicalTest.product_size.contains(filters["product_size"]))
    if filters["start_date"]:
        query = query.filter(MechanicalTest.test_date >= _date_bound(filters["start_date"]))
    if filters["end_date"]:
        query = query.filter(MechanicalTest.test_date <= _date_bound(filters["end_date"]))
    assert_source_size(query.count(), "mechanical")
    records = query.order_by(MechanicalTest.test_date.asc(), MechanicalTest.id.asc()).all()

    record_ids = [record.id for record in records]
    measurements: list[MechanicalMeasurement] = []
    if record_ids:
        measurements = (
            MechanicalMeasurement.query
            .filter(
                MechanicalMeasurement.test_id.in_(record_ids),
                MechanicalMeasurement.item == characteristic,
                MechanicalMeasurement.location == position,
            )
            .order_by(
                MechanicalMeasurement.test_id.asc(),
                MechanicalMeasurement.sample_no.asc(),
                MechanicalMeasurement.id.asc(),
            )
            .all()
        )

    by_record: dict[int, list[MechanicalMeasurement]] = defaultdict(list)
    for measurement in measurements:
        by_record[measurement.test_id].append(measurement)

    source_rows: list[dict[str, Any]] = []
    subgroups: list[SpcSubgroup] = []
    excluded_count = 0
    undated_count = 0
    distribution_values: list[float] = []
    prev_date: date | None = None
    intra_day_index = 0
    for record in records:
        record_measurements = by_record.get(record.id, [])
        sample_values: list[float] = []
        included_measurement_ids: list[int] = []
        exclusion_snapshot: list[dict[str, Any]] = []
        for measurement in record_measurements:
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
                "date": record.test_date,
                "measurement_id": measurement.id,
                "item": measurement.item,
                "location": measurement.location,
                "sample_no": measurement.sample_no,
                "value": measurement.value,
                "lower_limit": measurement.lower_limit,
                "excluded": bool(measurement.excluded),
                "exclusion_reason": measurement.exclusion_reason,
                "exclusion_user_id": measurement.exclusion_user_id,
                "excluded_at": measurement.excluded_at,
            })
            if measurement.value is None or measurement.excluded:
                if measurement.excluded:
                    excluded_count += 1
                continue
            value = float(measurement.value)
            sample_values.append(value)
            included_measurement_ids.append(measurement.id)
            distribution_values.append(value)

        if not sample_values:
            continue
        # 個別值時間序管制圖無法排入沒有測試日期的爐次，予以略過但另計數揭露。
        if record.test_date is None:
            undated_count += 1
            continue
        # 每爐次一個個別值 = 該爐次該（項目,位置）未排除樣本的平均 → n=1 → I-MR。
        individual = sum(sample_values) / len(sample_values)
        if record.test_date == prev_date:
            intra_day_index += 1
        else:
            intra_day_index = 0
            prev_date = record.test_date
        subgroups.append(SpcSubgroup(
            key=f"mechanical:{record.id}",
            timestamp=_sequence_timestamp(record.test_date, intra_day_index),
            values=[individual],
            record_ids=(record.id,),
            measurement_ids=included_measurement_ids,
            exclusion_snapshot=exclusion_snapshot,
            distribution_values=sample_values,
        ))

    specification = specification_from_mechanical_limits(measurements)
    reasons: list[SpcReason] = []
    if not measurements:
        reasons.append(SpcReason("NO_DATA", "篩選範圍內沒有可用的機械性質量測明細"))
    elif not subgroups:
        reasons.append(SpcReason("ALL_VALUES_EXCLUDED", "量測值皆無效或已排除統計"))
    if undated_count:
        reasons.append(SpcReason(
            "UNDATED_RECORDS_SKIPPED",
            f"有 {undated_count} 筆爐次缺測試日期，無法排入時間序，已排除於管制圖",
        ))

    data_hash = calculate_study_data_hash(
        source="mechanical", filters=filters, source_rows=source_rows,
        specification=specification,
        analysis_family=analysis_family,
        options=options,
        input_contract_version=input_contract_version,
    )
    return SpcStudyInput(
        source="mechanical",
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
            "undated_count": undated_count,
            "distribution_values": distribution_values,
            "position": position,
        },
    )
