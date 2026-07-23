"""機械性質 migration 41 的靜態安全結構測試。"""

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "migration" / "41_harden_mechanical_constraints.sql"


def test_migration_41_is_reentrant_and_preflights_legacy_data():
    sql = MIGRATION.read_text(encoding="utf-8")

    for constraint in (
        "uq_mech_batch_seq",
        "ck_mech_batch_seq_positive",
        "ck_mech_measurement_item",
        "ck_mech_measurement_location",
        "ck_mech_measurement_sample",
    ):
        assert constraint in sql
        assert "pg_constraint" in sql
    assert 'GROUP BY "機械性質檢驗_ID", "序號"' in sql
    assert 'HAVING COUNT(*) > 1' in sql
    assert '"序號" < 1' in sql
    assert '"量測項目" NOT IN' in sql
    assert '"測量位置" NOT IN' in sql
    assert '"取樣序" NOT IN' in sql
    assert "RAISE EXCEPTION" in sql
    assert "DELETE FROM" not in sql.upper()
