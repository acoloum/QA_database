-- Migration 08：使用者資料表新增建立時間欄位
-- 執行：psql -U postgres -d qa_database -f migration/08_add_user_created_at.sql

ALTER TABLE "使用者"
    ADD COLUMN IF NOT EXISTS "建立時間" TIMESTAMPTZ DEFAULT NOW();

-- 為已存在的舊帳號填入建立時間（設定為 migration 執行當下）
UPDATE "使用者" SET "建立時間" = NOW() WHERE "建立時間" IS NULL;
