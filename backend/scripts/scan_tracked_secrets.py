"""掃描 Git 追蹤檔中的常見部署秘密。"""

from __future__ import annotations

import codecs
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

BOM_ENCODINGS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)
BINARY_CONTROL_BYTES = frozenset(range(0, 9)) | frozenset((11, 12)) | frozenset(
    range(14, 32)
)


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


def is_probably_binary(content: bytes) -> bool:
    """以 NUL 與控制位元組比例辨識二進位內容。"""
    sample = content[:8192]
    if not sample:
        return False
    if 0 in sample:
        return True
    control_count = sum(byte in BINARY_CONTROL_BYTES for byte in sample)
    return control_count / len(sample) > 0.3


def decode_tracked_views(content: bytes) -> list[str]:
    """建立單位元組與多位元組文字視圖，供同一檔案完整掃描。"""
    views: list[str] = []

    def append_view(encoding: str) -> bool:
        try:
            decoded = content.decode(encoding)
        except UnicodeDecodeError:
            return False
        if decoded not in views:
            views.append(decoded)
        return True

    for bom, encoding in BOM_ENCODINGS:
        if content.startswith(bom):
            append_view(encoding)
            break

    for encoding in ("utf-8", "cp950", "latin-1"):
        if append_view(encoding):
            break

    if len(content) % 2 == 0:
        append_view("utf-16-le")
        append_view("utf-16-be")
    return views


def scan_file(path: Path, relative_path: Path) -> tuple[list[str], bool]:
    """回傳檔案的命中結果與是否因二進位內容略過。"""
    raw_content = path.read_bytes()
    findings: list[str] = []
    seen_findings: set[str] = set()
    for content in decode_tracked_views(raw_content):
        for line_number, line in enumerate(content.splitlines(), start=1):
            for rule, pattern in PATTERNS.items():
                if pattern.search(line):
                    finding = f"{relative_path.as_posix()}:{line_number}:{rule}"
                    if finding not in seen_findings:
                        findings.append(finding)
                        seen_findings.add(finding)
    return findings, is_probably_binary(raw_content)


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
