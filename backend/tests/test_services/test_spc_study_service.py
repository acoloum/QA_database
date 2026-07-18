"""SPC 研究分析與核准生命週期測試。"""

from datetime import date

import pytest

import backend.services.spc_study_service as spc_study_module
from backend.models import (
    AuditLog,
    Role,
    SpcEvent,
    SpcLimitVersion,
    SpcStudy,
    SpcStudyVersion,
    User,
)
from backend.services.spc_contracts import SpcStudyInput, SpcSubgroup
from backend.services.spc_errors import SpcConflict, SpcForbidden, SpcValidationError
from backend.services.spc_study_service import ADAPTERS, SpcStudyService, _calculate_results


def _role(db_session, code, permissions):
    role = Role(code=code, name=code, permissions=permissions)
    db_session.add(role)
    db_session.flush()
    return role


def _user(db_session, username, role):
    user = User(username=username, password="hashed", role=role)
    db_session.add(user)
    db_session.flush()
    return user


def _input(data_hash="a" * 64, shift=0.0):
    subgroups = tuple(
        SpcSubgroup(
            key=f"shipping:{index}", timestamp=date(2026, 7, index + 1),
            values=(9.8 + shift + index * 0.01, 10.2 + shift + index * 0.01),
            record_ids=(index + 1,), measurement_ids=(100 + index,),
            exclusion_snapshot=({
                "measurement_id": 100 + index, "excluded": False, "reason": None,
            },),
        )
        for index in range(5)
    )
    return SpcStudyInput(
        source="shipping", filters={
            "vendor": "甲", "material": "6061", "spec": "10*1*100",
            "field": "外徑", "start_date": "", "end_date": "",
        },
        process_stream_key="stream-a", characteristic="外徑",
        subgroups=subgroups,
        specification={"found": True, "LSL": 9.5, "USL": 10.5},
        data_hash=data_hash,
    )


def _constant_input(data_hash="d" * 64, value=12.0):
    result = _input(data_hash)
    return SpcStudyInput(
        source=result.source,
        filters=result.filters,
        process_stream_key=result.process_stream_key,
        characteristic=result.characteristic,
        subgroups=tuple(
            SpcSubgroup(
                key=group.key,
                timestamp=group.timestamp,
                values=(value, value),
                record_ids=group.record_ids,
                measurement_ids=group.measurement_ids,
                exclusion_snapshot=group.exclusion_snapshot,
            )
            for group in result.subgroups
        ),
        specification=result.specification,
        data_hash=data_hash,
    )


def _approvable_results(study_input):
    results = _calculate_results(study_input)
    results["time_model_result"] = {
        "candidate": "A1", "model": "A1", "confirmed": True,
        "statistically_controlled": True,
    }
    results["stability_result"] = {
        "evaluated": True, "stable": True,
        "location": {"stable": True, "violations": []},
        "variation": {"stable": True, "violations": []},
    }
    results["applicability_result"] = {
        "applicable": True, "chart_type": "xbar_r"
    }
    return results


def test_analyze_adds_immutable_version_and_keeps_full_sample_trace(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        manager = _user(db_session, "manager", "qa_supervisor")
        inputs = iter((_input(), _input("b" * 64, shift=0.1)))
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(inputs))

        first = SpcStudyService.analyze("shipping", {"field": "外徑"}, manager.id)
        original_chart = dict(first.chart_result)
        second = SpcStudyService.analyze("shipping", {"field": "外徑"}, manager.id)

        assert first.study_id == second.study_id
        assert (first.version_no, second.version_no) == (1, 2)
        assert first.chart_result == original_chart
        assert first.data_hash == "a" * 64
        assert second.data_hash == "b" * 64
        assert len(first.samples) == 5
        assert first.samples[0].source_record_ids == [1]
        assert first.samples[0].source_measurement_ids == [100]
        assert first.samples[0].exclusion_snapshot[0]["excluded"] is False


def test_submit_rejects_changed_source_data(app, db_session, monkeypatch):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        manager = _user(db_session, "manager-conflict", "qa_supervisor")
        inputs = iter((_input(), _input("c" * 64)))
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(inputs))
        version = SpcStudyService.analyze("shipping", {}, manager.id)

        with pytest.raises(SpcConflict) as exc:
            SpcStudyService.submit(version.id, manager.id, reason="建立基準")

        assert exc.value.code == "STUDY_DATA_CHANGED"
        assert db_session.get(SpcStudyVersion, version.id).status == "draft"


