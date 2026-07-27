-- MSA 第四版：建立研究生命週期、盲測觀測、不可變結果與工作流證據。
-- 計畫凍結後、觀測建立後、結果統計與決策一律 append-only；
-- 資料庫層以 trigger 阻擋繞過服務／ORM 的覆寫，只放行明確白名單的狀態變更。
BEGIN;

-- 研究編號採全域遞增 sequence；年份只表示建立年度，不逐年歸零。
CREATE SEQUENCE IF NOT EXISTS msa_study_number_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE "MSA研究" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究編號" VARCHAR(40) NOT NULL UNIQUE,
    "研究類型" VARCHAR(40) NOT NULL,
    "量測目的" VARCHAR(40) NOT NULL,
    "品質特性" VARCHAR(200) NOT NULL,
    "單位" VARCHAR(40) NOT NULL,
    "規格下限" NUMERIC,
    "規格上限" NUMERIC,
    "無公差原因" TEXT,
    "製程標準差" NUMERIC,
    "準則設定ID" INTEGER REFERENCES "MSA準則設定"("識別碼"),
    "負責人ID" INTEGER REFERENCES "使用者"("識別碼"),
    "主要執行者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'draft',
    "目前計畫版本ID" INTEGER,
    "目前結果版本ID" INTEGER,
    "前次核准研究ID" INTEGER REFERENCES "MSA研究"("識別碼"),
    "下次到期日" DATE,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "更新者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "更新時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_msa_study_status CHECK (
        "狀態" IN (
            'draft', 'ready', 'collecting', 'ready_for_analysis',
            'analyzed', 'submitted', 'approved', 'rejected',
            'voided', 'superseded'
        )
    ),
    CONSTRAINT ck_msa_study_purpose CHECK (
        "量測目的" IN ('product_control', 'process_control')
    ),
    CONSTRAINT ck_msa_study_spec_order CHECK (
        "規格下限" IS NULL
        OR "規格上限" IS NULL
        OR "規格下限" < "規格上限"
    )
);

CREATE INDEX idx_msa_study_status_due
    ON "MSA研究" ("狀態", "下次到期日");

CREATE TABLE "MSA研究設備" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究ID" INTEGER NOT NULL REFERENCES "MSA研究"("識別碼"),
    "設備ID" INTEGER NOT NULL REFERENCES "量測設備"("識別碼"),
    "角色" VARCHAR(40) NOT NULL,
    "量測模式" VARCHAR(60) NOT NULL DEFAULT 'default',
    "備註" TEXT,
    CONSTRAINT uq_msa_study_equipment_role
        UNIQUE ("研究ID", "設備ID", "角色", "量測模式"),
    CONSTRAINT ck_msa_study_equipment_role CHECK (
        "角色" IN (
            'primary_gauge', 'reference_standard', 'fixture', 'auxiliary'
        )
    )
);

CREATE TABLE "MSA計畫版本" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究ID" INTEGER NOT NULL REFERENCES "MSA研究"("識別碼"),
    "計畫版本號" INTEGER NOT NULL,
    "方法代碼" VARCHAR(80) NOT NULL,
    "方法版本" VARCHAR(40) NOT NULL,
    "設計型態" VARCHAR(40) NOT NULL DEFAULT 'crossed',
    "零件數" INTEGER NOT NULL,
    "評價人數" INTEGER NOT NULL,
    "試驗次數" INTEGER NOT NULL,
    "隨機種子" BIGINT NOT NULL,
    "隨機順序" JSONB NOT NULL DEFAULT '[]'::JSONB,
    "設備快照" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "準則快照" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "計數類別集合" JSONB NOT NULL DEFAULT '[]'::JSONB,
    "抽樣說明" TEXT,
    "環境說明" TEXT,
    "計畫雜湊" VARCHAR(64),
    "凍結者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "凍結時間" TIMESTAMPTZ,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_msa_plan_revision UNIQUE ("研究ID", "計畫版本號"),
    CONSTRAINT ck_msa_plan_counts CHECK (
        "零件數" > 0 AND "評價人數" > 0 AND "試驗次數" > 0
    ),
    CONSTRAINT ck_msa_plan_frozen_evidence CHECK (
        ("凍結時間" IS NULL AND "凍結者ID" IS NULL)
        OR ("凍結時間" IS NOT NULL AND "凍結者ID" IS NOT NULL
            AND "計畫雜湊" IS NOT NULL)
    )
);

