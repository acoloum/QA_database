"""出貨 SPC 資料轉接器測試。"""

from datetime import date

import pytest

from backend.models import (
    ShippingData, ShippingMeasurement, Vendor, VendorToleranceDetail, VendorToleranceMain,
)
from backend.services.spc_adapters.common import canonical_process_stream
from backend.services.spc_adapters.shipping import build_shipping_study_input


def _measurement(shipping_id, group_num, position, low, high, **overrides):
    values = {
        "shipping_id": shipping_id,
        "group_num": group_num,
        "item": "外徑",
        "position": position,
        "lower_limit": 9.5,
        "upper_limit": 10.5,
        "value_min": low,
        "value_max": high,
    }
    values.update(overrides)
    return ShippingMeasurement(**values)


def test_shipping_adapter_keeps_segmented_measurements_and_exclusion_snapshot(
    app, db_session
):
    with app.app_context():
        vendor = Vendor(name="甲供應商")
        db_session.add(vendor)
        db_session.flush()
        record = ShippingData(
            date=date(2026, 7, 1), material="6061", spec="10*1*100",
            order_num="SO-1", vendor_id=vendor.id, group_count=2,
        )
        db_session.add(record)
        db_session.flush()
        front = _measurement(record.id, 1, "前段", 9.8, 10.0)
        rear = _measurement(record.id, 1, "後段", 10.0, 10.2)
        excluded = _measurement(
            record.id, 2, "", 99, 100,
            excluded=True, exclusion_reason="量具滑動",
        )
        db_session.add_all([front, rear, excluded])
        db_session.commit()

        study_input = build_shipping_study_input({
            "field": "外徑", "vendor": "甲供應商", "material": "6061",
            "spec": "10*1*100", "start_date": date(2026, 7, 1),
            "end_date": "2026-07-31",
        })

        assert len(study_input.subgroups) == 1
        subgroup = study_input.subgroups[0]
        assert subgroup.record_ids == (record.id,)
        assert subgroup.measurement_ids == (front.id, rear.id)
        assert subgroup.values == (9.9, 10.1)
        assert [row["measurement_id"] for row in subgroup.exclusion_snapshot] == [
            front.id, rear.id, excluded.id,
        ]
        assert subgroup.exclusion_snapshot[-1]["excluded"] is True
        assert "exclusion_user_id" in subgroup.exclusion_snapshot[-1]
        assert "excluded_at" in subgroup.exclusion_snapshot[-1]
        assert study_input.specification["LSL"] == 9.5
        assert study_input.specification["USL"] == 10.5


def test_shipping_hash_is_order_independent_and_changes_with_source_value(
    app, db_session
):
    with app.app_context():
        vendor = Vendor(name="乙供應商")
        db_session.add(vendor)
        db_session.flush()
        record = ShippingData(
            date=date(2026, 7, 2), material="6063", spec="20*2*100",
            vendor_id=vendor.id, group_count=2,
        )
        db_session.add(record)
        db_session.flush()
        first = _measurement(record.id, 1, "前段", 19.8, 20.0)
        first.lower_limit = 19.5
        first.upper_limit = 20.5
        second = _measurement(record.id, 2, "後段", 20.0, 20.2)
        second.lower_limit = 19.5
        second.upper_limit = 20.5
        db_session.add_all([second, first])
        db_session.commit()

        args_a = {
            "vendor": "乙供應商", "material": "6063", "field": "外徑",
            "spec": "20*2*100", "start_date": "2026-07-01",
            "end_date": "2026-07-31",
        }
        args_b = dict(reversed(list(args_a.items())))
        a = build_shipping_study_input(args_a)
        b = build_shipping_study_input(args_b)
        assert a.filters == b.filters
        assert a.process_stream_key == b.process_stream_key
        assert a.data_hash == b.data_hash

        first.value_min = 19.7
        db_session.commit()
        changed = build_shipping_study_input(args_a)
        assert changed.data_hash != a.data_hash


def test_shipping_process_stream_uses_every_supported_filter():
    base = {
        "vendor": "甲", "material": "6061", "spec": "10*1*100",
        "field": "外徑", "start_date": "2026-07-01", "end_date": "2026-07-31",
    }
    original = canonical_process_stream("shipping", base)

    for name in base:
        changed = canonical_process_stream("shipping", {**base, name: f"{base[name]}-不同"})
        assert changed.key != original.key, name


def _shipping_record(db_session, vendor, *, material, spec, day):
    record = ShippingData(
        date=date(2026, 8, day), material=material, spec=spec,
        vendor_id=vendor.id, group_count=1,
    )
    db_session.add(record)
    db_session.flush()
    return record


def _thickness(record, value, **overrides):
    values = {
        "shipping_id": record.id, "group_num": 1, "item": "厚度", "position": "",
        "value_min": value, "value_max": value,
    }
    values.update(overrides)
    return ShippingMeasurement(**values)


