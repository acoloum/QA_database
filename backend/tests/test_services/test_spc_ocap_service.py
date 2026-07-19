"""持續 SPC 失控事件、OCAP 與排除稽核測試。"""

from datetime import date

import pytest

from backend.models import (
    AuditLog,
    PatrolDetail,
    PatrolMain,
    Role,
    ShippingData,
    ShippingMeasurement,
    SpcEvent,
    SpcLimitVersion,
    SpcOcap,
    SpcStudy,
    SpcStudySample,
    SpcStudyVersion,
    User,
)
from backend.services.patrol_service import PatrolService
from backend.services.shipping_service import ShippingService
from backend.services.spc_errors import SpcValidationError
from backend.services.spc_adapters.shipping import build_shipping_study_input
from backend.services.spc_ocap_service import SpcOcapService


def _actor(db_session):
    role = Role(code="qa_supervisor", name="QA主管", permissions={"spc.manage": True})
    actor = User(username="ocap-manager", password="hashed", role=role.code)
    db_session.add_all([role, actor])
    db_session.flush()
    return actor


def _role(db_session, code, name, permissions=None):
    role = Role(code=code, name=name, permissions=permissions or {})
    db_session.add(role)
    db_session.flush()
    return role


def _user(db_session, username, role, *, active=True):
    user = User(username=username, password="hashed", role=role, is_active=active)
    db_session.add(user)
    db_session.flush()
    return user


def _study_limit(db_session, actor, *, study_type="ongoing"):
    study = SpcStudy(
        source="shipping", study_type=study_type, process_stream_key="stream-ocap",
        characteristic="外徑", filters={}, status="active", created_by=actor.id,
    )
    db_session.add(study)
    db_session.flush()
    version = SpcStudyVersion(
        study_id=study.id, version_no=1, method_version="2026.1",
        data_hash="a" * 64, status="active", created_by=actor.id,
    )
    db_session.add(version)
    db_session.flush()
    limit = SpcLimitVersion(
        study_version_id=version.id, process_stream_key=study.process_stream_key,
        characteristic=study.characteristic, revision=1, chart_type="xbar_s",
        limits={}, status="active", created_by=actor.id, approved_by=actor.id,
    )
    db_session.add(limit)
    db_session.commit()
    return study, version, limit


def test_assignable_users_only_include_active_quality_roles(app, db_session):
    with app.app_context():
        for code, name in (
            ("qa_supervisor", "QA主管"),
            ("qc_manager", "品管經理"),
            ("admin", "系統管理員"),
            ("inspector", "檢驗員"),
        ):
            _role(db_session, code, name)
        qa = _user(db_session, "qa-active", "qa_supervisor")
        manager = _user(db_session, "manager-active", "qc_manager")
        admin = _user(db_session, "admin-active", "admin")
        _user(db_session, "qa-disabled", "qa_supervisor", active=False)
        _user(db_session, "inspector-active", "inspector")
        db_session.commit()

        rows = SpcOcapService.list_assignable_users()

        assert {row["id"] for row in rows} == {qa.id, manager.id, admin.id}
        assert {tuple(row) for row in rows} == {
            ("id", "username", "role", "role_name")
        }


def test_new_or_changed_owner_must_be_assignable(app, db_session):
    with app.app_context():
        actor = _actor(db_session)
        _role(db_session, "inspector", "檢驗員")
        invalid_owner = _user(db_session, "invalid-owner", "inspector")
        _, version, limit = _study_limit(db_session, actor)
        event = SpcOcapService.sync_events(limit.id, version.id, [{
            "chart_kind": "variation", "rule_code": "beyond_limits",
            "point_index": 1, "observed_value": 0.5,
        }])[0]

        with pytest.raises(SpcValidationError) as exc:
            SpcOcapService.save_ocap(event.id, actor.id, {
                "owner_id": invalid_owner.id, "status": "open",
            })

        assert exc.value.code == "SPC_OCAP_OWNER_NOT_ASSIGNABLE"
        assert SpcOcap.query.filter_by(event_id=event.id).first() is None
        assert AuditLog.query.filter_by(module="spc_ocap").count() == 0


