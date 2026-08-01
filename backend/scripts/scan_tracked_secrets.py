"""掃描 Git 追蹤檔中的常見部署秘密。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


JWT_PREFIX = "ey" + "J"
PGPASSWORD_NAME = "PGPASS" + "WORD"
SECRET_KEY_NAME = "SECRET_" + "KEY"

PATTERNS = {
    "JWT": re.compile(
        JWT_PREFIX + r"[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
    ),
    PGPASSWORD_NAME: re.compile(PGPASSWORD_NAME + r"\s*=", re.IGNORECASE),
    "固定 SECRET_KEY": re.compile(
        r"(?<!\$\{)"
        + SECRET_KEY_NAME
        + r"\s*[:=]\s*(?!(?:os\.)?(?:getenv|environ\.get)\()[^$<\s][^\r\n]+"
    ),
    "私鑰": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def tracked_files(repo_root: Path) -> list[Path]:
    """回傳目前 Git 索引中的檔案，避免掃描未追蹤的本機秘密。"""
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=repo_root, text=False
    )
    return [
        repo_root / Path(path.decode("utf-8", errors="surrogateescape"))
        for path in output.split(b"\0")
        if path
    ]


def scan_file(path: Path, relative_path: Path) -> tuple[list[str], bool]:
    """回傳檔案的命中結果與是否因二進位內容略過。"""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], True

    findings = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for rule, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(f"{relative_path.as_posix()}:{line_number}:{rule}")
    return findings, False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    findings: list[str] = []
    skipped_binary = 0
    files = tracked_files(repo_root)

    for path in files:
        file_findings, was_binary = scan_file(path, path.relative_to(repo_root))
        findings.extend(file_findings)
        skipped_binary += was_binary

    for finding in findings:
        print(finding)
    print(f"掃描摘要：掃描 {len(files)} 個追蹤檔案，略過 {skipped_binary} 個二進位檔案")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
