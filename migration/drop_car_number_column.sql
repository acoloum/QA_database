-- 警告：destructive，執行前必須確認所有 CAR 紀錄已透過 migrate_car_to_capa.sql 搬到 8D單號
ALTER TABLE "異常矯正單" DROP COLUMN IF EXISTS "CAR單號";
