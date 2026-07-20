# Migration 39：SPC 軟體確效執行紀錄補強手冊

本 migration 為 `SPC軟體確效執行` 新增 `差異明細`（JSONB，`NOT NULL DEFAULT
'[]'`）、將 `執行結果` 限制為 `PASS`／`FAIL` 的 CHECK constraint，並建立
`BEFORE UPDATE OR DELETE` 不可變 trigger（重用既有
`spc_block_immutable_change()` 函式）。腳本位於
`backend/migration/39_harden_spc_validation_runs.sql`，所有 DDL 在單一交易
內，preflight 失敗會整體回滾，不得手動刪除或合併既有確效證據。

## 背景

前次 Task 10 審查發現 `spc_advanced_regression.py` 僅新增死碼：執行者授權檢查
未接線、NaN/Infinity 仍直接拋例外、`SpcValidationRun` 未寫入差異明細，導致
`SPC軟體確效執行` 表缺少對應欄位與約束。本 migration 補齊資料庫端的約束，使
上述修正在資料庫層也具備強制力。

## 先決條件

- 使用 repo 根目錄 `C:\QC_Database\.env` 的 `DB_HOST`、`DB_PORT`、
  `DB_NAME`、`DB_USER`、`DB_PASSWORD`；不得將密碼寫入命令歷程、文件或輸出。
- 確認 PostgreSQL 18 `psql`：`C:\Program Files\PostgreSQL\18\bin\psql.exe`。
- 確認最近每日備份存在、可讀且大小不為零。2026-07-20 正式執行前確認：
  `C:\QC_Database\database_backup\backups\qa_backup_20260720_020002.dump`，
  大小 `5,179,509 bytes`。
- 正式套用前先完成 rollback dry-run；任何錯誤都必須停止，不可直接修改資料
  規避。

## Rollback dry-run

dry-run 檔只能建立在目前 worktree 的 `tmp\migration`，是 migration 的機械
複本，唯一差異是交易結尾由 `COMMIT` 改為 `ROLLBACK`（作法同
[migration 38 runbook](38-spc-analysis-family-runbook.md)）。

2026-07-20 執行證據：dry-run 路徑 prefix 驗證通過，`COMMIT=0`、
`ROLLBACK=1`；輸出依序為 `BEGIN` → `ALTER TABLE` → `DO`（preflight）→
`ALTER TABLE` ×2 → `DROP TRIGGER`／`CREATE TRIGGER` → `ROLLBACK`，結果 PASS，
無錯誤。

## 正式套用與 idempotent 重跑

2026-07-20 對 `qa_database` 的首次套用以 `COMMIT` 結束；第二次完整重跑同樣以
`COMMIT` 結束，只出現「欄位已存在，skipping」的 NOTICE，沒有錯誤或人工資料
修補，確認 idempotent。

## 套用後查核

2026-07-20 查核結果（`information_schema.columns` 與 `pg_constraint` /
`pg_trigger`）：

- `差異明細`：`is_nullable=NO`、`column_default='[]'::jsonb`。
- `ck_spc_validation_result`：CHECK `執行結果 IN ('PASS','FAIL')`。
- `trg_spc_validation_run_immutable`：`tgenabled='O'`（已啟用）。

既有 `SpcValidationRun.id=1`（2026-07-19、`程式版本=2026.1` 的舊確效證據）不受
影響，維持不可變。套用後以修正過的
`spc_advanced_regression.py --persist --executed-by 1` 重新執行一次確效，
新增 `id=2`（`程式版本=2026.2`、`執行結果=PASS`、`差異明細=[]`），作為本次
修正後的正式稽核紀錄。

## 暫存檔清理

取得證據後只清理由路徑 prefix 驗證過的 worktree 暫存檔（`tmp\migration`
內容可由 committed migration 重新產生，不含業務資料），作法同
[migration 38 runbook](38-spc-analysis-family-runbook.md)。2026-07-20 已清理
完畢。
