"""SPC migration 38 的 PostgreSQL 實際整合驗證。"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import uuid

import pytest


TEMP_DATABASE_PREFIX = "codex_spc38_"
MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "migration"
    / "38_add_spc_analysis_family.sql"
)


class _PostgresEnvironment(dict[str, str]):
    """避免 pytest 失敗訊息意外輸出連線密碼。"""

    def __repr__(self) -> str:
        safe = {
            key: ("***" if key == "PGPASSWORD" else value)
            for key, value in self.items()
        }
        return repr(safe)


def _connection_environment() -> _PostgresEnvironment:
    """僅在明確要求時讀取整合測試連線環境，不記錄密碼。"""

    required = (
        "SPC_POSTGRES_INTEGRATION",
        "SPC_PG_HOST",
        "SPC_PG_PORT",
        "SPC_PG_USER",
        "SPC_PG_PASSWORD",
    )
    if any(not os.environ.get(name) for name in required):
        pytest.skip("未設定 PostgreSQL migration 整合測試環境")
    return _PostgresEnvironment({
        "PGHOST": os.environ["SPC_PG_HOST"],
        "PGPORT": os.environ["SPC_PG_PORT"],
        "PGUSER": os.environ["SPC_PG_USER"],
        "PGPASSWORD": os.environ["SPC_PG_PASSWORD"],
        "PGCLIENTENCODING": "UTF8",
    })


def _psql(environment: _PostgresEnvironment, database: str, sql: str) -> str:
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
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def _run_migration(environment: _PostgresEnvironment, database: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            os.environ["SPC_PSQL_PATH"],
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            database,
            "-f",
            str(MIGRATION_PATH),
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env={**os.environ, **environment},
        check=False,
    )


def _drop_database(environment: _PostgresEnvironment, database: str) -> None:
    """只刪除經前綴與名稱驗證的整合測試 database。"""

    assert database.startswith(TEMP_DATABASE_PREFIX)
    _psql(
        environment,
        "postgres",
        f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE);',
    )


def _create_legacy_schema(
    environment: _PostgresEnvironment, database: str, *, limit_state: str, version_state: str
) -> None:
    """建立 migration 36 觸發器與 nullable 舊欄位的最小可驗證 schema。"""

    trigger_commands = {
        "O": "ENABLE TRIGGER",
        "A": "ENABLE ALWAYS TRIGGER",
        "R": "ENABLE REPLICA TRIGGER",
        "D": "DISABLE TRIGGER",
    }
    _psql(
        environment,
        database,
        f'''
CREATE TABLE "SPC研究" (
    "識別碼" INTEGER PRIMARY KEY,
    "資料來源" VARCHAR(20) NOT NULL,
    "研究類型" VARCHAR(30) NOT NULL,
    "分析族別" VARCHAR(20),
    "製程流識別鍵" VARCHAR(128) NOT NULL,
    "品質特性" VARCHAR(50) NOT NULL
);
ALTER TABLE "SPC研究" ADD CONSTRAINT uq_spc_study_identity
    UNIQUE ("資料來源", "研究類型", "製程流識別鍵", "品質特性");
CREATE INDEX idx_spc_study_stream_characteristic
    ON "SPC研究" ("製程流識別鍵", "品質特性");

CREATE TABLE "SPC研究版本" (
    "識別碼" INTEGER PRIMARY KEY,
    "研究ID" INTEGER NOT NULL,
    "分析選項快照" JSONB
);

CREATE TABLE "SPC界限版本" (
    "識別碼" INTEGER PRIMARY KEY,
    "研究版本ID" INTEGER NOT NULL,
    "分析族別" VARCHAR(20),
    "製程流識別鍵" VARCHAR(128) NOT NULL,
    "品質特性" VARCHAR(50) NOT NULL,
    "狀態" VARCHAR(30) NOT NULL
);
CREATE UNIQUE INDEX uq_spc_one_active_limit
    ON "SPC界限版本" ("製程流識別鍵", "品質特性")
    WHERE "狀態" = 'active';

CREATE FUNCTION spc_block_immutable_change()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'immutable evidence update blocked';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_spc_study_version_immutable
    BEFORE UPDATE ON "SPC研究版本"
    FOR EACH ROW EXECUTE FUNCTION spc_block_immutable_change();
CREATE TRIGGER trg_spc_limit_version_immutable
    BEFORE UPDATE ON "SPC界限版本"
    FOR EACH ROW EXECUTE FUNCTION spc_block_immutable_change();
ALTER TABLE "SPC研究版本"
    {trigger_commands[version_state]} trg_spc_study_version_immutable;
ALTER TABLE "SPC界限版本"
    {trigger_commands[limit_state]} trg_spc_limit_version_immutable;

INSERT INTO "SPC研究" VALUES (1, 'shipping', 'retrospective', NULL, 'stream-1', '外徑');
INSERT INTO "SPC研究版本" VALUES (1, 1, NULL);
INSERT INTO "SPC界限版本" VALUES (1, 1, NULL, 'stream-1', '外徑', 'active');
''',
    )


def _trigger_states(environment: _PostgresEnvironment, database: str) -> tuple[str, str]:
    output = _psql(
        environment,
        database,
        """
