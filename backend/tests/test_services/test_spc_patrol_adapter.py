"""巡檢 SPC 資料轉接器測試。"""

from datetime import date

from backend.models import Machine, Operator, PatrolDetail, PatrolMain, Vendor
from backend.services.spc_adapters.common import canonical_process_stream
from backend.services.spc_adapters.patrol import build_patrol_study_input


def test_patrol_adapter_keeps_detail_ids_values_and_exclusion_snapshot(
    app, db_session
):
    with app.app_context():
        machine = Machine(name="M-1")
        operator = Operator(name="王員")
        customer = Vendor(name="客戶甲")
        db_session.add_all([machine, operator, customer])
        db_session.flush()
        main = PatrolMain(
            date=date(2026, 7, 3), machine_id=machine.id, operator_id=operator.id,
            customer_id=customer.id, material="6061", spec="10*1*100",
        )
        db_session.add(main)
        db_session.flush()
        front = PatrolDetail(
            main_id=main.id, group=1, item="外徑", position="前段",
            min_val=9.8, max_val=10.0,
        )
        rear = PatrolDetail(
            main_id=main.id, group=1, item="外徑", position="後段",
            min_val=10.0, max_val=10.2,
        )
        excluded = PatrolDetail(
            main_id=main.id, group=1, item="外徑", position="中段",
            min_val=99, max_val=100, excluded=True, exclusion_reason="治具鬆動",
        )
        db_session.add_all([front, rear, excluded])
        db_session.commit()

        study_input = build_patrol_study_input({
            "m_id": str(machine.id), "op_id": str(operator.id),
            "cust_id": str(customer.id), "mat": "6061", "spec": "10*1*100",
            "item": "外徑", "pos": "", "s_date": date(2026, 7, 1),
            "e_date": "2026-07-31",
        })

        assert study_input.filters["m_id"] == machine.id
        assert study_input.filters["op_id"] == operator.id
        assert study_input.subgroups[0].record_ids == (main.id,)
        assert study_input.subgroups[0].measurement_ids == (front.id, rear.id)
        assert study_input.subgroups[0].values == (9.8, 10.0, 10.0, 10.2)
        assert study_input.subgroups[0].exclusion_snapshot[-1] == {
            "measurement_id": excluded.id,
            "excluded": True,
            "reason": "治具鬆動",
            "exclusion_user_id": None,
            "excluded_at": None,
        }


def test_patrol_hash_changes_when_exclusion_state_changes(app, db_session):
    with app.app_context():
        main = PatrolMain(date=date(2026, 7, 4), material="6063", spec="20*2*100")
        db_session.add(main)
        db_session.flush()
        detail = PatrolDetail(
            main_id=main.id, group=1, item="厚度", position="前段",
            min_val=1.9, max_val=2.1,
        )
        db_session.add(detail)
        db_session.commit()
        args = {"mat": "6063", "spec": "20*2*100", "item": "厚度", "pos": "前段"}

        before = build_patrol_study_input(args)
        detail.excluded = True
        detail.exclusion_reason = "量測程序錯誤"
        db_session.commit()
        after = build_patrol_study_input(args)

        assert before.data_hash != after.data_hash
        assert after.subgroups == ()


def test_patrol_process_stream_changes_when_machine_changes_and_normalizes_ids():
    base = {
        "m_id": "1", "op_id": "2", "cust_id": "3", "mat": "6061",
        "spec": "10*1*100", "item": "外徑", "pos": "前段",
        "s_date": "2026-07-01", "e_date": "2026-07-31",
    }
    a = canonical_process_stream("patrol", base)
    same = canonical_process_stream("patrol", {**base, "m_id": 1})
    b = canonical_process_stream("patrol", {**base, "m_id": "4"})

    assert a.filters["m_id"] == 1
    assert a.key == same.key
    assert a.key != b.key
