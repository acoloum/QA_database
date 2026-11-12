"""比對 models.py 的 metadata 與實際資料庫結構（唯讀）。

migration 是手寫 SQL、不會自動套用；測試又是用 create_all() 從 models 建表，
所以「測試全綠」不代表正式庫已套用。這裡直接檢查資料庫是否具備 models
需要的每張資料表、每個欄位與每個索引，漏套 migration 時能在啟動前就發現，
而不是等到使用者操作時才出現 500 或查詢突然變慢。

只檢查「缺少」：資料庫多出的表、欄位或索引（例如手動備份表）不視為問題。

索引以「欄位」比對而不看名稱：正式庫不少索引是早期以中文名稱或複合索引建立的，
只要某個既有索引（含主鍵、唯一約束）包含 models 索引的全部欄位，就視為已涵蓋。
型別與 CHECK／外鍵約束不在比對範圍內。
"""
from __future__ import annotations

from sqlalchemy import MetaData, inspect


def _live_index_column_sets(inspector, table_name: str) -> list[set[str]]:
    column_sets = [set(index["column_names"]) for index in inspector.get_indexes(table_name)]
    column_sets += [
        set(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
    ]
    primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
    if primary_key:
        column_sets.append(set(primary_key))
    return column_sets


def find_schema_drift(connection, metadata: MetaData) -> list[str]:
    """回傳資料庫缺少的資料表、欄位與索引；一致時回傳空 list。"""
    inspector = inspect(connection)
    live_tables = set(inspector.get_table_names())
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    missing_indexes: list[str] = []
    for table in metadata.sorted_tables:
        if table.name not in live_tables:
            missing_tables.append(f"資料庫缺少資料表 {table.name}")
            continue
        live_columns = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in live_columns:
                missing_columns.append(f"資料庫缺少欄位 {table.name}.{column.name}")

        live_index_columns = _live_index_column_sets(inspector, table.name)
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            wanted = [column.name for column in index.columns]
            if not wanted:  # 運算式索引無法以欄位比對，略過
                continue
            if not any(set(wanted) <= existing for existing in live_index_columns):
                missing_indexes.append(
                    f"資料庫缺少索引 {table.name}({', '.join(wanted)})"
                )
    return sorted(missing_tables) + missing_columns + missing_indexes
