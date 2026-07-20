"""SPC 研究分析與核准生命週期測試。"""

from datetime import date, datetime, timedelta, timezone

import pytest
import numpy as np
from scipy import stats as scipy_stats

import backend.services.spc_study_service as spc_study_module
from backend.models import (
    AuditLog,
    Role,
    ShippingData,
    ShippingMeasurement,
    SpcEvent,
    SpcLimitVersion,
    SPCCache,
    SpcStudy,
    SpcStudyVersion,
    User,
)
from backend.services.spc_contracts import SpcStudyInput, SpcSubgroup
from backend.services.spc_adapters.common import calculate_study_data_hash
from backend.services.spc_errors import (
    SpcConflict, SpcForbidden, SpcServiceError, SpcValidationError,
)
from backend.services.spc_study_service import (
    ADAPTERS,
    SpcStudyService,
    _calculate_results,
    _transformed_specification,
    _upsert_preview_cache,
)
from backend.services.spc_transformations import evaluate_transformations, transform_values
from backend.routes.spc_studies import serialize_event


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


@pytest.fixture
def spc_view_user(db_session):
    _role(db_session, "spc_viewer", {"spc.view": True})
    return _user(db_session, "spc-view-user", "spc_viewer")


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


def test_variable_calculation_passes_formal_stability_into_time_diagnostic(
    monkeypatch,
):
    captured = {}

    def diagnostic(_chart, _groups, _distribution, *, stability):
        captured["stability"] = stability
        return {
            "candidate": None,
            "confirmed": False,
            "reason_code": "TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT",
        }

    monkeypatch.setattr(spc_study_module, "diagnose_time_model", diagnostic)

    results = _calculate_results(_input())

    assert captured["stability"] is results["stability_result"]
    assert captured["stability"]["rules_used"] == [
        "beyond_limits", "run_9_same_side", "trend_6",
    ]


def test_analyze_rejects_unknown_analysis_family(app, db_session, spc_view_user):
    with pytest.raises(SpcValidationError) as error:
        SpcStudyService.analyze(
            "shipping", {}, spc_view_user.id, analysis_family="unknown"
        )

    assert error.value.code == "SPC_ANALYSIS_FAMILY_INVALID"


@pytest.mark.parametrize("analysis_family", [[], {}, 7])
def test_analyze_rejects_non_string_analysis_family(
    app, db_session, spc_view_user, analysis_family
):
    with pytest.raises(SpcValidationError) as error:
        SpcStudyService.analyze(
            "shipping", {}, spc_view_user.id, analysis_family=analysis_family
        )

    assert error.value.code == "SPC_ANALYSIS_FAMILY_INVALID"


@pytest.mark.parametrize("analysis_family", ["machine"])
def test_machine_analysis_rejects_non_patrol_source(
    app, db_session, spc_view_user, analysis_family
):
    with pytest.raises(SpcValidationError) as error:
        SpcStudyService.analyze(
            "shipping", {}, spc_view_user.id, analysis_family=analysis_family
        )

    assert error.value.code == "MACHINE_SOURCE_UNSUPPORTED"


def test_analyze_snapshots_options_and_includes_them_in_hash(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "spc_options_manager", {"spc.view": True, "spc.manage": True})
        manager = _user(db_session, "spc-options-manager", "spc_options_manager")
        source_rows = [{"id": 1, "value": 10.0}]
        specification = {"found": True, "LSL": 9.5, "USL": 10.5}
        options = {"subgroup": {"size": 5}, "rule_set": ["beyond_limits"]}

        def adapter(
            _filters, *, analysis_family, options, input_contract_version
        ):
            return SpcStudyInput(
                source="shipping",
                filters={"field": "外徑"},
                process_stream_key="options-stream",
                characteristic="外徑",
                subgroups=_input().subgroups,
                specification=specification,
                analysis_family=analysis_family,
                options=options,
                data_hash=calculate_study_data_hash(
                    source="shipping",
                    filters={"field": "外徑"},
                    source_rows=source_rows,
                    specification=specification,
                    analysis_family=analysis_family,
                    options=options,
                    input_contract_version=input_contract_version,
                ),
            )

        monkeypatch.setitem(ADAPTERS, "shipping", adapter)
        version = SpcStudyService.analyze(
            "shipping", {"field": "外徑"}, manager.id, options=options
        )

        assert version.analysis_options == options
        assert version.study.filters == {"field": "外徑"}
        assert version.data_hash == calculate_study_data_hash(
            source="shipping",
            filters={"field": "外徑"},
            source_rows=source_rows,
            specification=specification,
            analysis_family="variable",
            options=options,
            input_contract_version="2026.2",
        )

        with pytest.raises(SpcValidationError) as unconfirmed:
            SpcStudyService.submit(version.id, manager.id, reason="選項已確認")
        assert unconfirmed.value.code == "TIME_MODEL_UNCONFIRMED"
        assert version.status == "draft"


