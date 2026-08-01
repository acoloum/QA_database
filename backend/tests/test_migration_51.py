"""Migration 51 的 PostgreSQL JSONB merge 及 rollback 契約測試。"""

from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import os
import pytest
from sqlalchemy import create_engine, text


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / 'migration'
    / '51_backfill_route_permissions.sql'
)


def _assert_disposable_database(connection) -> None:
    """只允許特定前綴的隔離 PostgreSQL DB，禁止觸碰共用/正式庫。"""
    if connection.dialect.name != 'postgresql':
        pytest.fail('ROUTE_PERMISSION_TEST_DATABASE_URL 必須指向 PostgreSQL')
    database_name = connection.execute(text('SELECT current_database()')).scalar_one()
    if not database_name.startswith('codex_permissions51_'):
        pytest.fail('Migration 51 只允許 codex_permissions51_ 前綴隔離資料庫')


@contextmanager
def _migrated_role_schema(database_url):
    engine = create_engine(database_url)
    schema_name = f'route_permissions_{uuid4().hex}'
    try:
        with engine.connect() as connection:
            _assert_disposable_database(connection)
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(text('''
                CREATE TABLE "角色" (
                    "識別碼" SERIAL PRIMARY KEY,
                    "角色代碼" VARCHAR(30) UNIQUE NOT NULL,
                    "權限" JSONB NOT NULL DEFAULT '{}'::jsonb
                );
                INSERT INTO "角色" ("角色代碼", "權限") VALUES
                    ('inspector', '{"custom.keep": true, "mechanical.view": false}'),
                    ('qa_supervisor', '{"custom.keep": true}'),
                    ('qc_manager', '{"custom.keep": true}'),
                    ('admin', '{"custom.keep": true}'),
                    ('custom_role', '{"custom.only": true}');
            '''))
            connection.commit()
            if not MIGRATION_PATH.exists():
                pytest.fail('Migration 51 尚未建立')
            connection.exec_driver_sql(MIGRATION_PATH.read_text(encoding='utf-8'))
            connection.commit()
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
    database_url = os.getenv('ROUTE_PERMISSION_TEST_DATABASE_URL')
    if not database_url:
        pytest.skip('未設定 ROUTE_PERMISSION_TEST_DATABASE_URL')

    def create_schema():
        return _migrated_role_schema(database_url)

    return create_schema


@pytest.fixture
def migration_schema(migration_schema_factory):
    with migration_schema_factory() as migrated:
        yield migrated


def _connect(migration_schema):
    engine, schema_name = migration_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    return connection


def test_migration_51_merges_role_specific_permissions_and_preserves_custom_keys(
    migration_schema,
):
    """若 migration 覆蓋整個 JSONB 或合併方向相反，自訂 key 與批准值會遺失。"""
    connection = _connect(migration_schema)
    try:
        permissions = dict(connection.execute(text(
            'SELECT "角色代碼", "權限" FROM "角色"'
        )).all())
        assert permissions['inspector']['custom.keep'] is True
        assert permissions['inspector']['mechanical.view'] is True
        assert permissions['inspector']['mechanical.create'] is True
        assert permissions['qa_supervisor']['mechanical.edit'] is True
        assert permissions['qc_manager']['analytics.view'] is True
        assert permissions['admin']['vendor.view'] is True
        assert permissions['custom_role'] == {'custom.only': True}
    finally:
        connection.close()


def test_migration_51_is_idempotent(migration_schema):
    """重跑 migration 不可發生錯誤或改壞自訂 key。"""
    connection = _connect(migration_schema)
    try:
        migration_sql = MIGRATION_PATH.read_text(encoding='utf-8')
        connection.exec_driver_sql(migration_sql)
        connection.commit()
        permissions = connection.execute(text(
            'SELECT "權限" FROM "角色" WHERE "角色代碼" = \'inspector\''
        )).scalar_one()
        assert permissions['custom.keep'] is True
        assert permissions['mechanical.view'] is True
    finally:
        connection.close()


def test_migration_51_rollback_removes_only_added_keys(migration_schema):
    """rollback 只能移除 Task 4 新 key，不可刪除角色的其他權限。"""
    connection = _connect(migration_schema)
    try:
        connection.execute(text('''
            UPDATE "角色"
            SET "權限" = "權限"
                - 'tolerance.view'
                - 'mechanical.view'
                - 'mechanical.create'
                - 'mechanical.edit'
                - 'mechanical.delete'
                - 'task.view'
                - 'analytics.view'
                - 'vendor.view'
            WHERE "角色代碼" IN ('inspector', 'qa_supervisor', 'qc_manager', 'admin')
        '''))
        connection.commit()
        permissions = connection.execute(text(
            'SELECT "權限" FROM "角色" WHERE "角色代碼" = \'inspector\''
        )).scalar_one()
        assert permissions == {'custom.keep': True}
    finally:
        connection.close()


def test_migration_51_schema_instances_coexist_without_cross_cleanup(
    migration_schema_factory,
):
    """若 fixture 使用固定 schema 或先 DROP，平行執行會刪除彼此資料。"""
    with migration_schema_factory() as first:
        first_engine, first_schema = first
        with first_engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{first_schema}"'))
            connection.execute(text(
                'INSERT INTO "角色" ("角色代碼", "權限") '
                "VALUES ('first-only', '{\"sentinel\": true}'::jsonb)"
            ))
            connection.commit()

        with migration_schema_factory() as second:
            second_engine, second_schema = second
            assert second_schema != first_schema
            with second_engine.connect() as connection:
                connection.execute(text(f'SET search_path TO "{second_schema}"'))
                assert connection.execute(text(
                    'SELECT COUNT(*) FROM "角色" '
                    'WHERE "角色代碼" = \'first-only\''
                )).scalar_one() == 0

        with first_engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{first_schema}"'))
            assert connection.execute(text(
                'SELECT "權限" FROM "角色" '
                'WHERE "角色代碼" = \'first-only\''
            )).scalar_one() == {'sentinel': True}


@pytest.mark.parametrize('database_name', ('postgres', 'template1', 'qa_database'))
def test_migration_51_guard_rejects_non_disposable_database_name(database_name):
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