def test_unchanged_historical_owner_does_not_block_other_edits(app, db_session):
    with app.app_context():
        actor = _actor(db_session)
        historical_owner = _user(
            db_session, "historical-owner", actor.role, active=True
        )
        _, version, limit = _study_limit(db_session, actor)
        event = SpcOcapService.sync_events(limit.id, version.id, [{
            "chart_kind": "variation", "rule_code": "beyond_limits",
            "point_index": 2, "observed_value": 0.6,
        }])[0]
        created = SpcOcapService.save_ocap(event.id, actor.id, {
            "owner_id": historical_owner.id, "status": "open",
        })
        historical_owner.is_active = False
        db_session.commit()

        updated = SpcOcapService.save_ocap(event.id, actor.id, {
            "owner_id": historical_owner.id,
            "process_adjustment": "調整壓力參數",
            "status": "open",
        })

        assert updated.id == created.id
        assert updated.owner_id == historical_owner.id
        assert updated.process_adjustment == "調整壓力參數"


def test_existing_owner_cannot_change_to_disabled_user_without_audit(
    app, db_session
):
    with app.app_context():
        actor = _actor(db_session)
        disabled_owner = _user(
            db_session, "disabled-owner", actor.role, active=False
        )
        _, version, limit = _study_limit(db_session, actor)
        event = SpcOcapService.sync_events(limit.id, version.id, [{
            "chart_kind": "variation", "rule_code": "beyond_limits",
            "point_index": 3, "observed_value": 0.7,
        }])[0]
        created = SpcOcapService.save_ocap(event.id, actor.id, {
            "owner_id": actor.id,
            "process_adjustment": "原調整內容",
            "status": "open",
        })
        original_log_count = AuditLog.query.filter_by(module="spc_ocap").count()

        with pytest.raises(SpcValidationError) as exc:
            SpcOcapService.save_ocap(event.id, actor.id, {
                "owner_id": disabled_owner.id,
                "process_adjustment": "不應儲存的內容",
                "status": "open",
            })

        db_session.expire_all()
        persisted = db_session.get(SpcOcap, created.id)
        assert exc.value.code == "SPC_OCAP_OWNER_NOT_ASSIGNABLE"
        assert persisted.owner_id == actor.id
        assert persisted.process_adjustment == "原調整內容"
        assert AuditLog.query.filter_by(module="spc_ocap").count() == original_log_count


def test_ongoing_event_sync_is_idempotent_and_ocap_keeps_full_record(
    app, db_session
):
    with app.app_context():
        actor = _actor(db_session)
        _, version, limit = _study_limit(db_session, actor)
        violations = [{
            "chart_kind": "variation", "rule_code": "beyond_limits",
            "point_index": 4, "observed_value": 0.52,
        }]

        first = SpcOcapService.sync_events(limit.id, version.id, violations)
        second = SpcOcapService.sync_events(limit.id, version.id, violations)

        assert first[0].id == second[0].id
        assert SpcEvent.query.count() == 1

        ocap = SpcOcapService.save_ocap(first[0].id, actor.id, {
            "investigation_6m": {"machine": ["模具磨耗"], "method": ["換模延遲"]},
            "remeasurement": {"values": [10.01, 10.02], "result": "確認異常"},
            "process_adjustment": "更換模具並重新設定參數",
            "product_disposition": "隔離並全檢",
            "owner_id": actor.id,
            "effectiveness": "連續五組恢復穩定",
            "status": "closed",
        })

        assert ocap.event_id == first[0].id
        assert ocap.investigation_6m["machine"] == ["模具磨耗"]
        assert ocap.remeasurement["result"] == "確認異常"
        assert ocap.process_adjustment == "更換模具並重新設定參數"
        assert ocap.product_disposition == "隔離並全檢"
        assert ocap.owner_id == actor.id
        assert ocap.effectiveness == "連續五組恢復穩定"
        assert first[0].status == "closed"

        SpcOcapService.save_ocap(first[0].id, actor.id, {
            "process_adjustment": "更換模具並調整壓力參數",
            "effectiveness": "後續十組均維持穩定",
            "status": "closed",
        })
        ocap_logs = AuditLog.query.filter_by(module="spc_ocap").order_by(
            AuditLog.id
        ).all()
        assert ocap_logs[-1].old_value["process_adjustment"] == "更換模具並重新設定參數"
        assert ocap_logs[-1].new_value["process_adjustment"] == "更換模具並調整壓力參數"
        assert ocap_logs[-1].old_value["investigation_6m"] == {
            "machine": ["模具磨耗"], "method": ["換模延遲"]
        }
        assert ocap_logs[-1].new_value["effectiveness"] == "後續十組均維持穩定"


