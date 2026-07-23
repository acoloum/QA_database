-- 機械性質檢驗模組 Phase 1：主檔 + 批次 + 量測明細
CREATE TABLE IF NOT EXISTS "機械性質檢驗" (
    "識別碼"       SERIAL PRIMARY KEY,
    "產品尺寸"     VARCHAR(50) NOT NULL,
    "材質"         VARCHAR(50) NOT NULL,
    "廠商ID"       INTEGER REFERENCES "廠商資料"("識別碼"),
    "測試日期"     DATE,
    "T4溫度時間"   VARCHAR(100),
    "T6溫度時間"   VARCHAR(100),
    "備註"         VARCHAR,
    "是否NG"       BOOLEAN NOT NULL DEFAULT FALSE,
    "建立日期"     TIMESTAMPTZ DEFAULT NOW(),
    "建立者ID"     INTEGER REFERENCES "使用者"("識別碼"),
    "更新日期"     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mech_test_size     ON "機械性質檢驗" ("產品尺寸");
CREATE INDEX IF NOT EXISTS idx_mech_test_material ON "機械性質檢驗" ("材質");
CREATE INDEX IF NOT EXISTS idx_mech_test_date     ON "機械性質檢驗" ("測試日期");

-- 批次：一組 = 擠製編號 + 爐具編號，可多組
CREATE TABLE IF NOT EXISTS "機械性質批次" (
    "識別碼"          SERIAL PRIMARY KEY,
    "機械性質檢驗_ID" INTEGER NOT NULL REFERENCES "機械性質檢驗"("識別碼") ON DELETE CASCADE,
    "序號"            INTEGER NOT NULL DEFAULT 1,
    "擠製編號"        VARCHAR(100),
    "爐具編號"        VARCHAR(100),
    CONSTRAINT uq_mech_batch_seq UNIQUE ("機械性質檢驗_ID", "序號"),
    CONSTRAINT ck_mech_batch_seq_positive CHECK ("序號" >= 1)
);
CREATE INDEX IF NOT EXISTS idx_mech_batch_test_id ON "機械性質批次" ("機械性質檢驗_ID");

CREATE TABLE IF NOT EXISTS "機械性質量測明細" (
    "識別碼"          SERIAL PRIMARY KEY,
    "機械性質檢驗_ID" INTEGER NOT NULL REFERENCES "機械性質檢驗"("識別碼") ON DELETE CASCADE,
    "量測項目"        VARCHAR(20) NOT NULL,
    "測量位置"        VARCHAR(10) NOT NULL,
    "取樣序"          INTEGER NOT NULL,
    "量測值"          NUMERIC(12,4),
    "下限"            NUMERIC(12,4),
    "是否超差"        BOOLEAN NOT NULL DEFAULT FALSE,
    "排除統計"        BOOLEAN NOT NULL DEFAULT FALSE,
    "排除原因"        VARCHAR(200),
    "排除者ID"        INTEGER REFERENCES "使用者"("識別碼"),
    "排除時間"        TIMESTAMPTZ,
    CONSTRAINT uq_mech_group_item UNIQUE ("機械性質檢驗_ID", "量測項目", "測量位置", "取樣序"),
    CONSTRAINT ck_mech_measurement_item CHECK ("量測項目" IN ('EC值', '硬度', '抗拉強度', '降伏強度', '伸長率')),
    CONSTRAINT ck_mech_measurement_location CHECK ("測量位置" IN ('爐門', '爐頂')),
    CONSTRAINT ck_mech_measurement_sample CHECK ("取樣序" IN (1, 2))
);
CREATE INDEX IF NOT EXISTS idx_mech_meas_test_id ON "機械性質量測明細" ("機械性質檢驗_ID");