def test_legacy_2026_1_version_can_submit_and_approve_with_historical_hash(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "legacy_manager", {"spc.view": True, "spc.manage": True})
        _role(db_session, "legacy_approver", {"spc.approve": True})
        manager = _user(db_session, "legacy-hash-manager", "legacy_manager")
        approver = _user(db_session, "legacy-hash-approver", "legacy_approver")
        source_rows = [{"id": 1, "value": 10.0}]
        specification = {"found": True, "LSL": 9.5, "USL": 10.5}
        legacy_hash = calculate_study_data_hash(
            source="shipping",
            filters={"field": "外徑"},
            source_rows=source_rows,
            specification=specification,
            input_contract_version="2026.1",
        )
        calls = []

        def adapter(
            _filters, *, analysis_family, options, input_contract_version
        ):
            calls.append((analysis_family, options, input_contract_version))
            return SpcStudyInput(
                source="shipping",
                filters={"field": "外徑"},
                process_stream_key="legacy-hash-stream",
                characteristic="外徑",
                subgroups=_input().subgroups,
                specification=specification,
                analysis_family=analysis_family,
                options=options,
                data_hash=calculate_study_data_hash(
                    source="shipping",
                    filters={"field": "外徑"},
                    source_rows=source_rows,
                    specification=specification,
                    analysis_family=analysis_family,
                    options=options,
                    input_contract_version=input_contract_version,
                ),
            )

        monkeypatch.setitem(ADAPTERS, "shipping", adapter)
        study = SpcStudy(
            source="shipping",
            study_type="retrospective",
            analysis_family="variable",
            process_stream_key="legacy-hash-stream",
            characteristic="外徑",
            filters={"field": "外徑"},
            status="draft",
            created_by=manager.id,
        )
        results = _approvable_results(_input())
        version = SpcStudyVersion(
            study=study,
            version_no=1,
            method_version="2026.1",
            data_hash=legacy_hash,
            specification_snapshot=specification,
            status="draft",
            created_by=manager.id,
            **results,
        )
        db_session.add(version)
        db_session.commit()

        submitted = SpcStudyService.submit(version.id, manager.id, reason="保留舊版證據")
        limit = SpcStudyService.approve_and_activate(
            submitted.id, approver.id, reason="舊版雜湊一致"
        )

        assert calls == [("variable", {}, "2026.1"), ("variable", {}, "2026.1")]
        assert limit.analysis_family == "variable"


@pytest.mark.parametrize(
    ("action", "model"),
    [("time_model", "A1"), ("transformation", "johnson_su")],
)
def test_legacy_2026_1_decision_endpoints_cannot_create_successor(
    app, db_session, action, model
):
    with app.app_context():
        role = f"legacy_{action}_approver"
        _role(db_session, role, {"spc.approve": True})
        approver = _user(db_session, f"legacy-{action}-approver", role)
        study = SpcStudy(
            source="shipping", study_type="retrospective",
            analysis_family="variable", process_stream_key=f"legacy-{action}",
            characteristic="外徑", filters={}, status="draft",
            created_by=approver.id,
        )
        version = SpcStudyVersion(
            study=study, version_no=1, method_version="2026.1",
            data_hash="1" * 64, analysis_options={},
            specification_snapshot={"found": True, "LSL": 9.5, "USL": 10.5},
            chart_result={}, stability_result={}, capability_result={},
            applicability_result={}, status="draft", created_by=approver.id,
            time_model_result={
                "candidate": "A1", "confirmed": False,
                "statistically_controlled": True,
            },
            distribution_result={
                "transformation_candidates": [{
                    "model": "johnson_su", "accepted": True,
                    "params": {}, "reason_code": None,
                }],
            },
        )
        db_session.add(version)
        db_session.commit()

        with pytest.raises(SpcServiceError) as read_only:
            if action == "time_model":
                SpcStudyService.confirm_time_model(
                    version.id, approver.id, model=model, reason="舊版不可重算"
                )
            else:
                SpcStudyService.confirm_transformation(
                    version.id, approver.id, model=model, reason="舊版不可重算"
                )

        assert read_only.value.code == "SPC_METHOD_VERSION_READ_ONLY"
        assert read_only.value.status_code == 400
        assert version.status == "draft"
        assert SpcStudyVersion.query.filter_by(study_id=study.id).count() == 1


