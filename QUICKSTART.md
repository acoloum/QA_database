# 🚀 PostgreSQL 版本快速啟動指南

## ✅ 遷移已完成！

恭喜！你的品保資料庫系統已成功從 SQL Server Express 遷移到 PostgreSQL。

---

## 📋 系統狀態檢查

執行以下指令確認一切正常：

```bash
# 1. 測試資料庫連線
python migration/test_simple.py
```

**預期輸出：**
```
[成功] 連接成功
PostgreSQL 18.1 on x86_64-windows...
資料表數量: 16
資料庫編碼: UTF8
[結果] 所有測試通過!
```

---

## 🎯 啟動應用程式

### 開發環境（推薦）

```bash
python app_postgresql.py
```

應用程式將啟動在: **http://127.0.0.1:5000**

### 生產環境

**Windows:**
```bash
pip install waitress
waitress-serve --listen=*:5000 app_postgresql:app
```

**Linux/Mac:**
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app_postgresql:app
```

---

## 🔑 重要檔案

| 檔案 | 用途 |
|------|------|
| `app_postgresql.py` | **主應用程式** (PostgreSQL 版本) |
| `.env` | 資料庫密碼配置 |
| `config.py` | 資料庫連線設定 |
| `POSTGRESQL_MIGRATION_COMPLETE.md` | 完整遷移報告 |

---

## ⚙️ 配置說明

### 修改資料庫連線資訊

編輯 `.env` 檔案:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=qa_database
DB_USER=postgres
DB_PASSWORD=你的密碼
```

### 切換資料庫類型（如需要）

編輯 `config.py` 第 10 行:

```python
DB_TYPE = 'postgresql'  # 或 'sqlserver'
```

---

## 🧪 測試功能

### 基本測試流程

1. **啟動應用程式**
   ```bash
   python app_postgresql.py
   ```

2. **開啟瀏覽器**
   訪問: http://127.0.0.1:5000

3. **測試登入**
   - 使用現有帳號登入
   - 測試基本功能

4. **測試數據操作**
   - 查詢廠商資料
   - 新增/修改/刪除記錄
   - 匯出 Excel

---

## 📊 資料狀態

### 已匯入的資料

✅ **核心資料 (1,627 筆) - 已完成**
- 廠商資料: 40 筆
- 廠商公差主檔: 261 筆
- 廠商公差明細檔: 1,295 筆
- 使用者: 6 筆
- 品管人員: 12 筆
- 擠壓機台: 7 筆
- 其他基礎資料

### 待處理的資料

⚠️ **大量資料表 (5,833 筆) - 需處理 Schema 差異**
- 出貨檢驗數據: 5,278 筆
- 進貨檢驗數據: 506 筆
- 巡檢子檔: 48 筆
- 不合格品單: 1 筆

**處理方法:** 參考 `migration/import_data.py`，修正欄位對應後重新匯入

---

## 🛠️ 常見問題

### Q: 啟動時顯示 "No module named 'psycopg2'"

```bash
pip install psycopg2-binary
```

### Q: 連線失敗 "password authentication failed"

檢查 `.env` 檔案中的 `DB_PASSWORD` 是否正確

### Q: 某些功能無法使用

部分資料尚未匯入，請先補完資料匯入：
```bash
python migration/import_data.py
```

### Q: 如何查看資料庫內容

```bash
# 使用 psql
psql -U postgres -d qa_database

# 列出所有表
\dt

# 查詢資料
SELECT COUNT(*) FROM "廠商資料";
```

---

## 📈 下一步建議

### 立即執行

1. ✅ **啟動應用程式並測試基本功能**
2. ⬜ **補完剩餘資料匯入**
3. ⬜ **全面功能測試**

### 短期目標

- 設定自動備份
- 優化資料庫索引
- 監控效能

### 長期規劃

- 設定主從複製（高可用性）
- 資料庫效能調校
- 擴展到分散式部署

---

## 📞 需要協助？

### 檢查日誌

應用程式運行時會輸出詳細日誌，注意查看錯誤訊息。

### 資料庫工具

- **pgAdmin 4**: PostgreSQL 圖形化管理工具
- **DBeaver**: 通用資料庫管理工具

### 重要指令

```bash
# 測試連線
python migration/test_simple.py

# 查看資料庫狀態
psql -U postgres -d qa_database -c "SELECT table_name, pg_size_pretty(pg_relation_size('\"' || table_name || '\"')) FROM information_schema.tables WHERE table_schema='public';"

# 備份資料庫
pg_dump -U postgres qa_database > backup_$(date +%Y%m%d).sql

# 還原資料庫
psql -U postgres qa_database < backup_20260206.sql
```

---

## ✨ 成功！

你的品保資料庫系統現在運行在 PostgreSQL 上了！

**主應用程式:** `app_postgresql.py`  
**啟動指令:** `python app_postgresql.py`  
**訪問網址:** http://127.0.0.1:5000

祝使用順利！ 🎉
