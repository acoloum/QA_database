# 🚀 快速開始指南

## 一鍵部署 (推薦)

如果你是第一次執行遷移,請使用自動化精靈:

```bash
python migration/setup_wizard.py
```

這個精靈會自動完成:
- ✅ 檢查 Python 與 PostgreSQL 環境
- ✅ 安裝所有必要的 Python 套件 (psycopg2-binary, flask, pandas, openpyxl)
- ✅ 引導你設定資料庫連線資訊 (密碼會安全地儲存在 .env 檔案)
- ✅ 自動建立 PostgreSQL 資料庫 (qa_database)
- ✅ 測試資料庫連線

---

## 完成精靈後的步驟

精靈完成後,依序執行以下指令:

### 1️⃣ 部署資料庫 Schema
```bash
python migration/deploy_schema.py
```
**預期結果:** 建立 15 個資料表、索引、外鍵約束

### 2️⃣ 從 SQL Server 匯出資料
```bash
python migration/export_data.py
```
**預期結果:** 在 `migration/data_export/` 目錄下產生 CSV 檔案

### 3️⃣ 匯入資料到 PostgreSQL
```bash
python migration/import_data.py
```
**預期結果:** 顯示每個資料表的匯入筆數

### 4️⃣ 啟動 PostgreSQL 版本應用程式
```bash
python app_postgresql.py
```
**預期結果:** Flask 應用程式在 http://127.0.0.1:5000 啟動

### 5️⃣ (選擇性) 測試 API 端點
開啟另一個終端機視窗:
```bash
python migration/test_api.py
```
**預期結果:** 所有 API 端點測試通過

---

## 故障排除

### 問題: psycopg2-binary 安裝失敗
```bash
# 方案 1: 升級 pip
python -m pip install --upgrade pip
pip install psycopg2-binary

# 方案 2: 使用預編譯版本
pip install psycopg2-binary --only-binary :all:
```

### 問題: PostgreSQL 連線失敗 (密碼錯誤)
```bash
# 編輯 .env 檔案,修改 DB_PASSWORD
notepad .env   # Windows
nano .env      # Linux/Mac
```

### 問題: 資料庫已存在錯誤
**方案 1:** 刪除舊資料庫後重建
```sql
-- 在 pgAdmin 或 psql 執行
DROP DATABASE qa_database;
```
然後重新執行 `setup_wizard.py`

**方案 2:** 使用不同的資料庫名稱
編輯 `.env` 檔案,修改 `DB_NAME=qa_database_new`

### 問題: 找不到 psql 指令
**Windows:**
1. 開啟「環境變數」設定
2. 編輯 PATH,加入 PostgreSQL bin 目錄
3. 預設路徑: `C:\Program Files\PostgreSQL\16\bin`
4. 重新啟動終端機

**Linux/Mac:**
```bash
# 通常已自動加入 PATH
# 如果沒有,手動加入:
export PATH=/usr/lib/postgresql/16/bin:$PATH
```

### 問題: 資料匯入後筆數不符
```bash
# 檢查 SQL Server 原始筆數
python migration/export_data.py --dry-run

# 檢查 PostgreSQL 匯入筆數
python migration/test_connection.py
```

---

## 手動部署 (不使用精靈)

如果你偏好手動控制每個步驟:

### 步驟 1: 安裝依賴
```bash
pip install psycopg2-binary flask pandas openpyxl
```

### 步驟 2: 設定連線資訊
建立 `.env` 檔案:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=qa_database
DB_USER=postgres
DB_PASSWORD=你的密碼
```

### 步驟 3: 建立資料庫
**使用 pgAdmin:**
1. 右鍵 Databases → Create → Database
2. Name: qa_database
3. Owner: postgres
4. Encoding: UTF8

**使用 psql:**
```bash
psql -U postgres -c "CREATE DATABASE qa_database WITH ENCODING='UTF8';"
```

### 步驟 4: 測試連線
```bash
python migration/test_connection.py
```

### 步驟 5: 繼續執行部署步驟 (同上方 1️⃣-5️⃣)

---

## 回滾到 SQL Server

如果遷移後遇到問題,可以隨時切回 SQL Server:

### 方法 1: 修改環境變數
編輯 `.env`:
```
DB_TYPE=sqlserver  # 改為 sqlserver
```

### 方法 2: 直接使用原始檔案
```bash
python app.py  # 使用 SQL Server 版本
```

**注意:** `app.py` (SQL Server 版本) 保持完整未修改,隨時可用

---

## 環境變數說明

`.env` 檔案支援的變數:

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `DB_HOST` | PostgreSQL 主機位址 | localhost |
| `DB_PORT` | PostgreSQL 連接埠 | 5432 |
| `DB_NAME` | 資料庫名稱 | qa_database |
| `DB_USER` | 使用者名稱 | postgres |
| `DB_PASSWORD` | 密碼 | (必填) |

**安全提示:** `.env` 檔案已自動加入 `.gitignore`,不會被提交到 Git

---

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `setup_wizard.py` | ⭐ 自動化部署精靈 (推薦使用) |
| `deploy_schema.py` | 部署資料庫 schema |
| `export_data.py` | 從 SQL Server 匯出資料 |
| `import_data.py` | 匯入資料到 PostgreSQL |
| `test_connection.py` | 測試資料庫連線 |
| `test_api.py` | 測試 API 端點 |
| `DEPLOYMENT_GUIDE.md` | 詳細部署指南 |

---

## 需要幫助?

1. **檢查日誌:** 所有腳本都會輸出詳細的執行訊息
2. **查看文件:** 參考 `DEPLOYMENT_GUIDE.md` 詳細說明
3. **驗證環境:**
   ```bash
   python --version      # 檢查 Python 版本 (需要 3.7+)
   psql --version        # 檢查 PostgreSQL 版本
   pip list | grep psycopg2  # 檢查驅動是否安裝
   ```

---

**最後更新:** 2026-02-06
**適用版本:** PostgreSQL 12+ / Python 3.7+
