-- 新增出貨巡檢量測明細表與 SPC 快取表
BEGIN;

CREATE TABLE IF NOT EXISTS "出貨巡檢量測明細" (
    "識別碼"      SERIAL PRIMARY KEY,
    "出貨檢驗_ID" INTEGER NOT NULL REFERENCES "出貨檢驗數據"("識別碼") ON DELETE CASCADE,
    "組別"        INTEGER NOT NULL,
    "量測項目"    VARCHAR(30) NOT NULL,
    "下限"        NUMERIC(12, 4),
    "上限"        NUMERIC(12, 4),
    "量測最小值"  NUMERIC(12, 4),
    "量測最大值"  NUMERIC(12, 4),
    "量測值"      NUMERIC(12, 4),
    "是否超差"    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_shipping_group_item UNIQUE ("出貨檢驗_ID", "組別", "量測項目")
);

CREATE INDEX IF NOT EXISTS idx_shipping_meas_shipping_id ON "出貨巡檢量測明細"("出貨檢驗_ID");

CREATE TABLE IF NOT EXISTS "SPC快取" (
    "識別碼"    SERIAL PRIMARY KEY,
    "快取鍵"    VARCHAR(255) NOT NULL UNIQUE,
    "計算結果"  JSONB NOT NULL,
    "建立時間"  TIMESTAMP DEFAULT NOW(),
    "過期時間"  TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spc_cache_key ON "SPC快取"("快取鍵");

COMMIT;
