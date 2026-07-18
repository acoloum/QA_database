# Migration 36：SPC 研究版本化上線 Runbook

適用檔案：`backend/migration/36_create_spc_study_versioning.sql`。此 migration 保留舊 `SPC管制界限`，將其匯入為唯讀 `legacy_imported`，不得補造樣本雜湊、核准人或核准時間。

## 1. 上線前備份

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
pg_dump -Fc -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -f "backup-before-spc36-$stamp.dump"
pg_restore --list "backup-before-spc36-$stamp.dump" | Select-Object -First 20
```

確認備份檔非零、清單可讀，並記錄：資料庫名稱、備份檔 SHA-256、執行人、開始／完成時間。

## 2. 基準筆數

```sql
SELECT count(*) AS legacy_limit_count FROM "SPC管制界限";
SELECT count(*) AS shipping_excluded FROM "出貨巡檢量測明細" WHERE "排除統計" IS TRUE;
SELECT count(*) AS patrol_excluded FROM "巡檢子檔" WHERE "排除統計" IS TRUE;
```

將結果保存到變更單。不要只依畫面抽查。

## 3. Dry-run（必須 rollback）

`36_create_spc_study_versioning.sql` 自帶 `BEGIN/COMMIT`。dry-run 時先複製成暫存檔，把最後一行 `COMMIT;` 改成 `ROLLBACK;`，禁止直接修改版本庫原檔。

```powershell
Copy-Item backend\migration\36_create_spc_study_versioning.sql $env:TEMP\spc36-dry-run.sql
# 僅編輯暫存副本：最後 COMMIT 改為 ROLLBACK
psql -v ON_ERROR_STOP=1 -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -f $env:TEMP\spc36-dry-run.sql
```

在 rollback 前的同一交易中檢查下列條件；可把查詢插入暫存副本的 `ROLLBACK` 前：

```sql
SELECT count(*) FROM "SPC研究" WHERE "狀態" = 'legacy_imported';
SELECT count(*) FROM "SPC界限版本" WHERE "狀態" = 'legacy_imported';
SELECT count(*) FROM "SPC界限版本"
 WHERE "狀態" = 'legacy_imported'
   AND ("稽核不完整" IS NOT TRUE OR "核准者ID" IS NOT NULL OR "核准時間" IS NOT NULL);
```

預期：前兩個筆數都等於原 `SPC管制界限` 筆數；第三個筆數為 0。dry-run 完成後確認新表不存在或仍為執行前狀態。

## 4. 正式執行

```powershell
psql -v ON_ERROR_STOP=1 -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -f backend\migration\36_create_spc_study_versioning.sql
```

Migration 採 `IF NOT EXISTS` 與 legacy 唯一鍵防止重複匯入；仍須在維護時段執行並監看鎖等待。

## 5. 上線後核對

```sql
SELECT to_regclass('public."SPC管制界限"') AS legacy_table_still_exists;

SELECT
  (SELECT count(*) FROM "SPC管制界限") AS legacy_count,
  (SELECT count(*) FROM "SPC研究" WHERE "狀態"='legacy_imported') AS study_count,
  (SELECT count(*) FROM "SPC界限版本" WHERE "狀態"='legacy_imported') AS limit_count;

SELECT count(*) AS forged_approval_count
FROM "SPC界限版本"
WHERE "狀態"='legacy_imported'
  AND ("核准者ID" IS NOT NULL OR "核准時間" IS NOT NULL OR "稽核不完整" IS NOT TRUE);
```

成功條件：舊表仍存在；三個筆數一致；`forged_approval_count=0`。另抽查舊界限的 X／R 值與新 `界限內容` 一致，但不得將舊版標成 active。

## 6. 回復

若 migration 交易尚未提交，立即 `ROLLBACK`。若已提交且需回復：

1. 停止應用寫入並保存事故時間點之額外備份。
2. 優先以發版前 custom-format dump 還原到新的暫存資料庫，核對後再切換；不要直接覆蓋唯一可用資料庫。
3. 若只撤除新結構，須先確認 migration 36 後沒有正式研究／OCAP 新資料；有新資料時禁止 drop，改採資料修復方案。
4. 舊 `SPC管制界限` 從未被 migration 刪除，因此舊版應用可在相容性確認後回切。

回復完成後重新核對舊界限筆數、量測排除狀態與應用健康檢查，並把所有 SQL 輸出附在變更單。
