"""校正正式服務 smoke client 的 HTTP 契約測試。"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from io import BytesIO
from urllib import error as urllib_error

import pytest

from backend.scripts.smoke_calibration import (
    ActorCredentials,
    SmokeConfig,
    SmokeError,
    UrllibHttpClient,
    _assert_backend_calculation,
    _cleanup_nonformal,
    _expect,
    _request_validation,
    build_parser,
    run_smoke,
    validate_args,
)
from backend.tests.test_calibration_routes import (
    _authorization,
    _create_approved_calibration,
    _create_approved_template_and_version,
    _create_equipment,
)


class FakeHttpClient:
    """模擬外部 HTTP 邊界；回應保留正式 API 的完整 data envelope。"""

    def __init__(self, *, corrupt_fail_result: bool = False):
        self.calls: list[dict] = []
        self.corrupt_fail_result = corrupt_fail_result
        self._equipment_id = 100
        self._calibration_id = 300
        self._calibrations: dict[int, dict] = {}
        self._tokens = {
            "manager": "token-manager",
            "executor": "token-executor",
            "approver": "token-approver",
        }

    def request(
        self,
        method,
        path,
        *,
        token=None,
        json_body=None,
        form=None,
        files=None,
    ):
        actor = next(
            (name for name, value in self._tokens.items() if value == token),
            None,
        )
        self.calls.append({
            "actor": actor,
            "method": method,
            "path": path,
            "json": json_body,
            "form": form,
            "files": files,
        })

        if path == "/api/login":
            username = json_body["username"]
            return 200, {
                "token": self._tokens[username],
                "username": username,
                "user_id": {"manager": 11, "executor": 22, "approver": 33}[username],
                "role": username,
            }

        if method == "POST" and path == "/api/measurement-equipment":
            self._equipment_id += 1
            return 201, {"data": {
                "id": self._equipment_id,
                "equipment_no": json_body["equipment_no"],
                "name": json_body["name"],
                "status": "active",
                "calibration_interval_months": 12,
                "is_reference_standard": json_body["is_reference_standard"],
            }}

        if method == "POST" and path == "/api/calibration-templates":
            return 201, {"data": {
                "id": 201,
                "template_code": json_body["template_code"],
                "name": json_body["name"],
                "equipment_type": json_body["equipment_type"],
                "status": "active",
                "current_approved_version_id": None,
            }}
        if path == "/api/calibration-templates/201/versions":
            return 201, {"data": {
                "id": 202,
                "template_id": 201,
                "version_no": 1,
                "status": "draft",
                "row_version": 11,
                "points": [{"id": 203, **json_body["points"][0]}],
            }}
        if path == "/api/calibration-template-versions/202/submit":
            assert json_body["expected_version"] == 11
            return 200, {"data": {
                "id": 202,
                "status": "submitted",
                "row_version": 12,
            }}
        if path == "/api/calibration-template-versions/202/approve":
            assert json_body["expected_version"] == 12
            return 200, {"data": {
                "id": 202,
                "status": "approved",
                "row_version": 13,
            }}

        if method == "POST" and path == "/api/calibrations":
            assert actor == "executor", "建立校正必須由 executor 執行"
            self._calibration_id += 1
            calibration_id = self._calibration_id
            record = {
                "id": calibration_id,
                "equipment_id": json_body["equipment_id"],
                "calibration_type": json_body["calibration_type"],
                "status": "draft",
                "result": "pending",
                "row_version": 1,
                "data_hash": None,
                "points": [{
                    "id": calibration_id * 10,
                    "point_code": "P01",
                    "nominal_value": "10",
                    "required_repetitions": 3,
                    "result": "pending",
                    "readings": [
                        {"id": calibration_id * 100 + trial, "trial_no": trial}
                        for trial in (1, 2, 3)
                    ],
                }],
            }
            self._calibrations[calibration_id] = record
            return 201, {"data": record.copy()}

        if method == "PUT" and path.endswith("/readings"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            assert actor == "executor", "readings 必須由 executor 執行"
            assert (
                json_body["expected_version"] == record["row_version"]
            ), "readings expected_version 必須等於目前版本"
            assert record["status"] in {
                "draft", "in_progress"
            }, "readings 只允許可編輯狀態"
            point = json_body["points"][0]
            if "result" in point:
                return 422, {"error": {
                    "code": "CALIBRATION_UNKNOWN_FIELDS",
                    "message": "包含不允許欄位",
                    "details": {
                        "step": "readings",
                        "unknown_fields": ["result"],
                    },
                }}
            values = [
                item["indicated_value"]
                for item in point["readings"]
            ]
            failed = values == ["10.100", "10.110", "10.120"]
            result = "fail" if failed else "pass"
            if failed and self.corrupt_fail_result:
                result = "pass"
            if failed:
                errors = ("0.100", "0.110", "0.120")
                corrections = ("-0.100", "-0.110", "-0.120")
                mean_error = "0.110"
                error_range = "0.020"
                sample_stddev = "0.010"
            else:
                errors = ("0.001", "0.002", "0.003")
                corrections = ("-0.001", "-0.002", "-0.003")
                mean_error = "0.002"
                error_range = "0.002"
                sample_stddev = "0.001"
            record.update({
                "status": "in_progress",
                "result": result,
                "row_version": record["row_version"] + 1,
                "points": [{
                    **record["points"][0],
                    "average_value": None,
                    "error_value": None,
                    "repeatability_value": None,
                    "mean_error": mean_error,
                    "mean_correction": f"-{mean_error}",
                    "minimum_error": errors[0],
                    "maximum_error": errors[2],
                    "error_range": error_range,
                    "sample_stddev": sample_stddev,
                    "completed_reading_count": 3,
                    "result": result,
                    "readings": [{
                        "id": calibration_id * 100 + trial,
                        "trial_no": trial,
                        "standard_reading": None,
                        "indicated_value": value,
                        "effective_reference": "10",
                        "error_value": error_value,
                        "correction_value": correction,
                        "result": result,
                    } for trial, value, error_value, correction in zip(
                        (1, 2, 3),
                        values,
                        errors,
                        corrections,
                    )],
                }],
            })
            return 200, {"data": record.copy()}

        if path == "/api/attachments/upload":
            return 201, {
                "id": 401,
                "entity_type": form["entity_type"],
                "entity_id": int(form["entity_id"]),
                "file_name": files["file"][0],
                "mime_type": files["file"][2],
                "purpose": form["purpose"],
            }

        if method == "PATCH" and path.startswith("/api/calibrations/"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            assert actor == "manager", "更新校正必須由 manager 執行"
            assert (
                json_body["expected_version"] == record["row_version"]
            ), "更新 expected_version 必須等於目前版本"
            if record["status"] == "approved":
                return 409, {"error": {
                    "code": "CALIBRATION_STATUS_CONFLICT",
                    "message": "核准後校正證據不可修改",
                    "details": {
                        "calibration_id": calibration_id,
                        "status": "approved",
                    },
                }}
            assert record["status"] in {
                "draft", "in_progress"
            }, "更新只允許可編輯狀態"
            record["row_version"] += 1
            record["certificate_attachment_id"] = json_body[
                "certificate_attachment_id"
            ]
            return 200, {"data": record.copy()}

        if method == "POST" and path.endswith("/validate"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            assert actor == "manager", "validate 必須由 manager 執行"
            assert (
                json_body["expected_version"] == record["row_version"]
            ), "validate expected_version 必須等於目前版本"
            assert record["status"] in {
                "draft", "in_progress", "ready_for_submission"
            }, "validate 狀態不合法"
            if record["result"] == "pass":
                record["status"] = "ready_for_submission"
                record["row_version"] += 1
            return 200, {"data": {
                "result": record["result"],
                "blockers": [],
                "passed_scope_codes": (
                    ["OD-0-150"] if record["result"] == "pass" else []
                ),
                "failed_scope_codes": (
                    ["OD-0-150"] if record["result"] == "fail" else []
                ),
                "row_version": record["row_version"],
            }}

        if method == "POST" and path.endswith("/submit"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            assert actor == "manager", "submit 必須由 manager 執行"
            assert (
                json_body["expected_version"] == record["row_version"]
            ), "submit expected_version 必須等於目前版本"
            assert (
                record["status"] == "ready_for_submission"
            ), "submit 必須由待送審狀態執行"
            if (
                record["calibration_type"] == "external"
                and not record.get("certificate_attachment_id")
            ):
                return 422, {"error": {
                    "code": "CALIBRATION_CERTIFICATE_REQUIRED",
                    "message": "外校送審前必須綁定校正證書",
                    "details": {"calibration_id": calibration_id},
                }}
            record["status"] = "submitted"
            record["row_version"] += 1
            record["data_hash"] = f"hash-{calibration_id}"
            return 200, {"data": record.copy()}

        if (
            method == "POST"
            and path.endswith("/approve")
            and path.startswith("/api/calibrations/")
        ):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            assert actor == "approver", "approve 必須由 approver 執行"
            assert (
                json_body["expected_version"] == record["row_version"]
            ), "approve expected_version 必須等於目前版本"
            assert record["status"] == "submitted", "approve 必須由送審狀態執行"
            record["status"] = "approved"
            record["row_version"] += 1
            return 200, {"data": record.copy()}

        if method == "POST" and path.endswith("/void"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            assert actor == "manager", "void 必須由 manager 執行"
            assert (
                json_body["expected_version"] == record["row_version"]
            ), "void expected_version 必須等於目前版本"
            assert record["status"] in {
                "draft", "in_progress", "ready_for_submission"
            }, "void 不得處理正式狀態"
            record["status"] = "voided"
            record["row_version"] += 1
            return 200, {"data": record.copy()}

        if (
            method == "POST"
            and path == "/api/measurement-equipment/101/calibrations"
        ):
            return 410, {"error": {
                "code": "CALIBRATION_LEGACY_ENDPOINT_RETIRED",
                "message": "舊版簡易校正介面已退役，請使用校正登錄流程",
                "details": {},
            }}

        if path == "/api/msa/criteria":
            return 201, {"data": {"id": 501, "name": json_body["name"]}}
        if path == "/api/msa/criteria/501/versions":
            return 201, {"data": {"id": 502, "status": "draft"}}
        if path == "/api/msa/criteria/versions/502/approve":
            return 200, {"data": {"id": 502, "status": "approved"}}
        if path == "/api/msa/studies":
            return 201, {"data": {"id": 503, "study_no": "MSA-SMOKE-001"}}
        if path == "/api/msa/studies/503/plans":
            return 201, {"data": {"id": 504, "plan_hash": None}}
        if path == "/api/msa/plans/504/freeze":
            approved_id = 302
            return 200, {"data": {
                "id": 504,
                "plan_hash": "plan-hash-504",
                "equipment_snapshot": {
                    "checked_on": "2026-07-30",
                    "items": [{
                        "role": "primary_gauge",
                        "equipment_id": 101,
                        "calibration": {
                            "record_id": approved_id,
                            "data_level": "detailed",
                            "data_hash": f"hash-{approved_id}",
                            "status": "approved",
                            "result": "pass",
                        },
                    }],
                    "resolution_assessment": {"level": "ok"},
                },
            }}

        raise AssertionError(f"未定義 fake endpoint：{method} {path}")


@pytest.fixture
def config():
    return SmokeConfig(
        base_url="http://localhost",
        manager=ActorCredentials("manager", "manager-secret"),
        executor=ActorCredentials("executor", "executor-secret"),
        approver=ActorCredentials("approver", "approver-secret"),
        keep_data=False,
    )


def test_smoke_requires_distinct_executor_and_approver():
    parser = build_parser()
    args = parser.parse_args([
        "--base-url", "http://localhost",
        "--manager-user", "manager",
        "--manager-password", "manager-secret",
        "--executor-user", "qa",
        "--executor-password", "secret",
        "--approver-user", "qa",
        "--approver-password", "secret",
    ])

    with pytest.raises(SystemExit, match="執行者與核准者必須不同"):
        validate_args(args)


def test_smoke_requires_all_three_workflow_actors_to_be_distinct():
    parser = build_parser()
    args = parser.parse_args([
        "--base-url", "http://localhost",
        "--manager-user", "same",
        "--manager-password", "manager-secret",
        "--executor-user", "same",
        "--executor-password", "executor-secret",
        "--approver-user", "approver",
        "--approver-password", "approver-secret",
    ])

    with pytest.raises(SystemExit, match="管理者、執行者與核准者必須是三個不同帳號"):
        validate_args(args)


def test_smoke_runs_controlled_workflow_in_actor_and_endpoint_order(config):
    client = FakeHttpClient()

    evidence = run_smoke(
        config,
        http_client=client,
        output=lambda _message: None,
        now=lambda: datetime(2026, 7, 30, 8, 9, 10, tzinfo=timezone.utc),
    )

    selected = [
        (call["actor"], call["method"], call["path"])
        for call in client.calls
        if call["path"] != "/api/login"
    ]
    assert selected == [
        ("manager", "POST", "/api/measurement-equipment"),
        ("manager", "POST", "/api/measurement-equipment"),
        ("manager", "POST", "/api/calibration-templates"),
        ("manager", "POST", "/api/calibration-templates/201/versions"),
        ("manager", "POST", "/api/calibration-template-versions/202/submit"),
        ("approver", "POST", "/api/calibration-template-versions/202/approve"),
        ("executor", "POST", "/api/calibrations"),
        ("executor", "PUT", "/api/calibrations/301/readings"),
        ("manager", "POST", "/api/attachments/upload"),
        ("manager", "PATCH", "/api/calibrations/301"),
        ("manager", "POST", "/api/calibrations/301/validate"),
        ("manager", "POST", "/api/calibrations/301/submit"),
        ("approver", "POST", "/api/calibrations/301/approve"),
        ("executor", "POST", "/api/calibrations"),
        ("executor", "PUT", "/api/calibrations/302/readings"),
        ("manager", "POST", "/api/calibrations/302/validate"),
        ("manager", "POST", "/api/calibrations/302/submit"),
        ("approver", "POST", "/api/calibrations/302/approve"),
        ("manager", "PATCH", "/api/calibrations/302"),
        ("manager", "POST", "/api/measurement-equipment/101/calibrations"),
        ("executor", "POST", "/api/calibrations"),
        ("executor", "PUT", "/api/calibrations/303/readings"),
        ("executor", "PUT", "/api/calibrations/303/readings"),
        ("executor", "POST", "/api/calibrations"),
        ("executor", "PUT", "/api/calibrations/304/readings"),
        ("manager", "POST", "/api/calibrations/304/validate"),
        ("manager", "POST", "/api/calibrations/304/submit"),
        ("manager", "POST", "/api/msa/criteria"),
        ("manager", "POST", "/api/msa/criteria/501/versions"),
        ("approver", "POST", "/api/msa/criteria/versions/502/approve"),
        ("executor", "POST", "/api/msa/studies"),
        ("manager", "POST", "/api/msa/studies/503/plans"),
        ("manager", "POST", "/api/msa/plans/504/freeze"),
        ("manager", "POST", "/api/calibrations/303/void"),
        ("manager", "POST", "/api/calibrations/304/void"),
    ]
    assert evidence["approved_calibration_id"] == 302
    assert evidence["approved_data_hash"] == "hash-302"
    assert evidence["msa_calibration_id"] == 302
    assert evidence["msa_data_hash"] == "hash-302"


def test_smoke_propagates_versions_and_never_sends_client_side_result(config):
    client = FakeHttpClient()

    run_smoke(
        config,
        http_client=client,
        output=lambda _message: None,
        now=lambda: datetime(2026, 7, 30, 8, 9, 10, tzinfo=timezone.utc),
    )

    by_path = {call["path"]: call for call in client.calls}
    assert by_path[
        "/api/calibration-template-versions/202/submit"
    ]["json"]["expected_version"] == 11
    assert by_path[
        "/api/calibration-template-versions/202/approve"
    ]["json"]["expected_version"] == 12
    assert by_path[
        "/api/calibrations/302/submit"
    ]["json"]["expected_version"] == 3
    assert by_path[
        "/api/calibrations/302/approve"
    ]["json"]["expected_version"] == 4
    assert by_path[
        "/api/calibrations/301/validate"
    ]["json"]["expected_version"] == 3
    assert by_path[
        "/api/calibrations/302/validate"
    ]["json"]["expected_version"] == 2
    assert by_path[
        "/api/calibrations/304/validate"
    ]["json"]["expected_version"] == 2
    valid_readings = [
        call for call in client.calls
        if call["path"].endswith("/readings")
        and all("result" not in point for point in call["json"]["points"])
    ]
    assert valid_readings
    assert all(
        "result" not in reading
        for call in valid_readings
        for point in call["json"]["points"]
        for reading in point["readings"]
    )


def test_smoke_checks_manual_pass_rejection_attachment_gate_and_immutability(
    config,
):
    client = FakeHttpClient()

    evidence = run_smoke(
        config,
        http_client=client,
        output=lambda _message: None,
        now=lambda: datetime(2026, 7, 30, 8, 9, 10, tzinfo=timezone.utc),
    )

    assert evidence["manual_result_override_status"] == 422
    assert evidence["external_attachment_gate_status"] == 422
    assert evidence["approved_immutability_status"] == 409
    assert evidence["legacy_endpoint_status"] == 410
    assert evidence["failed_result"] == "fail"


def test_smoke_rejects_server_that_turns_out_of_tolerance_data_into_pass(config):
    client = FakeHttpClient(corrupt_fail_result=True)

    with pytest.raises(SmokeError, match="超差讀值必須由後端判定為 fail"):
        run_smoke(
            config,
            http_client=client,
            output=lambda _message: None,
            now=lambda: datetime(2026, 7, 30, 8, 9, 10, tzinfo=timezone.utc),
        )


def test_cleanup_only_voids_non_formal_records(config):
    client = FakeHttpClient()

    run_smoke(
        config,
        http_client=client,
        output=lambda _message: None,
        now=lambda: datetime(2026, 7, 30, 8, 9, 10, tzinfo=timezone.utc),
    )

    cleanup_paths = [
        call["path"]
        for call in client.calls
        if call["method"] in {"DELETE"}
        or call["path"].endswith("/void")
    ]
    assert cleanup_paths == [
        "/api/calibrations/303/void",
        "/api/calibrations/304/void",
    ]
    assert "/api/calibrations/301/void" not in cleanup_paths
    assert "/api/calibrations/302/void" not in cleanup_paths


def test_keep_data_skips_cleanup(config):
    client = FakeHttpClient()
    keep_config = SmokeConfig(
        base_url=config.base_url,
        manager=config.manager,
        executor=config.executor,
        approver=config.approver,
        keep_data=True,
    )

    run_smoke(
        keep_config,
        http_client=client,
        output=lambda _message: None,
        now=lambda: datetime(2026, 7, 30, 8, 9, 10, tzinfo=timezone.utc),
    )

    assert not any(
        call["method"] == "DELETE" or call["path"].endswith("/void")
        for call in client.calls
    )


def _detailed_saved_record():
    """真實 detailed serializer 的代表性回應，不沿用 legacy 統計欄位。"""
    return {
        "result": "pass",
        "points": [{
            "average_value": None,
            "error_value": None,
            "repeatability_value": None,
            "mean_error": "0.0020",
            "mean_correction": "-0.002",
            "minimum_error": "0.001",
            "maximum_error": "0.003",
            "error_range": "0.00200",
            "sample_stddev": "0.001",
            "completed_reading_count": 3,
            "result": "pass",
            "readings": [
                {
                    "trial_no": 1,
                    "standard_reading": None,
                    "indicated_value": "10.001",
                    "effective_reference": "10.000",
                    "error_value": "0.001",
                    "correction_value": "-0.001",
                    "result": "pass",
                },
                {
                    "trial_no": 2,
                    "standard_reading": None,
                    "indicated_value": "10.002",
                    "effective_reference": "10.000",
                    "error_value": "0.002",
                    "correction_value": "-0.002",
                    "result": "pass",
                },
                {
                    "trial_no": 3,
                    "standard_reading": None,
                    "indicated_value": "10.003",
                    "effective_reference": "10.000",
                    "error_value": "0.003",
                    "correction_value": "-0.003",
                    "result": "pass",
                },
            ],
        }],
    }


def test_backend_calculation_uses_real_detailed_saved_fields_and_decimal_literals():
    _assert_backend_calculation(_detailed_saved_record())


def test_backend_calculation_detects_detailed_serializer_contract_drift():
    record = _detailed_saved_record()
    record["points"][0]["readings"][1]["error_value"] = "0.0021"

    with pytest.raises(SmokeError, match="後端精確結果不符"):
        _assert_backend_calculation(record)


class FlaskTestClientAdapter:
    """讓 smoke request helper 真正穿過 Flask route 與權限 adapter。"""

    def __init__(self, client):
        self.client = client

    def request(
        self,
        method,
        path,
        *,
        token=None,
        json_body=None,
        form=None,
        files=None,
    ):
        assert form is None and files is None
        response = self.client.open(
            path,
            method=method,
            headers=_authorization(token) if token else {},
            json=json_body,
        )
        return response.status_code, response.get_json()


def test_script_validation_request_obeys_real_route_actor_and_version_contract(
    client,
    db_session,
    calibration_users,
):
    manager = calibration_users["manager"]
    template, version = _create_approved_template_and_version(
        db_session, calibration_users
    )
    equipment = _create_equipment(db_session, "EQ-SMOKE-ROUTE", "smoke route 卡尺")
    reference = _create_equipment(
        db_session, "REF-SMOKE-ROUTE", "smoke route 環規", is_ref=True
    )
    _create_approved_calibration(
        db_session, reference.id, date.today(), "pass"
    )
    db_session.commit()
    adapter = FlaskTestClientAdapter(client)
    create_status, create_body = adapter.request(
        "POST",
        "/api/calibrations",
        token=manager["token"],
        json_body={
            "equipment_id": equipment.id,
            "template_version_id": version.id,
            "calibration_type": "internal",
            "calibration_date": date.today().isoformat(),
            "reference_standard_equipment_id": reference.id,
            "environment_conditions": {
                "temperature": {"value": "23", "unit": "°C"},
            },
        },
    )
    assert create_status == 201
    created = create_body["data"]
    save_status, save_body = adapter.request(
        "PUT",
        f"/api/calibrations/{created['id']}/readings",
        token=manager["token"],
        json_body={
            "expected_version": created["row_version"],
            "points": [{
                "point_id": created["points"][0]["id"],
                "reference_value": "10.000",
                "readings": [
                    {"trial_no": 1, "indicated_value": "10.001"},
                    {"trial_no": 2, "indicated_value": "10.002"},
                    {"trial_no": 3, "indicated_value": "10.003"},
                ],
            }],
        },
    )
    assert save_status == 200
    saved = save_body["data"]
    _assert_backend_calculation(saved)

    denied = _request_validation(
        adapter,
        calibration_users["no_permission"]["token"],
        created["id"],
        saved["row_version"],
    )
    stale = _request_validation(
        adapter,
        manager["token"],
        created["id"],
        saved["row_version"] - 1,
    )
    current = _request_validation(
        adapter,
        manager["token"],
        created["id"],
        saved["row_version"],
    )

    assert denied[0] == 403
    assert denied[1]["error"]["code"] == "CALIBRATION_PERMISSION_DENIED"
    assert stale[0] == 409
    assert stale[1]["error"]["code"] == "CALIBRATION_VERSION_CONFLICT"
    assert current[0] == 200
    assert current[1]["data"]["row_version"] == saved["row_version"] + 1


def test_fake_rejects_wrong_actor_and_stale_version():
    fake = FakeHttpClient()
    fake._calibrations[901] = {
        "id": 901,
        "status": "draft",
        "result": "pending",
        "row_version": 2,
        "points": [{"id": 9010, "nominal_value": "10"}],
    }

    with pytest.raises(AssertionError, match="executor"):
        fake.request(
            "PUT",
            "/api/calibrations/901/readings",
            token="token-manager",
            json_body={"expected_version": 2, "points": []},
        )
    with pytest.raises(AssertionError, match="expected_version"):
        fake.request(
            "POST",
            "/api/calibrations/901/validate",
            token="token-manager",
            json_body={"expected_version": 1},
        )


def test_parser_reads_environment_and_keeps_localhost_default(monkeypatch):
    monkeypatch.setenv("CALIBRATION_SMOKE_MANAGER_USER", "manager-env")
    monkeypatch.setenv("CALIBRATION_SMOKE_MANAGER_PASSWORD", "manager-pw")
    monkeypatch.setenv("CALIBRATION_SMOKE_EXECUTOR_USER", "executor-env")
    monkeypatch.setenv("CALIBRATION_SMOKE_EXECUTOR_PASSWORD", "executor-pw")
    monkeypatch.setenv("CALIBRATION_SMOKE_APPROVER_USER", "approver-env")
    monkeypatch.setenv("CALIBRATION_SMOKE_APPROVER_PASSWORD", "approver-pw")
    monkeypatch.delenv("CALIBRATION_SMOKE_BASE_URL", raising=False)

    args = validate_args(build_parser().parse_args([]))

    assert args.base_url == "http://localhost"
    assert args.manager_user == "manager-env"
    assert args.executor_user == "executor-env"
    assert args.approver_user == "approver-env"


def test_parser_pre_clean_flag_exists_and_conflicts_with_keep_data():
    parser = build_parser()

    args = parser.parse_args(["--pre-clean"])
    assert args.pre_clean is True
    assert args.keep_data is False

    with pytest.raises(SystemExit):
        # --keep-data 與 --pre-clean 語意衝突（保留草稿 vs 清除全部 smoke 資料）
        parser.parse_args(["--keep-data", "--pre-clean"])


def test_smoke_rejects_duplicate_login_user_id(config):
    class DuplicateUserFake(FakeHttpClient):
        def request(self, method, path, **kwargs):
            status, body = super().request(method, path, **kwargs)
            if path == "/api/login":
                body["user_id"] = 99
            return status, body

    with pytest.raises(SmokeError, match="user_id 未保持三方職責分離"):
        run_smoke(config, http_client=DuplicateUserFake(), output=lambda _: None)


def test_multipart_body_has_matching_boundary_and_utf8_content():
    body, content_type = UrllibHttpClient._multipart(
        {"purpose": "校正證書"},
        {"file": ("證書.pdf", b"%PDF-test", "application/pdf")},
    )
    boundary = content_type.split("boundary=", 1)[1].encode()

    assert body.startswith(b"--" + boundary + b"\r\n")
    assert body.endswith(b"--" + boundary + b"--\r\n")
    assert "校正證書".encode() in body
    assert "證書.pdf".encode() in body
    assert b"%PDF-test" in body


def test_http_error_preserves_exact_json_error_envelope(monkeypatch):
    envelope = {
        "error": {
            "code": "CALIBRATION_VERSION_CONFLICT",
            "message": "校正紀錄已被其他人更新，請重新載入",
            "details": {"current_version": 3, "expected_version": 2},
        }
    }

    def raise_http_error(*_args, **_kwargs):
        raise urllib_error.HTTPError(
            "http://localhost/api/calibrations/1/validate",
            409,
            "Conflict",
            {},
            BytesIO(json.dumps(envelope, ensure_ascii=False).encode()),
        )

    monkeypatch.setattr(
        "backend.scripts.smoke_calibration.request.urlopen",
        raise_http_error,
    )
    status, body = UrllibHttpClient("http://localhost").request(
        "POST",
        "/api/calibrations/1/validate",
        json_body={"expected_version": 2},
    )

    assert status == 409
    assert body == envelope


def test_success_output_and_evidence_never_include_credentials_or_tokens(config):
    messages = []
    evidence = run_smoke(config, http_client=FakeHttpClient(), output=messages.append)
    serialized = "\n".join(messages) + json.dumps(evidence, ensure_ascii=False)

    for sensitive in (
        "manager-secret",
        "executor-secret",
        "approver-secret",
        "token-manager",
        "token-executor",
        "token-approver",
    ):
        assert sensitive not in serialized

    with pytest.raises(SmokeError) as exc:
        _expect(
            (
                500,
                {
                    "error": {
                        "code": "SERVER_ERROR",
                        "message": "token-manager manager-secret",
                    },
                },
            ),
            200,
            "敏感錯誤",
        )
    assert "token-manager" not in str(exc.value)
    assert "manager-secret" not in str(exc.value)


def test_manual_override_requires_exact_error(config):
    class WrongManualEnvelopeFake(FakeHttpClient):
        def request(self, method, path, **kwargs):
            status, body = super().request(method, path, **kwargs)
            payload = kwargs.get("json_body") or {}
            if path.endswith("/readings") and any(
                "result" in point for point in payload.get("points", [])
            ):
                body["error"]["code"] = "WRONG_MANUAL_CODE"
            return status, body

    with pytest.raises(SmokeError, match="CALIBRATION_UNKNOWN_FIELDS"):
        run_smoke(
            config,
            http_client=WrongManualEnvelopeFake(),
            output=lambda _message: None,
        )


def test_approved_immutability_requires_exact_error(config):
    class WrongImmutableEnvelopeFake(FakeHttpClient):
        def request(self, method, path, **kwargs):
            status, body = super().request(method, path, **kwargs)
            if method == "PATCH" and status == 409:
                body["error"]["code"] = "WRONG_IMMUTABLE_CODE"
            return status, body

    with pytest.raises(SmokeError, match="CALIBRATION_STATUS_CONFLICT"):
        run_smoke(
            config,
            http_client=WrongImmutableEnvelopeFake(),
            output=lambda _message: None,
        )


def test_cleanup_attempts_every_record_then_raises_safe_failure():
    calls = []
    messages = []

    def failing_call(actor, method, path, *, json_body):
        calls.append((actor, method, path, json_body))
        if path.endswith("/303/void"):
            raise SmokeError("secret-in-client-exception")
        return 500, {
            "error": {
                "code": "CLEANUP_FAILED",
                "message": "secret-in-server-message",
                "details": {"token": "must-not-print"},
            }
        }

    with pytest.raises(SmokeError, match="清理非正式資料失敗"):
        _cleanup_nonformal(
            failing_call,
            {303: 2, 304: 3},
            messages.append,
        )

    assert [call[2] for call in calls] == [
        "/api/calibrations/303/void",
        "/api/calibrations/304/void",
    ]
    assert "secret-in-server-message" not in "\n".join(messages)
    assert "must-not-print" not in "\n".join(messages)
    assert "secret-in-client-exception" not in "\n".join(messages)


def test_primary_failure_survives_cleanup_failure_and_cleanup_continues(config):
    class PrimaryAndCleanupFailureFake(FakeHttpClient):
        def request(self, method, path, **kwargs):
            if path == "/api/calibrations/303/void":
                self.calls.append({
                    "actor": "manager",
                    "method": method,
                    "path": path,
                    "json": kwargs.get("json_body"),
                    "form": None,
                    "files": None,
                })
                return 500, {"error": {"code": "CLEANUP_FAILED"}}
            status, body = super().request(method, path, **kwargs)
            if path == "/api/msa/plans/504/freeze":
                body["data"]["equipment_snapshot"]["items"] = []
            return status, body

    fake = PrimaryAndCleanupFailureFake()
    with pytest.raises(
        SmokeError,
        match="MSA 凍結快照缺少 smoke 設備資格",
    ):
        run_smoke(config, http_client=fake, output=lambda _message: None)

    assert [call["path"] for call in fake.calls if call["path"].endswith("/void")] == [
        "/api/calibrations/303/void",
        "/api/calibrations/304/void",
    ]
