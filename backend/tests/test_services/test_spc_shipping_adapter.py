"""出貨 SPC 資料轉接器測試。"""

from datetime import date

from backend.models import ShippingData, ShippingMeasurement, Vendor
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

