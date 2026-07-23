"""機械性質 migration 42 的安全搬移契約測試。"""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migration"
    / "42_split_mechanical_trace_numbers.sql"
)


def test_migration_42_has_state_guards_and_transaction():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "to_regclass" in sql
    assert "新舊追溯編號資料表同時存在" in sql
    assert "新表已存在且舊表已移除" in sql


def test_migration_42_deduplicates_each_type_and_resequences():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "DISTINCT ON" in sql
    assert 'btrim("擠製編號")' in sql
    assert 'btrim("爐具編號")' in sql
    assert "ROW_NUMBER() OVER" in sql
    assert "'擠製編號'" in sql
    assert "'T4爐號'" in sql


def test_migration_42_verifies_both_directions_before_drop():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.count("EXCEPT") >= 4
    assert "distinct_count" in sql
    assert "migrated_count" in sql
    assert sql.index("EXCEPT") < sql.index('DROP TABLE "機械性質批次"')