def test_retrospective_study_does_not_open_formal_event(app, db_session):
    with app.app_context():
        actor = _actor(db_session)
        _, version, limit = _study_limit(db_session, actor, study_type="retrospective")

        events = SpcOcapService.sync_events(limit.id, version.id, [{
            "chart_kind": "location", "rule_code": "trend_6",
            "point_index": 8, "observed_value": 10.8,
        }])

        assert events == []
        assert SpcEvent.query.count() == 0


def test_shipping_exclusion_restore_is_audited_and_changes_only_future_hash(
    app, db_session
):
    with app.app_context():
        actor = _actor(db_session)
        record = ShippingData(
            date=date(2026, 7, 1), material="6061", spec="10*1*100", group_count=2,
        )
        db_session.add(record)
        db_session.flush()
        measurement = ShippingMeasurement(
            shipping_id=record.id, group_num=1, item="外徑", position="",
            value_min=9.9, value_max=10.1, lower_limit=9.5, upper_limit=10.5,
        )
        db_session.add(measurement)
        db_session.commit()
        filters = {"field": "外徑", "material": "6061", "spec": "10*1*100"}
        before = build_shipping_study_input(filters)
        frozen_sample = SpcStudySample(
            version_id=_study_limit(db_session, actor)[1].id,
            source_record_type="ShippingMeasurement",
            source_record_id=record.id, source_measurement_id=measurement.id,
            source_record_ids=[record.id], source_measurement_ids=[measurement.id],
            subgroup_key="frozen", subgroup_order=0, values=[10.0], excluded=False,
            exclusion_snapshot=[{
                "measurement_id": measurement.id, "excluded": False, "reason": None,
            }],
        )
        db_session.add(frozen_sample)
        db_session.commit()

        ShippingService.set_measurement_exclusion(
            measurement.id, True, "量具滑動", actor_id=actor.id
        )
        excluded_hash = build_shipping_study_input(filters).data_hash
        ShippingService.set_measurement_exclusion(
            measurement.id, False, "重測確認原值有效", actor_id=actor.id
        )

        logs = AuditLog.query.filter_by(
            module="shipping_measurement", record_id=measurement.id
        ).order_by(AuditLog.id).all()
        assert [row.action for row in logs] == ["exclude", "restore"]
        assert logs[0].new_value["excluded"] is True
        assert logs[1].old_value["reason"] == "量具滑動"
        assert excluded_hash != before.data_hash
        assert frozen_sample.values == [10.0]
        assert frozen_sample.exclusion_snapshot[0]["excluded"] is False


def test_patrol_restore_requires_reason_and_keeps_both_audit_entries(app, db_session):
    with app.app_context():
        actor = _actor(db_session)
        main = PatrolMain(date=date(2026, 7, 1), material="6061", spec="10*1*100")
        db_session.add(main)
        db_session.flush()
        detail = PatrolDetail(
            main_id=main.id, group=1, item="外徑", position="前段",
            min_val=9.9, max_val=10.1,
        )
        db_session.add(detail)
        db_session.commit()

        PatrolService.set_patrol_detail_exclusion(
            detail.id, True, "治具鬆動", actor_id=actor.id
        )
        with pytest.raises(ValueError, match="恢復"):
            PatrolService.set_patrol_detail_exclusion(
                detail.id, False, "", actor_id=actor.id
            )
        PatrolService.set_patrol_detail_exclusion(
            detail.id, False, "重測與治具確認完成", actor_id=actor.id
        )

        logs = AuditLog.query.filter_by(
            module="patrol_detail", record_id=detail.id
        ).order_by(AuditLog.id).all()
        assert [row.action for row in logs] == ["exclude", "restore"]
        assert logs[0].user_id == actor.id
        assert logs[1].new_value["excluded"] is False