def _vendor_tolerance(db_session, vendor, *, material, spec, item="厚度", **detail):
    main = VendorToleranceMain(material=material, spec=spec, vendor_id=vendor.id)
    db_session.add(main)
    db_session.flush()
    db_session.add(VendorToleranceDetail(main_id=main.id, item=item, **detail))
    db_session.flush()
    return main


def test_shipping_specification_falls_back_to_vendor_tolerance_without_snapshot(
    app, db_session
):
    """量測明細沒有存上下限快照時，改以公差主檔解析規格（原本會一律判為無公差）。"""
    with app.app_context():
        vendor = Vendor(name="丙供應商")
        db_session.add(vendor)
        db_session.flush()
        main = _vendor_tolerance(
            db_session, vendor, material="6061-H", spec="28.7*5.1*920",
            std_val=5.1, tolerance_min=-0.1, tolerance_max=0.1,
            characteristic_class="主要",
        )
        first = _shipping_record(db_session, vendor, material="6061-H", spec="28.7*5.1*920", day=1)
        second = _shipping_record(db_session, vendor, material="6061-H", spec="28.7*5.1*920", day=2)
        db_session.add_all([_thickness(first, 5.12), _thickness(second, 5.08)])
        db_session.commit()

        spec = build_shipping_study_input({
            "field": "厚度", "vendor": "丙供應商", "material": "6061-H",
            "spec": "28.7*5.1*920",
        }).specification

        assert spec["found"] is True
        assert spec["consistent"] is True
        assert spec["LSL"] == pytest.approx(5.0)
        assert spec["USL"] == pytest.approx(5.2)
        assert spec["source"] == "vendor_tolerance"
        assert spec["characteristic_class"] == "主要"
        assert spec["tolerance_ids"] == [main.id]


def test_shipping_specification_prefers_measurement_snapshot_per_record(
    app, db_session
):
    with app.app_context():
        vendor = Vendor(name="丁供應商")
        db_session.add(vendor)
        db_session.flush()
        _vendor_tolerance(
            db_session, vendor, material="6063", spec="30*2",
            std_val=2.0, tolerance_min=-0.1, tolerance_max=0.1,
        )
        snap = _shipping_record(db_session, vendor, material="6063", spec="30*2", day=3)
        plain = _shipping_record(db_session, vendor, material="6063", spec="30*2", day=4)
        db_session.add_all([
            _thickness(snap, 2.0, lower_limit=1.9, upper_limit=2.1),
            _thickness(plain, 2.0),
        ])
        db_session.commit()

        spec = build_shipping_study_input({
            "field": "厚度", "vendor": "丁供應商", "material": "6063",
        }).specification

        assert spec["consistent"] is True
        assert spec["LSL"] == pytest.approx(1.9)
        assert spec["USL"] == pytest.approx(2.1)
        assert spec["source"] == "mixed"


def test_shipping_specification_marks_conflicting_limits_inconsistent(
    app, db_session
):
    """篩選範圍跨到不同規格（界限不同）時不得任選一組，須揭露不一致。"""
    with app.app_context():
        vendor = Vendor(name="戊供應商")
        db_session.add(vendor)
        db_session.flush()
        _vendor_tolerance(
            db_session, vendor, material="6061-F", spec="35*2.8",
            std_val=2.8, tolerance_min=-0.15, tolerance_max=0.15,
        )
        _vendor_tolerance(
            db_session, vendor, material="6061-F", spec="36*3.0",
            std_val=3.0, tolerance_min=-0.15, tolerance_max=0.15,
        )
        a = _shipping_record(db_session, vendor, material="6061-F", spec="35*2.8", day=5)
        b = _shipping_record(db_session, vendor, material="6061-F", spec="36*3.0", day=6)
        c = _shipping_record(db_session, vendor, material="6061-F", spec="99*9.9", day=7)
        db_session.add_all([_thickness(a, 2.8), _thickness(b, 3.0), _thickness(c, 9.9)])
        db_session.commit()

        spec = build_shipping_study_input({
            "field": "厚度", "vendor": "戊供應商", "material": "6061-F",
        }).specification

        assert spec["found"] is True
        assert spec["consistent"] is False
        assert spec["LSL"] is None and spec["USL"] is None
        assert spec["lower_values"] == pytest.approx([2.65, 2.85])
        assert spec["unresolved_record_ids"] == [c.id]


def test_shipping_specification_infers_one_sided_upper_limit(app, db_session):
    with app.app_context():
        vendor = Vendor(name="己供應商")
        db_session.add(vendor)
        db_session.flush()
        _vendor_tolerance(
            db_session, vendor, material="6005", spec="40*3",
            item="同心度", dim_max=0.2,
        )
        record = _shipping_record(db_session, vendor, material="6005", spec="40*3", day=8)
        db_session.add(_thickness(
            record, None, item="同心度", value_single=0.1,
        ))
        db_session.commit()

        spec = build_shipping_study_input({
            "field": "同心度", "vendor": "己供應商", "material": "6005",
        }).specification

        assert spec["USL"] == pytest.approx(0.2)
        assert spec["LSL"] is None
        assert spec["one_sided"] == "upper"
