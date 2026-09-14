#!/usr/bin/env bash
# ============================================
# QA Database - 啟動前端 (Linux, foreground)
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/src_frontend"

echo "========================================"
echo "  啟動前端 Dev Server"
echo "========================================"

if [[ ! -d "node_modules" ]]; then
  echo "[資訊] 未發現 node_modules，先執行 npm ci..."
  npm ci
fi

exec npm run dev
