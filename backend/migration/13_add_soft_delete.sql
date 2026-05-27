-- 遷移 13：新增軟刪除欄位 deleted_at（刪除時間）至四個主表
-- 執行日期：2026-05-27

ALTER TABLE "不合格品單"  ADD COLUMN IF NOT EXISTS "刪除時間" TIMESTAMP;
ALTER TABLE "異常矯正單"  ADD COLUMN IF NOT EXISTS "刪除時間" TIMESTAMP;
ALTER TABLE "重工申請單"  ADD COLUMN IF NOT EXISTS "刪除時間" TIMESTAMP;
ALTER TABLE "客訴紀錄"    ADD COLUMN IF NOT EXISTS "刪除時間" TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_ncmr_deleted_at      ON "不合格品單"("刪除時間");
CREATE INDEX IF NOT EXISTS idx_capa_deleted_at      ON "異常矯正單"("刪除時間");
CREATE INDEX IF NOT EXISTS idx_rework_deleted_at    ON "重工申請單"("刪除時間");
CREATE INDEX IF NOT EXISTS idx_complaint_deleted_at ON "客訴紀錄"("刪除時間");
