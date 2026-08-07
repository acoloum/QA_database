#!/usr/bin/env bash
# ============================================
# QA Database - Stop Backend + Frontend (Linux)
# ============================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PID_DIR="${SCRIPT_DIR}/.run"

echo "========================================"
echo "  QA Database - 停止服務"
echo "========================================"

stop_pid_file() {
  local name="$1"
  local file="$2"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      # 嘗試連同子程序一起終止
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill -TERM "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        pkill -KILL -P "$pid" 2>/dev/null || true
        kill -KILL "$pid" 2>/dev/null || true
      fi
      echo "  $name 已停止 (PID $pid)"
    else
      echo "  $name 未在執行 (stale PID $pid)"
    fi
    rm -f "$file"
  else
    echo "  $name 無 PID 檔，略過"
  fi
}

stop_pid_file "後端" "$PID_DIR/backend.pid"
stop_pid_file "前端" "$PID_DIR/frontend.pid"

# 備援：以 port 對應的程序為目標清理 (避免遺漏)
for port in 5001 5173; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null && echo "  已清理 port $port 殘留程序" || true
  fi
done

echo "========================================"
echo "  所有服務已停止"
echo "========================================"
