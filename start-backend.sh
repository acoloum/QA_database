#!/usr/bin/env bash
# ============================================
# QA Database - 啟動後端 (Linux, foreground)
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  啟動後端 (port 5001)"
echo "========================================"

if [[ ! -d "venv" ]]; then
  echo "[錯誤] 找不到 venv，請先執行 ./setup-zorin.sh" >&2
  exit 1
fi

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# shellcheck disable=SC1091
source venv/bin/activate
exec python -m backend.app
