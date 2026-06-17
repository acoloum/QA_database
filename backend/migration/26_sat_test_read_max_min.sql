-- Migration 26: SAT 量測點「校正測試儀表讀值」拆為最高溫 / 最低溫
-- 原單一讀值欄位更名為最高溫，並新增最低溫欄位

ALTER TABLE "SAT量測點明細"
    RENAME COLUMN "校正測試儀表讀值" TO "校正測試最高溫";

ALTER TABLE "SAT量測點明細"
    ADD COLUMN "校正測試最低溫" NUMERIC(8, 2);
