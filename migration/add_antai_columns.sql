-- =============================================
-- 安泰檢驗整合 — 資料庫欄位擴展
-- 新增組別 6~10 的所有項目欄位
-- 新增組別 1~10 的真圓度欄位
-- 新增 group_count (組數) 欄位
-- =============================================

-- 新增組數欄位 (預設5組，相容既有資料)
ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "組數" INTEGER DEFAULT 5;

-- 新增真圓度欄位 (組別 1~10)
DO $$
BEGIN
    FOR i IN 1..10 LOOP
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "真圓度%s" VARCHAR', i);
    END LOOP;
END $$;

-- 新增組別 6~10 的現有項目欄位
DO $$
BEGIN
    FOR i IN 6..10 LOOP
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "外徑%s-min" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "外徑%s-max" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "內徑%s-min" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "內徑%s-max" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "厚度%s-min" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "厚度%s-max" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "同心度%s" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "長度%s" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "硬度%s" VARCHAR', i);
        EXECUTE format('ALTER TABLE "出貨檢驗數據" ADD COLUMN IF NOT EXISTS "真直度%s" VARCHAR', i);
    END LOOP;
END $$;

-- 將既有資料的 group_count 設為 5 (如果為 NULL)
UPDATE "出貨檢驗數據" SET "組數" = 5 WHERE "組數" IS NULL;
