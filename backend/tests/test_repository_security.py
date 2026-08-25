"""驗證儲存庫不追蹤秘密，且 Compose 要求部署環境注入秘密。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


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
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_scanner_detects_utf16_tracked_text(repo_root: Path, tmp_path: Path) -> None:
    """防止 UTF-16 文字檔被誤判為二進位而略過秘密掃描。"""
    isolated_repo = tmp_path / "repository"
    scanner_path = isolated_repo / "backend" / "scripts" / "scan_tracked_secrets.py"
    scanner_path.parent.mkdir(parents=True)
    shutil.copy2(repo_root / "backend" / "scripts" / "scan_tracked_secrets.py", scanner_path)

    fake_secret = ("SECRET_" + "KEY") + "=" + "utf16-test-" + "secret"
    (isolated_repo / "utf16-secret.txt").write_text(fake_secret, encoding="utf-16")
    subprocess.run(
        ["git", "init", "--quiet"], cwd=isolated_repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "add", "backend/scripts/scan_tracked_secrets.py", "utf16-secret.txt"],
        cwd=isolated_repo,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [sys.executable, "backend/scripts/scan_tracked_secrets.py"],
        cwd=isolated_repo,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "utf16-secret.txt:1:固定 SECRET_KEY" in result.stdout


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_scanner_detects_utf16_without_bom_after_traditional_chinese(
    repo_root: Path, tmp_path: Path, encoding: str
) -> None:
    """防止無 BOM 的繁中 UTF-16 檔案略過後段秘密。"""
    isolated_repo = tmp_path / "repository"
    scanner_path = isolated_repo / "backend" / "scripts" / "scan_tracked_secrets.py"
    scanner_path.parent.mkdir(parents=True)
    shutil.copy2(repo_root / "backend" / "scripts" / "scan_tracked_secrets.py", scanner_path)

    fake_secret = ("SECRET_" + "KEY") + "=" + "utf16-test-" + "secret"
    fixture_name = f"{encoding}-secret.txt"
    fixture_content = ("繁體中文品質檢驗追蹤紀錄" * 80) + "\n" + fake_secret
    (isolated_repo / fixture_name).write_text(fixture_content, encoding=encoding)
    subprocess.run(
        ["git", "init", "--quiet"], cwd=isolated_repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "add", "backend/scripts/scan_tracked_secrets.py", fixture_name],
        cwd=isolated_repo,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [sys.executable, "backend/scripts/scan_tracked_secrets.py"],
        cwd=isolated_repo,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{fixture_name}:2:固定 SECRET_KEY" in result.stdout


def _publishes_postgres_on_loopback_only(rendered: str) -> bool:
    """確認 5432 只綁在 127.0.0.1。

    Compose 舊版把 ports 渲染成 "127.0.0.1:5432:5432" 短字串，v2.2x 之後改成
    長格式（host_ip / target / published 各自成欄）。以解析 YAML 判斷實際綁定，
    才不會因為輸出格式改版就漏掉「對外全開」這種真正該擋的設定。
    """
    config = yaml.safe_load(rendered)
    published = [
        port
        for service in (config.get("services") or {}).values()
        for port in (service.get("ports") or [])
    ]
    exposed_5432 = []
    for port in published:
        if isinstance(port, str):
            if port.endswith(":5432") or port == "5432":
                exposed_5432.append(port)
            continue
        if int(port.get("target", 0)) == 5432:
            exposed_5432.append(port)

    if not exposed_5432:
        return False
    for port in exposed_5432:
        host_ip = (
            port.rsplit(":", 2)[0] if isinstance(port, str)
            else port.get("host_ip", "")
        )
        if host_ip != "127.0.0.1":
            return False
    return True


def test_compose_requires_secrets(repo_root: Path) -> None:
    """Compose 缺少秘密時必須拒絕展開，注入測試秘密時可以展開。"""
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI 不可用，無法執行 Compose artifact 驗證")

    missing = subprocess.run(
        ["docker", "compose", "config"],
        cwd=repo_root,
        env=without_env("DB_PASSWORD", "SECRET_KEY"),
        text=True,
        encoding="utf-8",
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
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    assert rendered.returncode == 0, rendered.stderr
    assert _publishes_postgres_on_loopback_only(rendered.stdout), rendered.stdout
