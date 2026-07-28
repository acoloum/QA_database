import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError


MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migration"
    / "49_create_calibration_detail_registration.sql"
)


@pytest.fixture
def migrated_postgresql():
    database_url = os.getenv("CALIBRATION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("未設定 CALIBRATION_TEST_DATABASE_URL")

    engine = create_engine(database_url)
    schema_name = f"calibration_t49_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                pytest.fail("CALIBRATION_TEST_DATABASE_URL 必須指向 PostgreSQL")
            connection.execute(
                text(f'CREATE SCHEMA "{schema_name}"')
            )
            connection.commit()
            connection.execute(
                text(f'SET search_path TO "{schema_name}", public')
            )
            connection.execute(text(
                """
                CREATE TABLE "使用者" (
                    "識別碼" SERIAL PRIMARY KEY
                );
                CREATE TABLE "附件" (
                    "識別碼" SERIAL PRIMARY KEY
                );
                CREATE TABLE "量測設備" (
                    "識別碼" SERIAL PRIMARY KEY,
                    "設備編號" VARCHAR(80) NOT NULL UNIQUE
                );
                CREATE TABLE "設備校驗紀錄" (
                    "識別碼" SERIAL PRIMARY KEY,
                    "設備ID" INTEGER NOT NULL REFERENCES "量測設備"("識別碼"),
                    "校驗類型" VARCHAR(30) NOT NULL,
                    "校驗日期" DATE NOT NULL,
                    "結果" VARCHAR(30) NOT NULL,
                    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft'
                );
                CREATE TABLE "設備校驗補正點" (
                    "識別碼" SERIAL PRIMARY KEY,
                    "校驗紀錄ID" INTEGER NOT NULL
                        REFERENCES "設備校驗紀錄"("識別碼"),
                    "名目值" NUMERIC NOT NULL,
                    "器示值" NUMERIC NOT NULL
                );
                CREATE FUNCTION msa_block_approved_change()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF TG_OP = 'DELETE' OR OLD."狀態" = 'approved' THEN
                        RAISE EXCEPTION '核准的 MSA 證據不可修改或刪除';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER trg_equipment_calibration_approved_immutable
                    BEFORE UPDATE OR DELETE ON "設備校驗紀錄"
                    FOR EACH ROW
                    EXECUTE FUNCTION msa_block_approved_change();
                INSERT INTO "量測設備" ("設備編號") VALUES ('LEGACY-EQ');
                INSERT INTO "設備校驗紀錄" (
                    "設備ID", "校驗類型", "校驗日期", "結果", "狀態"
                ) VALUES (1, 'external', DATE '2026-01-02', 'pass', 'approved');
                INSERT INTO "設備校驗補正點" (
                    "校驗紀錄ID", "名目值", "器示值"
                ) VALUES (1, 10, 10.001);
                """
            ))
            connection.commit()
            migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")
            connection.exec_driver_sql(migration_sql)
            connection.commit()
        yield engine, schema_name
    finally:
        try:
            with engine.connect() as connection:
                connection.execute(text(
                    f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'
                ))
                connection.commit()
        finally:
            engine.dispose()


def _connect(migrated_postgresql):
    engine, schema_name = migrated_postgresql
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}", public'))
    return connection


