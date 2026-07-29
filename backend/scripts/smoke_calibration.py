"""校正詳細登錄正式服務 smoke client。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib import error, request
from uuid import uuid4


class SmokeError(RuntimeError):
    """smoke 任一步驟未符合正式 API 契約。"""


@dataclass(frozen=True)
class ActorCredentials:
    """單一流程角色的登入資料。"""

    username: str
    password: str


@dataclass(frozen=True)
class SmokeConfig:
    """smoke 執行設定；密碼只留在記憶體，不得輸出。"""

    base_url: str
    manager: ActorCredentials
    executor: ActorCredentials
    approver: ActorCredentials
    keep_data: bool = False


def build_parser() -> argparse.ArgumentParser:
    """建立可由專用環境變數補值的 CLI parser。"""
    parser = argparse.ArgumentParser(
        description="驗證校正詳細登錄、不可變證據與 MSA 資格",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("CALIBRATION_SMOKE_BASE_URL", "http://localhost"),
    )
    for actor in ("manager", "executor", "approver"):
        upper = actor.upper()
        parser.add_argument(
            f"--{actor}-user",
            default=os.getenv(f"CALIBRATION_SMOKE_{upper}_USER"),
        )
        parser.add_argument(
            f"--{actor}-password",
            default=os.getenv(f"CALIBRATION_SMOKE_{upper}_PASSWORD"),
        )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="保留非正式 smoke 草稿；核准證據本來就不會刪除",
    )
    return parser


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    """驗證 CLI 必填值與三方職責分離。"""
    missing = [
        name
        for name in (
            "manager_user",
            "manager_password",
            "executor_user",
            "executor_password",
            "approver_user",
            "approver_password",
        )
        if not str(getattr(args, name, "") or "").strip()
    ]
    if missing:
        raise SystemExit("缺少 smoke 帳號或密碼參數")
    if args.executor_user == args.approver_user:
        raise SystemExit("執行者與核准者必須不同")
    if len({
        args.manager_user,
        args.executor_user,
        args.approver_user,
    }) != 3:
        raise SystemExit("管理者、執行者與核准者必須是三個不同帳號")
    return args


class UrllibHttpClient:
    """不增加部署相依的最小 HTTP client。"""

    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict | None = None,
        form: dict | None = None,
        files: dict | None = None,
    ) -> tuple[int, dict]:
        """送出 JSON 或 multipart 請求並保留錯誤回應 envelope。"""
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = None
        if files:
            body, content_type = self._multipart(form or {}, files)
            headers["Content-Type"] = content_type
        elif json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        outgoing = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(outgoing, timeout=self.timeout) as response:
                return response.status, self._json(response.read())
        except error.HTTPError as http_error:
            return http_error.code, self._json(http_error.read())
        except error.URLError as url_error:
            raise SmokeError(
                f"無法連線至 {self.base_url}：{url_error.reason}"
            ) from url_error

    @staticmethod
    def _json(body: bytes) -> dict:
        if not body:
            return {}
        try:
            value = json.loads(body)
        except json.JSONDecodeError as json_error:
            preview = body[:200].decode("utf-8", "replace")
            raise SmokeError(f"服務回應不是 JSON：{preview}") from json_error
        if not isinstance(value, dict):
            raise SmokeError("服務回應 JSON 必須是物件")
        return value

    @staticmethod
    def _multipart(form: dict, files: dict) -> tuple[bytes, str]:
        boundary = f"----calibration-smoke-{uuid4().hex}"
        chunks: list[bytes] = []

        def append(value: str) -> None:
            chunks.append(value.encode("utf-8"))

        for name, value in form.items():
            append(f"--{boundary}\r\n")
            append(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            )
            append(f"{value}\r\n")
        for name, (filename, content, mime_type) in files.items():
            append(f"--{boundary}\r\n")
            append(
                "Content-Disposition: form-data; "
                f'name="{name}"; filename="{filename}"\r\n'
            )
            append(f"Content-Type: {mime_type}\r\n\r\n")
            chunks.append(content)
            append("\r\n")
        append(f"--{boundary}--\r\n")
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _expect(
    response: tuple[int, dict],
    wanted: int | tuple[int, ...],
    step: str,
) -> dict:
    """驗證 HTTP status，錯誤只輸出安全 envelope，不含認證資料。"""
    status, body = response
    wanted_statuses = (wanted,) if isinstance(wanted, int) else wanted
    if status not in wanted_statuses:
        code = _error_code(body) or "UNKNOWN"
        raise SmokeError(
            f"{step}：預期 HTTP {wanted_statuses}，實得 {status}；"
            f"error_code={code}"
        )
    return body


def _data(body: dict, step: str) -> dict:
    value = body.get("data")
    if not isinstance(value, dict):
        raise SmokeError(f"{step}：回應缺少 data 物件")
    return value


def _error_code(body: dict) -> str | None:
    error_value = body.get("error")
    return error_value.get("code") if isinstance(error_value, dict) else None


def _request_validation(
    client,
    token: str,
    calibration_id: int,
    expected_version: int,
) -> tuple[int, dict]:
    """依正式 route 契約送出帶版本的驗證請求。"""
    return client.request(
        "POST",
        f"/api/calibrations/{calibration_id}/validate",
        token=token,
        json_body={"expected_version": expected_version},
    )


def _record_readings(
    record: dict,
    values: tuple[str, str, str],
    *,
    include_manual_result: bool = False,
) -> dict:
    """只送原始輸入；正式 result 與統計值一律由後端產生。"""
    point = record["points"][0]
    payload = {
        "point_id": point["id"],
        "reference_value": point["nominal_value"],
        "readings": [
            {"trial_no": trial, "indicated_value": value}
            for trial, value in enumerate(values, start=1)
        ],
    }
    if include_manual_result:
        payload["result"] = "pass"
    return {
        "expected_version": record["row_version"],
        "points": [payload],
    }


def _assert_backend_calculation(record: dict) -> None:
    """以手工推導 literal 核對後端結果，不在 client 重跑正式演算法。"""
    try:
        point = record["points"][0]
        decimal_expected = {
            "mean_error": Decimal("0.002"),
            "mean_correction": Decimal("-0.002"),
            "minimum_error": Decimal("0.001"),
            "maximum_error": Decimal("0.003"),
            "error_range": Decimal("0.002"),
            "sample_stddev": Decimal("0.001"),
        }
        decimal_actual = {
            name: Decimal(str(point[name]))
            for name in decimal_expected
        }
        readings = point["readings"]
        expected_readings = [
            {
                "trial_no": trial_no,
                "standard_reading": None,
                "indicated_value": Decimal(indicated),
                "effective_reference": Decimal("10"),
                "error_value": Decimal(error_value),
                "correction_value": Decimal(correction),
                "result": "pass",
            }
            for trial_no, indicated, error_value, correction in (
                (1, "10.001", "0.001", "-0.001"),
                (2, "10.002", "0.002", "-0.002"),
                (3, "10.003", "0.003", "-0.003"),
            )
        ]
        actual_readings = [{
            "trial_no": item["trial_no"],
            "standard_reading": item.get("standard_reading"),
            "indicated_value": Decimal(str(item["indicated_value"])),
            "effective_reference": Decimal(str(item["effective_reference"])),
            "error_value": Decimal(str(item["error_value"])),
            "correction_value": Decimal(str(item["correction_value"])),
            "result": item["result"],
        } for item in readings]
        legacy_empty = all(
            point.get(name) is None
            for name in (
                "average_value",
                "error_value",
                "repeatability_value",
            )
        )
        matches = (
            record.get("result") == "pass"
            and point.get("result") == "pass"
            and point.get("completed_reading_count") == 3
            and decimal_actual == decimal_expected
            and actual_readings == expected_readings
            and legacy_empty
        )
    except (
        IndexError,
        KeyError,
        TypeError,
        InvalidOperation,
    ):
        matches = False
    if not matches:
        raise SmokeError(
            "三次讀值的後端精確結果不符；"
            f"record_result={record.get('result')}"
        )


def _approved_payload(expected_version: int, reason: str) -> dict:
    return {
        "expected_version": expected_version,
        "reason": reason,
        "confirmations": {
            "raw_readings": True,
            "calculations": True,
            "reference_standard": True,
            "attachments": True,
            "template_version": True,
        },
    }


def run_smoke(
    config: SmokeConfig,
    *,
    http_client=None,
    output=print,
    now=None,
) -> dict:
    """以三個獨立 actor 跑完整校正與 MSA 資格 HTTP smoke。"""
    client = http_client or UrllibHttpClient(config.base_url)
    clock = now or (lambda: datetime.now(timezone.utc))
    current = clock()
    today = current.date()
    prefix = f"SMOKE-CAL-{current.strftime('%Y%m%dT%H%M%S')}"
    evidence = {
        "prefix": prefix,
        "base_url": config.base_url.rstrip("/"),
        "steps": [],
    }
    nonformal: dict[int, int] = {}

    def step(name: str, detail) -> None:
        evidence["steps"].append({"step": name, "detail": detail})
        output(f"  ✓ {name}：{detail}")

    def call(
        actor: str,
        method: str,
        path: str,
        *,
        json_body=None,
        form=None,
        files=None,
    ):
        return client.request(
            method,
            path,
            token=tokens[actor],
            json_body=json_body,
            form=form,
            files=files,
        )

    credentials = {
        "manager": config.manager,
        "executor": config.executor,
        "approver": config.approver,
    }
    tokens = {}
    user_ids = {}
    for actor in ("executor", "manager", "approver"):
        credential = credentials[actor]
        body = _expect(
            client.request(
                "POST",
                "/api/login",
                json_body={
                    "username": credential.username,
                    "password": credential.password,
                },
            ),
            200,
            f"{actor} 登入",
        )
        token = body.get("token")
        user_id = body.get("user_id")
        if not isinstance(token, str) or not token or not isinstance(user_id, int):
            raise SmokeError(f"{actor} 登入回應缺少 token 或 user_id")
        tokens[actor] = token
        user_ids[actor] = user_id
    if len(set(user_ids.values())) != 3:
        raise SmokeError("登入後 user_id 未保持三方職責分離")
    step("三方登入", "executor、manager、approver 為不同 user_id")

    def create_equipment(suffix: str, *, reference: bool) -> dict:
        return _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    "/api/measurement-equipment",
                    json_body={
                        "equipment_no": f"{prefix}-{suffix}",
                        "name": (
                            "smoke 參考標準器"
                            if reference
                            else "smoke 游標卡尺"
                        ),
                        "equipment_type": "游標卡尺",
                        "status": "active",
                        "calibration_type": (
                            "external" if reference else "internal"
                        ),
                        "calibration_interval_months": 12,
                        "range_min": "0",
                        "range_max": "150",
                        "resolution": "0.001",
                        "unit": "mm",
                        "is_reference_standard": reference,
                        "affects_product_decision": not reference,
                    },
                ),
                201,
                f"建立{suffix}設備",
            ),
            f"建立{suffix}設備",
        )

    target = create_equipment("EQ", reference=False)
    reference_standard = create_equipment("REF", reference=True)
    step(
        "建立設備與標準器",
        f"equipment={target['id']} reference={reference_standard['id']}",
    )

    template = _data(
        _expect(
            call(
                "manager",
                "POST",
                "/api/calibration-templates",
                json_body={
                    "template_code": f"{prefix}-TPL",
                    "name": "smoke 游標卡尺校正",
                    "equipment_type": "游標卡尺",
                    "description": "正式服務可重複 smoke 專用模板",
                },
            ),
            201,
            "建立校正模板",
        ),
        "建立校正模板",
    )
    version = _data(
        _expect(
            call(
                "manager",
                "POST",
                f"/api/calibration-templates/{template['id']}/versions",
                json_body={
                    "procedure_code": f"{prefix}-WI",
                    "procedure_name": "smoke 游標卡尺校正程序",
                    "procedure_description": "三次讀值與逐點後端重算",
                    "default_repetitions": 3,
                    "environment_requirements": {},
                    "allow_limited_use": False,
                    "revision_reason": "正式服務 smoke 初版",
                    "points": [{
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
                        "instruction": "連續量測三次",
                    }],
                },
            ),
            201,
            "建立模板版本",
        ),
        "建立模板版本",
    )
    submitted_version = _data(
        _expect(
            call(
                "manager",
                "POST",
                f"/api/calibration-template-versions/{version['id']}/submit",
                json_body={
                    "expected_version": version["row_version"],
                    "reason": "smoke 模板送審",
                },
            ),
            200,
            "送審模板版本",
        ),
        "送審模板版本",
    )
    approved_version = _data(
        _expect(
            call(
                "approver",
                "POST",
                f"/api/calibration-template-versions/{version['id']}/approve",
                json_body={
                    "expected_version": submitted_version["row_version"],
                    "reason": "smoke 模板核准",
                },
            ),
            200,
            "核准模板版本",
        ),
        "核准模板版本",
    )
    if approved_version.get("status") != "approved":
        raise SmokeError("模板版本核准後狀態不是 approved")
    step("模板工作流", f"template={template['id']} version={version['id']}")

    try:
        def create_calibration(
            equipment_id: int,
            calibration_type: str,
            *,
            reference_id: int | None = None,
        ) -> dict:
            payload = {
                "equipment_id": equipment_id,
                "template_version_id": version["id"],
                "calibration_type": calibration_type,
                "calibration_date": today.isoformat(),
            }
            if calibration_type == "internal":
                payload["reference_standard_equipment_id"] = reference_id
            else:
                payload["calibration_provider"] = "smoke 外部校正實驗室"
                payload["certificate_no"] = f"{prefix}-CERT"
            record = _data(
                _expect(
                    call(
                        "executor",
                        "POST",
                        "/api/calibrations",
                        json_body=payload,
                    ),
                    201,
                    f"建立{calibration_type}校正草稿",
                ),
                f"建立{calibration_type}校正草稿",
            )
            nonformal[record["id"]] = record["row_version"]
            return record

        # 標準器需先以正式詳細外校證據取得有效資格。
        reference_record = create_calibration(
            reference_standard["id"],
            "external",
        )
        saved_reference = _data(
            _expect(
                call(
                    "executor",
                    "PUT",
                    f"/api/calibrations/{reference_record['id']}/readings",
                    json_body=_record_readings(
                        reference_record,
                        ("10.001", "10.002", "10.003"),
                    ),
                ),
                200,
                "保存標準器讀值",
            ),
            "保存標準器讀值",
        )
        nonformal[reference_record["id"]] = saved_reference["row_version"]
        attachment = _expect(
            call(
                "manager",
                "POST",
                "/api/attachments/upload",
                form={
                    "entity_type": "equipment_calibration",
                    "entity_id": str(reference_record["id"]),
                    "purpose": "cert",
                },
                files={
                    "file": (
                        f"{prefix}-certificate.pdf",
                        b"%PDF-1.4\n% calibration smoke evidence\n",
                        "application/pdf",
                    )
                },
            ),
            201,
            "上傳標準器證書",
        )
        bound_reference = _data(
            _expect(
                call(
                    "manager",
                    "PATCH",
                    f"/api/calibrations/{reference_record['id']}",
                    json_body={
                        "expected_version": saved_reference["row_version"],
                        "certificate_attachment_id": attachment["id"],
                    },
                ),
                200,
                "綁定標準器證書",
            ),
            "綁定標準器證書",
        )
        nonformal[reference_record["id"]] = bound_reference["row_version"]
        validated_reference = _data(
            _expect(
                _request_validation(
                    client,
                    tokens["manager"],
                    reference_record["id"],
                    bound_reference["row_version"],
                ),
                200,
                "驗證標準器校正",
            ),
            "驗證標準器校正",
        )
        nonformal[reference_record["id"]] = validated_reference["row_version"]
        submitted_reference = _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    f"/api/calibrations/{reference_record['id']}/submit",
                    json_body={
                        "expected_version": validated_reference["row_version"],
                        "reason": "smoke 標準器送審",
                    },
                ),
                200,
                "送審標準器校正",
            ),
            "送審標準器校正",
        )
        nonformal.pop(reference_record["id"], None)
        approved_reference = _data(
            _expect(
                call(
                    "approver",
                    "POST",
                    f"/api/calibrations/{reference_record['id']}/approve",
                    json_body=_approved_payload(
                        submitted_reference["row_version"],
                        "smoke 標準器證據完整",
                    ),
                ),
                200,
                "核准標準器校正",
            ),
            "核准標準器校正",
        )
        if approved_reference.get("status") != "approved":
            raise SmokeError("標準器校正未進入 approved")
        step(
            "建立有效標準器",
            f"calibration={approved_reference['id']}",
        )

        internal = create_calibration(
            target["id"],
            "internal",
            reference_id=reference_standard["id"],
        )
        saved_internal = _data(
            _expect(
                call(
                    "executor",
                    "PUT",
                    f"/api/calibrations/{internal['id']}/readings",
                    json_body=_record_readings(
                        internal,
                        ("10.001", "10.002", "10.003"),
                    ),
                ),
                200,
                "保存內校三次讀值",
            ),
            "保存內校三次讀值",
        )
        nonformal[internal["id"]] = saved_internal["row_version"]
        _assert_backend_calculation(saved_internal)
        validated_internal = _data(
            _expect(
                _request_validation(
                    client,
                    tokens["manager"],
                    internal["id"],
                    saved_internal["row_version"],
                ),
                200,
                "驗證內校",
            ),
            "驗證內校",
        )
        nonformal[internal["id"]] = validated_internal["row_version"]
        submitted_internal = _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    f"/api/calibrations/{internal['id']}/submit",
                    json_body={
                        "expected_version": validated_internal["row_version"],
                        "reason": "smoke 內校送審",
                    },
                ),
                200,
                "送審內校",
            ),
            "送審內校",
        )
        nonformal.pop(internal["id"], None)
        approved_internal = _data(
            _expect(
                call(
                    "approver",
                    "POST",
                    f"/api/calibrations/{internal['id']}/approve",
                    json_body=_approved_payload(
                        submitted_internal["row_version"],
                        "smoke 內校證據完整",
                    ),
                ),
                200,
                "核准內校",
            ),
            "核准內校",
        )
        approved_hash = approved_internal.get("data_hash")
        if (
            approved_internal.get("status") != "approved"
            or not isinstance(approved_hash, str)
            or not approved_hash
        ):
            raise SmokeError("內校核准後缺少 approved 狀態或 data_hash")
        evidence["approved_calibration_id"] = approved_internal["id"]
        evidence["approved_data_hash"] = approved_hash
        step(
            "內校核准",
            f"calibration={approved_internal['id']} hash={approved_hash[:12]}",
        )

        immutable_status, immutable_body = call(
            "manager",
            "PATCH",
            f"/api/calibrations/{internal['id']}",
            json_body={
                "expected_version": approved_internal["row_version"],
                "calibration_location": "不得改寫",
            },
        )
        _expect(
            (immutable_status, immutable_body),
            409,
            "核准後不可變",
        )
        immutable_error = immutable_body.get("error")
        if (
            _error_code(immutable_body) != "CALIBRATION_STATUS_CONFLICT"
            or not isinstance(immutable_error, dict)
            or immutable_error.get("details") != {
                "calibration_id": internal["id"],
                "status": "approved",
            }
        ):
            raise SmokeError(
                "核准後不可變未回 CALIBRATION_STATUS_CONFLICT 與精確 details"
            )
        evidence["approved_immutability_status"] = immutable_status

        legacy_status, legacy_body = call(
            "manager",
            "POST",
            f"/api/measurement-equipment/{target['id']}/calibrations",
            json_body={},
        )
        _expect((legacy_status, legacy_body), 410, "舊校正端點退役")
        if _error_code(legacy_body) != "CALIBRATION_LEGACY_ENDPOINT_RETIRED":
            raise SmokeError("舊校正端點未回 CALIBRATION_LEGACY_ENDPOINT_RETIRED")
        evidence["legacy_endpoint_status"] = legacy_status
        step("不可變與退役端點", "approved write blocked；legacy=410")

        failed_draft = create_calibration(
            target["id"],
            "internal",
            reference_id=reference_standard["id"],
        )
        manual_status, manual_body = call(
            "executor",
            "PUT",
            f"/api/calibrations/{failed_draft['id']}/readings",
            json_body=_record_readings(
                failed_draft,
                ("10.100", "10.110", "10.120"),
                include_manual_result=True,
            ),
        )
        _expect((manual_status, manual_body), 422, "禁止手改 pass")
        manual_error = manual_body.get("error")
        if (
            _error_code(manual_body) != "CALIBRATION_UNKNOWN_FIELDS"
            or not isinstance(manual_error, dict)
            or manual_error.get("details") != {
                "step": "readings",
                "unknown_fields": ["result"],
            }
        ):
            raise SmokeError(
                "禁止手改 pass 未回 CALIBRATION_UNKNOWN_FIELDS 與精確 details"
            )
        evidence["manual_result_override_status"] = manual_status
        failed = _data(
            _expect(
                call(
                    "executor",
                    "PUT",
                    f"/api/calibrations/{failed_draft['id']}/readings",
                    json_body=_record_readings(
                        failed_draft,
                        ("10.100", "10.110", "10.120"),
                    ),
                ),
                200,
                "保存超差讀值",
            ),
            "保存超差讀值",
        )
        nonformal[failed["id"]] = failed["row_version"]
        if (
            failed.get("result") != "fail"
            or failed["points"][0].get("result") != "fail"
        ):
            raise SmokeError("超差讀值必須由後端判定為 fail")
        evidence["failed_result"] = failed["result"]
        step("超差判定", "手改 pass=422；後端 result=fail")

        external = create_calibration(target["id"], "external")
        saved_external = _data(
            _expect(
                call(
                    "executor",
                    "PUT",
                    f"/api/calibrations/{external['id']}/readings",
                    json_body=_record_readings(
                        external,
                        ("10.001", "10.002", "10.003"),
                    ),
                ),
                200,
                "保存外校讀值",
            ),
            "保存外校讀值",
        )
        nonformal[external["id"]] = saved_external["row_version"]
        validated_external = _data(
            _expect(
                _request_validation(
                    client,
                    tokens["manager"],
                    external["id"],
                    saved_external["row_version"],
                ),
                200,
                "驗證外校草稿",
            ),
            "驗證外校草稿",
        )
        nonformal[external["id"]] = validated_external["row_version"]
        gate_status, gate_body = call(
            "manager",
            "POST",
            f"/api/calibrations/{external['id']}/submit",
            json_body={
                "expected_version": validated_external["row_version"],
                "reason": "缺附件應被阻擋",
            },
        )
        _expect((gate_status, gate_body), 422, "外校附件門檻")
        if _error_code(gate_body) != "CALIBRATION_CERTIFICATE_REQUIRED":
            raise SmokeError("外校缺附件未回 CALIBRATION_CERTIFICATE_REQUIRED")
        evidence["external_attachment_gate_status"] = gate_status
        step("外校附件門檻", "缺證書 submit=422")

        criteria = _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    "/api/msa/criteria",
                    json_body={
                        "name": f"{prefix}-MSA準則",
                        "applicable_study_types": ["grr_anova"],
                    },
                ),
                201,
                "建立 MSA 準則",
            ),
            "建立 MSA 準則",
        )
        criteria_version = _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    f"/api/msa/criteria/{criteria['id']}/versions",
                    json_body={
                        "method_version": "MSA4-1.0",
                        "effective_date": today.isoformat(),
                        "thresholds": {
                            "grr_accept_max": 10,
                            "grr_conditional_max": 30,
                            "ndc_min": 5,
                        },
                    },
                ),
                201,
                "建立 MSA 準則版本",
            ),
            "建立 MSA 準則版本",
        )
        _expect(
            call(
                "approver",
                "POST",
                f"/api/msa/criteria/versions/{criteria_version['id']}/approve",
                json_body={
                    "expected_status": "draft",
                    "reason": "smoke MSA 準則核准",
                },
            ),
            200,
            "核准 MSA 準則版本",
        )
        study = _data(
            _expect(
                call(
                    "executor",
                    "POST",
                    "/api/msa/studies",
                    json_body={
                        "study_type": "grr_anova",
                        "measurement_purpose": "product_control",
                        "characteristic": f"{prefix}-外徑",
                        "unit": "mm",
                        "lsl": "9.5",
                        "usl": "10.5",
                        "criteria_profile_id": criteria["id"],
                    },
                ),
                201,
                "建立 MSA 研究",
            ),
            "建立 MSA 研究",
        )
        plan = _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    f"/api/msa/studies/{study['id']}/plans",
                    json_body={
                        "method_code": "MSA4_GRR_ANOVA_1_0",
                        "part_count": 3,
                        "appraiser_count": 2,
                        "trial_count": 3,
                        "random_seed": 20260730,
                        "percent_basis": "tolerance",
                        "equipment": [{
                            "equipment_id": target["id"],
                            "role": "primary_gauge",
                            "measurement_mode": "外徑",
                        }],
                        "parts": [
                            {"part_identifier": f"smoke 件-{index}"}
                            for index in range(1, 4)
                        ],
                        "appraisers": [{"name": "甲"}, {"name": "乙"}],
                    },
                ),
                201,
                "建立 MSA 計畫",
            ),
            "建立 MSA 計畫",
        )
        frozen = _data(
            _expect(
                call(
                    "manager",
                    "POST",
                    f"/api/msa/plans/{plan['id']}/freeze",
                    json_body={},
                ),
                200,
                "凍結 MSA 計畫",
            ),
            "凍結 MSA 計畫",
        )
        items = (
            (frozen.get("equipment_snapshot") or {}).get("items") or []
        )
        snapshot = next(
            (
                item.get("calibration") or {}
                for item in items
                if item.get("equipment_id") == target["id"]
            ),
            None,
        )
        if not snapshot:
            raise SmokeError("MSA 凍結快照缺少 smoke 設備資格")
        if (
            snapshot.get("record_id") != approved_internal["id"]
            or snapshot.get("data_hash") != approved_hash
            or snapshot.get("data_level") != "detailed"
        ):
            raise SmokeError(
                "MSA 資格未引用核准詳細校正 ID 與 data_hash"
            )
        evidence["msa_calibration_id"] = snapshot["record_id"]
        evidence["msa_data_hash"] = snapshot["data_hash"]
        step(
            "MSA 資格快照",
            f"record={snapshot['record_id']} hash={snapshot['data_hash'][:12]}",
        )
    except Exception:
        if not config.keep_data:
            try:
                _cleanup_nonformal(call, nonformal, output)
            except SmokeError as cleanup_error:
                output(f"  ! {cleanup_error}")
        raise

    if config.keep_data:
        step("清理政策", "依 --keep-data 保留非正式草稿")
    else:
        _cleanup_nonformal(call, nonformal, output)
        evidence["steps"].append({
            "step": "清理政策",
            "detail": "只以正式 void workflow 作廢非正式 fail／缺附件草稿",
        })
    return evidence


def _cleanup_nonformal(call, records: dict[int, int], output) -> None:
    """只作廢仍可變的 smoke 草稿；核准或已送審證據永不刪除。"""
    failures: list[str] = []
    for calibration_id, row_version in list(records.items()):
        try:
            status, body = call(
                "manager",
                "POST",
                f"/api/calibrations/{calibration_id}/void",
                json_body={
                    "expected_version": row_version,
                    "reason": "smoke cleanup：作廢非正式測試資料",
                },
            )
        except Exception as cleanup_error:
            error_type = type(cleanup_error).__name__
            failures.append(
                f"calibration={calibration_id} exception={error_type}"
            )
            output(
                "  ! 清理失敗："
                f"calibration={calibration_id} exception={error_type}"
            )
            continue
        if status != 200:
            code = _error_code(body) or "UNKNOWN"
            failures.append(
                f"calibration={calibration_id} HTTP {status} code={code}"
            )
            output(
                "  ! 清理失敗："
                f"calibration={calibration_id} HTTP {status} code={code}"
            )
            continue
        output(f"  ✓ 清理非正式資料：calibration={calibration_id}")
        records.pop(calibration_id, None)
    if failures:
        raise SmokeError(f"清理非正式資料失敗：{'；'.join(failures)}")


def _config_from_args(args: argparse.Namespace) -> SmokeConfig:
    return SmokeConfig(
        base_url=args.base_url,
        manager=ActorCredentials(args.manager_user, args.manager_password),
        executor=ActorCredentials(args.executor_user, args.executor_password),
        approver=ActorCredentials(args.approver_user, args.approver_password),
        keep_data=args.keep_data,
    )


def main(argv=None) -> int:
    args = validate_args(build_parser().parse_args(argv))
    try:
        evidence = run_smoke(_config_from_args(args))
    except SmokeError as smoke_error:
        print(f"校正 smoke 失敗：{smoke_error}", file=sys.stderr)
        return 1
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
