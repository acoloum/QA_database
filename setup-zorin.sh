#!/usr/bin/env bash
# ============================================
# QA Database - Zorin OS 18 Setup Script
# Zorin OS 18 基於 Ubuntu 24.04 LTS (Noble Numbat)
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  QA Database - Zorin OS 18 環境設定"
echo "============================================"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "[警告] 請勿以 root 直接執行，sudo 會在需要時自動提示。" >&2
  exit 1
fi

# 偵測作業系統
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  echo "[資訊] 偵測到系統: ${PRETTY_NAME:-unknown}"
else
  echo "[警告] 無法偵測作業系統，繼續嘗試以 Ubuntu/Debian 方式安裝。"
fi

echo "[1/6] 更新 APT 套件索引..."
sudo apt-get update

echo "[2/6] 安裝系統相依套件 (Python、編譯工具、PostgreSQL client、libpq)..."
sudo apt-get install -y --no-install-recommends \
  build-essential \
  python3 \
  python3-venv \
  python3-dev \
  python3-pip \
  libpq-dev \
  postgresql-client \
  curl \
  ca-certificates \
  git

echo "[3/6] 安裝 Node.js 22 (NodeSource)..."
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | sed 's/v//' | cut -d. -f1)" -lt 22 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
else
  echo "       Node.js 已安裝: $(node -v)"
fi

echo "[4/6] (選用) 安裝 PostgreSQL 16 伺服器..."
read -r -p "       是否在此機器上安裝 PostgreSQL 16？[y/N] " install_pg
if [[ "${install_pg,,}" == "y" ]]; then
  sudo install -d /usr/share/postgresql-common/pgdg
  sudo curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "${VERSION_CODENAME}")-pgdg main" \
    | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y postgresql-16
  sudo systemctl enable --now postgresql
  echo "       PostgreSQL 16 已啟動。請以 sudo -u postgres psql 設定 postgres 密碼。"
else
  echo "       略過 PostgreSQL 伺服器安裝（可改用 docker-compose 啟動）。"
fi

echo "[5/6] 建立 Python 虛擬環境 (./venv) 並安裝後端套件..."
if [[ ! -d "venv" ]]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
deactivate

echo "[6/6] 安裝前端套件..."
pushd src_frontend >/dev/null
npm ci
popd >/dev/null

if [[ ! -f ".env" ]]; then
  echo ""
  echo "[資訊] 未發現 .env，從 .env.example 複製一份..."
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "       請編輯 .env 設定資料庫密碼與 SECRET_KEY。"
  fi
fi

echo ""
echo "============================================"
echo "  安裝完成！"
echo "  下一步："
echo "    1. 編輯 .env (DB 密碼 / SECRET_KEY)"
echo "    2. 建立資料庫: createdb -U postgres qa_database"
echo "       套用 schema: psql -U postgres -d qa_database -f migration/04_create_all_tables.sql"
echo "    3. 啟動服務: ./start.sh"
echo "============================================"
