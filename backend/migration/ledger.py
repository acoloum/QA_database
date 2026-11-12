r"""以 checksum 記錄正式資料庫已套用的 SQL migration。

預設只產生 manifest；連上資料庫時預設只做唯讀的狀態檢查。只有明確提供
``--apply`` 才會執行單一 migration，``--baseline`` 只寫紀錄、不執行 SQL，
避免把檔案掃描誤當成資料庫部署。

用法（repo 根目錄）：
    .\venv\Scripts\python.exe -m backend.migration.ledger                  # 列出 manifest
    .\venv\Scripts\python.exe -m backend.migration.ledger --app-db         # 唯讀狀態檢查
    .\venv\Scripts\python.exe -m backend.migration.ledger --app-db --apply 55
    .\venv\Scripts\python.exe -m backend.migration.ledger --app-db --baseline 54
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, inspect, text

MIGRATION_NAME = re.compile(r"^(?P<version>\d+)_.*\.sql$")
LEDGER_TABLE = "qms_schema_migrations"


@dataclass(frozen=True)
class MigrationArtifact:
    version: int
    name: str
    path: str
    sha256: str


def file_checksum(path: Path) -> str:
    """以 LF 正規化後計算 sha256。

    repo 開了 core.autocrlf，同一支檔案在不同 checkout 可能是 LF 或 CRLF；
    若直接雜湊原始位元組，git 一碰檔案就會被誤判為「checksum 不一致」。
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def discover_migrations(root: Path) -> list[MigrationArtifact]:
    """找出正向 migration，排除 rollback 與非 SQL 輔助檔。"""
    artifacts: list[MigrationArtifact] = []
    for path in sorted(root.glob("*.sql")):
        match = MIGRATION_NAME.match(path.name)
        if not match or path.name.endswith(".rollback.sql"):
            continue
        digest = file_checksum(path)
        artifacts.append(MigrationArtifact(
            version=int(match.group("version")),
            name=path.name,
            path=str(path),
            sha256=digest,
        ))
    versions = [item.version for item in artifacts]
    if len(versions) != len(set(versions)):
        duplicates = sorted({version for version in versions if versions.count(version) > 1})
        raise ValueError(f"migration 版本重複：{duplicates}")
    return sorted(artifacts, key=lambda item: item.version)


def ensure_ledger(connection) -> None:
    connection.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
            version INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            sha256 CHAR(64) NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))


def ledger_exists(connection) -> bool:
    return inspect(connection).has_table(LEDGER_TABLE)


def read_ledger(connection) -> dict[int, dict[str, str]]:
    """讀取已套用紀錄；ledger 表不存在時回傳空 dict，不會建立它（保持唯讀）。"""
    if not ledger_exists(connection):
        return {}
    rows = connection.execute(text(
        f"SELECT version, name, sha256 FROM {LEDGER_TABLE} ORDER BY version"
    )).mappings()
    return {int(row["version"]): dict(row) for row in rows}


def verify_ledger(artifacts: Iterable[MigrationArtifact], applied: dict[int, dict]) -> list[str]:
    """回傳未套用、checksum 漂移或資料庫多出的 migration 警告。"""
    current = {item.version: item for item in artifacts}
    issues: list[str] = []
    for item in artifacts:
        record = applied.get(item.version)
        if record is None:
            issues.append(f"待套用 {item.version:02d}_{item.name.split('_', 1)[1]}")
        elif record["sha256"] != item.sha256:
            issues.append(f"checksum 不一致 {item.name}")
    for version in sorted(set(applied) - set(current)):
        issues.append(f"資料庫有檔案不存在的 migration {version:02d}")
    return issues


def status_issues(connection, artifacts: list[MigrationArtifact]) -> list[str]:
    """唯讀狀態檢查：ledger 尚未建立時只回報一則提示，不逐支列出待套用。"""
    if not ledger_exists(connection):
        return [
            f"尚未建立 migration ledger（{LEDGER_TABLE}）；"
            "確認資料庫結構與 models 一致後執行 --baseline 建立基準"
        ]
    return verify_ledger(artifacts, read_ledger(connection))


