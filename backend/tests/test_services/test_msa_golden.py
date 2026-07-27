"""統計引擎 golden validation runner 測試。"""

import pytest

from backend.models import MsaValidationRun, User
from backend.services.msa_errors import MsaNotFound
from backend.services.msa_validation import MsaValidationService


@pytest.fixture
def actor(db_session):
    user = User(username="msa_golden_actor", password="x")
    db_session.add(user)
    db_session.commit()
    return user


def test_every_planned_method_has_a_golden_case():
    codes = MsaValidationService.case_codes()

    for expected in (
        "range_reference", "grr_xbar_r_reference",
        "anova_full_interaction", "anova_reduced_interaction",
        "bias_reference", "linearity_reference",
        "stability_xbar_r", "stability_i_mr",
        "attribute_binary", "attribute_multiclass",
        "nonrepeatable_paired",
    ):
        assert expected in codes


def test_not_applicable_and_non_finite_cases_are_covered():
    codes = MsaValidationService.case_codes()

    assert "not_applicable_unbalanced_xbar_r" in codes
    assert "not_applicable_nonrepeatable_assumptions" in codes
    assert "not_applicable_non_finite_reading" in codes


def test_validation_runner_persists_pass(db_session, actor):
    run = MsaValidationService.run_case(
        "grr_xbar_r_reference", actor_id=actor.id,
    )

    assert run.result == "PASS"
    assert run.differences == []
    assert run.method_versions == {"MSA4_GRR_XBAR_R_1_0": "1.0"}
    assert run.code_version
    assert run.tolerances
    assert len(run.fixture_hash) == 64
    assert run.executed_by_id == actor.id


def test_validation_runner_persists_fail(db_session, actor, monkeypatch):
    monkeypatch.setattr(
        MsaValidationService, "_compare",
        staticmethod(lambda *_args, **_kwargs: ["grr 超出容許誤差"]),
    )

    run = MsaValidationService.run_case(
        "grr_xbar_r_reference", actor_id=actor.id,
    )

    assert run.result == "FAIL"
    assert run.differences == ["grr 超出容許誤差"]
    assert MsaValidationRun.query.filter_by(result="FAIL").count() == 1


def test_all_golden_cases_pass(db_session, actor):
    runs = MsaValidationService.run_all(actor_id=actor.id)

    failures = {
        run.case_code: run.differences for run in runs if run.result == "FAIL"
    }
    assert failures == {}
    assert len(runs) == len(MsaValidationService.case_codes())


def test_not_applicable_case_passes_only_with_the_expected_reason(
    db_session, actor,
):
    run = MsaValidationService.run_case(
        "not_applicable_unbalanced_xbar_r", actor_id=actor.id,
    )

    assert run.result == "PASS"
    assert run.observed["not_applicable"] is True
    assert run.observed["reason"] == "unbalanced_design"


def test_non_finite_reading_case_is_recorded_as_not_applicable(
    db_session, actor,
):
    run = MsaValidationService.run_case(
        "not_applicable_non_finite_reading", actor_id=actor.id,
    )

    assert run.result == "PASS"
    assert run.observed["reason"] == "non_finite_reading"


def test_validation_run_cannot_be_updated_or_deleted(db_session, actor):
    run = MsaValidationService.run_case(
        "bias_reference", actor_id=actor.id,
    )

    run.result = "FAIL"
    with pytest.raises(ValueError, match="MSA 軟體確效執行不可修改"):
        db_session.commit()
    db_session.rollback()


def test_unknown_case_is_reported_as_not_found(db_session, actor):
    with pytest.raises(MsaNotFound) as error:
        MsaValidationService.run_case("不存在的案例", actor_id=actor.id)

    assert error.value.code == "MSA_VALIDATION_CASE_NOT_FOUND"


def test_fixture_hash_is_recorded_for_traceability(db_session, actor):
    first = MsaValidationService.run_case("bias_reference", actor_id=actor.id)
    second = MsaValidationService.run_case(
        "linearity_reference", actor_id=actor.id,
    )

    assert first.fixture_hash == second.fixture_hash
    assert first.fixture_hash == MsaValidationService.fixture_hash()


def test_missing_code_version_is_recorded_as_failure(
    db_session, actor, monkeypatch,
):
    monkeypatch.setattr(
        "backend.services.msa_validation.CODE_VERSION", "",
    )

    run = MsaValidationService.run_case(
        "grr_xbar_r_reference", actor_id=actor.id,
    )

    assert run.result == "FAIL"
    assert any("程式版本" in item for item in run.differences)
