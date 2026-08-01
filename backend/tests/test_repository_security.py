"""驗證儲存庫不追蹤秘密，且 Compose 要求部署環境注入秘密。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def without_env(*names: str) -> dict[str, str]:
    environment = os.environ.copy()
    for name in names:
        environment.pop(name, None)
    return environment


def with_test_secrets() -> dict[str, str]:
    environment = without_env("DB_PASSWORD", "SECRET_KEY")
    environment["DB_PASSWORD"] = "test-only-" + "password"
    environment["SECRET_KEY"] = "test-only-secret-key-32-bytes-" + "minimum"
    return environment


def test_tracked_files_do_not_contain_secrets(repo_root: Path) -> None:
    """防止已追蹤檔案重新納入可辨識的部署秘密。"""
    result = subprocess.run(
        [sys.executable, "backend/scripts/scan_tracked_secrets.py"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_compose_requires_secrets(repo_root: Path) -> None:
    """Compose 缺少秘密時必須拒絕展開，注入測試秘密時可以展開。"""
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI 不可用，無法執行 Compose artifact 驗證")

    missing = subprocess.run(
        ["docker", "compose", "config"],
        cwd=repo_root,
        env=without_env("DB_PASSWORD", "SECRET_KEY"),
        text=True,
        capture_output=True,
        check=False,
    )

    assert missing.returncode != 0
    assert "is required" in missing.stderr

    rendered = subprocess.run(
        ["docker", "compose", "config"],
        cwd=repo_root,
        env=with_test_secrets(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert rendered.returncode == 0, rendered.stderr
    assert "127.0.0.1:5432" in rendered.stdout
