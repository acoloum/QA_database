"""版本化 MSA 判定準則服務的驗證、交易與不可變證據測試。"""

from datetime import date
import json

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from backend.extensions import db
from backend.models import (
    AuditLog,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    User,
)
from backend.services import msa_criteria_service as criteria_module
from backend.services.msa_criteria_service import MsaCriteriaService
from backend.services.msa_errors import MsaConflict, MsaValidationError


@pytest.fixture
def criteria_actor(db_session):
    actor = User(
        username="criteria_actor",
        password="hashed",
        role="admin",
        is_active=True,
    )
    db_session.add(actor)
    db_session.commit()
    return actor


def _create_profile(criteria_actor, name="一般計量型準則"):
    return MsaCriteriaService.create_profile(
        {
            "name": name,
            "applicable_study_types": ["grr_anova", "stability"],
        },
        actor_id=criteria_actor.id,
    )


def _create_version(criteria_actor, profile, **overrides):
    payload = {
        "method_version": "MSA4-1.0",
        "effective_date": "2026-07-27",
        "thresholds": {
            "grr_accept_max": 9,
            "grr_conditional_max": 25,
            "ndc_min": 6,
        },
        "stability_rules": {
            "rule_set": "WECO",
            "enabled_rules": [1, 2, 3, 4],
        },
        "conditional_actions": [
            "記錄接受理由",
            "建立改善與監控措施",
        ],
        "basis": "AIAG MSA 第四版及顧客要求",
    }
    payload.update(overrides)
    return MsaCriteriaService.create_version(
        profile.id,
        payload,
        actor_id=criteria_actor.id,
    )


def test_default_fourth_edition_thresholds_are_explicit():
    thresholds = MsaCriteriaService.default_thresholds()

    assert thresholds == {
        "grr_accept_max": 10.0,
        "grr_conditional_max": 30.0,
        "ndc_min": 5,
        "alpha": 0.05,
        "kappa_min": 0.75,
        "effectiveness_min": 90.0,
        "false_accept_max": 5.0,
        "false_reject_max": 5.0,
    }
    assert MsaCriteriaService.default_stability_rules() == {
        "rule_set": "WECO",
        "enabled_rules": [1, 2, 3, 4],
    }


def test_default_snapshots_are_independent_copies():
    thresholds = MsaCriteriaService.default_thresholds()
    rules = MsaCriteriaService.default_stability_rules()
    thresholds["alpha"] = 0.2
    rules["enabled_rules"].append(5)

    assert MsaCriteriaService.default_thresholds()["alpha"] == 0.05
    assert MsaCriteriaService.default_stability_rules()["enabled_rules"] == [
        1,
        2,
        3,
        4,
    ]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"grr_accept_max": -0.01}, "grr_accept_max"),
        ({"grr_accept_max": 30}, "grr_accept_max"),
        ({"grr_conditional_max": 10}, "grr_conditional_max"),
        ({"grr_conditional_max": 100.01}, "grr_conditional_max"),
        ({"ndc_min": 1}, "ndc_min"),
        ({"ndc_min": 5.5}, "ndc_min"),
        ({"alpha": 0}, "alpha"),
        ({"alpha": 1}, "alpha"),
        ({"kappa_min": -0.01}, "kappa_min"),
        ({"kappa_min": 1.01}, "kappa_min"),
        ({"effectiveness_min": -0.01}, "effectiveness_min"),
        ({"effectiveness_min": 100.01}, "effectiveness_min"),
        ({"false_accept_max": -0.01}, "false_accept_max"),
        ({"false_accept_max": 100.01}, "false_accept_max"),
        ({"false_reject_max": -0.01}, "false_reject_max"),
        ({"false_reject_max": 100.01}, "false_reject_max"),
        ({"alpha": True}, "alpha"),
        ({"kappa_min": float("nan")}, "kappa_min"),
        ({"effectiveness_min": float("inf")}, "effectiveness_min"),
        ({"false_accept_max": 10**1000}, "false_accept_max"),
    ],
)
def test_threshold_boundaries_reject_invalid_values(
    db_session,
    criteria_actor,
    overrides,
    field,
):
    profile = _create_profile(criteria_actor, f"門檻-{field}-{len(overrides)}")
    thresholds = MsaCriteriaService.default_thresholds()
    thresholds.update(overrides)

    with pytest.raises(MsaValidationError) as captured:
        MsaCriteriaService.create_version(
            profile.id,
            {"thresholds": thresholds},
            actor_id=criteria_actor.id,
        )

    assert captured.value.code == "MSA_CRITERIA_THRESHOLDS_INVALID"
    assert captured.value.details["field"] == field
    assert MsaCriteriaVersion.query.filter_by(profile_id=profile.id).count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("thresholds", {"grr_accept_max": 8, "typo": 20}),
        (
            "stability_rules",
            {"rule_set": "WECO", "enabled_rules": [1], "typo": True},
        ),
        ("conditional_actions", []),
        ("conditional_actions", ["  "]),
        ("basis", "  "),
    ],
)
def test_criteria_snapshot_rejects_unknown_or_missing_content(
    criteria_actor,
    field,
    value,
):
    profile = _create_profile(criteria_actor, f"結構-{field}")

    with pytest.raises(MsaValidationError):
        MsaCriteriaService.create_version(
            profile.id,
            {field: value},
            actor_id=criteria_actor.id,
        )


