"""時間模型不可變後繼版本的 PostgreSQL 並發整合測試。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest


TEMP_DATABASE_PREFIX = "codex_spc_time_"
RUNNER = Path(__file__).with_name("spc_time_model_concurrency_runner.py")
REPO_ROOT = Path(__file__).resolve().parents[3]


def _required_environment() -> dict[str, str]:
    required = (
        "SPC_POSTGRES_INTEGRATION",
        "SPC_PSQL_PATH",
        "SPC_PG_HOST",
        "SPC_PG_PORT",
        "SPC_PG_USER",
        "SPC_PG_PASSWORD",
    )
    if any(not os.environ.get(name) for name in required):
        pytest.skip("未設定 PostgreSQL SPC 並發整合測試環境")
    return {
        "PGHOST": os.environ["SPC_PG_HOST"],
        "PGPORT": os.environ["SPC_PG_PORT"],
        "PGUSER": os.environ["SPC_PG_USER"],
        "PGPASSWORD": os.environ["SPC_PG_PASSWORD"],
        "PGCLIENTENCODING": "UTF8",
    }


def _psql(environment: dict[str, str], database: str, sql: str) -> None:
    result = subprocess.run(
        [
            os.environ["SPC_PSQL_PATH"],
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-Atq",
            "-d",
            database,
        ],
        input=sql,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env={**os.environ, **environment},
        check=False,
    )
    if result.returncode:
        safe_error = result.stderr.replace(environment["PGPASSWORD"], "***")
        raise AssertionError(safe_error)


def test_two_sessions_create_only_one_time_model_successor():
    environment = _required_environment()
    database = f"{TEMP_DATABASE_PREFIX}{uuid.uuid4().hex}"
    _psql(environment, "postgres", f'CREATE DATABASE "{database}";')
    try:
        runner_environment = {
            **os.environ,
            "DB_HOST": os.environ["SPC_PG_HOST"],
            "DB_PORT": os.environ["SPC_PG_PORT"],
            "DB_USER": os.environ["SPC_PG_USER"],
            "DB_PASSWORD": os.environ["SPC_PG_PASSWORD"],
            "DB_NAME": database,
            "SECRET_KEY": os.environ.get("SECRET_KEY") or "integration-only-secret",
            "PYTHONPATH": os.pathsep.join(filter(None, (
                str(REPO_ROOT), os.environ.get("PYTHONPATH"),
            ))),
        }
        result = subprocess.run(
            [sys.executable, str(RUNNER)],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=runner_environment,
            check=False,
            timeout=60,
        )
        safe_error = result.stderr.replace(environment["PGPASSWORD"], "***")
        assert result.returncode == 0, safe_error
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert sorted(item["status"] for item in payload["outcomes"]) == [
            "confirmed", "conflict",
        ]
        loser = next(
            item for item in payload["outcomes"] if item["status"] == "conflict"
        )
        assert loser["code"] == "SPC_TIME_MODEL_CONFIRM_CONFLICT"
        assert payload["version_count"] == 2
        assert payload["successor_count"] == 1
        assert payload["audit_count"] == 1
        assert payload["original_status"] == "superseded"
    finally:
        assert database.startswith(TEMP_DATABASE_PREFIX)
        _psql(
            environment,
            "postgres",
            f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE);',
        )
