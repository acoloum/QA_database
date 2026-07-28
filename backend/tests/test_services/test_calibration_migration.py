import json
import os
from decimal import Decimal
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
            "重複性上限", "參考值輸入模式", "必要重複次數", "結果"
        ) VALUES (
            :record_id, :template_point_id, 1, 'P01', '外徑',
            10, 'mm', 10, -0.02, 0.02,
            'all_readings', 'range', 0.01,
            'certified_value', 3, 'pass'
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


def _insert_template(connection):
    return connection.execute(text(
        """
        INSERT INTO "校正模板" (
            "模板代碼", "名稱", "適用設備類型"
        ) VALUES (
            :template_code, '游標卡尺', '游標卡尺'
        )
        RETURNING "識別碼"
        """
    ), {"template_code": f"CAL-{uuid4().hex}"}).scalar_one()


def _insert_template_version(
    connection,
    template_id,
    version_no,
    *,
    status="draft",
):
    return connection.execute(text(
        """
        INSERT INTO "校正模板版本" (
            "模板ID", "版本號", "程序代碼", "程序名稱",
            "預設重複次數", "環境要求", "狀態"
        ) VALUES (
            :template_id, :version_no, :procedure_code, :procedure_name,
            3, '{}'::JSONB, :status
        )
        RETURNING "識別碼"
        """
    ), {
        "template_id": template_id,
        "version_no": version_no,
        "procedure_code": f"WI-CAL-{version_no:03d}",
        "procedure_name": f"游標卡尺校正第 {version_no} 版",
        "status": status,
    }).scalar_one()


def _column_names(inspector, table_name, schema_name):
    return {
        column["name"]
        for column in inspector.get_columns(table_name, schema=schema_name)
    }


def _index_columns(inspector, table_name, schema_name):
    return {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes(table_name, schema=schema_name)
    }


def _unique_column_sets(inspector, table_name, schema_name):
    return {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(
            table_name,
            schema=schema_name,
        )
    }


def _foreign_key_targets(inspector, table_name, schema_name):
    return {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
        )
        for foreign_key in inspector.get_foreign_keys(
            table_name,
            schema=schema_name,
        )
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

    expected_table_columns = {
        "校正模板": {
            "識別碼", "模板代碼", "名稱", "適用設備類型",
            "說明", "狀態", "目前核准版本ID",
        },
        "校正模板版本": {
            "識別碼", "模板ID", "版本號", "程序代碼", "程序名稱",
            "程序說明", "預設重複次數", "環境要求", "允許限制使用",
            "狀態", "資料版本", "建立者ID", "建立時間", "核准者ID",
            "核准時間", "修訂原因", "送審者ID", "送審時間",
            "核准理由", "退回理由", "後繼版本ID",
        },
        "校正模板校正點": {
            "識別碼", "模板版本ID", "點位順序", "點位代碼",
            "量測模式", "名目值", "單位", "參考值輸入模式",
            "必要重複次數", "誤差下限", "誤差上限", "判定基礎",
            "重複性規則", "重複性上限", "資格範圍代碼",
            "資格範圍起點", "資格範圍終點", "要求不確定度",
            "必填", "操作提示",
        },
        "設備校正點": {
            "識別碼", "校驗紀錄ID", "模板校正點ID", "點位順序",
            "點位代碼", "量測模式", "名目值", "單位", "參考值",
            "誤差下限", "誤差上限", "判定基礎", "重複性規則",
            "重複性上限", "資格範圍代碼", "平均值", "誤差值",
            "重複性值", "結果", "備註", "參考值輸入模式",
            "必要重複次數", "資格範圍起點", "資格範圍終點",
            "要求不確定度", "必填", "平均器差", "平均補正值",
            "最小器差", "最大器差", "器差極差", "樣本標準差",
            "擴充不確定度", "涵蓋因子", "完整讀值數",
        },
        "設備校正原始讀值": {
            "識別碼", "設備校正點ID", "試驗序號", "器示值",
            "誤差值", "結果", "輸入者ID", "輸入時間",
            "標準器讀值", "有效參考值", "補正值", "最後修訂者ID",
            "最後修訂時間", "修訂原因",
        },
        "校正參考標準器快照": {
            "識別碼", "校驗紀錄ID", "參考標準設備ID", "設備編號",
            "名稱", "證書編號", "校驗有效期", "追溯標準", "快照資料",
            "建立時間", "型號", "序號", "量程下限", "量程上限",
            "解析度", "單位", "核准校驗紀錄ID", "校驗日期",
            "結果", "資料雜湊",
        },
    }
    for table_name, expected_columns in expected_table_columns.items():
        assert _column_names(
            inspector,
            table_name,
            schema_name,
        ) == expected_columns

    expected_record_columns = {
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
        "程序代碼",
        "程序名稱",
        "校正地點",
        "開始時間",
        "完成時間",
    }
    assert expected_record_columns <= _column_names(
        inspector,
        "設備校驗紀錄",
        schema_name,
    )

    expected_indexes = {
        "校正模板版本": {
            "idx_calibration_template_version_status": ("模板ID", "狀態"),
            "idx_calibration_template_version_successor": ("後繼版本ID",),
        },
        "校正模板校正點": {
            "idx_calibration_template_point_version": (
                "模板版本ID",
                "點位順序",
            ),
        },
        "設備校驗紀錄": {
            "idx_equipment_calibration_template_version": ("模板版本ID",),
            "idx_equipment_calibration_reference_standard": (
                "參考標準設備ID",
            ),
        },
        "設備校正點": {
            "idx_equipment_calibration_point_record": (
                "校驗紀錄ID",
                "點位順序",
            ),
        },
        "設備校正原始讀值": {
            "idx_equipment_calibration_reading_point": (
                "設備校正點ID",
                "試驗序號",
            ),
        },
        "校正參考標準器快照": {
            "idx_calibration_reference_snapshot_record": ("校驗紀錄ID",),
            "idx_calibration_reference_snapshot_approved_record": (
                "核准校驗紀錄ID",
            ),
        },
    }
    for table_name, table_indexes in expected_indexes.items():
        actual_indexes = _index_columns(
            inspector,
            table_name,
            schema_name,
        )
        for index_name, expected_columns in table_indexes.items():
            assert actual_indexes[index_name] == expected_columns

    approved_index = None
    with engine.connect() as connection:
        approved_index = connection.execute(text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = :schema_name
              AND indexname = 'uq_calibration_template_one_approved'
            """
        ), {"schema_name": schema_name}).scalar_one_or_none()
    assert approved_index is not None
    assert "CREATE UNIQUE INDEX" in approved_index
    assert '"模板ID"' in approved_index
    assert "WHERE" in approved_index
    assert "'approved'" in approved_index

    expected_unique_columns = {
        "校正模板": {("模板代碼",)},
        "校正模板版本": {("模板ID", "版本號")},
        "校正模板校正點": {
            ("模板版本ID", "點位順序"),
            ("模板版本ID", "點位代碼"),
        },
        "設備校正點": {
            ("校驗紀錄ID", "點位順序"),
            ("校驗紀錄ID", "點位代碼"),
        },
        "設備校正原始讀值": {("設備校正點ID", "試驗序號")},
        "校正參考標準器快照": {
            ("校驗紀錄ID", "參考標準設備ID"),
        },
    }
    for table_name, expected_uniques in expected_unique_columns.items():
        assert expected_uniques <= _unique_column_sets(
            inspector,
            table_name,
            schema_name,
        )

    expected_foreign_keys = {
        "校正模板": {
            (("目前核准版本ID",), "校正模板版本", ("識別碼",)),
        },
        "校正模板版本": {
            (("模板ID",), "校正模板", ("識別碼",)),
            (("建立者ID",), "使用者", ("識別碼",)),
            (("送審者ID",), "使用者", ("識別碼",)),
            (("核准者ID",), "使用者", ("識別碼",)),
            (("後繼版本ID",), "校正模板版本", ("識別碼",)),
        },
        "校正模板校正點": {
            (("模板版本ID",), "校正模板版本", ("識別碼",)),
        },
        "設備校驗紀錄": {
            (("模板版本ID",), "校正模板版本", ("識別碼",)),
            (("參考標準設備ID",), "量測設備", ("識別碼",)),
            (("送審者ID",), "使用者", ("識別碼",)),
            (("後繼紀錄ID",), "設備校驗紀錄", ("識別碼",)),
        },
        "設備校正點": {
            (("校驗紀錄ID",), "設備校驗紀錄", ("識別碼",)),
            (("模板校正點ID",), "校正模板校正點", ("識別碼",)),
        },
        "設備校正原始讀值": {
            (("設備校正點ID",), "設備校正點", ("識別碼",)),
            (("輸入者ID",), "使用者", ("識別碼",)),
            (("最後修訂者ID",), "使用者", ("識別碼",)),
        },
        "校正參考標準器快照": {
            (("校驗紀錄ID",), "設備校驗紀錄", ("識別碼",)),
            (("參考標準設備ID",), "量測設備", ("識別碼",)),
            (("核准校驗紀錄ID",), "設備校驗紀錄", ("識別碼",)),
        },
    }
    for table_name, expected_targets in expected_foreign_keys.items():
        assert expected_targets <= _foreign_key_targets(
            inspector,
            table_name,
            schema_name,
        )

    expected_check_constraints = {
        "校正模板版本": {
            "ck_calibration_template_default_repetitions",
            "ck_calibration_template_version_row_version",
            "ck_calibration_template_version_status",
        },
        "校正模板校正點": {
            "ck_calibration_template_point_repetitions",
            "ck_calibration_template_point_error_order",
            "ck_calibration_template_point_repeatability",
            "ck_calibration_template_point_qualification_range",
            "ck_calibration_template_point_reference_mode",
            "ck_calibration_template_point_evaluation_basis",
            "ck_calibration_template_point_repeatability_rule",
        },
        "設備校驗紀錄": {
            "ck_equipment_calibration_data_level",
            "ck_equipment_calibration_detailed_evidence",
            "ck_equipment_calibration_status",
            "ck_equipment_calibration_row_version",
        },
        "設備校正點": {
            "ck_equipment_calibration_point_error_order",
            "ck_equipment_calibration_point_repeatability",
            "ck_equipment_calibration_point_repetitions",
            "ck_equipment_calibration_point_completed_count",
            "ck_equipment_calibration_point_qualification_range",
            "ck_equipment_calibration_point_reference_mode",
            "ck_equipment_calibration_point_evaluation_basis",
            "ck_equipment_calibration_point_repeatability_rule",
            "ck_equipment_calibration_point_result",
            "ck_equipment_calibration_point_reference_required",
        },
        "設備校正原始讀值": {
            "ck_equipment_calibration_reading_trial",
            "ck_equipment_calibration_reading_result",
        },
    }
    for table_name, expected_constraints in expected_check_constraints.items():
        actual_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(
                table_name,
                schema=schema_name,
            )
        }
        assert expected_constraints <= actual_constraints

    jsonb_columns = {
        ("校正模板版本", "環境要求"),
        ("設備校驗紀錄", "模板快照"),
        ("設備校驗紀錄", "環境條件"),
        ("設備校驗紀錄", "計算摘要"),
        ("校正參考標準器快照", "快照資料"),
    }
    for table_name, column_name in jsonb_columns:
        columns = {
            column["name"]: column
            for column in inspector.get_columns(
                table_name,
                schema=schema_name,
            )
        }
        assert columns[column_name]["type"].__class__.__name__ == "JSONB"

    expected_defaults = {
        ("校正模板校正點", "要求不確定度"): "false",
        ("校正模板校正點", "必填"): "true",
        ("設備校正點", "要求不確定度"): "false",
        ("設備校正點", "必填"): "true",
        ("設備校正點", "完整讀值數"): "0",
    }
    for (table_name, column_name), expected_default in (
        expected_defaults.items()
    ):
        columns = {
            column["name"]: column
            for column in inspector.get_columns(
                table_name,
                schema=schema_name,
            )
        }
        column = columns[column_name]
        assert column["nullable"] is False
        assert str(column["default"]).lower() == expected_default


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


def test_database_rejects_non_positive_required_repetitions(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "校正模板校正點" (
                    "模板版本ID", "點位順序", "點位代碼", "量測模式",
                    "名目值", "單位", "參考值輸入模式", "必要重複次數",
                    "判定基礎", "必填"
                ) VALUES (
                    :version_id, 2, 'P02', '外徑', 20, 'mm',
                    'certified_value', 0, 'all_readings', TRUE
                )
                """
            ), {"version_id": evidence["version_id"]})
        connection.rollback()


