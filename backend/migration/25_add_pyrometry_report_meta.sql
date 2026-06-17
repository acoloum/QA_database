-- 25_add_pyrometry_report_meta.sql — 爐溫測試報告表頭欄位（QRA073/074）
-- 執行：psql -U postgres -d qa_database -f backend/migration/25_add_pyrometry_report_meta.sql

BEGIN;

ALTER TABLE "爐溫測試" ADD COLUMN IF NOT EXISTS "報告欄位" JSONB;

COMMIT;