@pytest.mark.parametrize(
    ("action", "model", "reason"),
    [
        ("time_model", "A1", "短"),
        ("time_model", "A1", "甲" * 501),
        ("transformation", "johnson_su", "短"),
        ("transformation", "johnson_su", "甲" * 501),
    ],
)
def test_decision_endpoint_reason_must_be_between_2_and_500_characters(
    app, db_session, action, model, reason
):
    with app.app_context():
        role = f"reason_{action}"
        _role(db_session, role, {"spc.approve": True})
        approver = _user(db_session, f"reason-{action}-{len(reason)}", role)
        study = SpcStudy(
            source="shipping", study_type="retrospective",
            analysis_family="variable", process_stream_key=f"reason-{action}-{len(reason)}",
            characteristic="外徑", filters={}, status="draft",
            created_by=approver.id,
        )
        version = SpcStudyVersion(
            study=study, version_no=1, method_version="2026.2",
            data_hash="2" * 64, analysis_options={}, specification_snapshot={},
            chart_result={}, stability_result={}, distribution_result={},
            capability_result={}, applicability_result={}, status="draft",
            created_by=approver.id,
            time_model_result={"candidate": "A1", "confirmed": False},
        )
        db_session.add(version)
        db_session.commit()

        with pytest.raises(SpcValidationError) as invalid_reason:
            if action == "time_model":
                SpcStudyService.confirm_time_model(
                    version.id, approver.id, model=model, reason=reason
                )
            else:
                SpcStudyService.confirm_transformation(
                    version.id, approver.id, model=model, reason=reason
                )

        assert invalid_reason.value.code == "REASON_LENGTH_INVALID"
        assert version.status == "draft"


def test_preview_cache_upsert_updates_existing_key_atomically(app, db_session):
    with app.app_context():
        first_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        second_expiry = first_expiry + timedelta(minutes=10)

        _upsert_preview_cache("same-key", {"revision": 1}, first_expiry)
        _upsert_preview_cache("same-key", {"revision": 2}, second_expiry)
        db_session.commit()

        rows = SPCCache.query.filter_by(cache_key="same-key").all()
        assert len(rows) == 1
        assert rows[0].result == {"revision": 2}
        assert rows[0].expires_at.replace(tzinfo=timezone.utc) == second_expiry


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
        _role(db_session, "qa_supervisor", {"spc.manage": True, "spc.approve": True})
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
        assert confirmed.time_model_result["system_candidate"] == "A1"
        assert confirmed.time_model_result["overridden"] is False
        assert confirmed.time_model_result["confirmation_reason"] == "工程與統計證據一致"
        assert len(confirmed.samples) == len(version.samples)
        assert confirmed.capability_result["cpk"] is not None
        assert confirmed.capability_result["time_model"]["confirmed"] is True
        assert confirmed.capability_result["applicable"] == "capability"

        submitted = SpcStudyService.submit(
            confirmed.id, manager.id, reason="送交生產基準核准"
        )
        limit = SpcStudyService.approve_and_activate(
            submitted.id, manager.id, reason="A1 證據符合生產基準"
        )
        assert limit.status == "active"
        assert limit.study_version_id == confirmed.id