@pytest.mark.parametrize("rule", ["range", "stddev"])
@pytest.mark.parametrize("limit", [None, -0.001])
def test_database_rejects_invalid_template_repeatability_limit(
    migrated_postgresql,
    rule,
    limit,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "校正模板校正點" (
                    "模板版本ID", "點位順序", "點位代碼", "量測模式",
                    "名目值", "單位", "參考值輸入模式", "必要重複次數",
                    "判定基礎", "重複性規則", "重複性上限", "必填"
                ) VALUES (
                    :version_id, 2, 'P02', '外徑', 20, 'mm',
                    'certified_value', 3, 'all_readings',
                    :rule, :limit, TRUE
                )
                """
            ), {
                "version_id": evidence["version_id"],
                "rule": rule,
                "limit": limit,
            })
        connection.rollback()


@pytest.mark.parametrize("rule", ["range", "stddev"])
@pytest.mark.parametrize("limit", [None, -0.001])
def test_database_rejects_invalid_actual_point_repeatability_limit(
    migrated_postgresql,
    rule,
    limit,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                UPDATE "設備校正點"
                SET "重複性規則" = :rule,
                    "重複性上限" = :limit
                WHERE "識別碼" = :point_id
                """
            ), {
                "point_id": evidence["point_id"],
                "rule": rule,
                "limit": limit,
            })
        connection.rollback()


