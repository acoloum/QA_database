"""migration ledger、結構漂移檢查與啟動前檢查的測試。

全部使用暫存目錄與 SQLite 記憶體庫，不連任何真實資料庫。
"""
import hashlib

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, text

from backend.migration import ledger, preflight, schema_check


def _write(root, name, sql="SELECT 1;"):
    path = root / name
    path.write_text(sql, encoding="utf-8")
    return path


@pytest.fixture
def migrations(tmp_path):
    _write(tmp_path, "01_create_a.sql", "CREATE TABLE a (id INTEGER);")
    _write(tmp_path, "02_add_b.sql", "CREATE TABLE b (id INTEGER);")
    _write(tmp_path, "02_add_b.rollback.sql", "DROP TABLE b;")
    _write(tmp_path, "README.md", "不是 migration")
    return tmp_path


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


def test_discover_ignores_rollback_and_non_sql(migrations):
    artifacts = ledger.discover_migrations(migrations)
    assert [a.version for a in artifacts] == [1, 2]
    expected = hashlib.sha256((migrations / "01_create_a.sql").read_bytes()).hexdigest()
    assert artifacts[0].sha256 == expected


def test_checksum_ignores_line_endings(migrations):
    """autocrlf 會讓同一支檔案在 LF／CRLF 間切換，checksum 不能因此變動。"""
    path = migrations / "01_create_a.sql"
    path.write_bytes(b"CREATE TABLE a (\r\n  id INTEGER\r\n);\r\n")
    crlf = ledger.discover_migrations(migrations)[0].sha256
    path.write_bytes(b"CREATE TABLE a (\n  id INTEGER\n);\n")
    assert ledger.discover_migrations(migrations)[0].sha256 == crlf


def test_discover_rejects_duplicate_versions(migrations):
    _write(migrations, "02_other.sql")
    with pytest.raises(ValueError, match="版本重複"):
        ledger.discover_migrations(migrations)


def test_status_is_read_only_when_ledger_missing(migrations, engine):
    artifacts = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        issues = ledger.status_issues(connection, artifacts)
        assert not inspect(connection).has_table(ledger.LEDGER_TABLE)
    assert len(issues) == 1
    assert "尚未建立" in issues[0]


def test_baseline_records_without_executing_sql(migrations, engine):
    artifacts = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        recorded = ledger.baseline(connection, artifacts, up_to=1)
        assert [a.version for a in recorded] == [1]
        # 基準只寫紀錄，不執行 SQL：表 a 不應被建立
        assert not inspect(connection).has_table("a")
        issues = ledger.status_issues(connection, artifacts)
    assert issues == ["待套用 02_add_b.sql"]


def test_baseline_is_idempotent_and_detects_checksum_drift(migrations, engine):
    artifacts = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        ledger.baseline(connection, artifacts, up_to=2)
        assert ledger.baseline(connection, artifacts, up_to=2) == []
        assert ledger.status_issues(connection, artifacts) == []

    _write(migrations, "01_create_a.sql", "CREATE TABLE a (id INTEGER, x INTEGER);")
    changed = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        assert ledger.status_issues(connection, changed) == ["checksum 不一致 01_create_a.sql"]
        with pytest.raises(ValueError, match="checksum 不一致"):
            ledger.baseline(connection, changed, up_to=2)


def test_apply_one_executes_and_records(migrations, engine):
    artifacts = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        ledger.apply_one(connection, artifacts[0], ledger.read_ledger(connection))
        assert inspect(connection).has_table("a")
        assert ledger.status_issues(connection, artifacts) == ["待套用 02_add_b.sql"]


def test_apply_one_executes_the_same_normalized_bytes_it_hashed(migrations, engine):
    """驗證與執行取自同一份正規化內容：CRLF 檔案寫入的字串值不可夾帶 \\r。"""
    # SQLite 一次只能執行一個敘述，先建表，migration 只放 INSERT
    (migrations / "03_seed.sql").write_bytes(b"INSERT INTO note VALUES ('a\r\nb');\r\n")
    artifact = ledger.discover_migrations(migrations)[-1]
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE note (body TEXT)"))
        ledger.apply_one(connection, artifact, {})
        assert connection.execute(text("SELECT body FROM note")).scalar() == "a\nb"


def test_apply_one_refuses_file_changed_after_discovery(migrations, engine):
    artifact = ledger.discover_migrations(migrations)[0]
    _write(migrations, "01_create_a.sql", "CREATE TABLE evil (id INTEGER);")
    with engine.begin() as connection:
        with pytest.raises(ValueError, match="掃描後被修改"):
            ledger.apply_one(connection, artifact, {})
        assert not inspect(connection).has_table("evil")


