# PostgreSQL 遷移 - 完整執行指南

## 🚀 快速開始（5 步驟完成遷移）

### 前置條件檢查
- ✅ PostgreSQL 已安裝
- ✅ SQL Server Express 資料庫已備份
- ✅ Python 3.7+ 已安裝
- ✅ 已安裝必要套件：`pip install psycopg2-binary pyodbc pandas`

---

## 📝 執行步驟

### 步驟 1：建立 PostgreSQL 資料庫 (2 分鐘)

**方法 A：使用 pgAdmin (推薦)**
1. 開啟 pgAdmin
2. 連接到 PostgreSQL 伺服器
3. 右鍵 "Databases" → "Create" → "Database..."
4. 名稱：`qa_database`
5. Owner：`postgres`
6. Encoding：`UTF8`
7. 點擊 "Save"

**方法 B：使用 SQL Shell (psql)**
```sql
CREATE DATABASE qa_database
    WITH OWNER = postgres
    ENCODING = 'UTF8';
```

---

### 步驟 2：配置資料庫連接 (1 分鐘)

編輯 `config.py` 第 25 行：

```python
'password': 'your_actual_password',  # 替換為實際密碼
```

---

### 步驟 3：部署資料庫 Schema (5 分鐘)

```bash
python migration/deploy_schema.py
```

**預期輸出：**
```
============================================================
PostgreSQL Schema 自動部署
============================================================

步驟 1: 連接到 PostgreSQL
  主機: localhost:5432
  資料庫: qa_database
  [OK] 連接成功

步驟 2: 執行 SQL 腳本
執行: 04_create_all_tables.sql
  說明: 建立所有基礎資料表
  [OK] 執行成功
...

步驟 3: 驗證資料庫結構
資料庫中的表格數量: 15
...

部署完成！
```

**驗證：**
```bash
python migration/test_connection.py
```

---

### 步驟 4：資料遷移 (10-30 分鐘，視資料量)

#### 4.1 從 SQL Server 匯出資料

```bash
python migration/export_data.py
```

**預期輸出：**
```
============================================================
SQL Server 資料匯出工具
============================================================

輸出目錄: migration/exported_data
連接到 SQL Server...
[OK] 連接成功

匯出: 品管人員
  記錄數: 25
  [OK] 已儲存: 品管人員.csv

...

匯出完成！
成功匯出: 15/15 個表格
總記錄數: 1,234
```

#### 4.2 匯入資料到 PostgreSQL

```bash
python migration/import_data.py
```

**預期輸出：**
```
============================================================
PostgreSQL 資料匯入工具
============================================================

連接到 PostgreSQL...
[OK] 連接成功

匯入: 品管人員
  來源: 品管人員.csv
  [OK] 成功匯入 25 筆記錄

...

重設序列起始值...
  品管人員.識別碼: 設定為 26
...

匯入完成！
成功匯入: 15/15 個表格
總記錄數: 1,234
```

---

### 步驟 5：測試驗證 (5-10 分鐘)

#### 5.1 啟動 PostgreSQL 版本的 Flask 應用

```bash
python app_postgresql.py
```

**預期輸出：**
```
 * Running on http://127.0.0.1:5000
```

#### 5.2 執行 API 測試

開啟另一個終端機：

```bash
python migration/test_api.py
```

**預期輸出：**
```
============================================================
API 端點測試
============================================================

階段 1: 基礎資料 API
測試: 獲取品管人員清單
  端點: GET /api/inspectors
  狀態碼: 200
[OK] 通過

...

測試摘要
總測試數: 10
通過: 10
失敗: 0

✓ 所有測試通過！
```

---

## 🔧 常見問題排除

### Q1: deploy_schema.py 連接失敗

**錯誤訊息：**
```
[ERROR] 連接失敗: FATAL: password authentication failed
```

