#!/bin/bash
# 啟動後端伺服器 (Flask + Waitress, port 5001)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
source venv/bin/activate

echo "========================================"
echo "  啟動後端伺服器 (port 5001)"
echo "========================================"

python -m backend.app
