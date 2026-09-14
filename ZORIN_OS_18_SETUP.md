# Zorin OS 18 部署指南

Zorin OS 18 基於 Ubuntu 24.04 LTS (Noble Numbat)，本指南說明如何在 Zorin OS 18 上安裝並執行本系統。

---

## 系統需求

| 項目 | 版本 |
|------|------|
| OS | Zorin OS 18 (Core/Pro/Lite 皆可) |
| Python | 3.11 以上 (Zorin OS 18 內建 3.12) |
| Node.js | 22.x |
| PostgreSQL | 16 |

---

## 方式 1：自動安裝腳本（建議）

```bash
# 賦予執行權限後執行
chmod +x setup-zorin.sh start.sh start-backend.sh start-frontend.sh stop.sh
./setup-zorin.sh
```

`setup-zorin.sh` 會自動：
- 透過 `apt` 安裝編譯工具、Python 開發套件、`libpq-dev`、PostgreSQL client。
- 安裝 Node.js 22 (NodeSource 源)。
- 詢問是否安裝 PostgreSQL 16 伺服器（也可改用 docker-compose）。
- 建立 `./venv` 並安裝 `requirements.txt`。
- 在 `src_frontend/` 執行 `npm ci`。
- 從 `.env.example` 複製出 `.env`。

完成後請：

1. 編輯 `.env` 設定 `DB_PASSWORD` 與 `SECRET_KEY`。
2. 建立資料庫並套用 schema：
   ```bash
   sudo -u postgres createdb qa_database
   sudo -u postgres psql -d qa_database -f migration/04_create_all_tables.sql
   ```
3. 啟動服務：
   ```bash
   ./start.sh
   ```

---

## 方式 2：Docker Compose（最快）

如果你只想跑起來，不在本機安裝 Python/Node：

```bash
# 安裝 Docker (Zorin OS 18 / Ubuntu 24.04)
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker

# 啟動全套服務
cp .env.docker .env
docker compose up -d
```

服務啟動後可由 `http://localhost:8080` 進入。

---

## 啟動 / 停止指令

| 指令 | 說明 |
|------|------|
| `./start.sh` | 同時啟動後端 (5001) 與前端 (5173)；以 nohup 背景執行，輸出寫入 `logs/`。 |
| `./start-backend.sh` | 前景啟動後端（適合除錯）。 |
| `./start-frontend.sh` | 前景啟動前端 dev server。 |
| `./stop.sh` | 依 `.run/*.pid` 與 port 5001/5173 終止服務。 |

PID 檔位於 `.run/`，日誌位於 `logs/`。

---

## 防火牆設定（選用）

Zorin OS 18 預設啟用 UFW。若要讓區網其他電腦訪問前後端：

```bash
sudo ufw allow 5173/tcp   # 前端 dev
sudo ufw allow 5001/tcp   # 後端 API
sudo ufw allow 8080/tcp   # Docker 部署
```

---

## 常見問題

**Q: `pip install` 卡在 `psycopg2-binary` 或 `pandas`？**  
A: 確認 `libpq-dev`、`build-essential`、`python3-dev` 都已安裝。`setup-zorin.sh` 已涵蓋。

**Q: Node.js 版本太舊？**  
A: Zorin OS 18 自帶 Node 18，本專案需要 22。`setup-zorin.sh` 會加入 NodeSource 源並安裝。

**Q: 連不上 PostgreSQL？**  
A: 確認 `pg_hba.conf` 允許 `localhost` 以密碼登入，或以 `sudo -u postgres psql` 設好密碼後同步到 `.env`。

**Q: 啟動 backend 顯示 `SECRET_KEY environment variable is not set`？**  
A: 編輯 `.env` 寫入 `SECRET_KEY`，或於同 shell `export SECRET_KEY=...` 後再啟動。
