-- 24_add_pyrometry_chart_data.sql — 爐溫測試保留時間序列原始數據（供曲線/詳細表重現）
-- 執行：psql -U postgres -d qa_database -f backend/migration/24_add_pyrometry_chart_data.sql

BEGIN;

ALTER TABLE "爐溫測試" ADD COLUMN IF NOT EXISTS "曲線資料" JSONB;

COMMIT;
