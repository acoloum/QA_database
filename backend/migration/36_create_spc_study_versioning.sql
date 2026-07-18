-- AIAG & VDA SPC 2026 現有資料版：研究版本、核准界限、事件、OCAP 與確效軌跡。
-- 舊「SPC管制界限」只匯入且完整保留；缺少原始樣本與核准人的舊資料明確標示稽核不完整。
BEGIN;

ALTER TABLE "出貨巡檢量測明細" ADD COLUMN IF NOT EXISTS "排除者ID" INTEGER;
ALTER TABLE "出貨巡檢量測明細" ADD COLUMN IF NOT EXISTS "排除時間" TIMESTAMPTZ;
ALTER TABLE "巡檢子檔" ADD COLUMN IF NOT EXISTS "排除者ID" INTEGER;
ALTER TABLE "巡檢子檔" ADD COLUMN IF NOT EXISTS "排除時間" TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_shipping_exclusion_user') THEN
        ALTER TABLE "出貨巡檢量測明細"
            ADD CONSTRAINT fk_shipping_exclusion_user
            FOREIGN KEY ("排除者ID") REFERENCES "使用者"("識別碼");
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_patrol_exclusion_user') THEN
        ALTER TABLE "巡檢子檔"
            ADD CONSTRAINT fk_patrol_exclusion_user
            FOREIGN KEY ("排除者ID") REFERENCES "使用者"("識別碼");
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS "SPC研究" (
    "識別碼" SERIAL PRIMARY KEY,
    "資料來源" VARCHAR(20) NOT NULL,
    "研究類型" VARCHAR(30) NOT NULL,
    "製程流識別鍵" VARCHAR(128) NOT NULL,
    "品質特性" VARCHAR(50) NOT NULL,
    "篩選條件" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "MSA狀態" VARCHAR(30),
    "抽樣說明" TEXT,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft',
    "舊界限ID" INTEGER UNIQUE REFERENCES "SPC管制界限"("識別碼"),
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_spc_study_stream_characteristic
    ON "SPC研究" ("製程流識別鍵", "品質特性");

CREATE TABLE IF NOT EXISTS "SPC研究版本" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究ID" INTEGER NOT NULL REFERENCES "SPC研究"("識別碼") ON DELETE CASCADE,
    "版本號" INTEGER NOT NULL,
    "方法版本" VARCHAR(30) NOT NULL,
    "程式版本" VARCHAR(80),
    "資料雜湊" VARCHAR(64),
    "規格快照" JSONB,
    "管制圖結果" JSONB,
    "穩定性結果" JSONB,
    "分布結果" JSONB,
    "時間模型結果" JSONB,
    "能力結果" JSONB,
    "適用性結果" JSONB,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft',
    "稽核不完整" BOOLEAN NOT NULL DEFAULT FALSE,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_spc_study_version UNIQUE ("研究ID", "版本號")
);

CREATE TABLE IF NOT EXISTS "SPC研究樣本" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究版本ID" INTEGER NOT NULL REFERENCES "SPC研究版本"("識別碼") ON DELETE CASCADE,
    "來源紀錄類型" VARCHAR(50) NOT NULL,
    "來源紀錄ID" INTEGER NOT NULL,
    "來源量測ID" INTEGER,
    "子組識別鍵" VARCHAR(128) NOT NULL,
    "子組順序" INTEGER NOT NULL,
    "量測值" JSONB NOT NULL,
    "排除統計" BOOLEAN NOT NULL DEFAULT FALSE,
    "排除原因" VARCHAR(200)
);

CREATE INDEX IF NOT EXISTS idx_spc_sample_version_order
    ON "SPC研究樣本" ("研究版本ID", "子組順序");

CREATE TABLE IF NOT EXISTS "SPC界限版本" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究版本ID" INTEGER NOT NULL REFERENCES "SPC研究版本"("識別碼") ON DELETE CASCADE,
    "製程流識別鍵" VARCHAR(128) NOT NULL,
    "品質特性" VARCHAR(50) NOT NULL,
    "修訂版次" INTEGER NOT NULL,
    "管制圖類型" VARCHAR(20) NOT NULL,
    "界限內容" JSONB NOT NULL,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft',
    "備註" TEXT,
    "變更原因" TEXT,
    "舊界限ID" INTEGER UNIQUE REFERENCES "SPC管制界限"("識別碼"),
    "稽核不完整" BOOLEAN NOT NULL DEFAULT FALSE,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "核准者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "核准時間" TIMESTAMPTZ,
    "生效時間" TIMESTAMPTZ,
    "停用者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "停用時間" TIMESTAMPTZ,
    CONSTRAINT uq_spc_limit_revision UNIQUE ("研究版本ID", "修訂版次")
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_spc_one_active_limit
    ON "SPC界限版本" ("製程流識別鍵", "品質特性")
    WHERE "狀態" = 'active';