def test_submit_approve_and_activate_writes_audit_and_limit(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        _role(db_session, "qc_manager", {"spc.approve": True})
        manager = _user(db_session, "manager-flow", "qa_supervisor")
        approver = _user(db_session, "approver-flow", "qc_manager")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())
        monkeypatch.setattr(spc_study_module, "_calculate_results", _approvable_results)
        version = SpcStudyService.analyze("shipping", {}, manager.id)

        submitted = SpcStudyService.submit(version.id, manager.id, reason="建立正式基準")
        active_limit = SpcStudyService.approve_and_activate(
            submitted.id, approver.id, reason="證據符合 A1 模型"
        )

        assert submitted.status == "active"
        assert submitted.study.status == "active"
        assert active_limit.status == "active"
        assert active_limit.approved_by == approver.id
        assert active_limit.limits["location"]["ucl"]
        actions = [row.action for row in AuditLog.query.filter_by(module="spc_study").all()]
        assert actions == ["analyze", "submit", "approve_activate"]


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda results: results.update(time_model_result={
            **results["time_model_result"], "confirmed": False,
        }),
         "TIME_MODEL_UNCONFIRMED"),
        (lambda results: results.update(stability_result={
                **results["stability_result"],
                "variation": {
                    **results["stability_result"]["variation"], "stable": False,
                },
            }),
         "PROCESS_UNSTABLE"),
        (lambda results: results.update(applicability_result={"applicable": False}),
         "CHART_NOT_APPLICABLE"),
        (lambda results: results.update(audit_incomplete=True),
         "AUDIT_INCOMPLETE"),
    ],
)
def test_approval_gate_rejects_unqualified_study(
    app, db_session, monkeypatch, mutation, expected_code
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        _role(db_session, "qc_manager", {"spc.approve": True})
        manager = _user(db_session, f"manager-{expected_code}", "qa_supervisor")
        approver = _user(db_session, f"approver-{expected_code}", "qc_manager")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())
        def gated_results(study_input):
            results = _approvable_results(study_input)
            mutation(results)
            return results
        monkeypatch.setattr(spc_study_module, "_calculate_results", gated_results)
        version = SpcStudyService.analyze("shipping", {}, manager.id)
        SpcStudyService.submit(version.id, manager.id, reason="送審")

        with pytest.raises(SpcValidationError) as exc:
            SpcStudyService.approve_and_activate(version.id, approver.id, reason="核准")

        assert exc.value.code == expected_code
        assert SpcLimitVersion.query.count() == 0


def test_manage_permission_cannot_approve(app, db_session, monkeypatch):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        manager = _user(db_session, "manager-only", "qa_supervisor")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())
        monkeypatch.setattr(spc_study_module, "_calculate_results", _approvable_results)
        version = SpcStudyService.analyze("shipping", {}, manager.id)
        SpcStudyService.submit(version.id, manager.id, reason="送審")

        with pytest.raises(SpcForbidden) as exc:
            SpcStudyService.approve_and_activate(version.id, manager.id, reason="自行核准")

        assert exc.value.code == "SPC_APPROVE_FORBIDDEN"


def test_confirm_time_model_recomputes_capability_indices(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        manager = _user(db_session, "manager-confirm-model", "qa_supervisor")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())
        def confirmable_results(study_input):
            results = _approvable_results(study_input)
            results["time_model_result"] = {
                "candidate": "A1", "confirmed": False,
                "statistically_controlled": True,
            }
            results["distribution_result"] = {
                "model": "normal", "label": "常態分布", "params": (10.02, 0.15),
                "accepted": True, "normal_ok": True, "unimodal": True,
                "reason_code": None, "candidates": [], "fit_method": "validated_test",
                "alpha": 0.05,
            }
            return results
        monkeypatch.setattr(spc_study_module, "_calculate_results", confirmable_results)
        version = SpcStudyService.analyze("shipping", {}, manager.id)

        confirmed = SpcStudyService.confirm_time_model(
            version.id, manager.id, model="A1", reason="工程與統計證據一致"
        )

        assert confirmed.id != version.id
        assert confirmed.version_no == 2
        assert db_session.get(SpcStudyVersion, version.id).time_model_result["confirmed"] is False
        assert len(confirmed.samples) == len(version.samples)
        assert confirmed.capability_result["cpk"] is not None
        assert confirmed.capability_result["time_model"]["confirmed"] is True
        assert confirmed.capability_result["applicable"] == "capability"


