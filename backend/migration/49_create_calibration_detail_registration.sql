-- 建立校正模板、逐點原始讀值與送審後不可變的詳細校正證據。
BEGIN;

CREATE TABLE "校正模板" (
    "識別碼" SERIAL PRIMARY KEY,
    "模板代碼" VARCHAR(80) NOT NULL UNIQUE,
    "名稱" VARCHAR(160) NOT NULL,
    "適用設備類型" VARCHAR(80) NOT NULL,
    "說明" TEXT,
    "狀態" VARCHAR(20) NOT NULL DEFAULT 'active',
    "目前核准版本ID" INTEGER
);

CREATE TABLE "校正模板版本" (
    "識別碼" SERIAL PRIMARY KEY,
    "模板ID" INTEGER NOT NULL REFERENCES "校正模板"("識別碼"),
    "版本號" INTEGER NOT NULL,
    "程序代碼" VARCHAR(80) NOT NULL,
    "程序名稱" VARCHAR(160) NOT NULL,
    "程序說明" TEXT,
    "預設重複次數" INTEGER NOT NULL,
    "環境要求" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "允許限制使用" BOOLEAN NOT NULL DEFAULT FALSE,
    "狀態" VARCHAR(20) NOT NULL DEFAULT 'draft',
    "資料版本" INTEGER NOT NULL DEFAULT 1,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "核准者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "核准時間" TIMESTAMPTZ,
    CONSTRAINT uq_calibration_template_version
        UNIQUE ("模板ID", "版本號"),
    CONSTRAINT ck_calibration_template_default_repetitions
        CHECK ("預設重複次數" > 0),
    CONSTRAINT ck_calibration_template_version_row_version
        CHECK ("資料版本" > 0)
);

ALTER TABLE "校正模板"
    ADD CONSTRAINT fk_calibration_template_current_approved_version
    FOREIGN KEY ("目前核准版本ID")
    REFERENCES "校正模板版本"("識別碼");

CREATE INDEX idx_calibration_template_version_status
    ON "校正模板版本" ("模板ID", "狀態");

CREATE TABLE "校正模板校正點" (
    "識別碼" SERIAL PRIMARY KEY,
    "模板版本ID" INTEGER NOT NULL
        REFERENCES "校正模板版本"("識別碼"),
    "點位順序" INTEGER NOT NULL,
    "點位代碼" VARCHAR(80) NOT NULL,
    "量測模式" VARCHAR(80) NOT NULL,
    "名目值" NUMERIC NOT NULL,
    "單位" VARCHAR(40) NOT NULL,
    "參考值輸入模式" VARCHAR(40) NOT NULL,
    "必要重複次數" INTEGER NOT NULL,
    "誤差下限" NUMERIC,
    "誤差上限" NUMERIC,
    "判定基礎" VARCHAR(40) NOT NULL,
    "重複性規則" VARCHAR(40),
    "重複性上限" NUMERIC,
    "資格範圍代碼" VARCHAR(80),
    "必填" BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_calibration_template_point_order
        UNIQUE ("模板版本ID", "點位順序"),
    CONSTRAINT uq_calibration_template_point_code
        UNIQUE ("模板版本ID", "點位代碼"),
    CONSTRAINT ck_calibration_template_point_repetitions
        CHECK ("必要重複次數" > 0),
    CONSTRAINT ck_calibration_template_point_error_order
        CHECK (
            "誤差下限" IS NULL
            OR "誤差上限" IS NULL
            OR "誤差下限" <= "誤差上限"
        ),
    CONSTRAINT ck_calibration_template_point_repeatability
        CHECK (
            "重複性規則" NOT IN ('range', 'stddev')
            OR (
                "重複性上限" IS NOT NULL
                AND "重複性上限" >= 0
            )
        )
);

CREATE INDEX idx_calibration_template_point_version
    ON "校正模板校正點" ("模板版本ID", "點位順序");

ALTER TABLE "設備校驗紀錄"
    ADD COLUMN "模板版本ID" INTEGER
        REFERENCES "校正模板版本"("識別碼"),
    ADD COLUMN "資料等級" VARCHAR(30) NOT NULL DEFAULT 'summary_legacy',
    ADD COLUMN "資料版本" INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN "模板快照" JSONB,
    ADD COLUMN "環境條件" JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN "計算摘要" JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN "計算版本" VARCHAR(40),
    ADD COLUMN "資料雜湊" VARCHAR(64),
    ADD COLUMN "參考標準設備ID" INTEGER
        REFERENCES "量測設備"("識別碼"),
    ADD COLUMN "送審者ID" INTEGER REFERENCES "使用者"("識別碼"),
    ADD COLUMN "送審時間" TIMESTAMPTZ,
    ADD COLUMN "退回理由" TEXT,
    ADD COLUMN "作廢理由" TEXT,
    ADD COLUMN "後繼紀錄ID" INTEGER
        REFERENCES "設備校驗紀錄"("識別碼");

-- Migration 44 的核准證據 trigger 會阻擋 legacy 正規化；交易內暫停後立即恢復。
ALTER TABLE "設備校驗紀錄" DISABLE TRIGGER USER;

UPDATE "設備校驗紀錄"
SET "資料等級" = 'summary_legacy',
    "狀態" = CASE
        WHEN "狀態" = 'approved' THEN 'approved'
        ELSE 'draft'
    END;

ALTER TABLE "設備校驗紀錄" ENABLE TRIGGER USER;