ALTER TABLE "MSA研究"
    ADD CONSTRAINT fk_msa_study_current_plan
    FOREIGN KEY ("目前計畫版本ID") REFERENCES "MSA計畫版本"("識別碼")
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE "MSA零件" (
    "識別碼" SERIAL PRIMARY KEY,
    "計畫版本ID" INTEGER NOT NULL REFERENCES "MSA計畫版本"("識別碼"),
    "零件序號" INTEGER NOT NULL,
    "盲碼" VARCHAR(40) NOT NULL,
    "零件識別" VARCHAR(200),
    "參考值" NUMERIC,
    "參考不確定度" NUMERIC,
    "備註" TEXT,
    CONSTRAINT uq_msa_part_no UNIQUE ("計畫版本ID", "零件序號"),
    CONSTRAINT uq_msa_part_blind_code UNIQUE ("計畫版本ID", "盲碼")
);

CREATE TABLE "MSA評價人" (
    "識別碼" SERIAL PRIMARY KEY,
    "計畫版本ID" INTEGER NOT NULL REFERENCES "MSA計畫版本"("識別碼"),
    "評價人序號" INTEGER NOT NULL,
    "盲碼" VARCHAR(40) NOT NULL,
    "使用者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "姓名" VARCHAR(120) NOT NULL,
    "資格說明" TEXT,
    CONSTRAINT uq_msa_appraiser_no UNIQUE ("計畫版本ID", "評價人序號"),
    CONSTRAINT uq_msa_appraiser_blind_code UNIQUE ("計畫版本ID", "盲碼")
);

CREATE TABLE "MSA觀測匯入批次" (
    "識別碼" SERIAL PRIMARY KEY,
    "計畫版本ID" INTEGER NOT NULL REFERENCES "MSA計畫版本"("識別碼"),
    "檔案名稱" VARCHAR(255) NOT NULL,
    "檔案SHA256" VARCHAR(64) NOT NULL,
    "計畫雜湊" VARCHAR(64),
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'previewed',
    "問題" JSONB NOT NULL DEFAULT '[]'::JSONB,
    "統計" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_msa_observation_import_sha
        UNIQUE ("計畫版本ID", "檔案SHA256"),
    CONSTRAINT ck_msa_observation_import_status CHECK (
        "狀態" IN ('previewed', 'confirmed', 'rejected')
    )
);

CREATE TABLE "MSA觀測" (
    "識別碼" SERIAL PRIMARY KEY,
    "計畫版本ID" INTEGER NOT NULL REFERENCES "MSA計畫版本"("識別碼"),
    "零件ID" INTEGER NOT NULL REFERENCES "MSA零件"("識別碼"),
    "評價人ID" INTEGER NOT NULL REFERENCES "MSA評價人"("識別碼"),
    "試驗次數" INTEGER NOT NULL,
    "要求順序" INTEGER NOT NULL,
    "實際輸入順序" INTEGER NOT NULL,
    "計量讀值" NUMERIC,
    "計數分類" VARCHAR(80),
    "量測時間" TIMESTAMPTZ,
    "來源" VARCHAR(30) NOT NULL,
    "輸入者ID" INTEGER NOT NULL REFERENCES "使用者"("識別碼"),
    "是否有效" BOOLEAN NOT NULL DEFAULT TRUE,
    "取代來源ID" INTEGER REFERENCES "MSA觀測"("識別碼"),
    "修正理由" TEXT,
    "匯入批次ID" INTEGER REFERENCES "MSA觀測匯入批次"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_msa_observation_one_value CHECK (
        ("計量讀值" IS NOT NULL AND "計數分類" IS NULL)
        OR ("計量讀值" IS NULL AND "計數分類" IS NOT NULL)
    ),
    CONSTRAINT ck_msa_observation_source CHECK (
        "來源" IN ('page_single', 'page_matrix', 'excel_import')
    ),
    CONSTRAINT ck_msa_observation_trial CHECK ("試驗次數" > 0)
);

