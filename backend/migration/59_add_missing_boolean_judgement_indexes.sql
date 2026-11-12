-- 補建 models.py 已宣告、但從未有 migration 建立的兩個判定欄位索引。
--
-- 背景：啟動前結構檢查（backend/migration/schema_check.py）比對正式庫時發現，
-- 出貨檢驗數據.是否超差 與 爐溫測試.是否合格 在 models.py 標了 index=True，
-- 測試庫由 create_all() 建出索引，正式庫卻從來沒有。巡檢主檔.是否超差 已有同類索引。
--
-- 索引名稱與 SQLAlchemy 依 index=True 自動產生的名稱一致（ix_<表>_<欄>）。
-- CREATE INDEX IF NOT EXISTS 可安全重複執行。

CREATE INDEX IF NOT EXISTS "ix_出貨檢驗數據_是否超差" ON "出貨檢驗數據" ("是否超差");
CREATE INDEX IF NOT EXISTS "ix_爐溫測試_是否合格" ON "爐溫測試" ("是否合格");
