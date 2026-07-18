"""SPC 研究版本、界限、事件、OCAP 與確效資料模型測試。"""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import (
    PatrolDetail,
    ShippingMeasurement,
    SpcEvent,
    SpcLimitVersion,
    SpcOcap,
    SpcStudy,
    SpcStudySample,
    SpcStudyVersion,
    SpcValidationRun,
    User,
)
from backend.seeds.seed_roles import ROLES


def _user(db_session, username="spc-user"):
    user = User(username=username, password="hashed", role="qc_manager")
    db_session.add(user)
    db_session.flush()
    return user


def _study_version(db_session, user, *, stream="stream-1", version_no=1):
    study = SpcStudy(
        source="shipping",
        study_type="retrospective",
        process_stream_key=stream,
        characteristic="外徑",
        filters={"field": "外徑", "start_date": "2026-07-01"},
        status="draft",
        created_by=user.id,
    )
    db_session.add(study)
    db_session.flush()
    version = SpcStudyVersion(
        study_id=study.id,
        version_no=version_no,
        method_version="2026.1",
        data_hash="a" * 64,
        specification_snapshot={"USL": 10.5, "LSL": 9.5},
        chart_result={"chart_type": "xbar_s"},
        stability_result={"stable": True},
        distribution_result={"model": "normal", "accepted": True},
        time_model_result={"candidate": "A1", "confirmed": False},
        capability_result={"ppk": 1.5, "cpk": None},
        applicability_result={"mode": "performance"},
        status="draft",
        created_by=user.id,
    )
    db_session.add(version)
    db_session.flush()
    return study, version


def test_spc_audit_entities_roundtrip_and_keep_relationships(app, db_session):
    with app.app_context():
        user = _user(db_session)
        study, version = _study_version(db_session, user)
        sample = SpcStudySample(
            version_id=version.id,
            source_record_type="ShippingMeasurement",
            source_record_id=10,
            source_measurement_id=20,
            subgroup_key="2026-07-01-G1",
            subgroup_order=0,
            values=[9.9, 10.0, 10.1],
            excluded=False,
        )
        db_session.add(sample)
        db_session.flush()
        limit = SpcLimitVersion(
            study_version_id=version.id,
            process_stream_key=study.process_stream_key,
            characteristic=study.characteristic,
            revision=1,
            chart_type="xbar_s",
            limits={"location": {"ucl": [10.4]}, "variation": {"ucl": [0.3]}},
            status="active",
            created_by=user.id,
            approved_by=user.id,
        )
        db_session.add(limit)
        db_session.flush()
        event = SpcEvent(
            limit_version_id=limit.id,
            study_version_id=version.id,
            sample_id=sample.id,
            chart_kind="variation",
            rule_code="beyond_limits",
            point_index=0,
            observed_value=0.5,
        )
        db_session.add(event)
        db_session.flush()
        ocap = SpcOcap(
            event_id=event.id,
            investigation_6m={"machine": ["模具磨耗"]},
            product_disposition="隔離待判",
            owner_id=user.id,
            created_by=user.id,
        )
        validation = SpcValidationRun(
            dataset_version="golden-a1-v1",
            method_version="2026.1",
            code_version="test",
            expected={"cpk": 1.5},
            actual={"cpk": 1.5},
            tolerances={"cpk": 1e-6},
            result="passed",
            executed_by=user.id,
        )
        db_session.add_all([ocap, validation])
        db_session.commit()

        assert study.versions == [version]
        assert version.samples == [sample]
        assert version.limit_versions == [limit]
        assert limit.events == [event]
        assert event.ocap is ocap


def test_study_version_number_is_unique_within_study(app, db_session):
    with app.app_context():
        user = _user(db_session)
        study, version = _study_version(db_session, user)
        duplicate = SpcStudyVersion(
            study_id=study.id,
            version_no=version.version_no,
            method_version="2026.1",
            data_hash="b" * 64,
            status="draft",
            created_by=user.id,
        )
        db_session.add(duplicate)

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


def test_only_one_active_limit_per_process_stream_and_characteristic(app, db_session):
    with app.app_context():
        user = _user(db_session)
        _, first_version = _study_version(db_session, user, stream="same-stream")
        _, second_version = _study_version(
            db_session, user, stream="same-stream", version_no=1
        )
        db_session.add_all([
            SpcLimitVersion(
                study_version_id=first_version.id,
                process_stream_key="same-stream",
                characteristic="外徑",
                revision=1,
                chart_type="xbar_s",
                limits={},
                status="active",
                created_by=user.id,
            ),
            SpcLimitVersion(
                study_version_id=second_version.id,
                process_stream_key="same-stream",
                characteristic="外徑",
                revision=1,
                chart_type="xbar_s",
                limits={},
                status="active",
                created_by=user.id,
            ),
        ])

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


def test_measurement_models_have_current_exclusion_actor_and_time_columns():
    assert hasattr(ShippingMeasurement, "exclusion_user_id")
    assert hasattr(ShippingMeasurement, "excluded_at")
    assert hasattr(PatrolDetail, "exclusion_user_id")
    assert hasattr(PatrolDetail, "excluded_at")


def test_seeded_roles_have_spc_permissions():
    by_code = {role["code"]: role["permissions"] for role in ROLES}

    assert by_code["inspector"]["spc.view"] is True
    assert by_code["qa_supervisor"]["spc.manage"] is True
    assert by_code["qc_manager"]["spc.approve"] is True
    assert by_code["admin"]["spc.approve"] is True


def test_migration_preserves_legacy_control_limit_table():
    migration = Path("backend/migration/36_create_spc_study_versioning.sql").read_text(
        encoding="utf-8"
    )
    normalized = migration.upper()

    assert 'DROP TABLE "SPC管制界限"' not in normalized
    assert 'DELETE FROM "SPC管制界限"' not in normalized
    assert "legacy_imported" in migration
    assert '"稽核不完整"' in migration
