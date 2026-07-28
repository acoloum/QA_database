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
    "修訂原因" TEXT,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "送審者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "送審時間" TIMESTAMPTZ,
    "核准者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "核准時間" TIMESTAMPTZ,
    "核准理由" TEXT,
    "退回理由" TEXT,
    "後繼版本ID" INTEGER REFERENCES "校正模板版本"("識別碼"),
    CONSTRAINT uq_calibration_template_version
        UNIQUE ("模板ID", "版本號"),
    CONSTRAINT ck_calibration_template_default_repetitions
        CHECK ("預設重複次數" > 0),
    CONSTRAINT ck_calibration_template_version_row_version
        CHECK ("資料版本" > 0),
    CONSTRAINT ck_calibration_template_version_status
        CHECK (
            "狀態" IN (
                'draft', 'submitted', 'approved', 'rejected', 'superseded'
            )
        )
);

ALTER TABLE "校正模板"
    ADD CONSTRAINT fk_calibration_template_current_approved_version
    FOREIGN KEY ("目前核准版本ID")
    REFERENCES "校正模板版本"("識別碼");

CREATE INDEX idx_calibration_template_version_status
    ON "校正模板版本" ("模板ID", "狀態");

CREATE INDEX idx_calibration_template_version_successor
    ON "校正模板版本" ("後繼版本ID");

CREATE UNIQUE INDEX uq_calibration_template_one_approved
    ON "校正模板版本" ("模板ID")
    WHERE "狀態" = 'approved';

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
    "重複性規則" VARCHAR(40) NOT NULL,
    "重複性上限" NUMERIC,
    "資格範圍代碼" VARCHAR(80),
    "資格範圍起點" NUMERIC,
    "資格範圍終點" NUMERIC,
    "要求不確定度" BOOLEAN NOT NULL DEFAULT FALSE,
    "必填" BOOLEAN NOT NULL DEFAULT TRUE,
    "操作提示" TEXT,
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
        ),
    CONSTRAINT ck_calibration_template_point_qualification_range
        CHECK (
            "資格範圍起點" IS NULL
            OR "資格範圍終點" IS NULL
            OR "資格範圍起點" <= "資格範圍終點"
        ),
    CONSTRAINT ck_calibration_template_point_reference_mode
        CHECK (
            "參考值輸入模式" IN ('certified_value', 'paired_reading')
        ),
    CONSTRAINT ck_calibration_template_point_evaluation_basis
        CHECK ("判定基礎" IN ('all_readings', 'mean_error')),
    CONSTRAINT ck_calibration_template_point_repeatability_rule
        CHECK ("重複性規則" IN ('none', 'range', 'stddev'))
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
    ADD COLUMN "程序代碼" VARCHAR(80),
    ADD COLUMN "程序名稱" VARCHAR(160),
    ADD COLUMN "校正地點" VARCHAR(200),
    ADD COLUMN "開始時間" TIMESTAMPTZ,
    ADD COLUMN "完成時間" TIMESTAMPTZ,
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
                'draft', 'in_progress', 'ready_for_submission',
                'submitted', 'approved', 'rejected',
                'voided', 'superseded'
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
    "參考值" NUMERIC,
    "誤差下限" NUMERIC,
    "誤差上限" NUMERIC,
    "判定基礎" VARCHAR(40) NOT NULL,
    "重複性規則" VARCHAR(40) NOT NULL,
    "重複性上限" NUMERIC,
    "資格範圍代碼" VARCHAR(80),
    "參考值輸入模式" VARCHAR(40) NOT NULL,
    "必要重複次數" INTEGER NOT NULL,
    "資格範圍起點" NUMERIC,
    "資格範圍終點" NUMERIC,
    "要求不確定度" BOOLEAN NOT NULL DEFAULT FALSE,
    "必填" BOOLEAN NOT NULL DEFAULT TRUE,
    "平均值" NUMERIC,
    "誤差值" NUMERIC,
    "重複性值" NUMERIC,
    "平均器差" NUMERIC,
    "平均補正值" NUMERIC,
    "最小器差" NUMERIC,
    "最大器差" NUMERIC,
    "器差極差" NUMERIC,
    "樣本標準差" NUMERIC,
    "擴充不確定度" NUMERIC,
    "涵蓋因子" NUMERIC,
    "完整讀值數" INTEGER NOT NULL DEFAULT 0,
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
        ),
    CONSTRAINT ck_equipment_calibration_point_repetitions
        CHECK ("必要重複次數" > 0),
    CONSTRAINT ck_equipment_calibration_point_completed_count
        CHECK (
            "完整讀值數" >= 0
            AND "完整讀值數" <= "必要重複次數"
        ),
    CONSTRAINT ck_equipment_calibration_point_qualification_range
        CHECK (
            "資格範圍起點" IS NULL
            OR "資格範圍終點" IS NULL
            OR "資格範圍起點" <= "資格範圍終點"
        ),
    CONSTRAINT ck_equipment_calibration_point_reference_mode
        CHECK (
            "參考值輸入模式" IN ('certified_value', 'paired_reading')
        ),
    CONSTRAINT ck_equipment_calibration_point_evaluation_basis
        CHECK ("判定基礎" IN ('all_readings', 'mean_error')),
    CONSTRAINT ck_equipment_calibration_point_repeatability_rule
        CHECK ("重複性規則" IN ('none', 'range', 'stddev')),
    CONSTRAINT ck_equipment_calibration_point_result
        CHECK ("結果" IN ('pending', 'pass', 'fail')),
    CONSTRAINT ck_equipment_calibration_point_reference_required
        CHECK (
            "參考值輸入模式" <> 'certified_value'
            OR "參考值" IS NOT NULL
        )
);

