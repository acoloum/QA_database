-- MSA 第四版：建立通用量測設備、匯入軌跡與版控判定準則。
-- 核准證據採 append-only；資料庫層以原始狀態阻擋繞過服務／ORM 的覆寫。
BEGIN;

CREATE OR REPLACE FUNCTION msa_limited_use_evidence_valid(
    applicable_modes JSONB,
    restriction_conditions TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN applicable_modes IS NULL
            OR jsonb_typeof(applicable_modes) <> 'array' THEN FALSE
        WHEN jsonb_array_length(applicable_modes) = 0 THEN FALSE
        WHEN BTRIM(COALESCE(restriction_conditions, '')) = '' THEN FALSE
        ELSE NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(applicable_modes) AS mode(value)
            WHERE jsonb_typeof(mode.value) <> 'string'
                OR BTRIM(mode.value #>> '{}') = ''
        )
    END
$$;

CREATE TABLE "量測設備" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備編號" VARCHAR(80) NOT NULL UNIQUE,
    "名稱" VARCHAR(160) NOT NULL,
    "設備類型" VARCHAR(80),
    "製造商" VARCHAR(120),
    "型號" VARCHAR(120),
    "序號" VARCHAR(160),
    "量程下限" NUMERIC,
    "量程上限" NUMERIC,
    "解析度" NUMERIC,
    "單位" VARCHAR(40),
    "部門" VARCHAR(120),
    "存放位置" VARCHAR(200),
    "保管人" VARCHAR(120),
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    "校驗類別" VARCHAR(30),
    "校驗豁免理由" TEXT,
    "校驗週期月數" INTEGER,
    "參考標準" BOOLEAN NOT NULL DEFAULT FALSE,
    "影響產品判定" BOOLEAN NOT NULL DEFAULT TRUE,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "更新者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "更新時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_equipment_status CHECK (
        "狀態" IN (
            'pending_review', 'active', 'maintenance', 'inactive', 'scrapped'
        )
    ),
    CONSTRAINT ck_equipment_calibration_type CHECK (
        "校驗類別" IS NULL
        OR "校驗類別" IN ('internal', 'external', 'exempt')
    ),
    CONSTRAINT ck_equipment_exemption_reason CHECK (
        "校驗類別" <> 'exempt'
        OR BTRIM(COALESCE("校驗豁免理由", '')) <> ''
    )
);

CREATE INDEX idx_equipment_status_due
    ON "量測設備" ("狀態", "設備編號");

CREATE TABLE "量測設備連結" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備ID" INTEGER NOT NULL REFERENCES "量測設備"("識別碼"),
    "來源模組" VARCHAR(50) NOT NULL,
    "來源實體類型" VARCHAR(80) NOT NULL,
    "來源實體ID" INTEGER NOT NULL,
    "目前正式連結" BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE UNIQUE INDEX uq_equipment_current_source_link
    ON "量測設備連結" ("來源模組", "來源實體類型", "來源實體ID")
    WHERE "目前正式連結" IS TRUE;

CREATE INDEX idx_equipment_link_equipment
    ON "量測設備連結" ("設備ID");

CREATE TABLE "設備校驗紀錄" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備ID" INTEGER NOT NULL REFERENCES "量測設備"("識別碼"),
    "校驗類型" VARCHAR(30) NOT NULL,
    "校驗日期" DATE NOT NULL,
    "有效日期" DATE,
    "下次校驗日" DATE,
    "校驗機構" VARCHAR(160),
    "證書編號" VARCHAR(160),
    "追溯標準" TEXT,
    "不確定度說明" TEXT,
    "結果" VARCHAR(30) NOT NULL,
    "適用量測模式" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "限制條件" TEXT,
    "核准理由" TEXT,
    "原始證書附件ID" INTEGER REFERENCES "附件"("識別碼"),
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft',
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "核准者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "核准時間" TIMESTAMPTZ,
    CONSTRAINT ck_equipment_calibration_result CHECK (
        "結果" IN ('pending', 'pass', 'fail', 'limited_use')
    ),
    CONSTRAINT ck_equipment_limited_use_modes CHECK (
        "結果" <> 'limited_use'
        OR msa_limited_use_evidence_valid(
            "適用量測模式", "限制條件"
        )
    )
);

CREATE INDEX idx_equipment_calibration_equipment_date
    ON "設備校驗紀錄" ("設備ID", "校驗日期");

CREATE INDEX idx_equipment_calibration_due_status
    ON "設備校驗紀錄" ("下次校驗日", "狀態");

CREATE TABLE "設備校驗補正點" (
    "識別碼" SERIAL PRIMARY KEY,
    "校驗紀錄ID" INTEGER NOT NULL REFERENCES "設備校驗紀錄"("識別碼"),
    "量測模式" VARCHAR(80),
    "名目值" NUMERIC NOT NULL,
    "器示值" NUMERIC NOT NULL,
    "誤差值" NUMERIC,
    "補正值" NUMERIC,
    "單位" VARCHAR(40),
    "適用量程起點" NUMERIC,
    "適用量程終點" NUMERIC
);

