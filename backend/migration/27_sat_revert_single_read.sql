-- Migration 27: SAT 量測點回歸單一校正測試讀值
-- 將 校正測試最高溫 改名為 校正測試讀值，並刪除 校正測試最低溫

ALTER TABLE "SAT量測點明細"
    RENAME COLUMN "校正測試最高溫" TO "校正測試讀值";

ALTER TABLE "SAT量測點明細"
    DROP COLUMN IF EXISTS "校正測試最低溫";