@pytest.mark.parametrize(
    "rules",
    [
        {"rule_set": "", "enabled_rules": [1]},
        {"rule_set": "WECO", "enabled_rules": []},
        {"rule_set": "WECO", "enabled_rules": [1, 1]},
        {"rule_set": "WECO", "enabled_rules": [0]},
        {"rule_set": "WECO", "enabled_rules": [True]},
    ],
)
def test_stability_rules_require_a_controlled_weco_structure(
    criteria_actor,
    rules,
):
    profile = _create_profile(criteria_actor, f"規則-{rules!r}")

    with pytest.raises(MsaValidationError) as captured:
        MsaCriteriaService.create_version(
            profile.id,
            {"stability_rules": rules},
            actor_id=criteria_actor.id,
        )

    assert captured.value.code == "MSA_CRITERIA_STABILITY_RULES_INVALID"


def test_create_version_is_draft_with_complete_deterministic_snapshot(
    db_session,
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)

    assert version.status == "draft"
    assert version.version_no == 1
    assert version.thresholds == {
        "grr_accept_max": 9.0,
        "grr_conditional_max": 25.0,
        "ndc_min": 6,
        "alpha": 0.05,
        "kappa_min": 0.75,
        "effectiveness_min": 90.0,
        "false_accept_max": 5.0,
        "false_reject_max": 5.0,
    }
    assert version.stability_rules == {
        "rule_set": "WECO",
        "enabled_rules": [1, 2, 3, 4],
    }
    assert version.conditional_actions == [
        "記錄接受理由",
        "建立改善與監控措施",
    ]
    assert version.basis == "AIAG MSA 第四版及顧客要求"
    assert json.dumps(
        MsaCriteriaService.serialize_version(version),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
    )

    audit = AuditLog.query.filter_by(
        module="msa_criteria",
        action="create_version",
        record_id=version.id,
    ).one()
    assert audit.new_value["criteria_snapshot"] == {
        "thresholds": version.thresholds,
        "stability_rules": version.stability_rules,
        "conditional_actions": version.conditional_actions,
        "basis": version.basis,
    }


def test_create_version_serializes_revision_numbers_under_profile_lock(
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    first = _create_version(criteria_actor, profile)
    second = _create_version(
        criteria_actor,
        profile,
        method_version="MSA4-1.1",
    )

    assert (first.version_no, second.version_no) == (1, 2)


def test_approving_new_version_updates_pointer_and_keeps_history_approved(
    db_session,
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    first = _create_version(criteria_actor, profile)
    MsaCriteriaService.approve_version(
        first.id,
        actor_id=criteria_actor.id,
        expected_status="draft",
    )
    second = _create_version(
        criteria_actor,
        profile,
        method_version="MSA4-1.1",
        thresholds={
            "grr_accept_max": 8,
            "grr_conditional_max": 20,
            "ndc_min": 5,
        },
    )

    approved = MsaCriteriaService.approve_version(
        second.id,
        actor_id=criteria_actor.id,
        expected_status="draft",
    )
    db_session.refresh(profile)
    db_session.refresh(first)

    assert profile.current_version_id == approved.id
    assert approved.status == "approved"
    assert approved.approved_by == criteria_actor.id
    assert approved.approved_at is not None
    assert first.status == "approved"
    assert approved.thresholds["alpha"] == 0.05
    assert approved.stability_rules["enabled_rules"] == [1, 2, 3, 4]
    assert approved.conditional_actions
    assert approved.basis

    audit = AuditLog.query.filter_by(
        module="msa_criteria",
        action="approve_version",
        record_id=approved.id,
    ).one()
    assert audit.new_value["profile_id"] == profile.id
    assert audit.new_value["version_id"] == approved.id
    assert audit.new_value["criteria_snapshot"] == {
        "thresholds": approved.thresholds,
        "stability_rules": approved.stability_rules,
        "conditional_actions": approved.conditional_actions,
        "basis": approved.basis,
    }


def test_approval_reason_is_recorded_in_the_audit_trail(criteria_actor):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)

    approved = MsaCriteriaService.approve_version(
        version.id,
        actor_id=criteria_actor.id,
        payload={"expected_status": "draft", "reason": "符合公司與顧客要求"},
    )

    audit = AuditLog.query.filter_by(
        module="msa_criteria",
        action="approve_version",
        record_id=approved.id,
    ).one()
    assert audit.new_value["reason"] == "符合公司與顧客要求"


def test_approval_without_reason_records_none(criteria_actor):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)

    approved = MsaCriteriaService.approve_version(
        version.id,
        actor_id=criteria_actor.id,
        expected_status="draft",
    )

    audit = AuditLog.query.filter_by(
        module="msa_criteria",
        action="approve_version",
        record_id=approved.id,
    ).one()
    assert audit.new_value["reason"] is None