-- 同一盲測任務同時只能有一筆有效觀測；修正以新增後繼紀錄表達。
CREATE UNIQUE INDEX uq_msa_effective_observation
    ON "MSA觀測" ("計畫版本ID", "零件ID", "評價人ID", "試驗次數")
    WHERE "是否有效" IS TRUE;

CREATE INDEX idx_msa_observation_plan_order
    ON "MSA觀測" ("計畫版本ID", "實際輸入順序");

CREATE TABLE "MSA結果版本" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究ID" INTEGER NOT NULL REFERENCES "MSA研究"("識別碼"),
    "計畫版本ID" INTEGER NOT NULL REFERENCES "MSA計畫版本"("識別碼"),
    "結果版本號" INTEGER NOT NULL,
    "方法代碼" VARCHAR(80) NOT NULL,
    "方法版本" VARCHAR(40) NOT NULL,
    "程式版本" VARCHAR(80) NOT NULL,
    "資料雜湊" VARCHAR(64) NOT NULL,
    "原始資料摘要" JSONB NOT NULL,
    "適用性結果" JSONB NOT NULL,
    "統計結果" JSONB NOT NULL,
    "圖表資料" JSONB NOT NULL,
    "準則快照" JSONB NOT NULL,
    "結論" JSONB NOT NULL,
    "警告" JSONB NOT NULL DEFAULT '[]'::JSONB,
    "阻擋條件" JSONB NOT NULL DEFAULT '[]'::JSONB,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'analyzed',
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_msa_result_revision UNIQUE ("研究ID", "結果版本號"),
    CONSTRAINT ck_msa_result_status CHECK (
        "狀態" IN (
            'analyzed', 'submitted', 'approved',
            'rejected', 'voided', 'superseded'
        )
    )
);

-- 同一研究同時只能有一個送審中的結果版本。
CREATE UNIQUE INDEX uq_msa_one_submitted_result
    ON "MSA結果版本" ("研究ID")
    WHERE "狀態" = 'submitted';

ALTER TABLE "MSA研究"
    ADD CONSTRAINT fk_msa_study_current_result
    FOREIGN KEY ("目前結果版本ID") REFERENCES "MSA結果版本"("識別碼")
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE "MSA工作流決策" (
    "識別碼" SERIAL PRIMARY KEY,
    "研究ID" INTEGER NOT NULL REFERENCES "MSA研究"("識別碼"),
    "結果版本ID" INTEGER REFERENCES "MSA結果版本"("識別碼"),
    "動作" VARCHAR(40) NOT NULL,
    "原狀態" VARCHAR(30),
    "新狀態" VARCHAR(30),
    "理由" TEXT,
    "執行者ID" INTEGER NOT NULL REFERENCES "使用者"("識別碼"),
    "職責分離檢查" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "附加資料" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_msa_decision_study
    ON "MSA工作流決策" ("研究ID", "建立時間");

CREATE TABLE "MSA再研究要求" (
    "識別碼" SERIAL PRIMARY KEY,
    "來源研究ID" INTEGER NOT NULL REFERENCES "MSA研究"("識別碼"),
    "觸發類型" VARCHAR(60) NOT NULL,
    "來源實體類型" VARCHAR(60) NOT NULL,
    "來源實體ID" INTEGER,
    "觸發內容" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "到期日" DATE,
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'open',
    "新研究ID" INTEGER REFERENCES "MSA研究"("識別碼"),
    "建立者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_msa_restudy_status CHECK (
        "狀態" IN ('open', 'in_progress', 'completed', 'dismissed')
    )
);

