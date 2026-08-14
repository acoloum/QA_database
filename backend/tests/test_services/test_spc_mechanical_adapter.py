"""機械性質 SPC 資料轉接器測試。"""

from datetime import date

from backend.models import (
    MechanicalTest, MechanicalMeasurement, Vendor,
    VendorToleranceDetail, VendorToleranceMain,
)
from backend.services.spc_adapters.common import canonical_process_stream
from backend.services.spc_adapters.mechanical import build_mechanical_study_input
from backend.services.spc_chart_engine import calculate_chart_set


def _test_record(db_session, vendor_id, test_date, samples):
    """建立一筆機械性質檢驗與其抗拉強度/爐門樣本。

    samples 為 (取樣序, 量測值, 是否排除) 的序列。
    """
    record = MechanicalTest(
        product_size="66.7*59", material="6061-T651",
        vendor_id=vendor_id, test_date=test_date,
    )
    db_session.add(record)
    db_session.flush()
    for sample_no, value, excluded in samples:
        db_session.add(MechanicalMeasurement(
            test_id=record.id, item="抗拉強度", location="爐門",
            sample_no=sample_no, value=value, lower_limit=350.0,
            excluded=excluded,
            exclusion_reason="試片異常" if excluded else None,
        ))
    return record


def test_mechanical_adapter_builds_one_individual_per_heat(app, db_session):
    with app.app_context():
        vendor = Vendor(name="安泰")
        db_session.add(vendor)
        db_session.flush()

        # 同日兩爐次（測嚴格遞增時間序）、隔日一爐次、含一筆排除樣本、一筆未排除。
        first = _test_record(db_session, vendor.id, date(2026, 7, 1),
                             [(1, 360.0, False), (2, 380.0, False)])
        second = _test_record(db_session, vendor.id, date(2026, 7, 1),
                              [(1, 400.0, False), (2, 300.0, True)])
        third = _test_record(db_session, vendor.id, date(2026, 7, 5),
                             [(1, 355.0, False)])
        db_session.commit()

        study_input = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "抗拉強度", "position": "爐門",
            "start_date": "2026-07-01", "end_date": "2026-07-31",
        })

        # 每爐次一個個別值，n=1
        assert len(study_input.subgroups) == 3
        assert all(subgroup.n == 1 for subgroup in study_input.subgroups)

        # 個別值 = 該爐次未排除樣本的平均（second 排除 300 後只剩 400）
        first_sub, second_sub, third_sub = study_input.subgroups
        assert first_sub.values == (370.0,)     # (360+380)/2
        assert second_sub.values == (400.0,)    # 300 已排除
        assert third_sub.values == (355.0,)
        assert first_sub.record_ids == (first.id,)

        # 依測試日期排序，同日以嚴格遞增序列時間戳區分
        timestamps = [subgroup.timestamp for subgroup in study_input.subgroups]
        assert all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))

        # 單邊下限規格
        assert study_input.specification["one_sided"] == "lower"
        assert study_input.specification["LSL"] == 350.0
        assert study_input.specification["USL"] is None

        # 排除樣本計數
        assert study_input.metadata["excluded_count"] == 1

        # 可產出 I-MR 管制圖
        chart = calculate_chart_set(study_input.subgroups)
        assert chart.chart_type == "i_mr"


def test_mechanical_adapter_skips_undated_records(app, db_session):
    with app.app_context():
        vendor = Vendor(name="安泰")
        db_session.add(vendor)
        db_session.flush()
        _test_record(db_session, vendor.id, date(2026, 7, 1), [(1, 360.0, False)])
        _test_record(db_session, vendor.id, None, [(1, 370.0, False)])
        db_session.commit()

        study_input = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "抗拉強度", "position": "爐門",
        })

        # 無測試日期的爐次無法排入時間序，排除於管制圖但揭露計數
        assert len(study_input.subgroups) == 1
        assert study_input.metadata["undated_count"] == 1
        assert any(reason.code == "UNDATED_RECORDS_SKIPPED" for reason in study_input.reasons)


