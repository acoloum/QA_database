-- 把舊版 CAR 模式 (CAR單號非空) 紀錄的 CAR單號 搬到 8D單號，加 'CAR-' 前綴避免衝突
-- 同時清空 CAR單號 避免之後 DROP COLUMN 時資料遺失歷史追溯
BEGIN;

UPDATE "異常矯正單"
SET "8D單號" = 'CAR-' || "CAR單號"
WHERE "CAR單號" IS NOT NULL
  AND "8D單號" IS NULL;

COMMIT;