-- 同一來源事件只建立一次再研究要求，讓觸發可安全重放。
CREATE UNIQUE INDEX uq_msa_restudy_source_event
    ON "MSA再研究要求" (
        "來源研究ID", "觸發類型", "來源實體類型", "來源實體ID"
    )
    WHERE "來源實體ID" IS NOT NULL;

CREATE TABLE "MSA軟體確效執行" (
    "識別碼" SERIAL PRIMARY KEY,
    "案例代碼" VARCHAR(120) NOT NULL,
    "資料指紋" VARCHAR(64) NOT NULL,
    "方法版本" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "程式版本" VARCHAR(80),
    "容許誤差" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "觀測值" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "期望值" JSONB NOT NULL DEFAULT '{}'::JSONB,
    "差異" JSONB NOT NULL DEFAULT '[]'::JSONB,
    "結果" VARCHAR(10) NOT NULL,
    "執行者ID" INTEGER REFERENCES "使用者"("識別碼"),
    "執行時間" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_msa_validation_result CHECK ("結果" IN ('PASS', 'FAIL'))
);

CREATE INDEX idx_msa_validation_case
    ON "MSA軟體確效執行" ("案例代碼", "執行時間");

-- ---------------------------------------------------------------------------
-- 不可變保護
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION msa_block_immutable_change()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'MSA 不可變證據不得修改或刪除';
END;
$$ LANGUAGE plpgsql;

-- 計畫凍結後即為正式設計證據；未凍結的草稿仍可調整。
CREATE OR REPLACE FUNCTION msa_block_frozen_plan_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD."凍結時間" IS NOT NULL THEN
            RAISE EXCEPTION '凍結後的 MSA 計畫版本不可刪除';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD."凍結時間" IS NOT NULL THEN
        RAISE EXCEPTION '凍結後的 MSA 計畫版本不可修改';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 零件與評價人在所屬計畫凍結後一併固定。
CREATE OR REPLACE FUNCTION msa_block_frozen_plan_child_change()
RETURNS TRIGGER AS $$
DECLARE
    frozen TIMESTAMPTZ;
    target_plan INTEGER;
BEGIN
    target_plan := CASE WHEN TG_OP = 'DELETE'
        THEN OLD."計畫版本ID" ELSE NEW."計畫版本ID" END;
    SELECT "凍結時間" INTO frozen
    FROM "MSA計畫版本" WHERE "識別碼" = target_plan;
    IF frozen IS NOT NULL THEN
        RAISE EXCEPTION '凍結後的 MSA 計畫內容不可修改或刪除';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

-- 觀測唯一允許的變更是把有效紀錄作廢，讓後繼紀錄接手。
CREATE OR REPLACE FUNCTION msa_block_observation_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'MSA 觀測不可刪除';
    END IF;
    IF OLD."是否有效" IS TRUE
        AND NEW."是否有效" IS FALSE
        AND NEW."識別碼" IS NOT DISTINCT FROM OLD."識別碼"
        AND NEW."計畫版本ID" IS NOT DISTINCT FROM OLD."計畫版本ID"
        AND NEW."零件ID" IS NOT DISTINCT FROM OLD."零件ID"
        AND NEW."評價人ID" IS NOT DISTINCT FROM OLD."評價人ID"
        AND NEW."試驗次數" IS NOT DISTINCT FROM OLD."試驗次數"
        AND NEW."要求順序" IS NOT DISTINCT FROM OLD."要求順序"
        AND NEW."實際輸入順序" IS NOT DISTINCT FROM OLD."實際輸入順序"
        AND NEW."計量讀值" IS NOT DISTINCT FROM OLD."計量讀值"
        AND NEW."計數分類" IS NOT DISTINCT FROM OLD."計數分類"
        AND NEW."量測時間" IS NOT DISTINCT FROM OLD."量測時間"
        AND NEW."來源" IS NOT DISTINCT FROM OLD."來源"
        AND NEW."輸入者ID" IS NOT DISTINCT FROM OLD."輸入者ID"
        AND NEW."取代來源ID" IS NOT DISTINCT FROM OLD."取代來源ID"
        AND NEW."匯入批次ID" IS NOT DISTINCT FROM OLD."匯入批次ID"
        AND NEW."建立時間" IS NOT DISTINCT FROM OLD."建立時間"
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'MSA 觀測不可直接修改；請建立後繼紀錄';
END;
$$ LANGUAGE plpgsql;