CREATE INDEX idx_equipment_correction_record
    ON "設備校驗補正點" ("校驗紀錄ID");

CREATE TABLE "設備狀態事件" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備ID" INTEGER NOT NULL REFERENCES "量測設備"("識別碼"),
    "事件類型" VARCHAR(40) NOT NULL,
    "發生時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "原因" TEXT,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "觸發MSA再研究" BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_equipment_status_event_equipment_time
    ON "設備狀態事件" ("設備ID", "發生時間");

CREATE TABLE "設備匯入批次" (
    "識別碼" SERIAL PRIMARY KEY,
    "原始檔名" VARCHAR(255) NOT NULL,
    "檔案SHA256" VARCHAR(64) NOT NULL,
    "檔案大小" BIGINT NOT NULL,
    "上傳者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "上傳時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "狀態" VARCHAR(30) NOT NULL,
    "總列數" INTEGER NOT NULL DEFAULT 0,
    "成功數" INTEGER NOT NULL DEFAULT 0,
    "待確認數" INTEGER NOT NULL DEFAULT 0,
    "拒絕數" INTEGER NOT NULL DEFAULT 0,
    "解析器版本" VARCHAR(80) NOT NULL
);

CREATE UNIQUE INDEX uq_equipment_import_sha
    ON "設備匯入批次" ("檔案SHA256");

CREATE INDEX idx_equipment_import_status_time
    ON "設備匯入批次" ("狀態", "上傳時間");

CREATE TABLE "設備匯入列" (
    "識別碼" SERIAL PRIMARY KEY,
    "匯入批次ID" INTEGER NOT NULL REFERENCES "設備匯入批次"("識別碼"),
    "原始列號" INTEGER NOT NULL,
    "原始JSON" JSONB NOT NULL,
    "正規化JSON" JSONB,
    "問題代碼" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "問題說明" TEXT,
    "對應設備ID" INTEGER REFERENCES "量測設備"("識別碼"),
    "確認者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "確認時間" TIMESTAMPTZ,
    CONSTRAINT uq_equipment_import_row
        UNIQUE ("匯入批次ID", "原始列號")
);

CREATE INDEX idx_equipment_import_row_equipment
    ON "設備匯入列" ("對應設備ID");

CREATE TABLE "MSA準則設定" (
    "識別碼" SERIAL PRIMARY KEY,
    "名稱" VARCHAR(160) NOT NULL,
    "顧客範圍" VARCHAR(200),
    "產品範圍" VARCHAR(200),
    "產品族範圍" VARCHAR(200),
    "品質特性範圍" VARCHAR(200),
    "特性重要度" VARCHAR(40),
    "適用研究類型" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "目前啟用版本ID" INTEGER
);

CREATE TABLE "MSA準則版本" (
    "識別碼" SERIAL PRIMARY KEY,
    "準則設定ID" INTEGER NOT NULL REFERENCES "MSA準則設定"("識別碼"),
    "版本號" INTEGER NOT NULL,
    "方法版本" VARCHAR(80) NOT NULL,
    "適用日期" DATE NOT NULL,
    "門檻" JSONB NOT NULL,
    "穩定性規則組" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "條件接受強制處置" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "依據" TEXT,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft',
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "核准者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "核准時間" TIMESTAMPTZ
);

ALTER TABLE "MSA準則版本"
    ADD CONSTRAINT uq_msa_criteria_revision
    UNIQUE ("準則設定ID", "版本號");

ALTER TABLE "MSA準則版本"
    ADD CONSTRAINT uq_msa_criteria_profile_version_identity
    UNIQUE ("準則設定ID", "識別碼");

ALTER TABLE "MSA準則設定"
    ADD CONSTRAINT fk_msa_criteria_current_version
    FOREIGN KEY ("識別碼", "目前啟用版本ID")
    REFERENCES "MSA準則版本"("準則設定ID", "識別碼")
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX idx_msa_criteria_status_effective
    ON "MSA準則版本" ("狀態", "適用日期");

CREATE OR REPLACE FUNCTION msa_block_approved_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' OR OLD."狀態" = 'approved' THEN
        RAISE EXCEPTION '核准的 MSA 證據不可修改或刪除';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_equipment_calibration_approved_immutable
    BEFORE UPDATE OR DELETE ON "設備校驗紀錄"
    FOR EACH ROW EXECUTE FUNCTION msa_block_approved_change();

CREATE TRIGGER trg_msa_criteria_version_approved_immutable
    BEFORE UPDATE OR DELETE ON "MSA準則版本"
    FOR EACH ROW EXECUTE FUNCTION msa_block_approved_change();

COMMIT;
