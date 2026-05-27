-- Migration 10：修正 CAPA/任務/單號一致性
-- 1. 使用者可選擇綁定品管人員，供「我的待辦」以品管人員 ID 查詢。
-- 2. 重要單號加唯一索引，搭配程式端 advisory lock 避免併發重號。

ALTER TABLE "使用者"
    ADD COLUMN IF NOT EXISTS "品管人員ID" INTEGER REFERENCES "品管人員"("識別碼");

CREATE UNIQUE INDEX IF NOT EXISTS ux_ncmr_number
    ON "不合格品單" ("NCMR單號")
    WHERE "NCMR單號" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_capa_8d_number
    ON "異常矯正單" ("8D單號")
    WHERE "8D單號" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_rework_number
    ON "重工申請單" ("申請單號")
    WHERE "申請單號" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_complaint_no
    ON "客訴紀錄" ("客訴單號")
    WHERE "客訴單號" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_no
    ON "橫展任務" ("任務單號")
    WHERE "任務單號" IS NOT NULL;
