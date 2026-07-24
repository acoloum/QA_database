-- 機械性質免測項目：設備故障等原因無法量測時標記，該項目不列入完成判定。
-- 冪等：可重複執行；表已存在則跳過。
BEGIN;

CREATE TABLE IF NOT EXISTS "機械性質免測項目" (
    "識別碼" SERIAL PRIMARY KEY,
    "機械性質檢驗_ID" INTEGER NOT NULL
        REFERENCES "機械性質檢驗" ("識別碼") ON DELETE CASCADE,
    "量測項目" VARCHAR(20) NOT NULL,
    "原因" VARCHAR(200) NOT NULL,
    "建立者ID" INTEGER REFERENCES "使用者" ("識別碼"),
    "建立日期" TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_mech_waived_item
        UNIQUE ("機械性質檢驗_ID", "量測項目"),
    CONSTRAINT ck_mech_waived_item
        CHECK ("量測項目" IN ('硬度', '抗拉強度', '降伏強度', '伸長率')),
    CONSTRAINT ck_mech_waived_reason
        CHECK ("原因" = trim("原因") AND length(trim("原因")) BETWEEN 1 AND 200)
);

CREATE INDEX IF NOT EXISTS ix_mech_waived_test_id
    ON "機械性質免測項目" ("機械性質檢驗_ID");

COMMIT;
