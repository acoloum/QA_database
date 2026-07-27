"""MSA 研究生命週期服務的驗證、編號與併發保護測試。"""

import pytest

from backend.extensions import db
from backend.models import MsaStudy, User
from backend.services.msa_errors import (
    MsaConflict,
    MsaNotFound,
    MsaValidationError,
)
from backend.services.msa_study_service import MsaStudyService


@pytest.fixture
def msa_manager(db_session):
    user = User(username="msa_workflow_manager", password="x")
    db_session.add(user)
    db_session.commit()
    return user


def _payload(**overrides):
    payload = {
        "study_type": "grr_xbar_r",
        "measurement_purpose": "product_control",
        "characteristic": "外徑",
        "unit": "mm",
        "lsl": 9.5,
        "usl": 10.5,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def draft_msa_study(db_session, msa_manager):
    return MsaStudyService.create(
        _payload(
            responsible_user_id=msa_manager.id,
            primary_executor_id=msa_manager.id,
        ),
        actor_id=msa_manager.id,
    )


@pytest.fixture
def ready_msa_study(db_session, draft_msa_study):
    draft_msa_study.status = "ready"
    db_session.commit()
    return draft_msa_study


def test_create_study_generates_transaction_safe_number(
    db_session, msa_manager,
):
    study = MsaStudyService.create(
        _payload(
            responsible_user_id=msa_manager.id,
            primary_executor_id=msa_manager.id,
        ),
        actor_id=msa_manager.id,
    )

    assert study.study_no.startswith("MSA-")
    assert study.status == "draft"
    assert study.created_by_id == msa_manager.id


def test_study_numbers_do_not_collide_across_creations(
    db_session, msa_manager,
):
    numbers = {
        MsaStudyService.create(
            _payload(), actor_id=msa_manager.id,
        ).study_no
        for _ in range(5)
    }

    assert len(numbers) == 5


def test_lower_spec_limit_must_be_below_upper(db_session, msa_manager):
    with pytest.raises(MsaValidationError) as error:
        MsaStudyService.create(
            _payload(lsl=10.5, usl=9.5), actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_STUDY_SPEC_INVALID"


def test_product_control_requires_spec_or_explicit_reason(
    db_session, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaStudyService.create(
            _payload(lsl=None, usl=None), actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_STUDY_TOLERANCE_REQUIRED"


def test_product_control_accepts_documented_absence_of_tolerance(
    db_session, msa_manager,
):
    study = MsaStudyService.create(
        _payload(
            lsl=None,
            usl=None,
            no_tolerance_reason="顧客僅要求製程變差比較，無圖面公差",
        ),
        actor_id=msa_manager.id,
    )

    assert study.no_tolerance_reason


def test_process_control_study_may_omit_tolerance(db_session, msa_manager):
    study = MsaStudyService.create(
        _payload(
            measurement_purpose="process_control",
            lsl=None,
            usl=None,
            process_sigma=0.2,
        ),
        actor_id=msa_manager.id,
    )

    assert study.measurement_purpose == "process_control"


@pytest.mark.parametrize(
    "payload",
    [
        {"study_type": "不存在的方法"},
        {"measurement_purpose": "unknown"},
        {"characteristic": "   "},
        {"unit": ""},
        {"lsl": float("nan")},
        {"process_sigma": -1},
        {"unexpected": True},
    ],
)
def test_create_rejects_invalid_payload(db_session, msa_manager, payload):
    with pytest.raises(MsaValidationError):
        MsaStudyService.create(_payload(**payload), actor_id=msa_manager.id)
    db.session.rollback()


def test_non_draft_identity_fields_cannot_be_patched(
    db_session, ready_msa_study, msa_manager,
):
    with pytest.raises(MsaConflict) as error:
        MsaStudyService.update(
            ready_msa_study.id,
            {"characteristic": "厚度"},
            actor_id=msa_manager.id,
            expected_updated_at=ready_msa_study.updated_at.isoformat(),
        )

    assert error.value.code == "MSA_STUDY_IDENTITY_LOCKED"


def test_draft_identity_fields_may_still_be_corrected(
    db_session, draft_msa_study, msa_manager,
):
    updated = MsaStudyService.update(
        draft_msa_study.id,
        {"characteristic": "厚度"},
        actor_id=msa_manager.id,
        expected_updated_at=draft_msa_study.updated_at.isoformat(),
    )

    assert updated.characteristic == "厚度"
    assert updated.updated_by_id == msa_manager.id


def test_stale_screen_cannot_overwrite_newer_study(
    db_session, draft_msa_study, msa_manager,
):
    stale_stamp = "2020-01-01T00:00:00+00:00"

    with pytest.raises(MsaConflict) as error:
        MsaStudyService.update(
            draft_msa_study.id,
            {"characteristic": "厚度"},
            actor_id=msa_manager.id,
            expected_updated_at=stale_stamp,
        )

    assert error.value.code == "MSA_VERSION_CONFLICT"


def test_update_requires_expected_updated_at(
    db_session, draft_msa_study, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaStudyService.update(
            draft_msa_study.id,
            {"characteristic": "厚度"},
            actor_id=msa_manager.id,
            expected_updated_at=None,
        )

    assert error.value.code == "MSA_EXPECTED_UPDATED_AT_REQUIRED"


def test_missing_study_is_reported_as_not_found(db_session, msa_manager):
    with pytest.raises(MsaNotFound) as error:
        MsaStudyService.get(999999)

    assert error.value.code == "MSA_STUDY_NOT_FOUND"


def test_list_is_bounded_and_uses_whitelisted_sort(db_session, msa_manager):
    MsaStudyService.create(_payload(), actor_id=msa_manager.id)

    page = MsaStudyService.list({"page": 1, "page_size": 25, "sort": "study_no"})

    assert set(page) == {"items", "page", "page_size", "total"}
    assert page["total"] >= 1


@pytest.mark.parametrize(
    "args",
    [
        {"page_size": 101},
        {"page": 0},
        {"sort": "; DROP TABLE"},
        {"order": "sideways"},
        {"unknown": "1"},
    ],
)
def test_list_rejects_unsafe_query(db_session, args):
    with pytest.raises(MsaValidationError):
        MsaStudyService.list(args)


def test_serialize_exposes_stable_study_contract(db_session, msa_manager):
    study = MsaStudyService.create(_payload(), actor_id=msa_manager.id)

    payload = MsaStudyService.serialize(study)

    assert payload["study_no"] == study.study_no
    assert payload["status"] == "draft"
    assert payload["lsl"] == "9.5000000000" or float(payload["lsl"]) == 9.5
    assert "updated_at" in payload


def test_status_is_not_patchable_through_update(
    db_session, draft_msa_study, msa_manager,
):
    """狀態只能由設計、分析與核准流程推進，不能直接改。"""
    with pytest.raises(MsaValidationError) as error:
        MsaStudyService.update(
            draft_msa_study.id,
            {"status": "approved"},
            actor_id=msa_manager.id,
            expected_updated_at=draft_msa_study.updated_at.isoformat(),
        )

    assert error.value.code == "MSA_UNKNOWN_FIELDS"
    assert db.session.get(MsaStudy, draft_msa_study.id).status == "draft"