CREATE INDEX idx_equipment_calibration_point_record
    ON "設備校正點" ("校驗紀錄ID", "點位順序");

CREATE TABLE "設備校正原始讀值" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備校正點ID" INTEGER NOT NULL
        REFERENCES "設備校正點"("識別碼"),
    "試驗序號" INTEGER NOT NULL,
    "標準器讀值" NUMERIC,
    "器示值" NUMERIC,
    "有效參考值" NUMERIC,
    "誤差值" NUMERIC,
    "補正值" NUMERIC,
    "結果" VARCHAR(30) NOT NULL DEFAULT 'pending',
    "輸入者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "輸入時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "最後修訂者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "最後修訂時間" TIMESTAMPTZ,
    "修訂原因" TEXT,
    CONSTRAINT uq_equipment_calibration_reading_trial
        UNIQUE ("設備校正點ID", "試驗序號"),
    CONSTRAINT ck_equipment_calibration_reading_trial
        CHECK ("試驗序號" > 0),
    CONSTRAINT ck_equipment_calibration_reading_result
        CHECK (
            "結果" IN (
                'pending', 'pass', 'fail', 'not_individually_evaluated'
            )
        )
);

CREATE INDEX idx_equipment_calibration_reading_point
    ON "設備校正原始讀值" ("設備校正點ID", "試驗序號");

CREATE TABLE "校正參考標準器快照" (
    "識別碼" SERIAL PRIMARY KEY,
    "校驗紀錄ID" INTEGER NOT NULL
        REFERENCES "設備校驗紀錄"("識別碼"),
    "參考標準設備ID" INTEGER NOT NULL
        REFERENCES "量測設備"("識別碼"),
    "核准校驗紀錄ID" INTEGER NOT NULL
        REFERENCES "設備校驗紀錄"("識別碼"),
    "設備編號" VARCHAR(80) NOT NULL,
    "名稱" VARCHAR(160) NOT NULL,
    "型號" VARCHAR(120),
    "序號" VARCHAR(160),
    "量程下限" NUMERIC,
    "量程上限" NUMERIC,
    "解析度" NUMERIC,
    "單位" VARCHAR(40),
    "校驗日期" DATE NOT NULL,
    "證書編號" VARCHAR(160),
    "校驗有效期" DATE,
    "結果" VARCHAR(30) NOT NULL,
    "資料雜湊" VARCHAR(64),
    "追溯標準" TEXT,
    "快照資料" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_calibration_reference_snapshot_equipment
        UNIQUE ("校驗紀錄ID", "參考標準設備ID")
);

CREATE INDEX idx_calibration_reference_snapshot_record
    ON "校正參考標準器快照" ("校驗紀錄ID");

CREATE INDEX idx_calibration_reference_snapshot_approved_record
    ON "校正參考標準器快照" ("核准校驗紀錄ID");

