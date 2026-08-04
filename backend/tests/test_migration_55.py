"""Migration 55 與 models.py 的外鍵索引同步契約。

migration/*.sql 是手動套用的，測試庫則由 create_all() 依 models.py 建立；
兩邊若漂移，測試會全綠但正式庫缺索引。這裡把「SQL 宣告的索引＝models.py
宣告的索引」釘成不變式。
"""

import re
from pathlib import Path

from backend.models import db


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / 'migration'
    / '55_add_fk_indexes.sql'
)

CREATE_INDEX_RE = re.compile(
    r'CREATE INDEX IF NOT EXISTS\s+(\S+)\s+ON\s+"([^"]+)"\s+\("([^"]+)"\);'
)


def _sql_indexes():
    return CREATE_INDEX_RE.findall(MIGRATION_PATH.read_text(encoding='utf-8'))


def test_migration_55_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_55_is_idempotent():
    """正式庫靠手動執行，重複套用不得炸掉。"""
    body = MIGRATION_PATH.read_text(encoding='utf-8')
    statements = [s for s in body.split('\n') if s.strip().upper().startswith('CREATE INDEX')]
    assert statements, '未解析到任何 CREATE INDEX'
    for statement in statements:
        assert 'IF NOT EXISTS' in statement, statement


def test_migration_55_targets_real_tables_and_columns():
    """中文識別碼打錯不會被其他測試發現，這裡逐一比對 metadata。"""
    metadata = db.Model.metadata
    for index_name, table_name, column_name in _sql_indexes():
        table = metadata.tables.get(table_name)
        assert table is not None, f'{index_name}: 表 {table_name} 不存在'
        assert column_name in table.columns, (
            f'{index_name}: 欄位 {table_name}.{column_name} 不存在'
        )


def test_migration_55_matches_models_declarations():
    """每條 SQL 索引都要在 models.py 有同名同欄的宣告，反之亦然。"""
    metadata = db.Model.metadata
    sql_indexes = {
        (name, table, column) for name, table, column in _sql_indexes()
    }

    for index_name, table_name, column_name in sql_indexes:
        table = metadata.tables[table_name]
        declared = [ix for ix in table.indexes if ix.name == index_name]
        assert declared, f'models.py 缺少索引宣告 {index_name}'
        assert [c.name for c in declared[0].columns] == [column_name], (
            f'{index_name} 的欄位與 models.py 不一致'
        )

    # 反向：models.py 中以本次命名慣例新增的索引，都必須出現在 migration 裡
    sql_names = {name for name, _, _ in sql_indexes}
    expected_names = {
        'idx_capa_ncmr',
        'idx_rework_exec_request',
        'idx_rework_insp_request',
        'idx_rework_cost_request',
        'idx_tus_point_test',
        'idx_sat_point_test',
        'idx_task_assignee',
        'idx_msa_study_equipment_equipment',
        'idx_msa_observation_import_batch',
        'idx_msa_result_version_plan_version',
        'idx_msa_decision_result_version',
    }
    assert sql_names == expected_names

    declared_names = {
        ix.name for table in metadata.tables.values() for ix in table.indexes
    }
    assert expected_names <= declared_names, (
        f'models.py 未宣告：{expected_names - declared_names}'
    )