ALTER TABLE "設備校驗紀錄"
    ADD CONSTRAINT ck_equipment_calibration_data_level
        CHECK ("資料等級" IN ('summary_legacy', 'detailed')),
    ADD CONSTRAINT ck_equipment_calibration_detailed_evidence
        CHECK (
            "資料等級" <> 'detailed'
            OR (
                "模板版本ID" IS NOT NULL
                AND "模板快照" IS NOT NULL
            )
        ),
    ADD CONSTRAINT ck_equipment_calibration_status
        CHECK (
            "狀態" IN (
                'draft', 'submitted', 'approved',
                'rejected', 'voided', 'superseded'
            )
        ),
    ADD CONSTRAINT ck_equipment_calibration_row_version
        CHECK ("資料版本" > 0);

CREATE INDEX idx_equipment_calibration_template_version
    ON "設備校驗紀錄" ("模板版本ID");

CREATE INDEX idx_equipment_calibration_reference_standard
    ON "設備校驗紀錄" ("參考標準設備ID");

CREATE TABLE "設備校正點" (
    "識別碼" SERIAL PRIMARY KEY,
    "校驗紀錄ID" INTEGER NOT NULL
        REFERENCES "設備校驗紀錄"("識別碼"),
    "模板校正點ID" INTEGER
        REFERENCES "校正模板校正點"("識別碼"),
    "點位順序" INTEGER NOT NULL,
    "點位代碼" VARCHAR(80) NOT NULL,
    "量測模式" VARCHAR(80) NOT NULL,
    "名目值" NUMERIC NOT NULL,
    "單位" VARCHAR(40) NOT NULL,
    "參考值" NUMERIC NOT NULL,
    "誤差下限" NUMERIC,
    "誤差上限" NUMERIC,
    "判定基礎" VARCHAR(40) NOT NULL,
    "重複性規則" VARCHAR(40),
    "重複性上限" NUMERIC,
    "資格範圍代碼" VARCHAR(80),
    "平均值" NUMERIC,
    "誤差值" NUMERIC,
    "重複性值" NUMERIC,
    "結果" VARCHAR(30) NOT NULL,
    "備註" TEXT,
    CONSTRAINT uq_equipment_calibration_point_order
        UNIQUE ("校驗紀錄ID", "點位順序"),
    CONSTRAINT uq_equipment_calibration_point_code
        UNIQUE ("校驗紀錄ID", "點位代碼"),
    CONSTRAINT ck_equipment_calibration_point_error_order
        CHECK (
            "誤差下限" IS NULL
            OR "誤差上限" IS NULL
            OR "誤差下限" <= "誤差上限"
        ),
    CONSTRAINT ck_equipment_calibration_point_repeatability
        CHECK (
            "重複性規則" NOT IN ('range', 'stddev')
            OR (
                "重複性上限" IS NOT NULL
                AND "重複性上限" >= 0
            )
        )
);

CREATE INDEX idx_equipment_calibration_point_record
    ON "設備校正點" ("校驗紀錄ID", "點位順序");

CREATE TABLE "設備校正原始讀值" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備校正點ID" INTEGER NOT NULL
        REFERENCES "設備校正點"("識別碼"),
    "試驗序號" INTEGER NOT NULL,
    "器示值" NUMERIC NOT NULL,
    "誤差值" NUMERIC,
    "結果" VARCHAR(30) NOT NULL,
    "輸入者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "輸入時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_equipment_calibration_reading_trial
        UNIQUE ("設備校正點ID", "試驗序號"),
    CONSTRAINT ck_equipment_calibration_reading_trial
        CHECK ("試驗序號" > 0)
);

CREATE INDEX idx_equipment_calibration_reading_point
    ON "設備校正原始讀值" ("設備校正點ID", "試驗序號");

CREATE TABLE "校正參考標準器快照" (
    "識別碼" SERIAL PRIMARY KEY,
    "校驗紀錄ID" INTEGER NOT NULL
        REFERENCES "設備校驗紀錄"("識別碼"),
    "參考標準設備ID" INTEGER NOT NULL
        REFERENCES "量測設備"("識別碼"),
    "設備編號" VARCHAR(80) NOT NULL,
    "名稱" VARCHAR(160) NOT NULL,
    "證書編號" VARCHAR(160),
    "校驗有效期" DATE,
    "追溯標準" TEXT,
    "快照資料" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_calibration_reference_snapshot_equipment
        UNIQUE ("校驗紀錄ID", "參考標準設備ID")
);

CREATE INDEX idx_calibration_reference_snapshot_record
    ON "校正參考標準器快照" ("校驗紀錄ID");

CREATE OR REPLACE FUNCTION calibration_block_frozen_reading_change()
RETURNS TRIGGER AS $$
DECLARE
    calibration_status VARCHAR(30);
BEGIN
    SELECT record."狀態"
    INTO calibration_status
    FROM "設備校正點" AS point
    JOIN "設備校驗紀錄" AS record
      ON record."識別碼" = point."校驗紀錄ID"
    WHERE point."識別碼" = OLD."設備校正點ID";

    IF calibration_status IN ('submitted', 'approved') THEN
        RAISE EXCEPTION '送審或核准後的原始讀值不可修改或刪除';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calibration_reading_frozen_immutable
    BEFORE UPDATE OR DELETE ON "設備校正原始讀值"
    FOR EACH ROW
    EXECUTE FUNCTION calibration_block_frozen_reading_change();

COMMIT;