@pytest.mark.parametrize("reason", [123, "理" * 501])
def test_approval_rejects_invalid_reason(criteria_actor, reason):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)

    with pytest.raises(MsaValidationError) as captured:
        MsaCriteriaService.approve_version(
            version.id,
            actor_id=criteria_actor.id,
            payload={"expected_status": "draft", "reason": reason},
        )

    assert captured.value.code == "MSA_CRITERIA_REASON_INVALID"
    db.session.rollback()


def test_duplicate_approval_is_a_conflict(criteria_actor):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)
    MsaCriteriaService.approve_version(
        version.id,
        actor_id=criteria_actor.id,
        expected_status="draft",
    )

    with pytest.raises(MsaConflict) as captured:
        MsaCriteriaService.approve_version(
            version.id,
            actor_id=criteria_actor.id,
            expected_status="draft",
        )

    assert captured.value.code == "MSA_VERSION_CONFLICT"


def test_approval_locks_version_and_profile_rows(
    app,
    db_session,
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)
    locked_sql = []

    def capture_sql(
        _conn,
        clauseelement,
        _multiparams,
        _params,
        _execution_options,
    ):
        sql = str(
            clauseelement.compile(
                dialect=postgresql.dialect(),
            )
        )
        if "FOR UPDATE" in sql:
            locked_sql.append(sql)

    event.listen(db.engine, "before_execute", capture_sql)
    try:
        MsaCriteriaService.approve_version(
            version.id,
            actor_id=criteria_actor.id,
            expected_status="draft",
        )
    finally:
        event.remove(db.engine, "before_execute", capture_sql)

    assert any('"MSA準則版本"' in sql for sql in locked_sql)
    assert any('"MSA準則設定"' in sql for sql in locked_sql)


def test_approval_rejects_cross_profile_locked_state(
    monkeypatch,
    criteria_actor,
):
    first_profile = _create_profile(criteria_actor, "第一準則")
    second_profile = _create_profile(criteria_actor, "第二準則")
    version = _create_version(criteria_actor, first_profile)

    monkeypatch.setattr(
        MsaCriteriaService,
        "_lock_profile",
        staticmethod(lambda _profile_id: second_profile),
    )

    with pytest.raises(MsaConflict) as captured:
        MsaCriteriaService.approve_version(
            version.id,
            actor_id=criteria_actor.id,
            expected_status="draft",
        )

    assert captured.value.code == "MSA_CRITERIA_PROFILE_CONFLICT"


def test_approval_rejects_profile_pointer_changed_while_waiting_for_lock(
    db_session,
    monkeypatch,
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    current = _create_version(criteria_actor, profile)
    MsaCriteriaService.approve_version(
        current.id,
        actor_id=criteria_actor.id,
        expected_status="draft",
    )
    target = _create_version(
        criteria_actor,
        profile,
        method_version="MSA4-1.1",
    )
    competing = _create_version(
        criteria_actor,
        profile,
        method_version="MSA4-1.2",
    )
    real_lock_profile = MsaCriteriaService._lock_profile

    def lock_after_competing_pointer_change(profile_id):
        locked = real_lock_profile(profile_id)
        locked.current_version_id = competing.id
        return locked

    monkeypatch.setattr(
        MsaCriteriaService,
        "_lock_profile",
        staticmethod(lock_after_competing_pointer_change),
    )

    with pytest.raises(MsaConflict) as captured:
        MsaCriteriaService.approve_version(
            target.id,
            actor_id=criteria_actor.id,
            expected_status="draft",
        )

    assert captured.value.code == "MSA_CRITERIA_PROFILE_CONFLICT"
    db_session.expire_all()
    assert db_session.get(MsaCriteriaProfile, profile.id).current_version_id == (
        current.id
    )
    assert db_session.get(MsaCriteriaVersion, target.id).status == "draft"


def test_audit_failure_rolls_back_approval_and_current_pointer(
    db_session,
    monkeypatch,
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(criteria_module, "log_audit", fail_audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        MsaCriteriaService.approve_version(
            version.id,
            actor_id=criteria_actor.id,
            expected_status="draft",
        )

    db_session.expire_all()
    persisted_profile = db_session.get(MsaCriteriaProfile, profile.id)
    persisted_version = db_session.get(MsaCriteriaVersion, version.id)
    assert persisted_profile.current_version_id is None
    assert persisted_version.status == "draft"
    assert persisted_version.approved_by is None
    assert persisted_version.approved_at is None


def test_in_place_json_mutation_does_not_change_approved_evidence(
    db_session,
    criteria_actor,
):
    profile = _create_profile(criteria_actor)
    version = _create_version(criteria_actor, profile)
    MsaCriteriaService.approve_version(
        version.id,
        actor_id=criteria_actor.id,
        expected_status="draft",
    )

    version.thresholds["grr_accept_max"] = 99
    version.stability_rules["enabled_rules"].clear()
    db_session.commit()
    db_session.expire_all()

    persisted = db_session.get(MsaCriteriaVersion, version.id)
    assert persisted.thresholds["grr_accept_max"] == 9.0
    assert persisted.stability_rules["enabled_rules"] == [1, 2, 3, 4]