-- 結果版本唯一允許的變更是工作流狀態；統計與快照永遠固定。
CREATE OR REPLACE FUNCTION msa_block_result_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'MSA 結果版本不可刪除';
    END IF;
    IF NEW."識別碼" IS NOT DISTINCT FROM OLD."識別碼"
        AND NEW."研究ID" IS NOT DISTINCT FROM OLD."研究ID"
        AND NEW."計畫版本ID" IS NOT DISTINCT FROM OLD."計畫版本ID"
        AND NEW."結果版本號" IS NOT DISTINCT FROM OLD."結果版本號"
        AND NEW."方法代碼" IS NOT DISTINCT FROM OLD."方法代碼"
        AND NEW."方法版本" IS NOT DISTINCT FROM OLD."方法版本"
        AND NEW."程式版本" IS NOT DISTINCT FROM OLD."程式版本"
        AND NEW."資料雜湊" IS NOT DISTINCT FROM OLD."資料雜湊"
        AND NEW."原始資料摘要" IS NOT DISTINCT FROM OLD."原始資料摘要"
        AND NEW."適用性結果" IS NOT DISTINCT FROM OLD."適用性結果"
        AND NEW."統計結果" IS NOT DISTINCT FROM OLD."統計結果"
        AND NEW."圖表資料" IS NOT DISTINCT FROM OLD."圖表資料"
        AND NEW."準則快照" IS NOT DISTINCT FROM OLD."準則快照"
        AND NEW."結論" IS NOT DISTINCT FROM OLD."結論"
        AND NEW."警告" IS NOT DISTINCT FROM OLD."警告"
        AND NEW."阻擋條件" IS NOT DISTINCT FROM OLD."阻擋條件"
        AND NEW."建立者ID" IS NOT DISTINCT FROM OLD."建立者ID"
        AND NEW."建立時間" IS NOT DISTINCT FROM OLD."建立時間"
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'MSA 結果版本的統計證據不可修改';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_msa_plan_frozen_immutable
    BEFORE UPDATE OR DELETE ON "MSA計畫版本"
    FOR EACH ROW EXECUTE FUNCTION msa_block_frozen_plan_change();

CREATE TRIGGER trg_msa_part_frozen_immutable
    BEFORE UPDATE OR DELETE ON "MSA零件"
    FOR EACH ROW EXECUTE FUNCTION msa_block_frozen_plan_child_change();

CREATE TRIGGER trg_msa_appraiser_frozen_immutable
    BEFORE UPDATE OR DELETE ON "MSA評價人"
    FOR EACH ROW EXECUTE FUNCTION msa_block_frozen_plan_child_change();

CREATE TRIGGER trg_msa_observation_append_only
    BEFORE UPDATE OR DELETE ON "MSA觀測"
    FOR EACH ROW EXECUTE FUNCTION msa_block_observation_change();

CREATE TRIGGER trg_msa_result_immutable
    BEFORE UPDATE OR DELETE ON "MSA結果版本"
    FOR EACH ROW EXECUTE FUNCTION msa_block_result_change();

CREATE TRIGGER trg_msa_decision_immutable
    BEFORE UPDATE OR DELETE ON "MSA工作流決策"
    FOR EACH ROW EXECUTE FUNCTION msa_block_immutable_change();

CREATE TRIGGER trg_msa_validation_immutable
    BEFORE UPDATE OR DELETE ON "MSA軟體確效執行"
    FOR EACH ROW EXECUTE FUNCTION msa_block_immutable_change();

COMMIT;
