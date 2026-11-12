# 資料庫 migration

結構異動以手寫、編號的 SQL 檔交付（`NN_說明.sql`，回復腳本為 `NN_說明.rollback.sql`）。
**不會自動套用**；測試用 `create_all()` 從 `models.py` 建表，所以測試全綠不代表正式庫已套用。

## 套用紀錄（ledger）

正式庫以 `qms_schema_migrations` 表記錄已套用的版本與檔案 checksum。以下指令都在 repo 根目錄執行，
`--app-db` 會沿用 `.env` 的連線設定，不必在命令列輸入密碼。

| 用途 | 指令 |
|------|------|
| 唯讀檢查狀態（不寫入資料庫） | `.\venv\Scripts\python.exe -m backend.migration.ledger --app-db` |
| 套用並記錄一支新 migration | `.\venv\Scripts\python.exe -m backend.migration.ledger --app-db --apply 55` |
| 為既有資料庫建立基準（只記錄、不執行 SQL） | `.\venv\Scripts\python.exe -m backend.migration.ledger --app-db --baseline 54` |
| 列出所有 migration 與 checksum | `.\venv\Scripts\python.exe -m backend.migration.ledger` |

- `--apply` 執行 SQL 後寫入紀錄。腳本本身沒有 `BEGIN/COMMIT` 時，兩者在同一個交易內、失敗一起回滾；
  腳本自帶 `COMMIT` 時，SQL 會先提交，若之後寫紀錄失敗，重跑 `--apply` 即可（請把 migration 寫成可重複執行）。
- `--baseline` 只用於 ledger 建立前就已手動套用過的資料庫；執行前會先比對資料庫結構與 `models.py`，
  不一致就拒絕，避免把漏套的 migration 記成已套用。
- 已記錄的檔案事後被修改時，狀態檢查會回報「checksum 不一致」。已套用的 migration 不要改，請另開新編號。

## 正式庫的例外：52 以 60 取代

`52_add_query_indexes.sql` 的識別字沒加雙引號，`SPC事件`、`主檔ID` 會被 PostgreSQL 轉成小寫而失敗，
因此從未在正式庫套用成功；其中多數索引也已由早期 `IX_…` 索引或 53 的 trgm 索引涵蓋。
**含英文大寫的中文識別字一律加雙引號。**
正式庫因此用 `--baseline` 把 52 記為已套用，改套 `60_add_query_indexes_missing_from_52.sql`
只補真正缺少的 10 個索引。60 的索引名稱與 52 相同，在已執行過 52 的資料庫上是 no-op；
60 的 rollback 只適用於正式庫。

## 啟動前檢查

`serve_qms.bat` 在啟動 waitress 前會執行唯讀的
`.\venv\Scripts\python.exe -m backend.migration.preflight`，結果寫進 `logs\qms_server.log`：

- 比對 `models.py` 需要的資料表、欄位與索引是否都在資料庫裡（只查缺少；索引以欄位比對、不看名稱，
  既有索引／主鍵／唯一約束包含其全部欄位即視為涵蓋；型別與 CHECK／外鍵約束不在範圍內）。
- 檢查每支 migration 是否都有套用紀錄、checksum 是否一致。

檢查失敗只寫警告，伺服器仍會啟動，避免開機時因檢查本身造成停機。
發生 500 錯誤時，先搜尋 log 裡的 `schema-preflight`。