@pytest.mark.parametrize("missing_evidence", ["template_version", "snapshot"])
def test_database_rejects_incomplete_detailed_record(
    migrated_postgresql,
    missing_evidence,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        template_version_id = (
            None
            if missing_evidence == "template_version"
            else evidence["version_id"]
        )
        template_snapshot = (
            None
            if missing_evidence == "snapshot"
            else '{"version_no": 1}'
        )
        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "設備校驗紀錄" (
                    "設備ID", "校驗類型", "校驗日期", "結果", "狀態",
                    "模板版本ID", "資料等級", "模板快照"
                ) VALUES (
                    1, 'internal', DATE '2026-07-28', 'pending', 'draft',
                    :template_version_id, 'detailed',
                    CAST(:template_snapshot AS JSONB)
                )
                """
            ), {
                "template_version_id": template_version_id,
                "template_snapshot": template_snapshot,
            })
        connection.rollback()


@pytest.mark.parametrize(
    ("column_name", "invalid_value"),
    [
        ("資料等級", "unknown"),
        ("狀態", "unknown"),
        ("資料版本", 0),
    ],
)
def test_database_rejects_invalid_record_invariant(
    migrated_postgresql,
    column_name,
    invalid_value,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        statements = {
            "資料等級": (
                'UPDATE "設備校驗紀錄" SET "資料等級" = :invalid_value '
                'WHERE "識別碼" = :record_id'
            ),
            "狀態": (
                'UPDATE "設備校驗紀錄" SET "狀態" = :invalid_value '
                'WHERE "識別碼" = :record_id'
            ),
            "資料版本": (
                'UPDATE "設備校驗紀錄" SET "資料版本" = :invalid_value '
                'WHERE "識別碼" = :record_id'
            ),
        }
        with pytest.raises(IntegrityError):
            connection.execute(
                text(statements[column_name]),
                {
                    "invalid_value": invalid_value,
                    "record_id": evidence["record_id"],
                },
            )
        connection.rollback()


def test_database_rejects_unknown_template_version_status(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                UPDATE "校正模板版本"
                SET "狀態" = 'unknown'
                WHERE "識別碼" = :version_id
                """
            ), {"version_id": evidence["version_id"]})
        connection.rollback()


