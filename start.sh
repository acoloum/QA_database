#!/bin/bash
# ========================================
# QA Database - 啟動前端與後端伺服器
# ========================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  品質小管家 - 啟動伺服器"
echo "========================================"

# 啟動後端
echo "[1/2] 啟動後端伺服器 (port 5001)..."
cd "$PROJECT_DIR"
source venv/bin/activate
python -m backend.app &
BACKEND_PID=$!
echo "  ✅ 後端 PID: $BACKEND_PID"

# 啟動前端
echo "[2/2] 啟動前端開發伺服器..."
cd "$PROJECT_DIR/src_frontend"
npm run dev &
FRONTEND_PID=$!
echo "  ✅ 前端 PID: $FRONTEND_PID"

echo ""
echo "========================================"
echo "  伺服器已啟動！"
echo "  後端: http://localhost:5001"
echo "  前端: http://localhost:5173"
echo "========================================"
echo "  按 Ctrl+C 停止所有伺服器"
echo "========================================"

# 捕捉 Ctrl+C，同時關閉前後端
trap "echo ''; echo '正在關閉伺服器...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待子程序
wait
