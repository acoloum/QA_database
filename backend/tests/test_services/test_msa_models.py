"""MSA 設備與準則資料模型的約束及不可變性測試。"""

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.models import (
    EquipmentCalibrationRecord,
    EquipmentImportBatch,
    MeasurementEquipment,
    MeasurementEquipmentLink,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
)


def _equipment(db_session, equipment_no):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="測試量具",
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _approved_calibration(db_session, equipment_no):
    equipment = _equipment(db_session, equipment_no)
    record = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date(2026, 7, 1),
        result="pass",
        status="approved",
    )
    db_session.add(record)
    db_session.commit()
    return record


def _approved_criteria_version(db_session, profile_name):
    profile = MsaCriteriaProfile(name=profile_name)
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id,
        version_no=1,
        method_version="MSA4-1.0",
        effective_date=date(2026, 7, 27),
        thresholds={
            "grr_accept_max": 10,
            "grr_conditional_max": 30,
            "ndc_min": 5,
        },
        status="approved",
    )
    db_session.add(version)
    db_session.commit()
    return version


def test_equipment_number_is_unique(db_session):
    db_session.add(
        MeasurementEquipment(equipment_no="EQ-001", name="游標卡尺")
    )
    db_session.commit()
    db_session.add(
        MeasurementEquipment(equipment_no="EQ-001", name="重複設備")
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_only_one_current_link_exists_for_each_source_entity(db_session):
    first = _equipment(db_session, "EQ-LINK-1")
    second = _equipment(db_session, "EQ-LINK-2")
    db_session.add(
        MeasurementEquipmentLink(
            equipment_id=first.id,
            source_module="pyrometry",
            source_entity_type="Recorder",
            source_entity_id=8,
            is_current=True,
        )
    )
    db_session.commit()
    db_session.add(
        MeasurementEquipmentLink(
            equipment_id=second.id,
            source_module="pyrometry",
            source_entity_type="Recorder",
            source_entity_id=8,
            is_current=True,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_equipment_import_file_hash_is_unique(db_session):
    first = EquipmentImportBatch(
        original_filename="equipment.xlsx",
        file_sha256="a" * 64,
        file_size=128,
        status="pending",
        parser_version="msa-equipment-v1",
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(
        EquipmentImportBatch(
            original_filename="equipment-copy.xlsx",
            file_sha256="a" * 64,
            file_size=128,
            status="pending",
            parser_version="msa-equipment-v1",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_approved_calibration_cannot_be_changed(db_session):
    record = _approved_calibration(db_session, "EQ-002")
    record.certificate_no = "CERT-CHANGED"

    with pytest.raises(ValueError, match="核准後的校驗紀錄不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_calibration_cannot_be_changed_after_status_downgrade(
    db_session,
):
    record = _approved_calibration(db_session, "EQ-003")
    record.status = "draft"
    record.certificate_no = "CERT-BYPASS"

    with pytest.raises(ValueError, match="核准後的校驗紀錄不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_calibration_cannot_be_deleted(db_session):
    record = _approved_calibration(db_session, "EQ-004")
    db_session.delete(record)

    with pytest.raises(ValueError, match="核准後的校驗紀錄不可刪除"):
        db_session.commit()
    db_session.rollback()


def test_approved_criteria_version_cannot_be_changed(db_session):
    version = _approved_criteria_version(db_session, "一般計量型")
    version.thresholds = {"grr_accept_max": 9}

    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_criteria_version_cannot_be_changed_after_status_downgrade(
    db_session,
):
    version = _approved_criteria_version(db_session, "重要特性計量型")
    version.status = "draft"
    version.thresholds = {"grr_accept_max": 9}

    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_criteria_version_cannot_be_deleted(db_session):
    version = _approved_criteria_version(db_session, "刪除保護準則")
    db_session.delete(version)

    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可刪除"):
        db_session.commit()
    db_session.rollback()


def test_criteria_version_number_is_unique_within_profile(db_session):
    profile = MsaCriteriaProfile(name="唯一版次準則")
    db_session.add(profile)
    db_session.flush()
    db_session.add_all(
        [
            MsaCriteriaVersion(
                profile_id=profile.id,
                version_no=1,
                method_version="MSA4-1.0",
                effective_date=date(2026, 7, 27),
                thresholds={"ndc_min": 5},
            ),
            MsaCriteriaVersion(
                profile_id=profile.id,
                version_no=1,
                method_version="MSA4-1.1",
                effective_date=date(2026, 8, 1),
                thresholds={"ndc_min": 5},
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_current_criteria_version_must_belong_to_same_profile(db_session):
    db_session.execute(text("PRAGMA foreign_keys = ON"))
    assert db_session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    try:
        profile_a = MsaCriteriaProfile(name="準則設定 A")
        profile_b = MsaCriteriaProfile(name="準則設定 B")
        db_session.add_all([profile_a, profile_b])
        db_session.commit()

        version_b = MsaCriteriaVersion(
            profile_id=profile_b.id,
            version_no=1,
            method_version="MSA4-1.0",
            effective_date=date(2026, 7, 27),
            thresholds={"ndc_min": 5},
        )
        db_session.add(version_b)
        db_session.commit()

        profile_a.current_version_id = version_b.id
        with pytest.raises(IntegrityError):
            db_session.commit()
    finally:
        db_session.rollback()
        db_session.execute(text("PRAGMA foreign_keys = OFF"))
