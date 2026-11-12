"""正式環境啟動前的資料庫檢查（唯讀）。

檢查兩件事：
1. 結構漂移：models.py 需要的資料表／欄位是否都在資料庫裡。
2. migration ledger：backend/migration 下的 SQL 是否都有套用紀錄、checksum 是否一致。

結束碼：0 = 通過；1 = 有問題（列出明細）；2 = 無法連線資料庫。
本檢查不會寫入資料庫，也不會建立 ledger 表。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.migration.preflight
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError

from backend.migration.ledger import discover_migrations, status_issues
from backend.migration.schema_check import find_schema_drift

MIGRATION_ROOT = Path(__file__).parent


def _say(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [schema-preflight] {message}", flush=True)


def run(engine, metadata: MetaData, migration_root: Path = MIGRATION_ROOT) -> int:
    artifacts = discover_migrations(migration_root)
    try:
        with engine.connect() as connection:
            drift = find_schema_drift(connection, metadata)
            pending = status_issues(connection, artifacts)
    except SQLAlchemyError as exc:
        _say(f"無法連線資料庫，略過檢查：{exc.__class__.__name__}: {exc}")
        return 2

    issues = drift + pending
    if not issues:
        _say(f"通過：資料庫結構與 models 一致，{len(artifacts)} 支 migration 皆已記錄")
        return 0
    _say(f"警告：發現 {len(issues)} 個問題，請先套用 migration 再使用相關功能")
    for issue in issues:
        _say(f"  - {issue}")
    return 1


def main() -> int:
    from sqlalchemy import create_engine

    from backend.config import SQLALCHEMY_DATABASE_URI
    from backend.extensions import db
    import backend.models  # noqa: F401  註冊所有模型到 metadata

    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    try:
        return run(engine, db.metadata)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