def test_bc_d_confirmation_requires_approve_reason_and_preserves_successor(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True})
        _role(db_session, "qc_manager", {"spc.approve": True})
        manager = _user(db_session, "manager-bcd", "qa_supervisor")
        approver = _user(db_session, "approver-bcd", "qc_manager")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())

        def b_candidate(study_input):
            results = _approvable_results(study_input)
            results["time_model_result"] = {"candidate": "B", "confirmed": False, "diagnostic_version": "2026.2", "reason_code": None}
            return results

        monkeypatch.setattr(spc_study_module, "_calculate_results", b_candidate)
        original = SpcStudyService.analyze("shipping", {}, manager.id)
        snapshot = dict(original.time_model_result)
        with pytest.raises(SpcForbidden) as forbidden:
            SpcStudyService.confirm_time_model(original.id, manager.id, model="B", reason="變異證據")
        assert forbidden.value.code == "SPC_APPROVE_FORBIDDEN"
        with pytest.raises(SpcValidationError) as missing_reason:
            SpcStudyService.confirm_time_model(original.id, approver.id, model="B", reason=" ")
        assert missing_reason.value.code == "REASON_REQUIRED"

        confirmed = SpcStudyService.confirm_time_model(original.id, approver.id, model="C4", reason="已核對批次切換紀錄")
        assert original.time_model_result == snapshot
        assert original.status == "superseded"
        assert confirmed.time_model_result["system_candidate"] == "B"
        assert confirmed.time_model_result["overridden"] is True
        assert confirmed.time_model_result["model"] == "C4"
        assert confirmed.time_model_result["confirmation_reason"] == "已核對批次切換紀錄"
        assert confirmed.time_model_result["confirmed_by"] == approver.id
        assert confirmed.time_model_result["confirmed_at"]
        assert confirmed.data_hash == original.data_hash
        assert confirmed.method_version == original.method_version
        assert confirmed.code_version == original.code_version
        assert confirmed.analysis_options == original.analysis_options
        assert confirmed.specification_snapshot == original.specification_snapshot
        assert confirmed.chart_result == original.chart_result
        assert confirmed.stability_result == original.stability_result
        assert confirmed.distribution_result == original.distribution_result
        assert confirmed.applicability_result == original.applicability_result
        assert confirmed.capability_result["cpk"] is None
        assert confirmed.capability_result["cp"] is None
        assert len(confirmed.samples) == len(original.samples)
        assert [sample.source_record_ids for sample in confirmed.samples] == [
            sample.source_record_ids for sample in original.samples
        ]
        assert [sample.source_measurement_ids for sample in confirmed.samples] == [
            sample.source_measurement_ids for sample in original.samples
        ]
        assert [sample.exclusion_snapshot for sample in confirmed.samples] == [
            sample.exclusion_snapshot for sample in original.samples
        ]


def test_unconfirmed_c3_cannot_submit_then_confirmed_successor_can_approve_research(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "spc_workflow", {"spc.manage": True, "spc.approve": True})
        actor = _user(db_session, "c3-workflow", "spc_workflow")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())

        def c3_candidate(study_input):
            results = _approvable_results(study_input)
            results["time_model_result"] = {
                "candidate": "C3", "confirmed": False,
                "statistically_controlled": False,
                "diagnostic_version": "2026.2", "reason_code": None,
            }
            return results

        monkeypatch.setattr(spc_study_module, "_calculate_results", c3_candidate)
        draft = SpcStudyService.analyze("shipping", {}, actor.id)

        with pytest.raises(SpcValidationError) as unconfirmed:
            SpcStudyService.submit(draft.id, actor.id, reason="不可跳過時間確認")
        assert unconfirmed.value.code == "TIME_MODEL_UNCONFIRMED"
        assert draft.status == "draft"

        confirmed = SpcStudyService.confirm_time_model(
            draft.id, actor.id, model="C3", reason="已核對長期時間序列"
        )
        submitted = SpcStudyService.submit(
            confirmed.id, actor.id, reason="送交研究核准"
        )
        approved = SpcStudyService.approve_research(
            submitted.id, actor.id, reason="只核准研究證據"
        )

        assert approved.status == "approved"
        assert approved.time_model_result["confirmed"] is True
        assert approved.time_model_result["model"] == "C3"
        assert SpcLimitVersion.query.count() == 0


def test_insufficient_time_diagnostic_cannot_create_successor(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qc_manager", {"spc.approve": True})
        approver = _user(db_session, "insufficient-diagnostic", "qc_manager")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())

        def insufficient(study_input):
            results = _approvable_results(study_input)
            results["time_model_result"] = {
                "candidate": None,
                "confirmed": False,
                "diagnostic_version": "2026.2",
                "reason_code": "TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT",
                "evidence": {"subgroup_count": 24, "minimum_subgroups": 25},
            }
            return results

        monkeypatch.setattr(spc_study_module, "_calculate_results", insufficient)
        original = SpcStudyService.analyze("shipping", {}, approver.id)

        with pytest.raises(SpcValidationError) as error:
            SpcStudyService.confirm_time_model(
                original.id, approver.id, model="A1", reason="資料仍不足"
            )

        assert error.value.code == "TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT"
        assert original.status == "draft"
        assert SpcStudyVersion.query.filter_by(study_id=original.study_id).count() == 1


