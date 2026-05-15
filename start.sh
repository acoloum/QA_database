#!/usr/bin/env bash
# ============================================
# QA Database - Start Backend + Frontend (Linux)
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"

PID_DIR="${SCRIPT_DIR}/.run"
mkdir -p "$PID_DIR"

echo "========================================"
echo "  QA Database - 啟動服務"
echo "========================================"

# 檢查 venv
if [[ ! -d "venv" ]]; then
  echo "[錯誤] 找不到 venv，請先執行 ./setup-zorin.sh" >&2
  exit 1
fi

# 載入 .env (若存在)
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# 啟動後端
echo "[1/2] 啟動後端 (port 5001)..."
# shellcheck disable=SC1091
source venv/bin/activate
nohup python -m backend.app >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
deactivate
echo "$BACKEND_PID" >"$PID_DIR/backend.pid"
echo "      後端 PID: $BACKEND_PID  (log: logs/backend.log)"

# 啟動前端
echo "[2/2] 啟動前端 (port 5173)..."
pushd src_frontend >/dev/null
nohup npm run dev >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
popd >/dev/null
echo "$FRONTEND_PID" >"$PID_DIR/frontend.pid"
echo "      前端 PID: $FRONTEND_PID  (log: logs/frontend.log)"

echo ""
echo "========================================"
echo "  服務已啟動！"
echo "  後端:  http://localhost:5001"
echo "  前端:  http://localhost:5173"
echo "  停止服務請執行: ./stop.sh"
echo "========================================"
