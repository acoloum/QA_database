-- 為重工申請單新增「廠商」與「材質」欄位
-- 用於支援從客訴直接開立的重工單（無 NCMR 關聯）以及讓使用者於編輯畫面修改廠商/材質

ALTER TABLE "重工申請單" ADD COLUMN IF NOT EXISTS "廠商" VARCHAR;
ALTER TABLE "重工申請單" ADD COLUMN IF NOT EXISTS "材質" VARCHAR;
