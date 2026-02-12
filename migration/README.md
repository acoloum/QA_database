# PostgreSQL 資料庫遷移指南

## 步驟 1：建立資料庫

請開啟 **pgAdmin** 或使用 **SQL Shell (psql)** 執行以下步驟：

### 方法 A：使用 pgAdmin（推薦）
1. 開啟 pgAdmin
2. 連接到 PostgreSQL 伺服器
3. 右鍵點擊 "Databases" → "Create" → "Database..."
4. 設定：
   - Database: `qa_database`
   - Owner: `postgres`
   - Encoding: `UTF8`
   - Collation: `Chinese (Traditional)_Taiwan.950` 或 `C`
   - Character type: `Chinese (Traditional)_Taiwan.950` 或 `C`
5. 點擊 "Save"

### 方法 B：使用 SQL Shell (psql)
1. 開啟「開始功能表」→ 搜尋 `SQL Shell (psql)`
2. 連接資訊全部按 Enter 使用預設值
3. 輸入 postgres 密碼
4. 執行以下 SQL：

```sql
CREATE DATABASE qa_database
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE = template0;
```

5. 驗證建立成功：
```sql
\l  -- 列出所有資料庫，應該會看到 qa_database
```

---

## 步驟 2：執行 Schema 建立腳本

資料庫建立完成後，請查看 `migration` 資料夾中的轉換後 SQL 檔案：

1. **02_create_all_tables.sql** - 建立所有資料表
2. **03_create_indexes.sql** - 建立索引

在 pgAdmin 的 Query Tool 或 psql 中依序執行這些檔案。

---

## 步驟 3：測試連接

執行以下 Python 測試腳本：

```bash
python migration/test_connection.py
```

---

## 注意事項

- PostgreSQL 預設不區分大小寫，但使用雙引號後會區分
- 中文資料表名和欄位名必須加雙引號
- 確保資料庫編碼為 UTF-8 以支援中文
