"""測試校正草稿建立與模板實例化。"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from backend.models import (
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    EquipmentCalibrationRecord,
    EquipmentCalibrationPoint,
    EquipmentCalibrationReading,
    MeasurementEquipment,
    Role,
    User,
)
from backend.services.calibration_service import CalibrationService
from backend.services.calibration_errors import (
    CalibrationNotFound,
    CalibrationConflict,
    CalibrationValidationError,
    CalibrationForbidden,
)
from backend.utils import generate_token


def _create_roles(db_session):
    inspector_role = Role(
        code="test_inspector",
        name="測試檢驗員",
        permissions={"calibration.view": True, "calibration.execute": True},
    )
    manager_role = Role(
        code="test_manager",
        name="測試管理者",
        permissions={
            "calibration.view": True,
            "calibration.execute": True,
            "calibration.manage": True,
        },
    )
    approver_role = Role(
        code="test_approver",
        name="測試核准者",
        permissions={
            "calibration.view": True,
            "calibration.approve": True,
        },
    )
    db_session.add_all([inspector_role, manager_role, approver_role])
    db_session.flush()
    return {
        "inspector": inspector_role,
        "manager": manager_role,
        "approver": approver_role,
    }


def _create_users(db_session, roles):
    users = {}
    for key, role in [
        ("executor", roles["manager"]),
        ("approver", roles["approver"]),
        ("inactive_manager", roles["manager"]),
    ]:
        user = User(
            username=f"test_{key}",
            password="hash",
            role=role.code,
            is_active=(key != "inactive_manager"),
        )
        db_session.add(user)
        users[key] = user
    db_session.flush()
    return users


def _create_equipment(
    db_session,
    equipment_no: str,
    name: str,
    equipment_type: str = "游標卡尺",
    is_reference_standard: bool = False,
    status: str = "active",
    calibration_interval_months: int = 12,
):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name=name,
        equipment_type=equipment_type,
        is_reference_standard=is_reference_standard,
        status=status,
        calibration_interval_months=calibration_interval_months,
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _create_approved_calibration(
    db_session,
    equipment_id: int,
    calibration_date: date,
    result: str = "pass",
    next_due_date: date = None,
    data_level: str = "summary_legacy",
):
    if next_due_date is None:
        next_due_date = calibration_date + timedelta(days=365)

    record = EquipmentCalibrationRecord(
        equipment_id=equipment_id,
        calibration_type="internal",
        calibration_date=calibration_date,
        next_due_date=next_due_date,
        result=result,
        data_level=data_level,
        status="approved",
        approved_by=1,
        approved_at=date.today(),
    )
    db_session.add(record)
    db_session.flush()
    return record


def _create_approved_template(db_session):
    """建立已核准的校正模板（透過服務層走完整工作流）。"""
    from backend.services.calibration_template_service import CalibrationTemplateService

    template = CalibrationTemplate(
        template_code="CAL-DRAFT-TEST",
        name="草稿測試模板",
        equipment_type="游標卡尺",
        status="active",
    )
    db_session.add(template)
    db_session.flush()

    # 用服務層建立版本並送審核准
    version = CalibrationTemplateService.create_version(
        template.id,
        {
            "procedure_code": "WI-CAL-DRAFT",
            "procedure_name": "草稿測試程序",
            "default_repetitions": 3,
            "environment_requirements": {
                "temperature": {"required": True, "unit": "°C"}
            },
            "allow_limited_use": False,
            "revision_reason": "初版",
            "points": [
                {
                    "point_order": 1,
                    "point_code": "P01",
                    "measurement_mode": "外徑",
                    "nominal_value": "10.000",
                    "unit": "mm",
                    "reference_input_mode": "certified_value",
                    "required_repetitions": 3,
                    "error_lower_limit": "-0.02",
                    "error_upper_limit": "0.02",
                    "evaluation_basis": "all_readings",
                    "repeatability_rule": "range",
                    "repeatability_limit": "0.03",
                    "qualification_scope_code": "OD-0-150",
                    "qualification_range_start": "0",
                    "qualification_range_end": "150",
                    "uncertainty_required": False,
                    "required": True,
                }
            ],
        },
        actor_id=1,
    )
    version_obj = db_session.get(CalibrationTemplateVersion, version["id"])

    # 送審
    CalibrationTemplateService.submit_version(
        version_obj.id,
        {"expected_version": 1, "reason": "送審"},
        actor_id=1,
    )

    # 核准（用不同使用者模擬）
    CalibrationTemplateService.approve_version(
        version_obj.id,
        {"expected_version": 2, "reason": "核准"},
        actor_id=2,
    )

    # 重新載入
    template = db_session.get(CalibrationTemplate, template.id)
    version_obj = db_session.get(CalibrationTemplateVersion, version_obj.id)

    return template, version_obj


class TestCreateCalibrationDraft:
    """測試建立校正草稿。"""

    def test_internal_draft_instantiates_points_from_approved_template(
        self, db_session, calibration_users
    ):
        """內校草稿應從核准模板實例化點位與讀值。"""
        manager_token = calibration_users["manager"]["token"]
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-DRAFT-01", "測試卡尺")

        ref_equipment = _create_equipment(
            db_session, "REF-DRAFT-01", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        # 使用服務直接建立
        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
            },
            actor_id=manager_user.id,
        )

        assert result["data_level"] == "detailed"
        assert result["status"] == "draft"
        assert result["template_version_id"] == version.id
        assert result["reference_standard_equipment_id"] == ref_equipment.id
        assert len(result["points"]) == 1
        assert result["points"][0]["point_code"] == "P01"
        assert result["points"][0]["required_repetitions"] == 3
        assert len(result["points"][0]["readings"]) == 3
        assert all(r["result"] == "pending" for r in result["points"][0]["readings"])

        # 驗證資料庫狀態
        record = db_session.get(EquipmentCalibrationRecord, result["id"])
        assert record.data_level == "detailed"
        assert record.template_snapshot is not None
        assert record.environment_conditions == {}
        assert len(record.calibration_points) == 1
        assert len(record.calibration_points[0].readings) == 3

    def test_external_draft_allows_missing_certificate(
        self, db_session, calibration_users
    ):
        """外校草稿可先不填證書。"""
        manager_token = calibration_users["manager"]["token"]
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-DRAFT-02", "外校卡尺")

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "external",
                "calibration_date": date.today().isoformat(),
                "calibration_provider": "校正實驗室 A",
            },
            actor_id=manager_user.id,
        )

        assert result["calibration_type"] == "external"
        assert result["reference_standard_equipment_id"] is None
        assert result["certificate_attachment_id"] is None

    def test_template_not_approved_rejected(
        self, db_session, calibration_users
    ):
        """未核准的模板版本應拒絕建立草稿。"""
        manager_user = calibration_users["manager"]["user"]

        template = CalibrationTemplate(
            template_code="CAL-DRAFT-REJECT",
            name="拒絕測試模板",
            equipment_type="游標卡尺",
            status="active",
        )
        db_session.add(template)
        db_session.flush()

        version = CalibrationTemplateVersion(
            template_id=template.id,
            version_no=1,
            procedure_code="WI-CAL-REJECT",
            procedure_name="拒絕測試程序",
            default_repetitions=3,
            environment_requirements={},
            allow_limited_use=False,
            status="draft",  # 未核准
            row_version=1,
            created_by=1,
        )
        db_session.add(version)
        db_session.flush()

        equipment = _create_equipment(db_session, "EQ-DRAFT-03", "拒絕卡尺")

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.create(
                {
                    "equipment_id": equipment.id,
                    "template_version_id": version.id,
                    "calibration_type": "internal",
                    "calibration_date": date.today().isoformat(),
                    "reference_standard_equipment_id": 1,
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_STATUS_CONFLICT"
        assert "只有核准版本可用於建立詳細校正" in exc.value.message

    def test_equipment_type_mismatch_rejected(
        self, db_session, calibration_users
    ):
        """設備類型與模板不符應拒絕。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(
            db_session, "EQ-DRAFT-04", "錯誤類型設備", equipment_type="環規"
        )

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.create(
                {
                    "equipment_id": equipment.id,
                    "template_version_id": version.id,
                    "calibration_type": "internal",
                    "calibration_date": date.today().isoformat(),
                    "reference_standard_equipment_id": 1,
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_STATUS_CONFLICT"
        assert "受校設備類型與模板適用類型不符" in exc.value.message

    def test_inactive_equipment_rejected(self, db_session, calibration_users):
        """停用設備應拒絕。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(
            db_session, "EQ-DRAFT-05", "停用卡尺", status="inactive"
        )

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.create(
                {
                    "equipment_id": equipment.id,
                    "template_version_id": version.id,
                    "calibration_type": "internal",
                    "calibration_date": date.today().isoformat(),
                    "reference_standard_equipment_id": 1,
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_STATUS_CONFLICT"
        assert "受校設備狀態非啟用" in exc.value.message

    def test_internal_missing_reference_standard_rejected(
        self, db_session, calibration_users
    ):
        """內校缺少參考標準器應拒絕。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-DRAFT-06", "缺標準器卡尺")

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.create(
                {
                    "equipment_id": equipment.id,
                    "template_version_id": version.id,
                    "calibration_type": "internal",
                    "calibration_date": date.today().isoformat(),
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_REQUIRED"

    def test_reference_standard_not_usable_rejected(
        self, db_session, calibration_users
    ):
        """不可用的參考標準器應拒絕。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-DRAFT-07", "參考器失效卡尺")

        # 建立參考標準器但校正失效
        ref_equipment = _create_equipment(
            db_session, "REF-FAIL", "失效參考器", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today() - timedelta(days=400),
            "fail",
            date.today() - timedelta(days=30),
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.create(
                {
                    "equipment_id": equipment.id,
                    "template_version_id": version.id,
                    "calibration_type": "internal",
                    "calibration_date": date.today().isoformat(),
                    "reference_standard_equipment_id": ref_equipment.id,
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"

    def test_equipment_cannot_be_own_reference_standard(
        self, db_session, calibration_users
    ):
        """受校設備不能同時作為自己的標準器。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(
            db_session, "EQ-DRAFT-08", "自循環卡尺", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.create(
                {
                    "equipment_id": equipment.id,
                    "template_version_id": version.id,
                    "calibration_type": "internal",
                    "calibration_date": date.today().isoformat(),
                    "reference_standard_equipment_id": equipment.id,
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert "受校設備不能同時作為自己的參考標準器" in exc.value.message


class TestUpdateCalibrationDraft:
    """測試更新校正草稿。"""

    def test_update_draft_environment_conditions(
        self, db_session, calibration_users
    ):
        """更新草稿環境條件應成功。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-UPDATE-01", "更新卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-UPDATE-01", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        # 建立草稿
        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
                "environment_conditions": {
                    "temperature": {"value": "23", "unit": "°C"}
                },
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        expected_version = result["row_version"]

        # 更新環境條件
        updated = CalibrationService.update(
            record_id,
            {
                "expected_version": expected_version,
                "environment_conditions": {"temperature": {"value": "23.5", "unit": "°C"}},
            },
            actor_id=manager_user.id,
        )

        assert updated["row_version"] == expected_version + 1
        assert updated["environment_conditions"]["temperature"]["value"] == "23.5"

    def test_update_submitted_rejected(self, db_session, calibration_users):
        """已送審狀態不可更新。"""
        manager_user = calibration_users["manager"]["user"]
        approver_user = calibration_users["approver"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-UPDATE-02", "已送審卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-UPDATE-02", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        # 建立草稿並送審
        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
                "environment_conditions": {
                    "temperature": {"value": "23", "unit": "°C"}
                },
            },
            actor_id=manager_user.id,
        )

        # 直接用 ORM 將狀態改為 submitted（模擬送審後）
        record = db_session.get(EquipmentCalibrationRecord, result["id"])
        record.status = "submitted"
        record.row_version += 1
        db_session.commit()

        # 嘗試更新應失敗
        with pytest.raises(CalibrationConflict) as exc:
            CalibrationService.update(
                record.id,
                {
                    "expected_version": record.row_version,
                    "environment_conditions": {},
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_STATUS_CONFLICT"
        assert "目前狀態不可編輯" in exc.value.message

    def test_version_conflict_rejected(self, db_session, calibration_users):
        """版本衝突應回 409。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-UPDATE-03", "衝突卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-UPDATE-03", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
                "environment_conditions": {
                    "temperature": {"value": "23", "unit": "°C"}
                },
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        stale_version = result["row_version"]

        # 先更新一次
        CalibrationService.update(
            record_id,
            {"expected_version": stale_version, "calibration_location": "新位置"},
            actor_id=manager_user.id,
        )

        # 再用舊版本號更新應失敗
        with pytest.raises(CalibrationConflict) as exc:
            CalibrationService.update(
                record_id,
                {"expected_version": stale_version, "calibration_location": "舊位置"},
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_VERSION_CONFLICT"


class TestSaveReadings:
    """測試批次保存讀值與重算。"""

    def test_save_readings_recalculates_and_persists_backend_evidence(
        self, db_session, calibration_users
    ):
        """保存讀值應觸發後端重算並持久化證據。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-READ-01", "讀值卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-READ-01", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        point_id = result["points"][0]["id"]
        expected_version = result["row_version"]

        # 保存讀值
        saved = CalibrationService.save_readings(
            record_id,
            {
                "expected_version": expected_version,
                "points": [
                    {
                        "point_id": point_id,
                        "reference_value": "10.000",
                        "expanded_uncertainty": "0.003",
                        "coverage_factor": "2",
                        "readings": [
                            {"trial_no": 1, "indicated_value": "10.010"},
                            {"trial_no": 2, "indicated_value": "10.020"},
                            {"trial_no": 3, "indicated_value": "10.000"},
                        ],
                    }
                ],
            },
            actor_id=manager_user.id,
        )

        assert saved["result"] == "pass"
        assert saved["status"] == "in_progress"
        assert saved["row_version"] == expected_version + 1
        assert saved["data_hash"] is not None

        point = saved["points"][0]
        assert point["mean_error"] == "0.0100000000"
        assert point["mean_correction"] == "-0.0100000000"
        assert point["result"] == "pass"

    def test_paired_reading_calculates_correctly(self, db_session, calibration_users):
        """paired_reading 模式應使用各自標準器讀值。"""
        manager_user = calibration_users["manager"]["user"]

        # 建立 paired_reading 模板（使用服務層走完整流程）
        from backend.services.calibration_template_service import CalibrationTemplateService

        template = CalibrationTemplate(
            template_code="CAL-PAIRED",
            name="雙讀值模板",
            equipment_type="游標卡尺",
            status="active",
        )
        db_session.add(template)
        db_session.flush()

        version = CalibrationTemplateService.create_version(
            template.id,
            {
                "procedure_code": "WI-CAL-PAIRED",
                "procedure_name": "雙讀值程序",
                "default_repetitions": 3,
                "environment_requirements": {},
                "allow_limited_use": False,
                "revision_reason": "初版",
                "points": [
                    {
                        "point_order": 1,
                        "point_code": "P01",
                        "measurement_mode": "外徑",
                        "nominal_value": "10.000",
                        "unit": "mm",
                        "reference_input_mode": "paired_reading",
                        "required_repetitions": 3,
                        "error_lower_limit": "-0.02",
                        "error_upper_limit": "0.02",
                        "evaluation_basis": "all_readings",
                        "repeatability_rule": "range",
                        "repeatability_limit": "0.01",
                        "qualification_scope_code": "OD-0-150",
                        "qualification_range_start": "0",
                        "qualification_range_end": "150",
                        "uncertainty_required": False,
                        "required": True,
                    }
                ],
            },
            actor_id=1,
        )
        version_obj = db_session.get(CalibrationTemplateVersion, version["id"])

        # 送審
        CalibrationTemplateService.submit_version(
            version_obj.id,
            {"expected_version": 1, "reason": "送審"},
            actor_id=1,
        )

        # 核准（用不同使用者模擬）
        CalibrationTemplateService.approve_version(
            version_obj.id,
            {"expected_version": 2, "reason": "核准"},
            actor_id=2,
        )

        equipment = _create_equipment(db_session, "EQ-PAIRED-01", "雙讀值卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-PAIRED-01", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version_obj.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        point_id = result["points"][0]["id"]
        expected_version = result["row_version"]

        # paired_reading：每筆提供 standard_reading
        saved = CalibrationService.save_readings(
            record_id,
            {
                "expected_version": expected_version,
                "points": [
                    {
                        "point_id": point_id,
                        "readings": [
                            {
                                "trial_no": 1,
                                "indicated_value": "10.010",
                                "standard_reading": "10.000",
                            },
                            {
                                "trial_no": 2,
                                "indicated_value": "10.015",
                                "standard_reading": "10.005",
                            },
                            {
                                "trial_no": 3,
                                "indicated_value": "10.005",
                                "standard_reading": "10.000",
                            },
                        ],
                    }
                ],
            },
            actor_id=manager_user.id,
        )

        assert saved["result"] == "pass"
        point = saved["points"][0]
        # 驗證有效參考值 = standard_reading
        readings = point["readings"]
        assert readings[0]["effective_reference"] == "10.0000000000"
        assert readings[1]["effective_reference"] == "10.0050000000"
        assert readings[2]["effective_reference"] == "10.0000000000"

    def test_unknown_point_id_rejected(self, db_session, calibration_users):
        """不存在的 point_id 應拒絕整批。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-READ-02", "錯誤點位卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-READ-02", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        expected_version = result["row_version"]

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.save_readings(
                record_id,
                {
                    "expected_version": expected_version,
                    "points": [
                        {
                            "point_id": 999999,
                            "readings": [{"trial_no": 1, "indicated_value": "10.010"}],
                        }
                    ],
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_POINT_INVALID"
        assert "校正點不屬於此校正紀錄" in exc.value.message

    def test_duplicate_trial_no_rejected(self, db_session, calibration_users):
        """重複 trial_no 應拒絕（資料庫 unique constraint）。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-READ-03", "重複試驗卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-READ-03", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        point_id = result["points"][0]["id"]
        expected_version = result["row_version"]

        # 傳入重複 trial_no - 服務層應該捕捉並拋出適當的錯誤
        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationService.save_readings(
                record_id,
                {
                    "expected_version": expected_version,
                    "points": [
                        {
                            "point_id": point_id,
                            "readings": [
                                {"trial_no": 1, "indicated_value": "10.010"},
                                {"trial_no": 1, "indicated_value": "10.020"},
                            ],
                        }
                    ],
                },
                actor_id=manager_user.id,
            )

        # 驗證錯誤碼
        assert exc.value.code == "CALIBRATION_READING_INVALID"

    def test_submitted_record_cannot_save_readings(self, db_session, calibration_users):
        """已送審紀錄不可保存讀值。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-READ-04", "已送審卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-READ-04", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
            },
            actor_id=manager_user.id,
        )

        record = db_session.get(EquipmentCalibrationRecord, result["id"])
        record.status = "submitted"
        record.row_version += 1
        db_session.commit()

        with pytest.raises(CalibrationConflict) as exc:
            CalibrationService.save_readings(
                record.id,
                {
                    "expected_version": record.row_version,
                    "points": [
                        {
                            "point_id": record.calibration_points[0].id,
                            "readings": [{"trial_no": 1, "indicated_value": "10.010"}],
                        }
                    ],
                },
                actor_id=manager_user.id,
            )

        assert exc.value.code == "CALIBRATION_STATUS_CONFLICT"
        assert "目前狀態不可編輯" in exc.value.message


class TestValidateCalibration:
    """測試驗證校正紀錄。"""

    def test_validate_returns_blockers_when_incomplete(
        self, db_session, calibration_users
    ):
        """未填讀值時驗證應回傳 blockers。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-VAL-01", "驗證卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-VAL-01", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
                "environment_conditions": {
                    "temperature": {"value": "23", "unit": "°C"}
                },
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]

        # 尚未保存讀值，驗證
        validation = CalibrationService.validate(
            record_id,
            {"expected_version": result["row_version"]},
            actor_id=manager_user.id,
        )

        assert validation["result"] == "pending"
        assert "CALIBRATION_READING_MISSING" in validation["blockers"]

    def test_validate_pass_sets_ready_for_submission(
        self, db_session, calibration_users
    ):
        """全部合格時驗證應將狀態設為 ready_for_submission。"""
        manager_user = calibration_users["manager"]["user"]

        template, version = _create_approved_template(db_session)

        equipment = _create_equipment(db_session, "EQ-VAL-02", "合格卡尺")
        ref_equipment = _create_equipment(
            db_session, "REF-VAL-02", "參考環規", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today(),
            "pass",
            date.today() + timedelta(days=365),
        )
        db_session.commit()

        result = CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "internal",
                "calibration_date": date.today().isoformat(),
                "reference_standard_equipment_id": ref_equipment.id,
                "environment_conditions": {
                    "temperature": {"value": "23", "unit": "°C"}
                },
            },
            actor_id=manager_user.id,
        )

        record_id = result["id"]
        point_id = result["points"][0]["id"]

        # 保存合格讀值
        saved = CalibrationService.save_readings(
            record_id,
            {
                "expected_version": result["row_version"],
                "points": [
                    {
                        "point_id": point_id,
                        "reference_value": "10.000",
                        "readings": [
                            {"trial_no": 1, "indicated_value": "10.010"},
                            {"trial_no": 2, "indicated_value": "10.005"},
                            {"trial_no": 3, "indicated_value": "10.000"},
                        ],
                    }
                ],
            },
            actor_id=manager_user.id,
        )

        # 驗證
        validation = CalibrationService.validate(
            record_id,
            {"expected_version": saved["row_version"]},
            actor_id=manager_user.id,
        )

        assert validation["result"] == "pass"
        assert validation["blockers"] == []

        # 狀態應變為 ready_for_submission
        record = db_session.get(EquipmentCalibrationRecord, record_id)
        assert record.status == "ready_for_submission"


def test_list_total_is_not_limited_by_page_size(db_session, calibration_users):
    """total 必須代表全部篩選結果，不可只計算目前頁面。"""
    equipment = _create_equipment(db_session, "EQ-LIST-TOTAL", "分頁測試卡尺")
    for day in range(3):
        db_session.add(
            EquipmentCalibrationRecord(
                equipment_id=equipment.id,
                calibration_type="external",
                calibration_date=date.today() - timedelta(days=day),
                result="pass",
                status="approved",
                data_level="summary_legacy",
            )
        )
    db_session.commit()

    result = CalibrationService.list(
        {"page": 1, "page_size": 1},
        actor_id=calibration_users["viewer"]["user"].id,
    )

    assert result["total"] == 3
    assert len(result["items"]) == 1


def test_list_risk_sort_is_applied_before_pagination(
    db_session, calibration_users
):
    """風險排序必須在資料庫分頁前完成，不可只重排目前頁面。"""
    equipment = _create_equipment(db_session, "EQ-RISK-SORT", "風險排序卡尺")
    for result in ("pass", "limited_use", "fail"):
        db_session.add(
            EquipmentCalibrationRecord(
                equipment_id=equipment.id,
                calibration_type="external",
                calibration_date=date.today(),
                result=result,
                status="approved",
                data_level="summary_legacy",
                applicable_modes=["外徑"] if result == "limited_use" else [],
                restriction_conditions=(
                    "僅限外徑模式" if result == "limited_use" else None
                ),
            )
        )
    db_session.commit()

    first = CalibrationService.list(
        {"page": 1, "page_size": 1, "sort": "risk", "order": "asc"},
        actor_id=calibration_users["viewer"]["user"].id,
    )
    second = CalibrationService.list(
        {"page": 2, "page_size": 1, "sort": "risk", "order": "asc"},
        actor_id=calibration_users["viewer"]["user"].id,
    )

    assert first["items"][0]["result"] == "fail"
    assert second["items"][0]["result"] == "limited_use"


def test_list_search_filters_equipment_number_and_name(
    db_session, calibration_users
):
    """工作佇列搜尋應由後端在分頁前套用設備編號或名稱。"""
    matched = _create_equipment(
        db_session,
        "EQ-QUEUE-MATCH",
        "工作佇列專用卡尺",
    )
    other = _create_equipment(
        db_session,
        "EQ-QUEUE-OTHER",
        "一般量具",
    )
    for equipment in (matched, other):
        db_session.add(
            EquipmentCalibrationRecord(
                equipment_id=equipment.id,
                calibration_type="external",
                calibration_date=date.today(),
                result="pass",
                status="approved",
                data_level="summary_legacy",
            )
        )
    db_session.commit()

    result = CalibrationService.list(
        {
            "page": 1,
            "page_size": 25,
            "search": "專用卡尺",
            "sort": "risk",
            "order": "asc",
        },
        actor_id=calibration_users["viewer"]["user"].id,
    )

    assert result["total"] == 1
    assert result["items"][0]["equipment_no"] == "EQ-QUEUE-MATCH"


def test_template_snapshot_preserves_zero_decimal_values(
    db_session, calibration_users
):
    """模板快照與實際點位序列化不得把合法的 0 誤判為空值。"""
    manager = calibration_users["manager"]["user"]
    _, version = _create_approved_template(db_session)
    equipment = _create_equipment(db_session, "EQ-ZERO", "零值快照卡尺")
    db_session.commit()

    result = CalibrationService.create(
        {
            "equipment_id": equipment.id,
            "template_version_id": version.id,
            "calibration_type": "external",
            "calibration_date": date.today().isoformat(),
        },
        actor_id=manager.id,
    )

    snapshot_point = result["template_snapshot"]["points"][0]
    assert snapshot_point["qualification_range_start"] == "0"
    assert result["points"][0]["qualification_range_start"] == "0"


def test_environment_condition_rejects_non_finite_decimal(
    db_session, calibration_users
):
    """環境數值禁止 NaN 與 Infinity，且失敗時不得留下草稿。"""
    manager = calibration_users["manager"]["user"]
    _, version = _create_approved_template(db_session)
    equipment = _create_equipment(db_session, "EQ-NAN", "非有限值測試卡尺")
    db_session.commit()
    before = db_session.query(EquipmentCalibrationRecord).count()

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.create(
            {
                "equipment_id": equipment.id,
                "template_version_id": version.id,
                "calibration_type": "external",
                "calibration_date": date.today().isoformat(),
                "environment_conditions": {
                    "temperature": {"value": "NaN", "unit": "°C"}
                },
            },
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_FIELD_INVALID"
    assert db_session.query(EquipmentCalibrationRecord).count() == before


def test_required_environment_value_can_remain_empty_in_draft(
    db_session, calibration_users
):
    """必要環境值可先存草稿，完整性應留到 validate 階段判定。"""
    manager = calibration_users["manager"]["user"]
    _, version = _create_approved_template(db_session)
    equipment = _create_equipment(
        db_session, "EQ-ENV-DRAFT", "環境草稿測試卡尺"
    )
    db_session.commit()

    result = CalibrationService.create(
        {
            "equipment_id": equipment.id,
            "template_version_id": version.id,
            "calibration_type": "external",
            "calibration_date": date.today().isoformat(),
            "environment_conditions": {
                "temperature": {"value": None, "unit": "°C"}
            },
        },
        actor_id=manager.id,
    )

    assert result["status"] == "draft"
    assert result["environment_conditions"]["temperature"]["value"] is None

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.validate(
            result["id"],
            {"expected_version": result["row_version"]},
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_DATA_INCOMPLETE"
    assert (
        exc.value.details["field"]
        == "environment_conditions.temperature"
    )


def test_update_date_revalidates_existing_reference_and_preserves_draft_on_error(
    db_session, calibration_users
):
    """內校日期延後時必須重驗既有標準器，失敗不得污染草稿。"""
    manager = calibration_users["manager"]["user"]
    _, version = _create_approved_template(db_session)
    equipment = _create_equipment(db_session, "EQ-REVALIDATE", "日期重驗卡尺")
    reference = _create_equipment(
        db_session,
        "REF-REVALIDATE",
        "日期重驗標準器",
        is_reference_standard=True,
    )
    calibration_day = date.today()
    _create_approved_calibration(
        db_session,
        reference.id,
        calibration_day,
        result="pass",
        next_due_date=calibration_day + timedelta(days=1),
    )
    db_session.commit()
    created = CalibrationService.create(
        {
            "equipment_id": equipment.id,
            "template_version_id": version.id,
            "calibration_type": "internal",
            "calibration_date": calibration_day.isoformat(),
            "reference_standard_equipment_id": reference.id,
        },
        actor_id=manager.id,
    )

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.update(
            created["id"],
            {
                "expected_version": created["row_version"],
                "calibration_date": (
                    calibration_day + timedelta(days=2)
                ).isoformat(),
            },
            actor_id=manager.id,
        )

    assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
    db_session.expire_all()
    persisted = db_session.get(EquipmentCalibrationRecord, created["id"])
    assert persisted.calibration_date == calibration_day
    assert persisted.row_version == created["row_version"]