SELECT tgname || ':' || tgenabled::text
FROM pg_trigger
WHERE tgname IN ('trg_spc_limit_version_immutable', 'trg_spc_study_version_immutable')
ORDER BY tgname;
""",
    )
    return tuple(line.split(":", 1)[1] for line in output.splitlines())  # type: ignore[return-value]


def _assert_successful_migration(
    environment: _PostgresEnvironment, database: str, *, limit_state: str, version_state: str
) -> None:
    first = _run_migration(environment, database)
    assert first.returncode == 0, first.stderr
    second = _run_migration(environment, database)
    assert second.returncode == 0, second.stderr

    assert _psql(
        environment,
        database,
        """
SELECT (SELECT "分析族別" FROM "SPC研究" WHERE "識別碼" = 1)
    || '|' || (SELECT "分析選項快照"::text FROM "SPC研究版本" WHERE "識別碼" = 1)
    || '|' || (SELECT "分析族別" FROM "SPC界限版本" WHERE "識別碼" = 1);
""",
    ) == "variable|{}|variable"
    assert _trigger_states(environment, database) == (limit_state, version_state)

    _psql(
        environment,
        database,
        """
INSERT INTO "SPC研究" (
    "識別碼", "資料來源", "研究類型", "分析族別", "製程流識別鍵", "品質特性"
) VALUES (2, 'shipping', 'retrospective', 'attribute', 'stream-1', '外徑');
INSERT INTO "SPC界限版本" (
    "識別碼", "研究版本ID", "分析族別", "製程流識別鍵", "品質特性", "狀態"
) VALUES (2, 1, 'attribute', 'stream-1', '外徑', 'active');
""",
    )
    assert _psql(
        environment,
        database,
        """
SELECT pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'uq_spc_study_identity';
""",
    ) == 'UNIQUE ("資料來源", "研究類型", "分析族別", "製程流識別鍵", "品質特性")'
    assert '"分析族別", "製程流識別鍵", "品質特性"' in _psql(
        environment,
        database,
        """
SELECT pg_get_indexdef(indexrelid)
FROM pg_index
WHERE indexrelid = 'idx_spc_study_stream_characteristic'::regclass;
""",
    )


def _assert_preflight_rollback(
    environment: _PostgresEnvironment, database: str, *, limit_state: str, version_state: str
) -> None:
    _psql(
        environment,
        database,
        "UPDATE \"SPC研究\" SET \"分析族別\" = 'unsupported' WHERE \"識別碼\" = 1;",
    )
    result = _run_migration(environment, database)
    assert result.returncode != 0
    assert "不支援值" in result.stderr
    assert _trigger_states(environment, database) == (limit_state, version_state)
    assert _psql(
        environment,
        database,
        """
SELECT (SELECT "分析族別" FROM "SPC研究" WHERE "識別碼" = 1)
    || '|' || COALESCE((SELECT "分析族別" FROM "SPC界限版本" WHERE "識別碼" = 1), 'NULL')
    || '|' || COALESCE((SELECT "分析選項快照"::text FROM "SPC研究版本" WHERE "識別碼" = 1), 'NULL');
""",
    ) == "unsupported|NULL|NULL"


def test_migration_38_postgres_is_idempotent_and_preserves_trigger_states():
    environment = _connection_environment()
    database = f"{TEMP_DATABASE_PREFIX}{uuid.uuid4().hex}"
    _psql(environment, "postgres", f'CREATE DATABASE "{database}";')
    try:
        for limit_state, version_state in (("O", "A"), ("R", "D")):
            _create_legacy_schema(
                environment,
                database,
                limit_state=limit_state,
                version_state=version_state,
            )
            _assert_successful_migration(
                environment,
                database,
                limit_state=limit_state,
                version_state=version_state,
            )
            _psql(environment, database, 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;')

        _create_legacy_schema(environment, database, limit_state="A", version_state="R")
        _assert_preflight_rollback(
            environment,
            database,
            limit_state="A",
            version_state="R",
        )
    finally:
        _drop_database(environment, database)
