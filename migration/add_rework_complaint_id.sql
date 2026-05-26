-- 重工申請單新增客訴 ID 欄位，用於追溯由客訴開立的重工單
ALTER TABLE "重工申請單"
    ADD COLUMN IF NOT EXISTS "客訴_ID" INTEGER;
