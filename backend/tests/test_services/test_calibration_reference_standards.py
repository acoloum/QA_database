"""測試校正參考標準器資格驗證。"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from backend.models import (
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    Role,
    User,
)
from backend.services.calibration_eligibility import CalibrationEligibilityService
from backend.services.calibration_errors import (
    CalibrationNotFound,
    CalibrationValidationError,
)
from backend.utils import generate_token


def _create_roles(db_session):
    """建立測試角色。"""
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
    """建立測試使用者。"""
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
    """建立量測設備。"""
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
    applicable_modes = None,
    restriction_conditions = None,
):
    """建立核准校正紀錄。"""
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
    # limited_use 需要 applicable_modes 和 restriction_conditions
    if result == "limited_use":
        if applicable_modes is None:
            record.applicable_modes = ["外徑"]
        else:
            record.applicable_modes = applicable_modes
        if restriction_conditions is None:
            record.restriction_conditions = "僅限外徑量測"
        else:
            record.restriction_conditions = restriction_conditions
    db_session.add(record)
    db_session.flush()
    return record


def _create_approved_template_with_points(db_session, manager_token, client):
    """建立已核准的校正模板版本。"""
    # 建立模板
    template_resp = client.post(
        "/api/calibration-templates",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "template_code": "CAL-TEST",
            "name": "測試模板",
            "equipment_type": "游標卡尺",
        },
    )
    assert template_resp.status_code == 201
    template = template_resp.get_json()["data"]

    # 建立版本
    version_resp = client.post(
        f"/api/calibration-templates/{template['id']}/versions",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "procedure_code": "WI-CAL-TEST",
            "procedure_name": "測試程序",
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
                    "reference_input_mode": "certified_value",
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
    )
    assert version_resp.status_code == 201
    version = version_resp.get_json()["data"]

    # 送審
    submit_resp = client.post(
        f"/api/calibration-template-versions/{version['id']}/submit",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"expected_version": version["row_version"], "reason": "送審"},
    )
    assert submit_resp.status_code == 200

    # 核准
    approver_resp = client.post(
        "/api/auth/login",
        json={"username": "test_approver", "password": "hash"},
    )
    approver_token = approver_resp.get_json()["data"]["token"]

    approve_resp = client.post(
        f"/api/calibration-template-versions/{version['id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"expected_version": version["row_version"] + 1, "reason": "核准"},
    )
    assert approve_resp.status_code == 200

    return client.get(
        f"/api/calibration-templates/{template['id']}",
        headers={"Authorization": f"Bearer {manager_token}"},
    ).get_json()["data"]


class TestAssertReferenceStandardUsable:
    """測試參考標準器資格檢查。"""

    def test_valid_reference_standard_passes(
        self, client, db_session, calibration_users
    ):
        """有效的參考標準器應通過驗證。"""
        manager_token = calibration_users["manager"]["token"]

        # 建立參考標準器設備
        ref_equipment = _create_equipment(
            db_session,
            "REF-001",
            "參考環規",
            equipment_type="環規",
            is_reference_standard=True,
            calibration_interval_months=12,
        )

        # 建立核准校正紀錄
        cal_date = date.today() - timedelta(days=30)
        due_date = date.today() + timedelta(days=335)
        _create_approved_calibration(
            db_session, ref_equipment.id, cal_date, "pass", due_date
        )
        db_session.commit()

        # 驗證
        result = CalibrationEligibilityService.assert_reference_standard_usable(
            ref_equipment.id, on_date=date.today()
        )

        assert result.equipment_id == ref_equipment.id
        assert result.equipment_no == "REF-001"
        assert result.result == "pass"
        assert result.next_due_date == due_date

    def test_not_marked_reference_standard_fails(
        self, client, db_session, calibration_users
    ):
        """未標記為參考標準器的設備應失敗。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(
            db_session, "EQ-001", "一般卡尺", is_reference_standard=False
        )

        # 即使有核准校正也應失敗
        _create_approved_calibration(
            db_session, equipment.id, date.today(), "pass", date.today() + timedelta(days=365)
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationEligibilityService.assert_reference_standard_usable(
                equipment.id, on_date=date.today()
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert exc.value.details["reason"] == "not_marked_reference_standard"

    def test_inactive_status_fails(self, client, db_session, calibration_users):
        """停用狀態的參考標準器應失敗。"""
        manager_token = calibration_users["manager"]["token"]

        ref_equipment = _create_equipment(
            db_session,
            "REF-002",
            "停用參考器",
            is_reference_standard=True,
            status="inactive",
        )
        _create_approved_calibration(
            db_session, ref_equipment.id, date.today(), "pass", date.today() + timedelta(days=365)
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationEligibilityService.assert_reference_standard_usable(
                ref_equipment.id, on_date=date.today()
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert exc.value.details["reason"] == "status_not_active"

    def test_no_approved_calibration_fails(self, client, db_session, calibration_users):
        """無核准校正紀錄的參考標準器應失敗。"""
        manager_token = calibration_users["manager"]["token"]

        ref_equipment = _create_equipment(
            db_session, "REF-003", "無校正器", is_reference_standard=True
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationEligibilityService.assert_reference_standard_usable(
                ref_equipment.id, on_date=date.today()
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert exc.value.details["reason"] == "no_approved_calibration"

    def test_result_not_pass_fails(self, client, db_session, calibration_users):
        """校正結果非 pass/limited_use 應失敗。"""
        manager_token = calibration_users["manager"]["token"]

        ref_equipment = _create_equipment(
            db_session, "REF-004", "失效參考器", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session, ref_equipment.id, date.today(), "fail", date.today() + timedelta(days=365)
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationEligibilityService.assert_reference_standard_usable(
                ref_equipment.id, on_date=date.today()
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert exc.value.details["reason"] == "result_not_pass"

    def test_missing_next_due_date_fails(self, client, db_session, calibration_users):
        """缺少下次校驗日的參考標準器應失敗。"""
        manager_token = calibration_users["manager"]["token"]

        ref_equipment = _create_equipment(
            db_session, "REF-005", "無效期參考器", is_reference_standard=True
        )
        record = EquipmentCalibrationRecord(
            equipment_id=ref_equipment.id,
            calibration_type="internal",
            calibration_date=date.today(),
            next_due_date=None,  # 缺少
            result="pass",
            data_level="summary_legacy",
            status="approved",
            approved_by=1,
            approved_at=date.today(),
        )
        db_session.add(record)
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationEligibilityService.assert_reference_standard_usable(
                ref_equipment.id, on_date=date.today()
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert exc.value.details["reason"] == "missing_next_due_date"

    def test_overdue_fails(self, client, db_session, calibration_users):
        """已逾期的參考標準器應失敗。"""
        manager_token = calibration_users["manager"]["token"]

        ref_equipment = _create_equipment(
            db_session, "REF-006", "逾期參考器", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today() - timedelta(days=400),
            "pass",
            date.today() - timedelta(days=30),  # 已逾期 30 天
        )
        db_session.commit()

        with pytest.raises(CalibrationValidationError) as exc:
            CalibrationEligibilityService.assert_reference_standard_usable(
                ref_equipment.id, on_date=date.today()
            )

        assert exc.value.code == "CALIBRATION_REFERENCE_INVALID"
        assert exc.value.details["reason"] == "overdue"

    def test_limited_use_passes(self, client, db_session, calibration_users):
        """limited_use 結果應通過（只要有效期內）。"""
        manager_token = calibration_users["manager"]["token"]

        ref_equipment = _create_equipment(
            db_session, "REF-007", "限制使用參考器", is_reference_standard=True
        )
        _create_approved_calibration(
            db_session,
            ref_equipment.id,
            date.today() - timedelta(days=30),
            "limited_use",
            date.today() + timedelta(days=335),
        )
        db_session.commit()

        result = CalibrationEligibilityService.assert_reference_standard_usable(
            ref_equipment.id, on_date=date.today()
        )

        assert result.result == "limited_use"


class TestEquipmentQualification:
    """測試設備校正資格查詢。"""

    def test_qualified_equipment(self, client, db_session, calibration_users):
        """合格設備應回傳 is_qualified=True。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-001", "合格卡尺")
        _create_approved_calibration(
            db_session,
            equipment.id,
            date.today() - timedelta(days=30),
            "pass",
            date.today() + timedelta(days=335),
        )
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is True
        assert result.blockers == ()
        assert result.result == "pass"
        assert result.next_due_date == date.today() + timedelta(days=335)

    def test_inactive_equipment_not_qualified(self, client, db_session, calibration_users):
        """停用設備應有 blocker。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(
            db_session, "EQ-002", "停用卡尺", status="inactive"
        )
        _create_approved_calibration(
            db_session,
            equipment.id,
            date.today() - timedelta(days=30),
            "pass",
            date.today() + timedelta(days=335),
        )
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_EQUIPMENT_INACTIVE" in result.blockers

    def test_no_approved_record_not_qualified(self, client, db_session, calibration_users):
        """無核准校正紀錄應有 blocker。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-003", "新卡尺")
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_NO_APPROVED_RECORD" in result.blockers
        assert result.calibration_record_id is None

    def test_fail_result_not_qualified(self, client, db_session, calibration_users):
        """校正結果 fail 應有 blocker。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-004", "失效卡尺")
        _create_approved_calibration(
            db_session,
            equipment.id,
            date.today() - timedelta(days=30),
            "fail",
            date.today() + timedelta(days=335),
        )
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_RESULT_NOT_QUALIFIED" in result.blockers

    def test_missing_due_date_not_qualified(self, client, db_session, calibration_users):
        """缺少下次校驗日應有 blocker。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-005", "無效期卡尺")
        record = EquipmentCalibrationRecord(
            equipment_id=equipment.id,
            calibration_type="internal",
            calibration_date=date.today(),
            next_due_date=None,
            result="pass",
            data_level="summary_legacy",
            status="approved",
            approved_by=1,
            approved_at=date.today(),
        )
        db_session.add(record)
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_MISSING_DUE_DATE" in result.blockers

    def test_overdue_not_qualified(self, client, db_session, calibration_users):
        """逾期設備應有 blocker。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-006", "逾期卡尺")
        _create_approved_calibration(
            db_session,
            equipment.id,
            date.today() - timedelta(days=400),
            "pass",
            date.today() - timedelta(days=30),
        )
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_OVERDUE" in result.blockers

    def test_limited_use_mode_not_covered_not_qualified(
        self, client, db_session, calibration_users
    ):
        """limited_use 但量測模式未涵蓋應有 blocker。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-007", "限制使用卡尺")
        record = _create_approved_calibration(
            db_session,
            equipment.id,
            date.today() - timedelta(days=30),
            "limited_use",
            date.today() + timedelta(days=335),
        )
        # 設定僅涵蓋外徑模式
        record.applicable_modes = ["外徑"]
        record.restriction_conditions = "僅限外徑量測"
        db_session.commit()

        # 查詢內徑模式
        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today(), measurement_mode="內徑"
        )

        assert result.is_qualified is False
        assert "CALIBRATION_MODE_NOT_COVERED" in result.blockers

    def test_limited_use_mode_covered_qualified(
        self, client, db_session, calibration_users
    ):
        """limited_use 且量測模式涵蓋應合格。"""
        manager_token = calibration_users["manager"]["token"]

        equipment = _create_equipment(db_session, "EQ-008", "限制使用卡尺")
        record = _create_approved_calibration(
            db_session,
            equipment.id,
            date.today() - timedelta(days=30),
            "limited_use",
            date.today() + timedelta(days=335),
        )
        record.applicable_modes = ["外徑"]
        record.restriction_conditions = "僅限外徑量測"
        db_session.commit()

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today(), measurement_mode="外徑"
        )

        assert result.is_qualified is True
        assert result.applicable_modes == ["外徑"]

def test_equipment_qualification_limited_use_incomplete_data_not_qualified(
        db_session, monkeypatch
    ):
        """limited_use 但缺少模式或限制條件應有 blocker。"""
        from types import SimpleNamespace

        equipment = _create_equipment(
            db_session, "EQ-LIMIT-INCOMPLETE", "限制使用資料不完整"
        )
        db_session.commit()
        incomplete_record = SimpleNamespace(
            id=987,
            calibration_date=date.today(),
            next_due_date=date.today() + timedelta(days=30),
            result="limited_use",
            data_level="detailed",
            applicable_modes=[],
            restriction_conditions=None,
            data_hash="hash",
        )
        monkeypatch.setattr(
            CalibrationEligibilityService,
            "_latest_approved_calibration",
            staticmethod(
                lambda equipment_id, *, on_date=None: incomplete_record
            ),
        )

        result = CalibrationEligibilityService.equipment_qualification(
            equipment.id, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_LIMITED_USE_INCOMPLETE" in result.blockers


def test_nonexistent_equipment_returns_qualification_with_blocker(
        client, db_session, calibration_users
    ):
        """不存在的設備 ID 應回傳包含 blocker 的資格物件，不拋出例外。"""
        result = CalibrationEligibilityService.equipment_qualification(
            999999, on_date=date.today()
        )

        assert result.is_qualified is False
        assert "CALIBRATION_EQUIPMENT_NOT_FOUND" in result.blockers
        assert result.equipment_id == 999999


def test_latest_approved_calibration_uses_id_as_same_day_tie_breaker(db_session):
    """同日多筆核准紀錄時，以較新 ID 決定資格，避免查詢結果不穩定。"""
    equipment = _create_equipment(
        db_session,
        "REF-SAME-DAY",
        "同日排序標準器",
        is_reference_standard=True,
    )
    calibration_day = date.today()
    _create_approved_calibration(
        db_session,
        equipment.id,
        calibration_day,
        result="pass",
        next_due_date=calibration_day + timedelta(days=365),
    )
    newer = _create_approved_calibration(
        db_session,
        equipment.id,
        calibration_day,
        result="fail",
        next_due_date=calibration_day + timedelta(days=365),
    )
    db_session.commit()

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationEligibilityService.assert_reference_standard_usable(
            equipment.id, on_date=calibration_day
        )

    assert exc.value.details["calibration_record_id"] == newer.id
    assert exc.value.details["reason"] == "result_not_pass"