def test_ongoing_analysis_uses_active_limits_and_creates_formal_events(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True, "spc.view": True})
        manager = _user(db_session, "manager-ongoing", "qa_supervisor")
        inputs = iter((
            _input(),
            _input("b" * 64, shift=2.0),
            _input("b" * 64, shift=2.0),
        ))
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(inputs))

        baseline = SpcStudyService.analyze("shipping", {}, manager.id)
        limit = SpcLimitVersion(
            study_version_id=baseline.id,
            process_stream_key=baseline.study.process_stream_key,
            characteristic=baseline.study.characteristic,
            revision=1,
            chart_type="xbar_r",
            limits={
                "location": {"cl": [10.0] * 5, "ucl": [10.6] * 5, "lcl": [9.4] * 5},
                "variation": {"cl": [0.4] * 5, "ucl": [1.2] * 5, "lcl": [0.0] * 5},
                "subgroup_sizes": [2] * 5,
            },
            status="active",
            created_by=manager.id,
            approved_by=manager.id,
        )
        db_session.add(limit)
        db_session.commit()

        ongoing = SpcStudyService.analyze(
            "shipping", {}, manager.id, study_type="ongoing"
        )

        assert ongoing.study.study_type == "ongoing"
        assert ongoing.status == "active"
        assert ongoing.study.status == "active"
        assert ongoing.chart_result["location"]["cl"] == [10.0] * 5
        assert ongoing.chart_result["location"]["ucl"] == [10.6] * 5
        assert ongoing.stability_result["location"]["stable"] is False
        assert SpcEvent.query.filter_by(
            limit_version_id=limit.id, study_version_id=ongoing.id
        ).count() >= 1
        assert all(event.sample_id is not None for event in SpcEvent.query.all())

        first_event_count = SpcEvent.query.count()
        SpcStudyService.analyze("shipping", {}, manager.id, study_type="ongoing")
        assert SpcEvent.query.count() == first_event_count


def test_ongoing_analysis_preserves_approved_rules_and_accepts_zero_variation(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True, "spc.view": True})
        manager = _user(db_session, "manager-rules", "qa_supervisor")
        inputs = iter((_input(), _constant_input()))
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(inputs))

        def baseline_results(study_input):
            results = _calculate_results(study_input)
            results["stability_result"]["rules_used"] = ["beyond_limits"]
            results["stability_result"]["location"]["rules_used"] = ["beyond_limits"]
            results["stability_result"]["variation"]["rules_used"] = ["beyond_limits"]
            return results

        monkeypatch.setattr(spc_study_module, "_calculate_results", baseline_results)

        baseline = SpcStudyService.analyze("shipping", {}, manager.id)
        limit = SpcLimitVersion(
            study_version_id=baseline.id,
            process_stream_key=baseline.study.process_stream_key,
            characteristic=baseline.study.characteristic,
            revision=1,
            chart_type="xbar_r",
            limits={
                "location": {"cl": [10.0] * 5, "ucl": [10.6] * 5, "lcl": [9.4] * 5},
                "variation": {"cl": [0.4] * 5, "ucl": [1.2] * 5, "lcl": [0.1] * 5},
                "subgroup_sizes": [2] * 5,
            },
            status="active",
            created_by=manager.id,
            approved_by=manager.id,
        )
        db_session.add(limit)
        db_session.commit()

        ongoing = SpcStudyService.analyze(
            "shipping", {}, manager.id, study_type="ongoing"
        )

        assert ongoing.chart_result["variation"]["values"] == [0.0] * 5
        assert ongoing.stability_result["rules_used"] == ["beyond_limits"]
        assert ongoing.stability_result["variation"]["rules_used"] == ["beyond_limits"]


def test_ongoing_analysis_rolls_back_events_when_audit_write_fails(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True, "spc.view": True})
        manager = _user(db_session, "manager-atomic", "qa_supervisor")
        inputs = iter((_input(), _input("e" * 64, shift=2.0)))
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(inputs))
        baseline = SpcStudyService.analyze("shipping", {}, manager.id)
        limit = SpcLimitVersion(
            study_version_id=baseline.id,
            process_stream_key=baseline.study.process_stream_key,
            characteristic=baseline.study.characteristic,
            revision=1,
            chart_type="xbar_r",
            limits={
                "location": {"cl": [10.0] * 5, "ucl": [10.6] * 5, "lcl": [9.4] * 5},
                "variation": {"cl": [0.4] * 5, "ucl": [1.2] * 5, "lcl": [0.0] * 5},
                "subgroup_sizes": [2] * 5,
            },
            status="active",
            created_by=manager.id,
            approved_by=manager.id,
        )
        db_session.add(limit)
        db_session.commit()
        version_count = SpcStudyVersion.query.count()

        monkeypatch.setattr(
            spc_study_module, "log_audit",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit failed")),
        )
        with pytest.raises(RuntimeError, match="audit failed"):
            SpcStudyService.analyze("shipping", {}, manager.id, study_type="ongoing")
        db_session.rollback()

        assert SpcStudyVersion.query.count() == version_count
        assert SpcEvent.query.count() == 0
        assert SpcStudy.query.filter_by(study_type="ongoing").count() == 0
