"""校正正式服務 smoke client 的 HTTP 契約測試。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.scripts.smoke_calibration import (
    ActorCredentials,
    SmokeConfig,
    SmokeError,
    build_parser,
    run_smoke,
    validate_args,
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
            point = json_body["points"][0]
            if "result" in point:
                return 422, {"error": {
                    "code": "CALIBRATION_UNKNOWN_FIELDS",
                    "message": "包含不允許欄位",
                    "details": {"unknown_fields": ["result"]},
                }}
            values = [
                item["indicated_value"]
                for item in point["readings"]
            ]
            failed = values == ["10.100", "10.110", "10.120"]
            result = "fail" if failed else "pass"
            if failed and self.corrupt_fail_result:
                result = "pass"
            record.update({
                "status": "in_progress",
                "result": result,
                "row_version": record["row_version"] + 1,
                "points": [{
                    **record["points"][0],
                    "average_value": "10.11" if failed else "10.002",
                    "error_value": "0.11" if failed else "0.002",
                    "repeatability_value": "0.02" if failed else "0.002",
                    "mean_error": "0.11" if failed else "0.002",
                    "mean_correction": "-0.11" if failed else "-0.002",
                    "error_range": "0.02" if failed else "0.002",
                    "result": result,
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
            if record["status"] == "approved":
                return 409, {"error": {
                    "code": "CALIBRATION_IMMUTABLE",
                    "message": "核准後校正證據不可修改",
                    "details": {"calibration_id": calibration_id},
                }}
            record["row_version"] += 1
            record["certificate_attachment_id"] = json_body[
                "certificate_attachment_id"
            ]
            return 200, {"data": record.copy()}

        if path.endswith("/validate"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
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

        if path.endswith("/submit"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
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

        if path.endswith("/approve") and path.startswith("/api/calibrations/"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
            record["status"] = "approved"
            record["row_version"] += 1
            return 200, {"data": record.copy()}

        if path.endswith("/void"):
            calibration_id = int(path.split("/")[3])
            record = self._calibrations[calibration_id]
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