CREATE TABLE IF NOT EXISTS "SPC事件" (
    "識別碼" SERIAL PRIMARY KEY,
    "界限版本ID" INTEGER NOT NULL REFERENCES "SPC界限版本"("識別碼") ON DELETE CASCADE,
    "研究版本ID" INTEGER NOT NULL REFERENCES "SPC研究版本"("識別碼"),
    "研究樣本ID" INTEGER REFERENCES "SPC研究樣本"("識別碼"),
    "圖別" VARCHAR(20) NOT NULL,
    "規則代碼" VARCHAR(50) NOT NULL,
    "點序號" INTEGER NOT NULL,
    "觀測值" NUMERIC(18, 8),
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'open',
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_spc_event_rule_point
        UNIQUE ("界限版本ID", "研究版本ID", "圖別", "規則代碼", "點序號")
);

CREATE TABLE IF NOT EXISTS "SPC異常處置" (
    "識別碼" SERIAL PRIMARY KEY,
    "事件ID" INTEGER NOT NULL UNIQUE REFERENCES "SPC事件"("識別碼") ON DELETE CASCADE,
    "6M調查" JSONB,
    "重新量測" JSONB,
    "製程調整" TEXT,
    "產品處置" TEXT,
    "負責人ID" INTEGER REFERENCES "使用者"("識別碼"),
    "效果確認" TEXT,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'open',
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "更新者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "更新時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS "SPC軟體確效執行" (
    "識別碼" SERIAL PRIMARY KEY,
    "基準資料版本" VARCHAR(80) NOT NULL,
    "方法版本" VARCHAR(30) NOT NULL,
    "程式版本" VARCHAR(80) NOT NULL,
    "預期結果" JSONB NOT NULL,
    "實際結果" JSONB NOT NULL,
    "容許誤差" JSONB NOT NULL,
    "執行結果" VARCHAR(20) NOT NULL,
    "執行者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "執行時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 舊界限沒有完整樣本、方法版本及核准軌跡，因此匯入為唯讀且不可直接啟用的版本。
INSERT INTO "SPC研究" (
    "資料來源", "研究類型", "製程流識別鍵", "品質特性", "篩選條件",
    "狀態", "舊界限ID", "建立時間"
)
SELECT
    old."資料來源",
    'retrospective',
    md5(concat_ws('|', old."資料來源", old."廠商", old."材質", old."規格", old."量測項目", old."位置")),
    old."量測項目",
    jsonb_build_object(
        'source', old."資料來源", 'vendor', old."廠商", 'material', old."材質",
        'spec', old."規格", 'field', old."量測項目", 'position', old."位置"
    ),
    'legacy_imported',
    old."識別碼",
    COALESCE(old."建立時間", CURRENT_TIMESTAMP)
FROM "SPC管制界限" AS old
WHERE NOT EXISTS (
    SELECT 1 FROM "SPC研究" AS study WHERE study."舊界限ID" = old."識別碼"
);

INSERT INTO "SPC研究版本" (
    "研究ID", "版本號", "方法版本", "程式版本", "資料雜湊",
    "管制圖結果", "適用性結果", "狀態", "稽核不完整", "建立時間"
)
SELECT
    study."識別碼", 1, 'legacy-pre-2026', NULL, NULL,
    jsonb_build_object(
        'chart_type', 'xbar_r', 'x_cl', old."X中心線", 'x_ucl', old."X上限",
        'x_lcl', old."X下限", 'r_cl', old."R中心線", 'r_ucl', old."R上限",
        'r_lcl', old."R下限", 'avg_n', old."子組大小"
    ),
    jsonb_build_object('reason_code', 'legacy_audit_incomplete'),
    'legacy_imported', TRUE, COALESCE(old."建立時間", CURRENT_TIMESTAMP)
FROM "SPC研究" AS study
JOIN "SPC管制界限" AS old ON old."識別碼" = study."舊界限ID"
WHERE NOT EXISTS (
    SELECT 1 FROM "SPC研究版本" AS version
    WHERE version."研究ID" = study."識別碼" AND version."版本號" = 1
);

INSERT INTO "SPC界限版本" (
    "研究版本ID", "製程流識別鍵", "品質特性", "修訂版次", "管制圖類型",
    "界限內容", "狀態", "備註", "舊界限ID", "稽核不完整", "建立時間"
)
SELECT
    version."識別碼", study."製程流識別鍵", study."品質特性", 1, 'xbar_r',
    jsonb_build_object(
        'location', jsonb_build_object(
            'cl', old."X中心線", 'ucl', old."X上限", 'lcl', old."X下限"
        ),
        'variation', jsonb_build_object(
            'cl', old."R中心線", 'ucl', old."R上限", 'lcl', old."R下限"
        ),
        'avg_n', old."子組大小"
    ),
    'legacy_imported',
    '舊版資料缺少樣本雜湊、完整方法版本及核准軌跡，不得直接作為新版啟用界限。',
    old."識別碼", TRUE, COALESCE(old."建立時間", CURRENT_TIMESTAMP)
FROM "SPC研究" AS study
JOIN "SPC研究版本" AS version
    ON version."研究ID" = study."識別碼" AND version."版本號" = 1
JOIN "SPC管制界限" AS old ON old."識別碼" = study."舊界限ID"
WHERE NOT EXISTS (
    SELECT 1 FROM "SPC界限版本" AS limits WHERE limits."舊界限ID" = old."識別碼"
);

COMMIT;
