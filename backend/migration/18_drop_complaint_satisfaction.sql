-- 移除客訴的「客戶滿意度」與「滿意度備註」欄位（結案流程已不再需要滿意度）

ALTER TABLE "客訴紀錄" DROP COLUMN IF EXISTS "客戶滿意度";
ALTER TABLE "客訴紀錄" DROP COLUMN IF EXISTS "滿意度備註";