**解決方法：**
1. 確認 `config.py` 的密碼正確
2. 確認 PostgreSQL 服務正在運行
3. 檢查 PostgreSQL 的 `pg_hba.conf` 設定

---

### Q2: export_data.py 找不到 SQL Server

**錯誤訊息：**
```
[ERROR] 連接失敗: Data source name not found
```

**解決方法：**
1. 確認 SQL Server Express 正在運行
2. 確認實例名稱為 `SQLEXPRESS`
3. 如果使用不同實例名，修改 `export_data.py` 中的連接字串

---

### Q3: import_data.py 違反外鍵約束

**錯誤訊息：**
```
[ERROR] 違反完整性約束: FOREIGN KEY constraint
```

**解決方法：**
1. 確認匯入順序正確（腳本已預設正確順序）
2. 檢查 CSV 資料中的 ID 是否正確
3. 暫時停用外鍵約束：
   ```sql
   SET session_replication_role = 'replica';  -- 匯入前
   -- 執行匯入
   SET session_replication_role = 'origin';   -- 匯入後
   ```

---

### Q4: API 測試失敗

**錯誤訊息：**
```
[ERROR] 連接失敗 - Flask 伺服器未運行
```

**解決方法：**
1. 確認 Flask 應用正在運行：`python app_postgresql.py`
2. 確認埠號 5000 未被佔用
3. 檢查 Flask 啟動時的錯誤訊息

---

## 📊 驗證檢查清單

### 資料庫結構驗證
- [ ] 15 個資料表全部建立
- [ ] 10+ 個索引建立成功
- [ ] 外鍵約束正常運作

### 資料完整性驗證
- [ ] 所有表的記錄數與 SQL Server 相符
- [ ] 序列起始值正確設定
- [ ] 中文資料正確顯示

### API 功能驗證
- [ ] 基礎資料查詢正常（品管人員、廠商等）
- [ ] 出貨檢驗數據查詢正常
- [ ] 巡檢數據查詢正常
- [ ] 登入功能正常（需先建立測試使用者）

---

## 🎯 效能優化建議

### 1. 分析查詢效能
```sql
EXPLAIN ANALYZE
SELECT * FROM "出貨檢驗數據"
WHERE "檢驗日期" >= '2025-01-01'
ORDER BY "識別碼" DESC;
```

### 2. 建立額外索引（如需要）
```sql
CREATE INDEX "IX_出貨檢驗_訂單號碼" ON "出貨檢驗數據"("訂單號碼");
```

### 3. 更新統計資訊
```sql
ANALYZE "出貨檢驗數據";
VACUUM ANALYZE;
```

---

## 📝 回滾計畫

如果遷移失敗需要回滾：

1. **停止 PostgreSQL 應用**
   ```bash
   # 按 Ctrl+C 停止 app_postgresql.py
   ```

2. **恢復使用 SQL Server**
   ```bash
   python app.py  # 使用原始版本
   ```

3. **保留資料**
   - PostgreSQL 資料庫保持不變
   - 可隨時重新嘗試

---

## 🚀 後續步驟

遷移完成後的建議：

1. **監控運行狀況** (1-2 週)
   - 記錄任何錯誤或異常
   - 比對 SQL Server 和 PostgreSQL 的查詢結果

2. **建立備份策略**
   ```bash
   pg_dump -U postgres qa_database > backup_$(date +%Y%m%d).sql
   ```

3. **設定自動備份**
   - 使用 cron (Linux) 或工作排程器 (Windows)
   - 建議每日備份

4. **效能調校**
   - 根據實際使用情況調整索引
   - 調整 PostgreSQL 配置參數

---

## 📞 支援資源

- PostgreSQL 官方文件：https://www.postgresql.org/docs/
- psycopg2 文件：https://www.psycopg.org/docs/
- Flask 文件：https://flask.palletsprojects.com/

---

**最後更新**: 2026-02-06  
**版本**: 1.1  
**狀態**: 生產就緒
