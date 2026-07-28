-- 48_add_reference_standard_to_calibration.sql
-- 為設備校驗紀錄新增參考標準器欄位，用於內校追溯標準器資訊。

ALTER TABLE "設備校驗紀錄"
  ADD COLUMN "參考標準器編號" VARCHAR(160),
  ADD COLUMN "參考標準器有效期" DATE;