def test_mechanical_adapter_separates_positions(app, db_session):
    with app.app_context():
        vendor = Vendor(name="安泰")
        db_session.add(vendor)
        db_session.flush()
        record = MechanicalTest(
            product_size="66.7*59", material="6061-T651",
            vendor_id=vendor.id, test_date=date(2026, 7, 1),
        )
        db_session.add(record)
        db_session.flush()
        db_session.add_all([
            MechanicalMeasurement(test_id=record.id, item="抗拉強度", location="爐門",
                                  sample_no=1, value=360.0, lower_limit=350.0),
            MechanicalMeasurement(test_id=record.id, item="抗拉強度", location="爐頂",
                                  sample_no=1, value=340.0, lower_limit=350.0),
        ])
        db_session.commit()

        door = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "抗拉強度", "position": "爐門",
        })
        top = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "抗拉強度", "position": "爐頂",
        })

        # 爐門/爐頂為不同製程流，各自只取自己位置的值
        assert door.subgroups[0].values == (360.0,)
        assert top.subgroups[0].values == (340.0,)
        assert door.process_stream_key != top.process_stream_key


def test_mechanical_process_stream_uses_every_supported_filter():
    base = {
        "vendor_id": 2, "material": "6061-T651", "product_size": "66.7*59",
        "item": "抗拉強度", "position": "爐門",
        "start_date": "2026-07-01", "end_date": "2026-07-31",
    }
    original = canonical_process_stream("mechanical", base)
    for name in base:
        altered = "9" if name == "vendor_id" else f"{base[name]}-不同"
        changed = canonical_process_stream("mechanical", {**base, name: altered})
        assert changed.key != original.key, name


def _tolerance(db_session, vendor_id, item, characteristic_class, *, dim_min=350.0):
    """建立一筆對應 6061-T651 / 66.7*59 的廠商公差明細。"""
    main = VendorToleranceMain(
        vendor_id=vendor_id, material="6061-T651", spec="66.7*59",
    )
    db_session.add(main)
    db_session.flush()
    db_session.add(VendorToleranceDetail(
        main_id=main.id, item=item, dim_min=dim_min,
        characteristic_class=characteristic_class,
    ))
    return main


def test_specification_carries_characteristic_class_from_tolerance(app, db_session):
    """公差檔標為「主要」時，規格快照必須帶出來供目標值查表使用。"""
    with app.app_context():
        vendor = Vendor(name="安泰")
        db_session.add(vendor)
        db_session.flush()
        _tolerance(db_session, vendor.id, "抗拉強度", "主要")
        _test_record(db_session, vendor.id, date(2026, 7, 1), [(1, 360.0, False)])
        db_session.commit()

        study_input = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "抗拉強度", "position": "爐門",
        })

        assert study_input.specification["characteristic_class"] == "主要"
        assert study_input.specification["characteristic_class_consistent"] is True


def test_hardness_maps_to_rockwell_tolerance_item(app, db_session):
    """機械性質的「硬度」對應公差檔的「洛氏硬度」，重要度要跟著對上。"""
    with app.app_context():
        vendor = Vendor(name="安泰")
        db_session.add(vendor)
        db_session.flush()
        _tolerance(db_session, vendor.id, "洛氏硬度", "主要", dim_min=60.0)
        record = MechanicalTest(
            product_size="66.7*59", material="6061-T651",
            vendor_id=vendor.id, test_date=date(2026, 7, 1),
        )
        db_session.add(record)
        db_session.flush()
        db_session.add(MechanicalMeasurement(
            test_id=record.id, item="硬度", location="爐門",
            sample_no=1, value=62.0, lower_limit=60.0,
        ))
        db_session.commit()

        study_input = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "硬度", "position": "爐門",
        })

        assert study_input.specification["characteristic_class"] == "主要"


def test_unregistered_characteristic_class_falls_back_to_other(app, db_session):
    """查無公差來源時退回「其他」，並標記為未確認，不擅自沿用其他項目的重要度。"""
    with app.app_context():
        vendor = Vendor(name="安泰")
        db_session.add(vendor)
        db_session.flush()
        _test_record(db_session, vendor.id, date(2026, 7, 1), [(1, 360.0, False)])
        db_session.commit()

        study_input = build_mechanical_study_input({
            "vendor_id": vendor.id, "material": "6061-T651",
            "product_size": "66.7*59", "item": "抗拉強度", "position": "爐門",
        })

        assert study_input.specification["characteristic_class"] == "其他"