CREATE OR REPLACE FUNCTION calibration_block_frozen_template_version_change()
RETURNS TRIGGER AS $$
DECLARE
    successor_template_id INTEGER;
    successor_version_no INTEGER;
    creates_cycle BOOLEAN;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW."後繼版本ID" IS NOT NULL THEN
            RAISE EXCEPTION '後繼版本只能在核准版本受控取代時設定';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        IF OLD."狀態" IN ('approved', 'superseded') THEN
            RAISE EXCEPTION '核准或已取代的校正模板版本不可刪除';
        END IF;
        RETURN OLD;
    END IF;

    IF NEW."狀態" NOT IN (
        'draft', 'submitted', 'approved', 'rejected', 'superseded'
    ) THEN
        -- 未知值交由資料表 CHECK constraint 統一拒絕。
        RETURN NEW;
    END IF;

    IF OLD."狀態" IN ('rejected', 'superseded') THEN
        RAISE EXCEPTION '退回或已取代的校正模板版本不可修改';
    END IF;

    IF OLD."狀態" = 'draft' THEN
        IF NEW."狀態" = 'draft' THEN
            IF NEW."後繼版本ID"
                IS DISTINCT FROM OLD."後繼版本ID" THEN
                RAISE EXCEPTION
                    '後繼版本只能在核准版本受控取代時設定';
            END IF;
            RETURN NEW;
        END IF;

        IF NEW."狀態" <> 'submitted' THEN
            RAISE EXCEPTION '不允許的校正模板版本狀態轉態';
        END IF;
        IF (
            to_jsonb(NEW)
            - ARRAY['狀態', '送審者ID', '送審時間', '資料版本']
        ) IS DISTINCT FROM (
            to_jsonb(OLD)
            - ARRAY['狀態', '送審者ID', '送審時間', '資料版本']
        ) THEN
            RAISE EXCEPTION '校正模板版本轉態欄位不符合白名單';
        END IF;
        IF NEW."資料版本" <> OLD."資料版本" + 1 THEN
            RAISE EXCEPTION '狀態轉態時資料版本必須精確增加 1';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD."狀態" = 'submitted' THEN
        IF NEW."狀態" NOT IN ('approved', 'rejected') THEN
            RAISE EXCEPTION '不允許的校正模板版本狀態轉態';
        END IF;
        IF (
            to_jsonb(NEW)
            - ARRAY[
                '狀態', '核准者ID', '核准時間', '核准理由',
                '退回理由', '資料版本'
            ]
        ) IS DISTINCT FROM (
            to_jsonb(OLD)
            - ARRAY[
                '狀態', '核准者ID', '核准時間', '核准理由',
                '退回理由', '資料版本'
            ]
        ) THEN
            RAISE EXCEPTION '校正模板版本轉態欄位不符合白名單';
        END IF;
        IF NEW."資料版本" <> OLD."資料版本" + 1 THEN
            RAISE EXCEPTION '狀態轉態時資料版本必須精確增加 1';
        END IF;
        IF NEW."狀態" = 'approved'
            AND NEW."退回理由" IS NOT NULL THEN
            RAISE EXCEPTION '核准時必須清除退回理由';
        END IF;
        IF NEW."狀態" = 'rejected'
            AND NEW."核准理由" IS NOT NULL THEN
            RAISE EXCEPTION '退回時必須清除核准理由';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD."狀態" = 'approved' THEN
        IF NEW."狀態" <> 'superseded'
            OR NEW."後繼版本ID" IS NULL THEN
            RAISE EXCEPTION
                '核准的校正模板版本只允許連結後繼版本後取代';
        END IF;
        IF (
                to_jsonb(NEW)
                - ARRAY['狀態', '後繼版本ID', '資料版本']
            ) IS DISTINCT FROM (
                to_jsonb(OLD)
                - ARRAY['狀態', '後繼版本ID', '資料版本']
            ) THEN
            RAISE EXCEPTION '校正模板版本轉態欄位不符合白名單';
        END IF;

        IF NEW."資料版本" <> OLD."資料版本" + 1 THEN
            RAISE EXCEPTION '狀態轉態時資料版本必須精確增加 1';
        END IF;
        IF NEW."後繼版本ID" = OLD."識別碼" THEN
            RAISE EXCEPTION '後繼版本不可指向自身';
        END IF;

        SELECT version."模板ID", version."版本號"
        INTO successor_template_id, successor_version_no
        FROM "校正模板版本" AS version
        WHERE version."識別碼" = NEW."後繼版本ID";

        IF successor_template_id IS NULL THEN
            RAISE EXCEPTION '指定的後繼版本不存在';
        END IF;
        IF successor_template_id <> OLD."模板ID" THEN
            RAISE EXCEPTION '後繼版本必須屬於同一模板';
        END IF;
        IF successor_version_no <= OLD."版本號" THEN
            RAISE EXCEPTION '後繼版本號必須嚴格大於原版本';
        END IF;

        WITH RECURSIVE successor_chain AS (
            SELECT version."識別碼", version."後繼版本ID"
            FROM "校正模板版本" AS version
            WHERE version."識別碼" = NEW."後繼版本ID"
            UNION
            SELECT version."識別碼", version."後繼版本ID"
            FROM "校正模板版本" AS version
            JOIN successor_chain AS chain
              ON version."識別碼" = chain."後繼版本ID"
        )
        SELECT EXISTS (
            SELECT 1
            FROM successor_chain
            WHERE "識別碼" = OLD."識別碼"
        )
        INTO creates_cycle;

        IF creates_cycle THEN
            RAISE EXCEPTION '後繼版本不可形成循環';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION '不允許的校正模板版本狀態轉態';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calibration_template_version_frozen_immutable
    BEFORE INSERT OR UPDATE OR DELETE ON "校正模板版本"
    FOR EACH ROW
    EXECUTE FUNCTION calibration_block_frozen_template_version_change();

