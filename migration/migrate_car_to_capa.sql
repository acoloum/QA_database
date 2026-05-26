-- 把舊版 CAR 模式 (CAR單號非空) 紀錄的 CAR單號 資料複製到 8D單號，加 'CAR-' 前綴避免衝突
-- CAR單號 欄位本身保留不動，待 Task 16（drop_car_number_column.sql）執行時一併 DROP
BEGIN;

UPDATE "異常矯正單"
SET "8D單號" = 'CAR-' || "CAR單號"
WHERE "CAR單號" IS NOT NULL
  AND "8D單號" IS NULL;

COMMIT;
