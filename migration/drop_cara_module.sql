-- 警告：destructive，執行前必須先確認 migrate_cara_to_capa.sql 已成功
BEGIN;

-- 客訴紀錄移除 related_cara_id 欄位
ALTER TABLE "客訴紀錄" DROP COLUMN IF EXISTS "關聯CARA_ID";

-- DROP CARA 表
DROP TABLE IF EXISTS "矯正措施要求";

COMMIT;
