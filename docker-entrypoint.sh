#!/bin/bash
set -e

echo "============================================"
echo " QC Database System - Starting..."
echo "============================================"

# Start Nginx in background
echo "[1/2] Starting Nginx (Frontend)..."
nginx -g "daemon on;"

# Start Flask backend with Waitress
echo "[2/2] Starting Flask Backend (Waitress)..."
echo "  → Backend:  http://localhost:5001"
echo "  → Frontend: http://localhost:80"
echo "============================================"

cd /app
exec python -m backend.app
