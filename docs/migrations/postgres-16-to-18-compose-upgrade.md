# Docker Compose 的 PostgreSQL 16 → 18 升級手冊

`docker-compose.yml` 的資料庫服務原本是 `postgres:16-alpine`，與正式環境實際使用
的 PostgreSQL 18 不一致。本文件記錄該調整、以及**既有資料卷**的轉換步驟。

## 這次改了什麼

```diff
-    image: postgres:16-alpine
+    image: postgres:18-alpine
     volumes:
-      - postgres_data:/var/lib/postgresql/data
+      - postgres_data:/var/lib/postgresql
```

掛載點一起改是必要的，不是順手整理：官方 postgres 映像自 18 起把 `PGDATA` 改為
**版本專屬路徑** `/var/lib/postgresql/18/docker`（19 會是 `/var/lib/postgresql/19/…`，
依此類推）。若仍照舊掛在 `/var/lib/postgresql/data`，實際資料會寫在 volume 之外的
容器可寫層，**容器一旦重建就整個消失**，而且過程中不會有任何錯誤訊息。

## 先決條件：你是哪一種情況？

先確認機器上有沒有既有的資料卷：

```bash
docker volume ls --filter name=qa_database_postgres_data
```

- **沒有列出任何東西**（全新部署，或本機根本不用 Docker）
  → 不需要轉換。直接 `docker compose up -d`，PostgreSQL 18 會自行 initdb。
  本文件其餘章節可略過。

- **有列出 `qa_database_postgres_data`**
  → 該卷內是 PostgreSQL 16 的資料目錄，**18 拒絕直接啟動**（會出現
  `database files are incompatible with server`）。請依下節轉換。

> 官方映像不內含跨版本的 `pg_upgrade` 組合，因此下列採用 dump／restore。
> 本系統資料量在數 MB 等級（近期正式備份約 5 MB），這個做法幾分鐘內可完成，
> 且比 `pg_upgrade --link` 更容易驗證與回復。

## 轉換步驟

全程**不刪除舊卷**。舊卷就是回復點。

### 1. 在舊版仍運作時匯出

```bash
# 確認 16 的容器正在跑
docker compose ps db

# 完整匯出（含角色與權限）；輸出到 repo 外的備份目錄
docker compose exec -T db pg_dumpall -U postgres > /path/to/backup/qa_pg16_dumpall.sql

# 立刻確認檔案不是空的、而且結尾完整
ls -l /path/to/backup/qa_pg16_dumpall.sql
tail -1 /path/to/backup/qa_pg16_dumpall.sql   # 應為 "-- PostgreSQL database cluster dump complete"
```

匯出檔含明文連線資訊與資料，請比照既有備份的保管方式，不要放進版控。

### 2. 停止服務並把舊卷改名保留

```bash
docker compose down            # 不要加 -v，那會刪掉資料卷

# 以改名的方式保留舊卷：建立新卷、複製內容、再刪掉原名
docker volume create qa_database_postgres_data_pg16_backup
docker run --rm \
  -v qa_database_postgres_data:/from \
  -v qa_database_postgres_data_pg16_backup:/to \
  alpine sh -c "cd /from && cp -a . /to"

# 確認備份卷有內容後，才移除原名的卷
docker run --rm -v qa_database_postgres_data_pg16_backup:/v alpine ls /v
docker volume rm qa_database_postgres_data
```

### 3. 以 18 啟動並還原

```bash
docker compose up -d db        # 空卷 → 18 自行 initdb
docker compose ps db           # 等 healthcheck 變成 healthy

docker compose exec -T db psql -U postgres < /path/to/backup/qa_pg16_dumpall.sql
```

`pg_dumpall` 的輸出含 `CREATE DATABASE`，因此還原時連到預設的 `postgres` 庫即可。

### 4. 驗證

```bash
# 版本確認
docker compose exec -T db psql -U postgres -c "SELECT version();"

# 排序規則必須與舊庫一致（compose 的 POSTGRES_INITDB_ARGS 已固定為 C）
docker compose exec -T db psql -U postgres -d qa_database \
  -c "SELECT datcollate, datctype FROM pg_database WHERE datname='qa_database';"

# 主要資料表筆數，與升級前的紀錄逐一比對
docker compose exec -T db psql -U postgres -d qa_database -c "
  SELECT '出貨檢驗數據' AS 資料表, count(*) FROM \"出貨檢驗數據\"
  UNION ALL SELECT '不合格品單', count(*) FROM \"不合格品單\"
  UNION ALL SELECT '機械性質檢驗', count(*) FROM \"機械性質檢驗\";"

# trgm 等擴充是否隨 dump 一起回來
docker compose exec -T db psql -U postgres -d qa_database -c "\dx"
```

升級**前**請先在舊版跑一次同樣的計數查詢並留存結果，否則沒有比對基準。

### 5. 啟動應用並確認

```bash
docker compose up -d
curl -f http://localhost:8080/api/health || echo "健康檢查失敗"
```

## 回復

還原失敗或驗證對不上時，改回舊卷即可，資料原封不動：

```bash
docker compose down
docker volume rm qa_database_postgres_data
docker volume create qa_database_postgres_data
docker run --rm \
  -v qa_database_postgres_data_pg16_backup:/from \
  -v qa_database_postgres_data:/to \
  alpine sh -c "cd /from && cp -a . /to"
```

接著把 `docker-compose.yml` 的 `image` 與掛載點改回 16 的版本再啟動。兩者必須
一起改回去——只改映像會讓 18 的資料路徑對不上。

## 注意事項

- 確認一切正常、且至少完成一次新版的日常備份之後，才刪除
  `qa_database_postgres_data_pg16_backup`。
- `POSTGRES_INITDB_ARGS` 的 `--lc-collate=C --lc-ctype=C` 不可更動。換卷等於重新
  initdb，排序規則一旦不同，字串索引順序與比較結果都會跟著變。
- 本系統的正式環境是 Windows 上的原生 PostgreSQL 18，不經由這份 compose；此處的
  調整是讓容器化部署與正式環境一致，並非正式環境的升級程序。