def _insert_detailed_evidence(connection, *, status="draft"):
    template_id = connection.execute(text(
        """
        INSERT INTO "校正模板" (
            "模板代碼", "名稱", "適用設備類型"
        ) VALUES (
            :template_code, '游標卡尺', '游標卡尺'
        )
        RETURNING "識別碼"
        """
    ), {"template_code": f"CAL-{uuid4().hex}"}).scalar_one()
    version_id = connection.execute(text(
        """
        INSERT INTO "校正模板版本" (
            "模板ID", "版本號", "程序代碼", "程序名稱",
            "預設重複次數", "環境要求", "允許限制使用", "狀態"
        ) VALUES (
            :template_id, 1, 'WI-CAL-001', '游標卡尺內校',
            3, '{}'::jsonb, TRUE, 'draft'
        )
        RETURNING "識別碼"
        """
    ), {"template_id": template_id}).scalar_one()
    template_point_id = connection.execute(text(
        """
        INSERT INTO "校正模板校正點" (
            "模板版本ID", "點位順序", "點位代碼", "量測模式",
            "名目值", "單位", "參考值輸入模式", "必要重複次數",
            "誤差下限", "誤差上限", "判定基礎", "重複性規則",
            "重複性上限", "必填"
        ) VALUES (
            :version_id, 1, 'P01', '外徑', 10, 'mm',
            'certified_value', 3, -0.02, 0.02,
            'all_readings', 'range', 0.01, TRUE
        )
        RETURNING "識別碼"
        """
    ), {"version_id": version_id}).scalar_one()
    record_id = connection.execute(text(
        """
        INSERT INTO "設備校驗紀錄" (
            "設備ID", "校驗類型", "校驗日期", "結果", "狀態",
            "模板版本ID", "資料等級", "模板快照"
        ) VALUES (
            1, 'internal', DATE '2026-07-28', 'pass', :status,
            :version_id, 'detailed', '{"version_no": 1}'::jsonb
        )
        RETURNING "識別碼"
        """
    ), {"status": status, "version_id": version_id}).scalar_one()
    point_id = connection.execute(text(
        """
        INSERT INTO "設備校正點" (
            "校驗紀錄ID", "模板校正點ID", "點位順序", "點位代碼",
            "量測模式", "名目值", "單位", "參考值",
            "誤差下限", "誤差上限", "判定基礎", "重複性規則",
            "重複性上限", "結果"
        ) VALUES (
            :record_id, :template_point_id, 1, 'P01', '外徑',
            10, 'mm', 10, -0.02, 0.02,
            'all_readings', 'range', 0.01, 'pass'
        )
        RETURNING "識別碼"
        """
    ), {
        "record_id": record_id,
        "template_point_id": template_point_id,
    }).scalar_one()
    reading_id = connection.execute(text(
        """
        INSERT INTO "設備校正原始讀值" (
            "設備校正點ID", "試驗序號", "器示值", "誤差值", "結果"
        ) VALUES (:point_id, 1, 10.001, 0.001, 'pass')
        RETURNING "識別碼"
        """
    ), {"point_id": point_id}).scalar_one()
    return {
        "template_id": template_id,
        "version_id": version_id,
        "template_point_id": template_point_id,
        "record_id": record_id,
        "point_id": point_id,
        "reading_id": reading_id,
    }


def test_migration_creates_tables_columns_indexes_and_foreign_keys(
    migrated_postgresql,
):
    engine, schema_name = migrated_postgresql
    inspector = inspect(engine)
    expected_tables = {
        "校正模板",
        "校正模板版本",
        "校正模板校正點",
        "設備校正點",
        "設備校正原始讀值",
        "校正參考標準器快照",
    }
    assert expected_tables <= set(inspector.get_table_names(schema=schema_name))

    record_columns = {
        column["name"]
        for column in inspector.get_columns("設備校驗紀錄", schema=schema_name)
    }
    assert {
        "模板版本ID",
        "資料等級",
        "資料版本",
        "模板快照",
        "環境條件",
        "計算摘要",
        "計算版本",
        "資料雜湊",
        "參考標準設備ID",
        "送審者ID",
        "送審時間",
        "退回理由",
        "作廢理由",
        "後繼紀錄ID",
    } <= record_columns

    point_indexes = {
        index["name"]
        for index in inspector.get_indexes("設備校正點", schema=schema_name)
    }
    assert "idx_equipment_calibration_point_record" in point_indexes

    foreign_keys = inspector.get_foreign_keys(
        "設備校正原始讀值",
        schema=schema_name,
    )
    assert any(
        foreign_key["referred_table"] == "設備校正點"
        for foreign_key in foreign_keys
    )