def test_database_rejects_reversed_template_qualification_range(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                UPDATE "校正模板校正點"
                SET "資格範圍起點" = 150,
                    "資格範圍終點" = 0
                WHERE "識別碼" = :template_point_id
                """
            ), {"template_point_id": evidence["template_point_id"]})
        connection.rollback()


@pytest.mark.parametrize(
    ("column_name", "invalid_value"),
    [
        ("參考值輸入模式", "unknown"),
        ("判定基礎", "unknown"),
        ("重複性規則", "unknown"),
    ],
)
def test_database_rejects_unknown_template_point_rule(
    migrated_postgresql,
    column_name,
    invalid_value,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()
        statements = {
            "參考值輸入模式": (
                'UPDATE "校正模板校正點" '
                'SET "參考值輸入模式" = :value WHERE "識別碼" = :point_id'
            ),
            "判定基礎": (
                'UPDATE "校正模板校正點" '
                'SET "判定基礎" = :value WHERE "識別碼" = :point_id'
            ),
            "重複性規則": (
                'UPDATE "校正模板校正點" '
                'SET "重複性規則" = :value WHERE "識別碼" = :point_id'
            ),
        }

        with pytest.raises(IntegrityError):
            connection.execute(text(statements[column_name]), {
                "value": invalid_value,
                "point_id": evidence["template_point_id"],
            })
        connection.rollback()


@pytest.mark.parametrize("status", ["in_progress", "ready_for_submission"])
def test_database_accepts_calibration_execution_status(
    migrated_postgresql,
    status,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.execute(text(
            """
            UPDATE "設備校驗紀錄"
            SET "狀態" = :status
            WHERE "識別碼" = :record_id
            """
        ), {"record_id": evidence["record_id"], "status": status})
        connection.commit()

        actual_status = connection.execute(text(
            """
            SELECT "狀態"
            FROM "設備校驗紀錄"
            WHERE "識別碼" = :record_id
            """
        ), {"record_id": evidence["record_id"]}).scalar_one()
        assert actual_status == status


@pytest.mark.parametrize(
    ("column_name", "invalid_value"),
    [
        ("必要重複次數", 0),
        ("完整讀值數", -1),
        ("完整讀值數", 4),
    ],
)
def test_database_rejects_invalid_actual_point_count(
    migrated_postgresql,
    column_name,
    invalid_value,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()
        statements = {
            "必要重複次數": (
                'UPDATE "設備校正點" SET "必要重複次數" = :value '
                'WHERE "識別碼" = :point_id'
            ),
            "完整讀值數": (
                'UPDATE "設備校正點" SET "完整讀值數" = :value '
                'WHERE "識別碼" = :point_id'
            ),
        }

        with pytest.raises(IntegrityError):
            connection.execute(text(statements[column_name]), {
                "value": invalid_value,
                "point_id": evidence["point_id"],
            })
        connection.rollback()


def test_database_rejects_reversed_actual_qualification_range(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                UPDATE "設備校正點"
                SET "資格範圍起點" = 150,
                    "資格範圍終點" = 0
                WHERE "識別碼" = :point_id
                """
            ), {"point_id": evidence["point_id"]})
        connection.rollback()


