"""機器研究專用規格解析與巡檢觀測值測試。"""

from datetime import date

from backend.models import (
    Machine, Operator, PatrolDetail, PatrolMain, Vendor,
    VendorToleranceDetail, VendorToleranceMain,
)
from backend.services.spc_adapters.patrol import (
    build_patrol_study_input, resolve_machine_tolerance_specification,
)


def _tolerance(db_session, *, material="6061", spec="10*1*100", vendor_id=None,
               item="外徑", position="前段", lsl=9.0, usl=11.0):
    main = VendorToleranceMain(material=material, spec=spec, vendor_id=vendor_id)
    db_session.add(main)
    db_session.flush()
    detail = VendorToleranceDetail(
        main_id=main.id, item=item, position=position,
        dim_min=lsl, dim_max=usl, characteristic_class="主要",
    )
    db_session.add(detail)
    db_session.flush()
    return main, detail


def test_machine_specification_never_matches_approximate_material_or_spec(app, db_session):
    with app.app_context():
        _tolerance(db_session, material="6061-T6", spec="10*1*100")
        _tolerance(db_session, material="6061", spec="10*1")
        db_session.commit()

        result = resolve_machine_tolerance_specification(
            material="6061", spec="10*1*100", characteristic="外徑", position="前段",
            vendor_id=None,
        )

        assert result["found"] is False
        assert result["consistent"] is False


def test_machine_specification_accepts_identical_duplicates_and_preserves_all_ids(app, db_session):
    with app.app_context():
        first_main, first_detail = _tolerance(db_session)
        second_main, second_detail = _tolerance(db_session)
        db_session.commit()

        result = resolve_machine_tolerance_specification(
            material="6061", spec="10*1*100", characteristic="外徑", position="前段",
            vendor_id=None,
        )

        assert result["found"] is True
        assert result["consistent"] is True
        assert result["LSL"] == 9.0
        assert result["USL"] == 11.0
        assert result["master_ids"] == [first_main.id, second_main.id]
        assert result["detail_ids"] == [first_detail.id, second_detail.id]


def test_machine_specification_uses_exact_customer_or_generic_scope(app, db_session):
    with app.app_context():
        vendor = Vendor(name="客戶甲")
        db_session.add(vendor)
        db_session.flush()
        _tolerance(db_session, vendor_id=None, lsl=9.0, usl=11.0)
        _, customer_detail = _tolerance(db_session, vendor_id=vendor.id, lsl=9.5, usl=10.5)
        db_session.commit()

        customer_result = resolve_machine_tolerance_specification(
            material="6061", spec="10*1*100", characteristic="外徑", position="前段",
            vendor_id=vendor.id,
        )
        generic_result = resolve_machine_tolerance_specification(
            material="6061", spec="10*1*100", characteristic="外徑", position="前段",
            vendor_id=None,
        )

        assert customer_result["vendor_scope"] == "exact_vendor"
        assert customer_result["detail_ids"] == [customer_detail.id]
        assert customer_result["LSL"] == 9.5
        assert generic_result["vendor_scope"] == "generic_only"
        assert generic_result["LSL"] == 9.0


def test_machine_specification_rejects_conflicting_or_invalid_bounds(app, db_session):
    with app.app_context():
        _tolerance(db_session, lsl=9.0, usl=11.0)
        _tolerance(db_session, lsl=9.2, usl=11.0)
        db_session.commit()

        result = resolve_machine_tolerance_specification(
            material="6061", spec="10*1*100", characteristic="外徑", position="前段",
            vendor_id=None,
        )

        assert result["found"] is False
        assert result["consistent"] is False
        assert result["reason_code"] == "MACHINE_SPECIFICATION_INCONSISTENT"


def test_machine_specification_allows_single_sided_limits(app, db_session):
    with app.app_context():
        _tolerance(db_session, lsl=None, usl=11.0)
        db_session.commit()

        result = resolve_machine_tolerance_specification(
            material="6061", spec="10*1*100", characteristic="外徑", position="前段",
            vendor_id=None,
        )

        assert result["found"] is True
        assert result["consistent"] is True
        assert result["LSL"] is None
        assert result["USL"] == 11.0


def test_machine_adapter_keeps_equal_min_max_as_two_observations_and_exact_stream(app, db_session):
    with app.app_context():
        machine = Machine(name="M-1")
        other_machine = Machine(name="M-2")
        operator = Operator(name="王員")
        db_session.add_all([machine, other_machine, operator])
        db_session.flush()
        _tolerance(db_session)
        selected = PatrolMain(
            date=date(2026, 7, 1), machine_id=machine.id, operator_id=operator.id,
            material="6061", spec="10*1*100",
        )
        different_machine = PatrolMain(
            date=date(2026, 7, 1), machine_id=other_machine.id, material="6061", spec="10*1*100",
        )
        db_session.add_all([selected, different_machine])
        db_session.flush()
        exact = PatrolDetail(main_id=selected.id, group=1, item="外徑", position="前段", min_val=10.0, max_val=10.0)
        max_only = PatrolDetail(main_id=selected.id, group=1, item="外徑", position="前段", min_val=None, max_val=10.1)
        wrong_position = PatrolDetail(main_id=selected.id, group=1, item="外徑", position="後段", min_val=99.0, max_val=99.0)
        wrong_machine = PatrolDetail(main_id=different_machine.id, group=1, item="外徑", position="前段", min_val=98.0, max_val=98.0)
        db_session.add_all([exact, max_only, wrong_position, wrong_machine])
        db_session.commit()

        study_input = build_patrol_study_input(
            {"m_id": machine.id, "mat": "6061", "spec": "10*1*100", "item": "外徑", "pos": "前段"},
            analysis_family="machine",
            options={"conditions_confirmed": True, "condition_reason": "固定條件"},
        )

        assert study_input.subgroups[0].values == (10.0, 10.0, 10.1)
        assert study_input.subgroups[0].distribution_values == (10.0, 10.0, 10.1)
        assert study_input.metadata["source_semantics"] == "patrol_min_max_observations"
        assert study_input.metadata["detail_ids"] == [exact.id, max_only.id]
        assert study_input.specification["consistent"] is True
