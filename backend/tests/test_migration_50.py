"""Migration 50 的 PostgreSQL 可執行契約測試。"""

from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import os
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / 'migration'
    / '50_add_user_token_version.sql'
)


def _assert_disposable_database(connection) -> None:
    """阻止 migration 測試連到正式資料庫。"""
    if connection.dialect.name != 'postgresql':
        pytest.fail('TOKEN_VERSION_TEST_DATABASE_URL 必須指向 PostgreSQL')
    current_database = connection.execute(text('SELECT current_database()')).scalar_one()
    if not current_database.startswith('codex_token50_'):
        pytest.fail(
            'Migration 50 測試僅允許 codex_token50_ 前綴的隔離資料庫'
        )


@contextmanager
def _migrated_user_schema(database_url):
    """建立並於離開 context 時清理 migration 測試 schema。"""
    engine = create_engine(database_url)
    schema_name = f'token_version_migration_{uuid4().hex}'
    try:
        with engine.connect() as connection:
            _assert_disposable_database(connection)
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(text('''
                CREATE TABLE "使用者" (
                    "識別碼" SERIAL PRIMARY KEY,
                    "使用者名稱" VARCHAR(50) NOT NULL
                );
                INSERT INTO "使用者" ("使用者名稱") VALUES ('legacy-user');
            '''))
            connection.commit()

            if not MIGRATION_PATH.exists():
                pytest.fail('Migration 50 尚未建立，無法執行 PostgreSQL artifact')
            migration_sql = MIGRATION_PATH.read_text(encoding='utf-8')
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.exec_driver_sql(migration_sql)
            connection.commit()
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
        yield engine, schema_name
    finally:
        try:
            with engine.connect() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                connection.commit()
        finally:
            engine.dispose()


@pytest.fixture
def migration_schema_factory():
    """提供可在同一測試內建立多個 migration schema 的 factory。"""
    database_url = os.getenv('TOKEN_VERSION_TEST_DATABASE_URL')
    if not database_url:
        pytest.skip('未設定 TOKEN_VERSION_TEST_DATABASE_URL')

    def create_schema():
        return _migrated_user_schema(database_url)

    return create_schema


@pytest.fixture
def migrated_user_table(migration_schema_factory):
    """在明確指定的隔離 PostgreSQL database 內建立暫存 schema。"""
    with migration_schema_factory() as migrated:
        yield migrated


def _connect(migrated_user_table):
    engine, schema_name = migrated_user_table
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    return connection


def test_migration_50_backfills_default_and_constraints(migrated_user_table):
    """缺少回填、default、NOT NULL 或非負約束都會破壞版本契約。"""
    connection = _connect(migrated_user_table)
    try:
        legacy_version = connection.execute(text(
            'SELECT "憑證版本" FROM "使用者" WHERE "使用者名稱" = \'legacy-user\''
        )).scalar_one()
        assert legacy_version == 0

        columns = {column['name']: column for column in inspect(connection).get_columns('使用者')}
        token_version = columns['憑證版本']
        assert token_version['nullable'] is False
        assert str(token_version['default']).strip("'::integer") == '0'

        inserted = connection.execute(text(
            'INSERT INTO "使用者" ("使用者名稱") VALUES (\'new-user\') '
            'RETURNING "憑證版本"'
        )).scalar_one()
        assert inserted == 0

        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(text(
                    'INSERT INTO "使用者" ("使用者名稱", "憑證版本") '
                    "VALUES ('invalid-user', -1)"
                ))
    finally:
        connection.rollback()
        connection.close()


def test_migration_50_is_safe_to_run_twice(migrated_user_table):
    """缺少 conrelid 範圍的冪等檢查會在第二次執行時失敗。"""
    connection = _connect(migrated_user_table)
    try:
        migration_sql = MIGRATION_PATH.read_text(encoding='utf-8')
        connection.exec_driver_sql(migration_sql)
        connection.commit()
        assert connection.execute(text(
            'SELECT COUNT(*) FROM pg_constraint '
            "WHERE conname = 'ck_user_token_version_nonnegative' "
            "AND conrelid = '\"使用者\"'::regclass"
        )).scalar_one() == 1
    finally:
        connection.close()


@pytest.mark.parametrize('database_name', ('postgres', 'template1', 'shared_qc_test'))
def test_migration_50_guard_rejects_non_disposable_database_name(database_name):
    """只排除 qa_database 仍可能誤用 postgres、template 或共享測試資料庫。"""
    class ConnectionStub:
        class Dialect:
            name = 'postgresql'

        dialect = Dialect()

        @staticmethod
        def execute(_statement):
            class Result:
                @staticmethod
                def scalar_one():
                    return database_name

            return Result()

    with pytest.raises(pytest.fail.Exception):
        _assert_disposable_database(ConnectionStub())


def test_migration_50_schema_instances_coexist_without_deleting_each_other(
    migration_schema_factory,
):
    """固定 schema 與預先 DROP 會讓平行 fixture 刪除彼此的 migration artifact。"""
    with migration_schema_factory() as first:
        first_engine, first_schema = first
        with first_engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{first_schema}"'))
            connection.execute(text(
                'INSERT INTO "使用者" ("使用者名稱") VALUES (\'first-only\')'
            ))
            connection.commit()

        with migration_schema_factory() as second:
            second_engine, second_schema = second
            assert second_schema != first_schema
            with second_engine.connect() as connection:
                connection.execute(text(f'SET search_path TO "{second_schema}"'))
                assert connection.execute(text(
                    'SELECT COUNT(*) FROM "使用者" '
                    'WHERE "使用者名稱" = \'first-only\''
                )).scalar_one() == 0

        with first_engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{first_schema}"'))
            assert connection.execute(text(
                'SELECT COUNT(*) FROM "使用者" '
                'WHERE "使用者名稱" = \'first-only\''
            )).scalar_one() == 1
