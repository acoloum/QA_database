-- 出貨巡檢量測明細新增「測量位置」欄位（支援外徑前/中/後分段量測）
-- 空字串 = 未分段；唯一鍵納入位置。既有資料不需搬移。
BEGIN;

ALTER TABLE "出貨巡檢量測明細"
    ADD COLUMN IF NOT EXISTS "測量位置" VARCHAR(10) NOT NULL DEFAULT '';

ALTER TABLE "出貨巡檢量測明細"
    DROP CONSTRAINT IF EXISTS uq_shipping_group_item;

ALTER TABLE "出貨巡檢量測明細"
    ADD CONSTRAINT uq_shipping_group_item
    UNIQUE ("出貨檢驗_ID", "組別", "量測項目", "測量位置");

COMMIT;
