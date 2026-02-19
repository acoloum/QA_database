#!/bin/bash
# 啟動前端開發伺服器 (Vite, port 5173)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR/src_frontend"

echo "========================================"
echo "  啟動前端開發伺服器"
echo "========================================"

npm run dev
