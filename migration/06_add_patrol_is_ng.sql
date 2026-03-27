-- Migration 06: 巡檢主檔新增「是否超差」欄位
-- 對應 PatrolMain.is_ng

ALTER TABLE "巡檢主檔"
    ADD COLUMN IF NOT EXISTS "是否超差" BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_巡檢主檔_是否超差
    ON "巡檢主檔" ("是否超差");