def test_reconfirming_same_original_returns_stable_conflict_and_one_successor(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "qc_manager", {"spc.approve": True})
        approver = _user(db_session, "time-model-cas", "qc_manager")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())

        def candidate(study_input):
            results = _approvable_results(study_input)
            results["time_model_result"] = {
                "candidate": "C1",
                "confirmed": False,
                "diagnostic_version": "2026.2",
                "reason_code": None,
                "evidence": {"source": "controlled"},
            }
            return results

        monkeypatch.setattr(spc_study_module, "_calculate_results", candidate)
        original = SpcStudyService.analyze("shipping", {}, approver.id)
        confirmed = SpcStudyService.confirm_time_model(
            original.id, approver.id, model="C1", reason="第一次確認"
        )

        with pytest.raises(SpcConflict) as conflict:
            SpcStudyService.confirm_time_model(
                original.id, approver.id, model="C2", reason="競態重試"
            )

        assert conflict.value.code == "SPC_TIME_MODEL_CONFIRM_CONFLICT"
        versions = SpcStudyVersion.query.filter_by(study_id=original.study_id).all()
        audits = AuditLog.query.filter_by(
            action="confirm_time_model", module="spc_study"
        ).all()
        assert {version.id for version in versions} == {original.id, confirmed.id}
        assert len(audits) == 1


def _transformation_input(
    data_hash="e" * 64,
    *,
    stream="transform-stream",
    specification=None,
    values=None,
    characteristic="外徑",
):
    probabilities = np.linspace(0.01, 0.99, 50)
    values = np.asarray(values) if values is not None else scipy_stats.lognorm.ppf(
        probabilities, 0.7, loc=0.0, scale=np.exp(1.0)
    )
    subgroups = tuple(
        SpcSubgroup(
            key=f"transform:{index}",
            timestamp=date(2026, 7, index + 1),
            values=(float(values[index * 2]), float(values[index * 2 + 1])),
            record_ids=(index + 1,),
            measurement_ids=(500 + index,),
        )
        for index in range(25)
    )
    return SpcStudyInput(
        source="shipping",
        filters={"field": "外徑"},
        process_stream_key=stream,
        characteristic=characteristic,
        subgroups=subgroups,
        specification=(specification or {"found": True, "LSL": 0.8, "USL": 12.0}),
        data_hash=data_hash,
    )


def test_confirm_transformation_creates_immutable_transformed_successor(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "transform_approver", {"spc.manage": True, "spc.approve": True})
        approver = _user(db_session, "transform-user", "transform_approver")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _transformation_input())
        original = SpcStudyService.analyze("shipping", {"field": "外徑"}, approver.id)
        original_samples = [list(sample.values) for sample in original.samples]
        original_chart = dict(original.chart_result)
        original_time_model = dict(original.time_model_result)

        successor = SpcStudyService.confirm_transformation(
            original.id,
            approver.id,
            model="johnson_sl",
            reason="原始尺度偏態，採用對數常態轉換",
        )

        assert original.status == "superseded"
        assert original.chart_result == original_chart
        assert successor.version_no == original.version_no + 1
        assert successor.data_hash == original.data_hash
        assert successor.analysis_options == original.analysis_options
        assert successor.specification_snapshot == original.specification_snapshot
        assert [sample.values for sample in successor.samples] == original_samples
        assert successor.chart_result["scale"] == "transformed"
        assert successor.capability_result["scale"] == "transformed"
        assert successor.capability_result["original_scale"]["quantiles"]
        assert successor.capability_result["original_scale"]["ppm"] == successor.capability_result["ppm"]
        assert successor.distribution_result["transformation_decision"]["model"] == "johnson_sl"
        assert successor.distribution_result["transformation_decision"]["confirmed_by"] == approver.id
        assert successor.distribution_result["transformation_decision"]["confirmation_reason"]
        assert successor.distribution_result["original_model"] == original.distribution_result["model"]
        assert successor.time_model_result == original_time_model


def test_transformation_requires_approve_accepted_candidate_reason_and_stable_conflict(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "transform_manager", {"spc.manage": True})
        _role(db_session, "transform_qc", {"spc.approve": True})
        manager = _user(db_session, "transform-manager", "transform_manager")
        approver = _user(db_session, "transform-approver", "transform_qc")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _transformation_input())
        original = SpcStudyService.analyze("shipping", {}, manager.id)

        with pytest.raises(SpcForbidden) as forbidden:
            SpcStudyService.confirm_transformation(
                original.id, manager.id, model="johnson_sl", reason="無權確認"
            )
        assert forbidden.value.code == "SPC_APPROVE_FORBIDDEN"
        with pytest.raises(SpcValidationError) as reason_error:
            SpcStudyService.confirm_transformation(
                original.id, approver.id, model="johnson_sl", reason=" "
            )
        assert reason_error.value.code == "REASON_REQUIRED"
        with pytest.raises(SpcValidationError) as candidate_error:
            SpcStudyService.confirm_transformation(
                original.id, approver.id, model="not-a-candidate", reason="測試"
            )
        assert candidate_error.value.code == "TRANSFORMATION_UNCONFIRMED"

        successor = SpcStudyService.confirm_transformation(
            original.id, approver.id, model="johnson_sl", reason="正式確認"
        )
        with pytest.raises(SpcConflict) as conflict:
            SpcStudyService.confirm_transformation(
                original.id, approver.id, model="johnson_sl", reason="競態重試"
            )
        assert conflict.value.code == "SPC_TRANSFORMATION_CONFIRM_CONFLICT"
        assert successor.status == "draft"