CREATE OR REPLACE FUNCTION calibration_block_controlled_template_point_change()
RETURNS TRIGGER AS $$
DECLARE
    original_status VARCHAR(20);
    destination_status VARCHAR(20);
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT version."狀態"
        INTO destination_status
        FROM "校正模板版本" AS version
        WHERE version."識別碼" = NEW."模板版本ID";

        IF destination_status IN (
            'submitted', 'approved', 'rejected', 'superseded'
        ) THEN
            RAISE EXCEPTION '送審後的模板校正點不可新增';
        END IF;
        RETURN NEW;
    END IF;

    SELECT version."狀態"
    INTO original_status
    FROM "校正模板版本" AS version
    WHERE version."識別碼" = OLD."模板版本ID";

    IF TG_OP = 'UPDATE' THEN
        SELECT version."狀態"
        INTO destination_status
        FROM "校正模板版本" AS version
        WHERE version."識別碼" = NEW."模板版本ID";
    END IF;

    IF original_status IN ('submitted', 'approved', 'rejected', 'superseded')
        OR destination_status IN (
            'submitted', 'approved', 'rejected', 'superseded'
        ) THEN
        RAISE EXCEPTION '送審後的模板校正點不可修改、重掛或刪除';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calibration_template_point_controlled_immutable
    BEFORE INSERT OR UPDATE OR DELETE ON "校正模板校正點"
    FOR EACH ROW
    EXECUTE FUNCTION calibration_block_controlled_template_point_change();

CREATE OR REPLACE FUNCTION calibration_block_frozen_point_change()
RETURNS TRIGGER AS $$
DECLARE
    original_status VARCHAR(30);
    destination_status VARCHAR(30);
BEGIN
    SELECT record."狀態"
    INTO original_status
    FROM "設備校驗紀錄" AS record
    WHERE record."識別碼" = OLD."校驗紀錄ID";

    IF TG_OP = 'UPDATE' THEN
        SELECT record."狀態"
        INTO destination_status
        FROM "設備校驗紀錄" AS record
        WHERE record."識別碼" = NEW."校驗紀錄ID";
    END IF;

    IF original_status IN ('submitted', 'approved')
        OR destination_status IN ('submitted', 'approved') THEN
        RAISE EXCEPTION '送審或核准後的校正點不可修改或刪除';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calibration_point_frozen_immutable
    BEFORE UPDATE OR DELETE ON "設備校正點"
    FOR EACH ROW
    EXECUTE FUNCTION calibration_block_frozen_point_change();

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
