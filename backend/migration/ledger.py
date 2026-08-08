"""以 checksum 記錄正式資料庫已套用的 SQL migration。

預設只產生 manifest；只有明確提供 ``--apply`` 與資料庫 URL 時才會執行
單一 migration，避免把檔案掃描誤當成資料庫部署。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text

MIGRATION_NAME = re.compile(r"^(?P<version>\d+)_.*\.sql$")
LEDGER_TABLE = "qms_schema_migrations"


@dataclass(frozen=True)
class MigrationArtifact:
    version: int
    name: str
    path: str
    sha256: str


def discover_migrations(root: Path) -> list[MigrationArtifact]:
    """找出正向 migration，排除 rollback 與非 SQL 輔助檔。"""
    artifacts: list[MigrationArtifact] = []
    for path in sorted(root.glob("*.sql")):
        match = MIGRATION_NAME.match(path.name)
        if not match or path.name.endswith(".rollback.sql"):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
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


def read_ledger(connection) -> dict[int, dict[str, str]]:
    ensure_ledger(connection)
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


def apply_one(connection, artifact: MigrationArtifact, applied: dict[int, dict]) -> None:
    """在同一交易執行一個 migration，並寫入 checksum ledger。"""
    existing = applied.get(artifact.version)
    if existing:
        if existing["sha256"] != artifact.sha256:
            raise ValueError(f"migration {artifact.name} checksum 不一致")
        return
    sql = Path(artifact.path).read_text(encoding="utf-8")
    connection.exec_driver_sql(sql)
    connection.execute(text(
        f"INSERT INTO {LEDGER_TABLE} (version, name, sha256) VALUES (:version, :name, :sha256)"
    ), {"version": artifact.version, "name": artifact.name, "sha256": artifact.sha256})


def main() -> int:
    parser = argparse.ArgumentParser(description="QMS SQL migration checksum ledger")
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--database-url")
    parser.add_argument("--apply", type=int, metavar="VERSION")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    artifacts = discover_migrations(args.root)
    if not args.database_url:
        payload = [asdict(item) for item in artifacts]
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "\n".join(
            f"{item.version:02d} {item.name} {item.sha256}" for item in artifacts
        ))
        return 0

    engine = create_engine(args.database_url)
    with engine.begin() as connection:
        applied = read_ledger(connection)
        if args.apply is not None:
            artifact = next((item for item in artifacts if item.version == args.apply), None)
            if artifact is None:
                raise SystemExit(f"找不到 migration 版本：{args.apply}")
            apply_one(connection, artifact, applied)
            print(f"已套用 {artifact.name}")
        else:
            issues = verify_ledger(artifacts, applied)
            print("\n".join(issues) if issues else "migration ledger 已同步")
            return 1 if issues else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