def test_transformation_and_time_confirmation_order_produces_same_scale_evidence(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "sequence_approver", {"spc.manage": True, "spc.approve": True})
        actor = _user(db_session, "sequence-user", "sequence_approver")

        def adapter(filters):
            return _transformation_input(
                stream=f"sequence-{filters['sequence']}",
                data_hash=("1" if filters["sequence"] == "transform-first" else "2") * 64,
            )

        monkeypatch.setitem(ADAPTERS, "shipping", adapter)
        transform_original = SpcStudyService.analyze(
            "shipping", {"sequence": "transform-first"}, actor.id
        )
        transformed = SpcStudyService.confirm_transformation(
            transform_original.id, actor.id, model="johnson_sl", reason="先確認轉換"
        )
        transform_then_time = SpcStudyService.confirm_time_model(
            transformed.id, actor.id, model="A2", reason="後確認原尺度時間模型"
        )

        time_original = SpcStudyService.analyze(
            "shipping", {"sequence": "time-first"}, actor.id
        )
        timed = SpcStudyService.confirm_time_model(
            time_original.id, actor.id, model="A2", reason="先確認原尺度時間模型"
        )
        time_then_transform = SpcStudyService.confirm_transformation(
            timed.id, actor.id, model="johnson_sl", reason="後確認轉換"
        )

        for key in ("pp", "ppk", "ppu", "ppl", "ppm"):
            assert transform_then_time.capability_result[key] == time_then_transform.capability_result[key]
        assert transform_then_time.capability_result["original_scale"] == time_then_transform.capability_result["original_scale"]
        assert transform_then_time.capability_result["transformed_specification"] == time_then_transform.capability_result["transformed_specification"]
        assert transform_then_time.distribution_result["transformation_decision"] == transformed.distribution_result["transformation_decision"]
        assert transform_then_time.chart_result["scale"] == "transformed"


def test_upper_only_boxcox_ignores_inapplicable_nonpositive_limits(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "boxcox_approver", {"spc.manage": True, "spc.approve": True})
        actor = _user(db_session, "boxcox-user", "boxcox_approver")
        values = np.power(0.25 * scipy_stats.norm.ppf(np.linspace(0.01, 0.99, 50)) + 2.0, 4.0)
        source = _transformation_input(
            stream="boxcox-upper",
            values=values,
            specification={
                "found": True,
                "one_sided": "upper",
                "USL": 80.0,
                "LSL": 0.0,
                "nominal": 0.0,
            },
        )
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: source)
        original = SpcStudyService.analyze("shipping", {}, actor.id)

        successor = SpcStudyService.confirm_transformation(
            original.id, actor.id, model="boxcox", reason="上限單側轉換"
        )

        transformed_spec = successor.capability_result["transformed_specification"]
        assert transformed_spec["USL"] is not None
        assert "LSL" not in transformed_spec
        assert "nominal" not in transformed_spec
        assert successor.specification_snapshot["LSL"] == 0.0


def test_transformed_specification_maps_only_applicable_sides():
    values = np.power(
        0.25 * scipy_stats.norm.ppf(np.linspace(0.01, 0.99, 50)) + 2.0,
        4.0,
    )
    candidate = next(
        item for item in evaluate_transformations(values)["candidates"]
        if item["model"] == "boxcox"
    )

    lower = _transformed_specification(
        {"one_sided": "lower", "LSL": 1.0, "USL": 0.0, "nominal": 0.0},
        candidate,
    )
    two_sided = _transformed_specification(
        {"LSL": 1.0, "USL": 80.0, "nominal": 0.0}, candidate
    )

    assert set(lower) & {"LSL", "USL", "nominal"} == {"LSL"}
    assert set(two_sided) & {"LSL", "USL", "nominal"} == {"LSL", "USL"}


