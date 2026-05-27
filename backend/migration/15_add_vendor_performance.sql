-- 新增廠商績效表
BEGIN;

CREATE TABLE IF NOT EXISTS "廠商績效" (
    "識別碼"          SERIAL PRIMARY KEY,
    "廠商_ID"          INTEGER NOT NULL REFERENCES "廠商資料"("識別碼") ON DELETE CASCADE,
    "期間"             VARCHAR(7) NOT NULL,
    "檢驗批次數"       INTEGER DEFAULT 0,
    "不良批次數"       INTEGER DEFAULT 0,
    "缺陷率"           FLOAT DEFAULT 0.0,
    "CAPA件數"         INTEGER DEFAULT 0,
    "平均CAPA結案天數" FLOAT,
    "客訴件數"         INTEGER DEFAULT 0,
    "績效評分"         FLOAT DEFAULT 100.0,
    "計算時間"         TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_vendor_period UNIQUE ("廠商_ID", "期間")
);

COMMIT;