def test_migration_preserves_legacy_data_without_creating_raw_readings(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        legacy = connection.execute(text(
            """
            SELECT "資料等級", "狀態", "結果"
            FROM "設備校驗紀錄"
            WHERE "識別碼" = 1
            """
        )).one()
        assert legacy == ("summary_legacy", "approved", "pass")
        assert connection.execute(
            text('SELECT COUNT(*) FROM "設備校正原始讀值"')
        ).scalar_one() == 0
        assert connection.execute(
            text('SELECT COUNT(*) FROM "量測設備"')
        ).scalar_one() == 1
        assert connection.execute(
            text('SELECT COUNT(*) FROM "設備校驗紀錄"')
        ).scalar_one() == 1
        assert connection.execute(
            text('SELECT COUNT(*) FROM "設備校驗補正點"')
        ).scalar_one() == 1
        trigger_enabled = connection.execute(text(
            """
            SELECT trigger.tgenabled
            FROM pg_trigger AS trigger
            JOIN pg_class AS target
              ON target.oid = trigger.tgrelid
            JOIN pg_namespace AS namespace
              ON namespace.oid = target.relnamespace
            WHERE namespace.nspname = current_schema()
              AND target.relname = '設備校驗紀錄'
              AND trigger.tgname =
                  'trg_equipment_calibration_approved_immutable'
            """
        )).scalar_one()
        assert trigger_enabled == "O"


def test_database_constraints_reject_duplicate_and_invalid_evidence(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        transaction = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "校正模板版本" (
                    "模板ID", "版本號", "程序代碼", "程序名稱",
                    "預設重複次數", "環境要求", "允許限制使用", "狀態"
                ) VALUES (
                    :template_id, 1, 'WI-CAL-002', '重複版次',
                    3, '{}'::jsonb, FALSE, 'draft'
                )
                """
            ), {"template_id": evidence["template_id"]})
        transaction.rollback()

        for statement in (
            """
            INSERT INTO "校正模板校正點" (
                "模板版本ID", "點位順序", "點位代碼", "量測模式",
                "名目值", "單位", "參考值輸入模式", "必要重複次數",
                "誤差下限", "誤差上限", "判定基礎", "重複性規則",
                "重複性上限", "必填"
            ) VALUES (
                :version_id, 2, 'P01', '外徑', 20, 'mm',
                'certified_value', 3,
                -0.02, 0.02, 'all_readings', 'range', 0.01, TRUE
            )
            """,
            """
            INSERT INTO "校正模板校正點" (
                "模板版本ID", "點位順序", "點位代碼", "量測模式",
                "名目值", "單位", "參考值輸入模式", "必要重複次數",
                "誤差下限", "誤差上限", "判定基礎", "重複性規則",
                "重複性上限", "必填"
            ) VALUES (
                :version_id, 2, 'P02', '外徑', 20, 'mm',
                'certified_value', 3,
                0.02, -0.02, 'all_readings', 'range', 0.01, TRUE
            )
            """,
        ):
            nested = connection.begin_nested()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(statement),
                    {"version_id": evidence["version_id"]},
                )
            nested.rollback()

        nested = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "設備校正原始讀值" (
                    "設備校正點ID", "試驗序號", "器示值", "結果"
                ) VALUES (:point_id, 1, 10.002, 'pass')
                """
            ), {"point_id": evidence["point_id"]})
        nested.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_database_trigger_blocks_frozen_reading_changes(
    migrated_postgresql,
    status,
    operation,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection, status=status)
        connection.commit()

        statement = (
            'UPDATE "設備校正原始讀值" SET "器示值" = 99 '
            'WHERE "識別碼" = :reading_id'
            if operation == "update"
            else (
                'DELETE FROM "設備校正原始讀值" '
                'WHERE "識別碼" = :reading_id'
            )
        )
        with pytest.raises(DBAPIError, match="原始讀值不可"):
            connection.execute(
                text(statement),
                {"reading_id": evidence["reading_id"]},
            )
        connection.rollback()
