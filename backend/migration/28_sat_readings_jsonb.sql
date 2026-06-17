-- Migration 28: SAT 量測點明細新增多讀值 JSONB 欄位
ALTER TABLE "SAT量測點明細"
    ADD COLUMN IF NOT EXISTS "量測讀值" JSONB;