@pytest.mark.parametrize(
    ("column_name", "invalid_value"),
    [
        ("參考值輸入模式", "unknown"),
        ("判定基礎", "unknown"),
        ("重複性規則", "unknown"),
        ("結果", "unknown"),
    ],
)
def test_database_rejects_unknown_actual_point_rule(
    migrated_postgresql,
    column_name,
    invalid_value,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()
        statements = {
            "參考值輸入模式": (
                'UPDATE "設備校正點" SET "參考值輸入模式" = :value '
                'WHERE "識別碼" = :point_id'
            ),
            "判定基礎": (
                'UPDATE "設備校正點" SET "判定基礎" = :value '
                'WHERE "識別碼" = :point_id'
            ),
            "重複性規則": (
                'UPDATE "設備校正點" SET "重複性規則" = :value '
                'WHERE "識別碼" = :point_id'
            ),
            "結果": (
                'UPDATE "設備校正點" SET "結果" = :value '
                'WHERE "識別碼" = :point_id'
            ),
        }

        with pytest.raises(IntegrityError):
            connection.execute(text(statements[column_name]), {
                "value": invalid_value,
                "point_id": evidence["point_id"],
            })
        connection.rollback()


def test_database_allows_paired_point_without_fixed_reference(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.execute(text(
            """
            UPDATE "設備校正點"
            SET "參考值輸入模式" = 'paired_reading',
                "參考值" = NULL
            WHERE "識別碼" = :point_id
            """
        ), {"point_id": evidence["point_id"]})
        connection.commit()


def test_database_requires_fixed_reference_for_certified_value(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                UPDATE "設備校正點"
                SET "參考值" = NULL
                WHERE "識別碼" = :point_id
                """
            ), {"point_id": evidence["point_id"]})
        connection.rollback()


def test_database_allows_empty_draft_reading_placeholder(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        reading_id = connection.execute(text(
            """
            INSERT INTO "設備校正原始讀值" (
                "設備校正點ID", "試驗序號"
            ) VALUES (:point_id, 2)
            RETURNING "識別碼"
            """
        ), {"point_id": evidence["point_id"]}).scalar_one()
        connection.commit()

        reading = connection.execute(text(
            """
            SELECT "器示值", "結果"
            FROM "設備校正原始讀值"
            WHERE "識別碼" = :reading_id
            """
        ), {"reading_id": reading_id}).one()
        assert reading == (None, "pending")


def test_database_rejects_unknown_reading_result(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "設備校正原始讀值" (
                    "設備校正點ID", "試驗序號", "結果"
                ) VALUES (:point_id, 2, 'unknown')
                """
            ), {"point_id": evidence["point_id"]})
        connection.rollback()


def test_reference_snapshot_persists_complete_jsonb_and_normalized_evidence(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        snapshot_data = {
            "schema_version": 1,
            "source": "calibration_submission",
            "qualification": {"usable": True, "blockers": []},
        }
        snapshot_id = connection.execute(text(
            """
            INSERT INTO "校正參考標準器快照" (
                "校驗紀錄ID", "參考標準設備ID", "核准校驗紀錄ID",
                "設備編號", "名稱", "型號", "序號",
                "量程下限", "量程上限", "解析度", "單位",
                "校驗日期", "校驗有效期", "結果", "證書編號",
                "資料雜湊", "快照資料"
            ) VALUES (
                :record_id, 1, 1, 'LEGACY-EQ', '參考標準器',
                'REF-100', 'SN-001', 0, 150, 0.01, 'mm',
                DATE '2026-01-02', DATE '2027-01-02', 'pass',
                'CERT-001', :data_hash, CAST(:snapshot_data AS JSONB)
            )
            RETURNING "識別碼"
            """
        ), {
            "record_id": evidence["record_id"],
            "data_hash": "a" * 64,
            "snapshot_data": json.dumps(snapshot_data),
        }).scalar_one()
        connection.commit()

        snapshot = connection.execute(text(
            """
            SELECT "核准校驗紀錄ID", "型號", "序號", "量程下限",
                   "量程上限", "解析度", "單位", "校驗日期",
                   "校驗有效期", "結果", "資料雜湊", "快照資料"
            FROM "校正參考標準器快照"
            WHERE "識別碼" = :snapshot_id
            """
        ), {"snapshot_id": snapshot_id}).one()
        assert snapshot[0] == 1
        assert snapshot[1:7] == (
            "REF-100",
            "SN-001",
            Decimal("0"),
            Decimal("150"),
            Decimal("0.01"),
            "mm",
        )
        assert snapshot[9] == "pass"
        assert snapshot[10] == "a" * 64
        assert snapshot[11] == snapshot_data


def test_reference_snapshot_rejects_unknown_approved_record(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "校正參考標準器快照" (
                    "校驗紀錄ID", "參考標準設備ID",
                    "核准校驗紀錄ID", "設備編號", "名稱",
                    "校驗日期", "結果", "快照資料"
                ) VALUES (
                    :record_id, 1, 999999, 'LEGACY-EQ',
                    '參考標準器', DATE '2026-01-02', 'pass', '{}'::JSONB
                )
                """
            ), {"record_id": evidence["record_id"]})
        connection.rollback()


@pytest.mark.parametrize(
    "status",
    ["submitted", "rejected", "approved", "superseded"],
)
def test_database_blocks_new_point_in_controlled_template_version(
    migrated_postgresql,
    status,
):
    with _connect(migrated_postgresql) as connection:
        template_id = _insert_template(connection)
        version_id = _insert_template_version(
            connection,
            template_id,
            1,
            status=status,
        )
        connection.commit()

        with pytest.raises(DBAPIError, match="模板校正點"):
            connection.execute(text(
                """
                INSERT INTO "校正模板校正點" (
                    "模板版本ID", "點位順序", "點位代碼", "量測模式",
                    "名目值", "單位", "參考值輸入模式", "必要重複次數",
                    "判定基礎", "重複性規則"
                ) VALUES (
                    :version_id, 1, 'P01', '外徑', 10, 'mm',
                    'certified_value', 3, 'all_readings', 'none'
                )
                """
            ), {"version_id": version_id})
        connection.rollback()


def test_database_allows_new_point_in_draft_template_version(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        template_id = _insert_template(connection)
        version_id = _insert_template_version(connection, template_id, 1)

        point_id = connection.execute(text(
            """
            INSERT INTO "校正模板校正點" (
                "模板版本ID", "點位順序", "點位代碼", "量測模式",
                "名目值", "單位", "參考值輸入模式", "必要重複次數",
                "判定基礎", "重複性規則"
            ) VALUES (
                :version_id, 1, 'P01', '外徑', 10, 'mm',
                'certified_value', 3, 'all_readings', 'none'
            )
            RETURNING "識別碼"
            """
        ), {"version_id": version_id}).scalar_one()
        connection.commit()

        assert point_id is not None


def test_database_rejects_two_approved_versions_in_same_transaction(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        template_id = _insert_template(connection)

        with pytest.raises(IntegrityError):
            connection.execute(text(
                """
                INSERT INTO "校正模板版本" (
                    "模板ID", "版本號", "程序代碼", "程序名稱",
                    "預設重複次數", "環境要求", "狀態"
                ) VALUES
                    (
                        :template_id, 1, 'WI-CAL-001', '第一版',
                        3, '{}'::JSONB, 'approved'
                    ),
                    (
                        :template_id, 2, 'WI-CAL-002', '第二版',
                        3, '{}'::JSONB, 'approved'
                    )
                """
            ), {"template_id": template_id})
        connection.rollback()


def test_database_rejects_two_approved_versions_across_transactions(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as first_connection:
        template_id = _insert_template(first_connection)
        _insert_template_version(
            first_connection,
            template_id,
            1,
            status="approved",
        )
        first_connection.commit()

    with _connect(migrated_postgresql) as second_connection:
        with pytest.raises(IntegrityError):
            _insert_template_version(
                second_connection,
                template_id,
                2,
                status="approved",
            )
        second_connection.rollback()


@pytest.mark.parametrize("status", ["approved", "superseded"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_database_blocks_frozen_template_version_changes(
    migrated_postgresql,
    status,
    operation,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        connection.execute(text(
            """
            UPDATE "校正模板版本"
            SET "狀態" = :status
            WHERE "識別碼" = :version_id
            """
        ), {"status": status, "version_id": evidence["version_id"]})
        connection.commit()
        statements = {
            "update": (
                'UPDATE "校正模板版本" '
                'SET "程序名稱" = \'嘗試改寫受控版本\' '
                'WHERE "識別碼" = :version_id'
            ),
            "delete": (
                'DELETE FROM "校正模板版本" '
                'WHERE "識別碼" = :version_id'
            ),
        }

        with pytest.raises(DBAPIError, match="校正模板版本"):
            connection.execute(
                text(statements[operation]),
                {"version_id": evidence["version_id"]},
            )
        connection.rollback()


def test_database_allows_controlled_template_version_supersession(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        template_id = _insert_template(connection)
        version_id = _insert_template_version(
            connection,
            template_id,
            1,
            status="approved",
        )
        successor_id = _insert_template_version(
            connection,
            template_id,
            2,
            status="submitted",
        )
        connection.commit()

        # 受控核准使用單一交易：先讓舊版離開 approved，再核准新版。
        connection.execute(text(
            """
            UPDATE "校正模板版本"
            SET "狀態" = 'superseded',
                "後繼版本ID" = :successor_id,
                "資料版本" = "資料版本" + 1
            WHERE "識別碼" = :version_id
            """
        ), {
            "version_id": version_id,
            "successor_id": successor_id,
        })
        connection.execute(text(
            """
            UPDATE "校正模板版本"
            SET "狀態" = 'approved',
                "資料版本" = "資料版本" + 1
            WHERE "識別碼" = :successor_id
            """
        ), {"successor_id": successor_id})
        connection.execute(text(
            """
            UPDATE "校正模板"
            SET "目前核准版本ID" = :successor_id
            WHERE "識別碼" = :template_id
            """
        ), {
            "successor_id": successor_id,
            "template_id": template_id,
        })
        connection.commit()

        version = connection.execute(text(
            """
            SELECT "狀態", "後繼版本ID", "資料版本"
            FROM "校正模板版本"
            WHERE "識別碼" = :version_id
            """
        ), {"version_id": version_id}).one()
        assert version == ("superseded", successor_id, 2)
        assert connection.execute(text(
            """
            SELECT "狀態"
            FROM "校正模板版本"
            WHERE "識別碼" = :successor_id
            """
        ), {"successor_id": successor_id}).scalar_one() == "approved"
        assert connection.execute(text(
            """
            SELECT "目前核准版本ID"
            FROM "校正模板"
            WHERE "識別碼" = :template_id
            """
        ), {"template_id": template_id}).scalar_one() == successor_id


@pytest.mark.parametrize(
    ("case_name", "row_version_expression", "expected_message"),
    [
        ("self", '"資料版本" + 1', "後繼版本"),
        ("cross_template", '"資料版本" + 1', "後繼版本"),
        ("backward", '"資料版本" + 1', "後繼版本"),
        ("row_version_unchanged", '"資料版本"', "資料版本"),
        ("row_version_jump", '"資料版本" + 2', "資料版本"),
    ],
)
def test_database_rejects_invalid_template_successor(
    migrated_postgresql,
    case_name,
    row_version_expression,
    expected_message,
):
    with _connect(migrated_postgresql) as connection:
        template_id = _insert_template(connection)
        if case_name == "backward":
            successor_id = _insert_template_version(
                connection,
                template_id,
                1,
                status="submitted",
            )
            old_id = _insert_template_version(
                connection,
                template_id,
                2,
                status="approved",
            )
        else:
            old_id = _insert_template_version(
                connection,
                template_id,
                1,
                status="approved",
            )
            if case_name == "self":
                successor_id = old_id
            elif case_name == "cross_template":
                other_template_id = _insert_template(connection)
                successor_id = _insert_template_version(
                    connection,
                    other_template_id,
                    2,
                    status="submitted",
                )
            else:
                successor_id = _insert_template_version(
                    connection,
                    template_id,
                    2,
                    status="submitted",
                )
        connection.commit()

        with pytest.raises(DBAPIError, match=expected_message):
            connection.execute(text(
                f"""
                UPDATE "校正模板版本"
                SET "狀態" = 'superseded',
                    "後繼版本ID" = :successor_id,
                    "資料版本" = {row_version_expression}
                WHERE "識別碼" = :old_id
                """
            ), {
                "successor_id": successor_id,
                "old_id": old_id,
            })
        connection.rollback()


def test_database_rejects_two_version_successor_cycle(
    migrated_postgresql,
):
    with _connect(migrated_postgresql) as connection:
        template_id = _insert_template(connection)
        old_id = _insert_template_version(
            connection,
            template_id,
            1,
            status="approved",
        )
        successor_id = _insert_template_version(
            connection,
            template_id,
            2,
            status="submitted",
        )
        connection.commit()

        connection.execute(text(
            """
            UPDATE "校正模板版本"
            SET "狀態" = 'superseded',
                "後繼版本ID" = :successor_id,
                "資料版本" = "資料版本" + 1
            WHERE "識別碼" = :old_id
            """
        ), {"successor_id": successor_id, "old_id": old_id})
        connection.execute(text(
            """
            UPDATE "校正模板版本"
            SET "狀態" = 'approved'
            WHERE "識別碼" = :successor_id
            """
        ), {"successor_id": successor_id})
        connection.commit()

        with pytest.raises(DBAPIError, match="後繼版本"):
            connection.execute(text(
                """
                UPDATE "校正模板版本"
                SET "狀態" = 'superseded',
                    "後繼版本ID" = :old_id,
                    "資料版本" = "資料版本" + 1
                WHERE "識別碼" = :successor_id
                """
            ), {
                "old_id": old_id,
                "successor_id": successor_id,
            })
        connection.rollback()


@pytest.mark.parametrize(
    "status",
    ["submitted", "approved", "rejected", "superseded"],
)
@pytest.mark.parametrize("operation", ["update", "reparent", "delete"])
def test_database_blocks_controlled_template_point_changes(
    migrated_postgresql,
    status,
    operation,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        target_template_id = connection.execute(text(
            """
            INSERT INTO "校正模板" ("模板代碼", "名稱", "適用設備類型")
            VALUES (:template_code, '重掛目標模板', '游標卡尺')
            RETURNING "識別碼"
            """
        ), {"template_code": f"TARGET-{uuid4().hex}"}).scalar_one()
        target_version_id = connection.execute(text(
            """
            INSERT INTO "校正模板版本" (
                "模板ID", "版本號", "程序代碼", "程序名稱",
                "預設重複次數", "環境要求", "狀態"
            ) VALUES (
                :template_id, 1, 'WI-TARGET', '重掛目標程序',
                3, '{}'::JSONB, 'draft'
            )
            RETURNING "識別碼"
            """
        ), {"template_id": target_template_id}).scalar_one()
        connection.execute(text(
            """
            UPDATE "校正模板版本"
            SET "狀態" = :status
            WHERE "識別碼" = :version_id
            """
        ), {"status": status, "version_id": evidence["version_id"]})
        connection.commit()
        statements = {
            "update": (
                'UPDATE "校正模板校正點" '
                'SET "操作提示" = \'嘗試改寫受控校正點\' '
                'WHERE "識別碼" = :point_id'
            ),
            "reparent": (
                'UPDATE "校正模板校正點" '
                'SET "模板版本ID" = :target_version_id '
                'WHERE "識別碼" = :point_id'
            ),
            "delete": (
                'DELETE FROM "校正模板校正點" '
                'WHERE "識別碼" = :point_id'
            ),
        }

        with pytest.raises(DBAPIError, match="模板校正點"):
            connection.execute(text(statements[operation]), {
                "point_id": evidence["template_point_id"],
                "target_version_id": target_version_id,
            })
        connection.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
@pytest.mark.parametrize("operation", ["update", "reparent", "delete"])
def test_database_trigger_blocks_frozen_point_changes(
    migrated_postgresql,
    status,
    operation,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        if operation == "delete":
            connection.execute(text(
                """
                DELETE FROM "設備校正原始讀值"
                WHERE "識別碼" = :reading_id
                """
            ), {"reading_id": evidence["reading_id"]})
        connection.execute(text(
            """
            UPDATE "設備校驗紀錄"
            SET "狀態" = :status
            WHERE "識別碼" = :record_id
            """
        ), {"record_id": evidence["record_id"], "status": status})
        destination_record_id = connection.execute(text(
            """
            INSERT INTO "設備校驗紀錄" (
                "設備ID", "校驗類型", "校驗日期", "結果", "狀態"
            ) VALUES (
                1, 'internal', DATE '2026-07-28', 'pending', 'draft'
            )
            RETURNING "識別碼"
            """
        )).scalar_one()
        connection.commit()

        statements = {
            "update": (
                'UPDATE "設備校正點" SET "備註" = \'嘗試改寫\' '
                'WHERE "識別碼" = :point_id'
            ),
            "reparent": (
                'UPDATE "設備校正點" SET "校驗紀錄ID" = :destination_id '
                'WHERE "識別碼" = :point_id'
            ),
            "delete": (
                'DELETE FROM "設備校正點" WHERE "識別碼" = :point_id'
            ),
        }
        with pytest.raises(DBAPIError, match="校正點不可"):
            connection.execute(text(statements[operation]), {
                "point_id": evidence["point_id"],
                "destination_id": destination_record_id,
            })
        connection.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
def test_database_trigger_blocks_point_reparent_into_frozen_record(
    migrated_postgresql,
    status,
):
    with _connect(migrated_postgresql) as connection:
        evidence = _insert_detailed_evidence(connection)
        destination_record_id = connection.execute(text(
            """
            INSERT INTO "設備校驗紀錄" (
                "設備ID", "校驗類型", "校驗日期", "結果", "狀態"
            ) VALUES (
                1, 'internal', DATE '2026-07-28', 'pending', :status
            )
            RETURNING "識別碼"
            """
        ), {"status": status}).scalar_one()
        connection.commit()

        with pytest.raises(DBAPIError, match="校正點不可"):
            connection.execute(text(
                """
                UPDATE "設備校正點"
                SET "校驗紀錄ID" = :destination_id
                WHERE "識別碼" = :point_id
                """
            ), {
                "point_id": evidence["point_id"],
                "destination_id": destination_record_id,
            })
        connection.rollback()


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