def test_status_reports_versions_missing_from_disk(migrations, engine):
    artifacts = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        ledger.baseline(connection, artifacts, up_to=2)
        connection.execute(text(
            f"INSERT INTO {ledger.LEDGER_TABLE} (version, name, sha256) "
            "VALUES (99, '99_gone.sql', :sha)"
        ), {"sha": "0" * 64})
        assert ledger.status_issues(connection, artifacts) == ["資料庫有檔案不存在的 migration 99"]


def _metadata():
    metadata = MetaData()
    Table("檢驗", metadata, Column("id", Integer, primary_key=True), Column("名稱", String(20)))
    Table("明細", metadata, Column("id", Integer, primary_key=True))
    return metadata


def test_schema_drift_reports_missing_tables_and_columns(engine):
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "檢驗" (id INTEGER PRIMARY KEY)'))
        issues = schema_check.find_schema_drift(connection, _metadata())
    assert issues == ["資料庫缺少資料表 明細", "資料庫缺少欄位 檢驗.名稱"]


def _indexed_metadata():
    metadata = MetaData()
    Table(
        "出貨",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("材質", String(20), index=True),
        Column("類型", String(20)),
        Column("實體ID", Integer, index=True),
    )
    return metadata


def test_schema_drift_reports_missing_index(engine):
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "出貨" (id INTEGER PRIMARY KEY, "材質" TEXT, "類型" TEXT, "實體ID" INTEGER)'))
        connection.execute(text('CREATE INDEX "ix_複合" ON "出貨" ("類型", "實體ID")'))
        issues = schema_check.find_schema_drift(connection, _indexed_metadata())
    # 實體ID 已被複合索引包含，只有材質真正缺索引
    assert issues == ["資料庫缺少索引 出貨(材質)"]


def test_schema_drift_accepts_index_with_different_name(engine):
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "出貨" (id INTEGER PRIMARY KEY, "材質" TEXT, "類型" TEXT, "實體ID" INTEGER)'))
        connection.execute(text('CREATE INDEX "idx_中文名稱" ON "出貨" ("材質")'))
        connection.execute(text('CREATE INDEX "idx_entity" ON "出貨" ("實體ID")'))
        assert schema_check.find_schema_drift(connection, _indexed_metadata()) == []


def test_schema_drift_empty_when_in_sync(engine):
    metadata = _metadata()
    with engine.begin() as connection:
        metadata.create_all(connection)
        assert schema_check.find_schema_drift(connection, metadata) == []


def test_preflight_ok_when_schema_and_ledger_in_sync(migrations, engine, capsys):
    metadata = _metadata()
    artifacts = ledger.discover_migrations(migrations)
    with engine.begin() as connection:
        metadata.create_all(connection)
        ledger.baseline(connection, artifacts, up_to=2)
    assert preflight.run(engine, metadata, migrations) == 0
    assert "通過" in capsys.readouterr().out


def test_preflight_fails_on_drift_or_pending(migrations, engine, capsys):
    metadata = _metadata()
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "檢驗" (id INTEGER PRIMARY KEY)'))
    assert preflight.run(engine, metadata, migrations) == 1
    out = capsys.readouterr().out
    assert "資料庫缺少資料表 明細" in out
    assert "尚未建立" in out
    # 啟動前檢查本身必須唯讀
    assert not inspect(engine).has_table(ledger.LEDGER_TABLE)


def _create_index_statements(path):
    import re
    pattern = re.compile(r'CREATE INDEX IF NOT EXISTS ("?)(\w+)\1\s+ON ("?)(\S+?)\3 \(("?)(\S+?)\5\);')
    return [
        (match[1], match[3], match[5], all(match[i] == '"' for i in (0, 2, 4)))
        for match in pattern.findall(path.read_text(encoding="utf-8"))
    ]


def test_migration_60_only_repeats_indexes_from_52():
    """60 只補正式庫缺的 52 索引：名稱／表／欄位與 52 相同，且識別字全部加引號。

    52 的識別字沒加引號，SPC事件、主檔ID 會被 PostgreSQL 轉成小寫而失敗；60 不可重蹈覆轍。
    """
    artifacts = {a.version: a for a in ledger.discover_migrations(ledger.Path(ledger.__file__).parent)}
    from_52 = {stmt[:3] for stmt in _create_index_statements(ledger.Path(artifacts[52].path))}
    from_60 = _create_index_statements(ledger.Path(artifacts[60].path))
    assert len(from_60) == 10
    assert {stmt[:3] for stmt in from_60} <= from_52
    assert all(quoted for *_, quoted in from_60)


def test_preflight_reports_connection_failure(migrations, capsys):
    broken = create_engine("sqlite:////nonexistent-dir/qms.db")
    assert preflight.run(broken, _metadata(), migrations) == 2
    assert "無法連線" in capsys.readouterr().out