def test_shape_characteristic_uses_normal_assessment_after_transformation(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "shape_transform_approver", {"spc.manage": True, "spc.approve": True})
        actor = _user(db_session, "shape-transform", "shape_transform_approver")
        source = _transformation_input(
            stream="shape-transform", characteristic="真圓度"
        )
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: source)
        original = SpcStudyService.analyze("shipping", {}, actor.id)

        successor = SpcStudyService.confirm_transformation(
            original.id, actor.id, model="johnson_sl", reason="形狀特性轉換"
        )

        assert successor.distribution_result["model"] == "normal"
        assert successor.distribution_result["original_characteristic"] == "真圓度"


def test_ongoing_uses_transformed_observations_and_preserves_raw_samples(
    app, db_session, monkeypatch
):
    with app.app_context():
        _role(db_session, "ongoing_transform_approver", {"spc.manage": True, "spc.approve": True})
        actor = _user(db_session, "ongoing-transform", "ongoing_transform_approver")
        baseline = _transformation_input(stream="ongoing-transform", data_hash="7" * 64)
        outlier_values = np.asarray([
            value for group in baseline.subgroups for value in group.values
        ])
        outlier_values[-2:] = [200.0, 220.0]
        ongoing = _transformation_input(
            stream="ongoing-transform", data_hash="8" * 64, values=outlier_values
        )
        inputs = iter((baseline, baseline, baseline, ongoing))
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(inputs))
        original = SpcStudyService.analyze("shipping", {}, actor.id)
        transformed = SpcStudyService.confirm_transformation(
            original.id, actor.id, model="johnson_sl", reason="採用轉換基準"
        )
        controlled = SpcStudyService.confirm_time_model(
            transformed.id, actor.id, model="A2", reason="確認原尺度時間模型"
        )
        monkeypatch.setattr(spc_study_module, "_assert_approvable", lambda _version: None)
        submitted = SpcStudyService.submit(controlled.id, actor.id, reason="送審轉換基準")
        limit = SpcStudyService.approve_and_activate(submitted.id, actor.id, reason="核准轉換基準")

        monitored = SpcStudyService.analyze(
            "shipping", {}, actor.id, study_type="ongoing"
        )

        decision = controlled.distribution_result["transformation_decision"]
        expected_last = float(np.mean(transform_values([200.0, 220.0], decision)))
        assert limit.limits["scale"] == "transformed"
        assert limit.limits["transformation_decision"] == decision
        assert limit.limits["transformed_specification"]
        assert monitored.chart_result["scale"] == "transformed"
        assert monitored.chart_result["transformation_decision"] == decision
        assert monitored.chart_result["location"]["values"][-1] == pytest.approx(expected_last)
        assert monitored.samples[-1].values == [200.0, 220.0]
        assert monitored.stability_result["violations"]
        events = SpcEvent.query.filter_by(study_version_id=monitored.id).all()
        location_event = next(
            event for event in events
            if float(event.observed_value) == pytest.approx(expected_last)
        )
        serialized = serialize_event(
            location_event,
            versions_by_id={monitored.id: monitored},
            samples_by_id={monitored.samples[-1].id: monitored.samples[-1]},
        )
        assert serialized["scale"] == "transformed"
        assert serialized["transformation_decision"] == decision
        assert serialized["original_sample_values"] == [200.0, 220.0]