def _record(connection, artifact: MigrationArtifact) -> None:
    connection.execute(text(
        f"INSERT INTO {LEDGER_TABLE} (version, name, sha256) VALUES (:version, :name, :sha256)"
    ), {"version": artifact.version, "name": artifact.name, "sha256": artifact.sha256})


def baseline(connection, artifacts: list[MigrationArtifact], up_to: int) -> list[MigrationArtifact]:
    """把版本 <= up_to 的 migration 記為已套用，但不執行 SQL。

    用於 ledger 建立前就已手動套用過的正式庫。已有紀錄者略過；
    紀錄的 checksum 與檔案不符時拒絕，避免把改過的檔案蓋成「已套用」。
    回傳本次新記錄的 migration。
    """
    ensure_ledger(connection)
    applied = read_ledger(connection)
    recorded: list[MigrationArtifact] = []
    for artifact in artifacts:
        if artifact.version > up_to:
            continue
        existing = applied.get(artifact.version)
        if existing:
            if existing["sha256"] != artifact.sha256:
                raise ValueError(f"migration {artifact.name} checksum 不一致")
            continue
        _record(connection, artifact)
        recorded.append(artifact)
    return recorded


def apply_one(connection, artifact: MigrationArtifact, applied: dict[int, dict]) -> None:
    """在同一交易執行一個 migration，並寫入 checksum ledger。"""
    existing = applied.get(artifact.version)
    if existing:
        if existing["sha256"] != artifact.sha256:
            raise ValueError(f"migration {artifact.name} checksum 不一致")
        return
    ensure_ledger(connection)
    sql = Path(artifact.path).read_text(encoding="utf-8")
    connection.exec_driver_sql(sql)
    _record(connection, artifact)


def _app_database_url():
    """沿用應用程式設定（.env）的連線資訊，避免在命令列打出密碼。"""
    from backend.config import SQLALCHEMY_DATABASE_URI
    return SQLALCHEMY_DATABASE_URI


def main() -> int:
    parser = argparse.ArgumentParser(description="QMS SQL migration checksum ledger")
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--database-url")
    target.add_argument("--app-db", action="store_true", help="使用 backend/config.py（.env）的資料庫")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", type=int, metavar="VERSION", help="執行並記錄單一 migration")
    action.add_argument(
        "--baseline", type=int, metavar="VERSION",
        help="把 <= VERSION 的 migration 記為已套用但不執行（需先通過結構比對）",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    artifacts = discover_migrations(args.root)
    database_url = _app_database_url() if args.app_db else args.database_url
    if not database_url:
        if args.apply is not None or args.baseline is not None:
            parser.error("--apply / --baseline 需要 --database-url 或 --app-db")
        payload = [asdict(item) for item in artifacts]
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "\n".join(
            f"{item.version:02d} {item.name} {item.sha256}" for item in artifacts
        ))
        return 0

    engine = create_engine(database_url)
    if args.baseline is not None:
        from backend.extensions import db
        import backend.models  # noqa: F401  註冊所有模型到 metadata
        from backend.migration.schema_check import find_schema_drift

        with engine.begin() as connection:
            drift = find_schema_drift(connection, db.metadata)
            if drift:
                print("資料庫結構與 models 不一致，拒絕建立基準：")
                print("\n".join(drift))
                return 1
            recorded = baseline(connection, artifacts, args.baseline)
        print(f"已記錄 {len(recorded)} 支 migration 為已套用（未執行 SQL）")
        return 0

    if args.apply is not None:
        artifact = next((item for item in artifacts if item.version == args.apply), None)
        if artifact is None:
            raise SystemExit(f"找不到 migration 版本：{args.apply}")
        with engine.begin() as connection:
            apply_one(connection, artifact, read_ledger(connection))
        print(f"已套用 {artifact.name}")
        return 0

    with engine.connect() as connection:
        issues = status_issues(connection, artifacts)
    print("\n".join(issues) if issues else "migration ledger 已同步")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
