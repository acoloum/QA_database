"""屬性資料來源轉接器測試。"""

from datetime import date

from backend.models import PatrolDetail, PatrolMain, ShippingData, ShippingMeasurement
from backend.services.spc_adapters.attribute import build_attribute_study_input


def _shipping_record(db_session, record_date, *, is_ng, has_specification=True):
    record = ShippingData(
        date=record_date,
        material="6061",
        spec="10*1*100",
        order_num=f"SO-{record_date.isoformat()}-{is_ng}",
        is_ng=is_ng,
    )
    db_session.add(record)
    db_session.flush()
    db_session.add(ShippingMeasurement(
        shipping_id=record.id,
        group_num=1,
        item="外徑",
        position="",
        lower_limit=9.5 if has_specification else None,
        upper_limit=10.5 if has_specification else None,
        value_min=9.8,
        value_max=10.0,
        is_ng=bool(is_ng),
    ))
    return record


def test_shipping_attribute_adapter_groups_day_week_and_month_and_preserves_counts(
    app, db_session
):
    with app.app_context():
        first = _shipping_record(db_session, date(2026, 7, 1), is_ng=False)
        second = _shipping_record(db_session, date(2026, 7, 1), is_ng=True)
        third = _shipping_record(db_session, date(2026, 7, 6), is_ng=True)
        db_session.commit()

        filters = {"material": "6061", "spec": "10*1*100", "field": "外徑"}
        by_day = build_attribute_study_input("shipping", filters, "day")
        by_week = build_attribute_study_input("shipping", filters, "week")
        by_month = build_attribute_study_input("shipping", filters, "month")

        assert [(group.inspected, group.nonconforming) for group in by_day.subgroups] == [
            (2, 1), (1, 1),
        ]
        assert by_day.subgroups[0].record_ids == (first.id, second.id)
        assert by_day.subgroups[1].record_ids == (third.id,)
        assert [(group.inspected, group.nonconforming) for group in by_week.subgroups] == [
            (2, 1), (1, 1),
        ]
        assert [(group.inspected, group.nonconforming) for group in by_month.subgroups] == [
            (3, 2),
        ]
        assert by_month.characteristic == "不符合單位"
        assert by_month.analysis_family == "attribute"
        assert by_month.options == {"interval": "month"}
        assert by_month.filters["field"] == "外徑"


def test_shipping_attribute_adapter_excludes_unknown_classification_with_snapshot(
    app, db_session
):
    with app.app_context():
        eligible = _shipping_record(db_session, date(2026, 7, 1), is_ng=False)
        unknown = _shipping_record(
            db_session, date(2026, 7, 1), is_ng=None, has_specification=False
        )
        db_session.commit()

        study_input = build_attribute_study_input("shipping", {"field": "外徑"}, "day")

        assert study_input.subgroups[0].record_ids == (eligible.id,)
        assert study_input.metadata["classification_snapshot"] == [{
            "record_id": unknown.id,
            "eligible": False,
            "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
        }]


def test_patrol_attribute_adapter_excludes_record_when_tolerance_cannot_be_resolved(
    app, db_session, monkeypatch
):
    with app.app_context():
        main = PatrolMain(
            date=date(2026, 7, 2), material="6063", spec="20*2*100", is_ng=True
        )
        db_session.add(main)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=main.id,
            group=1,
            item="厚度",
            position="前段",
            min_val=1.9,
            max_val=2.1,
        ))
        db_session.commit()
        monkeypatch.setattr(
            "backend.services.spc_adapters.attribute.resolve_tolerance_specification",
            lambda **_kwargs: {"found": False, "LSL": None, "USL": None},
        )

        study_input = build_attribute_study_input(
            "patrol", {"mat": "6063", "spec": "20*2*100", "item": "厚度"}, "day"
        )

        assert study_input.subgroups == ()
        assert study_input.metadata["classification_snapshot"] == [{
            "record_id": main.id,
            "eligible": False,
            "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
        }]