def test_stable_transformed_baseline_reaches_approved_ongoing_without_gate_patch(
    app, db_session
):
    """以真實出貨轉接器驗證穩定轉換基準可完成正式生命週期。"""

    with app.app_context():
        _role(
            db_session,
            "transformed_e2e_approver",
            {"spc.manage": True, "spc.approve": True, "spc.view": True},
        )
        actor = _user(db_session, "transformed-e2e", "transformed_e2e_approver")
        probabilities = np.linspace(0.01, 0.99, 90)
        values = scipy_stats.lognorm.ppf(
            probabilities, 0.6, loc=0.0, scale=np.exp(1.0)
        )
        values = np.random.default_rng(41).permutation(values)
        for index in range(30):
            record = ShippingData(
                date=date(2026, 6, index + 1),
                material="SPC-E2E",
                spec="LENGTH-TRANSFORM",
                order_num=f"SPC-E2E-{index + 1}",
                group_count=3,
            )
            db_session.add(record)
            db_session.flush()
            for group in range(3):
                db_session.add(ShippingMeasurement(
                    shipping_id=record.id,
                    group_num=group + 1,
                    item="長度",
                    position="",
                    value_single=float(values[index * 3 + group]),
                    lower_limit=0.2,
                    upper_limit=15.0,
                ))
        db_session.commit()

        filters = {
            "field": "長度",
            "material": "SPC-E2E",
            "spec": "LENGTH-TRANSFORM",
        }
        baseline = SpcStudyService.analyze("shipping", filters, actor.id)
        transformed = SpcStudyService.confirm_transformation(
            baseline.id,
            actor.id,
            model="johnson_sl",
            reason="固定基準偏態，確認採 Johnson SL 轉換",
        )
        controlled = SpcStudyService.confirm_time_model(
            transformed.id,
            actor.id,
            model="A2",
            reason="轉換後位置與變異圖均穩定，確認 A2",
        )
        submitted = SpcStudyService.submit(
            controlled.id, actor.id, reason="送審穩定轉換基準"
        )
        limit = SpcStudyService.approve_and_activate(
            submitted.id, actor.id, reason="核准穩定轉換基準"
        )

        new_record = ShippingData(
            date=date(2026, 7, 1), material="SPC-E2E", spec="LENGTH-TRANSFORM",
            order_num="SPC-E2E-ONGOING", group_count=3,
        )
        db_session.add(new_record)
        db_session.flush()
        for group, value in enumerate((8.0, 8.5, 9.0), start=1):
            db_session.add(ShippingMeasurement(
                shipping_id=new_record.id, group_num=group, item="長度", position="",
                value_single=value, lower_limit=0.2, upper_limit=15.0,
            ))
        db_session.commit()

        ongoing = SpcStudyService.analyze(
            "shipping", filters, actor.id, study_type="ongoing"
        )

        assert controlled.stability_result["stable"] is True
        assert limit.status == "active"
        assert limit.study_version_id == controlled.id
        assert limit.limits["scale"] == "transformed"
        assert limit.limits["transformation_decision"]["params"] == (
            controlled.distribution_result["transformation_decision"]["params"]
        )
        assert ongoing.status == "active"
        assert ongoing.chart_result["scale"] == "transformed"
        assert ongoing.time_model_result["reason_code"] == "ONGOING_USES_APPROVED_LIMITS"
        assert ongoing.time_model_result["limit_version_id"] == limit.id
        assert ongoing.data_hash != controlled.data_hash
        assert ongoing.samples[-1].values == [8.0, 8.5, 9.0]
        assert ongoing.samples[-1].source_record_ids == [new_record.id]
        assert len(ongoing.samples[-1].source_measurement_ids) == 3
        decision = controlled.distribution_result["transformation_decision"]
        expected_transformed = float(np.mean(transform_values([8.0, 8.5, 9.0], decision)))
        assert ongoing.chart_result["location"]["values"][-1] == pytest.approx(
            expected_transformed
        )
        assert ongoing.chart_result["location"]["cl"] == [
            limit.limits["location"]["cl"][0]
        ] * len(ongoing.samples)
        assert ongoing.chart_result["transformation_decision"]["params"] == decision["params"]
        assert [row.action for row in AuditLog.query.filter_by(module="spc_study").all()] == [
            "analyze", "confirm_transformation", "confirm_time_model", "submit",
            "approve_activate", "analyze",
        ]


def test_bcd_research_approval_never_creates_production_limits(app, db_session, monkeypatch):
    with app.app_context():
        _role(db_session, "qa_supervisor", {"spc.manage": True, "spc.approve": True})
        actor = _user(db_session, "approver-research", "qa_supervisor")
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())

        def d_candidate(study_input):
            results = _approvable_results(study_input)
            results["time_model_result"] = {"candidate": "D", "confirmed": False, "diagnostic_version": "2026.2"}
            return results

        monkeypatch.setattr(spc_study_module, "_calculate_results", d_candidate)
        draft = SpcStudyService.analyze("shipping", {}, actor.id)
        confirmed = SpcStudyService.confirm_time_model(draft.id, actor.id, model="D", reason="位置與變異皆改變")
        submitted = SpcStudyService.submit(confirmed.id, actor.id, reason="送研究核准")
        with pytest.raises(SpcValidationError) as production:
            SpcStudyService.approve_and_activate(submitted.id, actor.id, reason="不可啟用界限")
        assert production.value.code == "TIME_MODEL_UNCONFIRMED"
        approved = SpcStudyService.approve_research(submitted.id, actor.id, reason="僅保留研究證據")
        assert approved.status == "approved"
        assert SpcLimitVersion.query.count() == 0


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
