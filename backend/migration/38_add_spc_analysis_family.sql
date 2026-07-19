-- SPC 2026.2 分析族別、選項快照與族別化唯一鍵。
-- 初次安裝以 NOT NULL DEFAULT 建欄，避免更新不可變稽核證據。

BEGIN;

ALTER TABLE "SPC研究"
    ADD COLUMN IF NOT EXISTS "分析族別" VARCHAR(20) NOT NULL DEFAULT 'variable';
ALTER TABLE "SPC研究版本"
    ADD COLUMN IF NOT EXISTS "分析選項快照" JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE "SPC界限版本"
    ADD COLUMN IF NOT EXISTS "分析族別" VARCHAR(20) NOT NULL DEFAULT 'variable';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM "SPC研究"
        WHERE "分析族別" IS NOT NULL
          AND "分析族別" NOT IN ('variable', 'attribute', 'machine')
    ) OR EXISTS (
        SELECT 1 FROM "SPC界限版本"
        WHERE "分析族別" IS NOT NULL
          AND "分析族別" NOT IN ('variable', 'attribute', 'machine')
    ) THEN
        RAISE EXCEPTION 'SPC 分析族別存在不支援值，請先人工確認後再執行 migration 38';
    END IF;
END $$;

-- 只有曾由中斷或人工變更留下 nullable 欄位時才受控回填。
-- 兩個 immutable trigger 的原始啟用狀態會在成功與例外路徑完整還原。
DO $$
DECLARE
    limit_trigger_state "char";
    version_trigger_state "char";
BEGIN
    SELECT tgenabled INTO limit_trigger_state
    FROM pg_trigger
    WHERE tgrelid = '"SPC界限版本"'::regclass
      AND tgname = 'trg_spc_limit_version_immutable';
    SELECT tgenabled INTO version_trigger_state
    FROM pg_trigger
    WHERE tgrelid = '"SPC研究版本"'::regclass
      AND tgname = 'trg_spc_study_version_immutable';

    IF EXISTS (SELECT 1 FROM "SPC研究" WHERE "分析族別" IS NULL) THEN
        UPDATE "SPC研究"
        SET "分析族別" = 'variable'
        WHERE "分析族別" IS NULL;
    END IF;

    IF EXISTS (SELECT 1 FROM "SPC界限版本" WHERE "分析族別" IS NULL) THEN
        IF limit_trigger_state IS NOT NULL AND limit_trigger_state <> 'D' THEN
            ALTER TABLE "SPC界限版本"
                DISABLE TRIGGER trg_spc_limit_version_immutable;
        END IF;
        UPDATE "SPC界限版本"
        SET "分析族別" = 'variable'
        WHERE "分析族別" IS NULL;
        IF limit_trigger_state = 'O' THEN
            ALTER TABLE "SPC界限版本"
                ENABLE TRIGGER trg_spc_limit_version_immutable;
        ELSIF limit_trigger_state = 'A' THEN
            ALTER TABLE "SPC界限版本"
                ENABLE ALWAYS TRIGGER trg_spc_limit_version_immutable;
        ELSIF limit_trigger_state = 'R' THEN
            ALTER TABLE "SPC界限版本"
                ENABLE REPLICA TRIGGER trg_spc_limit_version_immutable;
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM "SPC研究版本" WHERE "分析選項快照" IS NULL) THEN
        IF version_trigger_state IS NOT NULL AND version_trigger_state <> 'D' THEN
            ALTER TABLE "SPC研究版本"
                DISABLE TRIGGER trg_spc_study_version_immutable;
        END IF;
        UPDATE "SPC研究版本"
        SET "分析選項快照" = '{}'::jsonb
        WHERE "分析選項快照" IS NULL;
        IF version_trigger_state = 'O' THEN
            ALTER TABLE "SPC研究版本"
                ENABLE TRIGGER trg_spc_study_version_immutable;
        ELSIF version_trigger_state = 'A' THEN
            ALTER TABLE "SPC研究版本"
                ENABLE ALWAYS TRIGGER trg_spc_study_version_immutable;
        ELSIF version_trigger_state = 'R' THEN
            ALTER TABLE "SPC研究版本"
                ENABLE REPLICA TRIGGER trg_spc_study_version_immutable;
        END IF;
    END IF;
EXCEPTION WHEN OTHERS THEN
    IF limit_trigger_state = 'O' THEN
        ALTER TABLE "SPC界限版本"
            ENABLE TRIGGER trg_spc_limit_version_immutable;
    ELSIF limit_trigger_state = 'A' THEN
        ALTER TABLE "SPC界限版本"
            ENABLE ALWAYS TRIGGER trg_spc_limit_version_immutable;
    ELSIF limit_trigger_state = 'R' THEN
        ALTER TABLE "SPC界限版本"
            ENABLE REPLICA TRIGGER trg_spc_limit_version_immutable;
    END IF;
    IF version_trigger_state = 'O' THEN
        ALTER TABLE "SPC研究版本"
            ENABLE TRIGGER trg_spc_study_version_immutable;
    ELSIF version_trigger_state = 'A' THEN
        ALTER TABLE "SPC研究版本"
            ENABLE ALWAYS TRIGGER trg_spc_study_version_immutable;
    ELSIF version_trigger_state = 'R' THEN
        ALTER TABLE "SPC研究版本"
            ENABLE REPLICA TRIGGER trg_spc_study_version_immutable;
    END IF;
    RAISE;
END $$;

ALTER TABLE "SPC研究"
    ALTER COLUMN "分析族別" SET DEFAULT 'variable',
    ALTER COLUMN "分析族別" SET NOT NULL;
ALTER TABLE "SPC研究版本"
    ALTER COLUMN "分析選項快照" SET DEFAULT '{}'::jsonb,
    ALTER COLUMN "分析選項快照" SET NOT NULL;
ALTER TABLE "SPC界限版本"
    ALTER COLUMN "分析族別" SET DEFAULT 'variable',
    ALTER COLUMN "分析族別" SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM "SPC研究"
        GROUP BY "資料來源", "研究類型", "分析族別", "製程流識別鍵", "品質特性"
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'SPC研究回填分析族別後存在重複自然鍵，請先人工確認歷程後再執行 migration 38';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM "SPC界限版本"
        WHERE "狀態" = 'active'
        GROUP BY "分析族別", "製程流識別鍵", "品質特性"
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'SPC界限版本回填分析族別後存在重複啟用識別鍵，請先人工確認歷程後再執行 migration 38';
    END IF;
END $$;

ALTER TABLE "SPC研究" DROP CONSTRAINT IF EXISTS uq_spc_study_identity;
ALTER TABLE "SPC研究" ADD CONSTRAINT uq_spc_study_identity
    UNIQUE ("資料來源", "研究類型", "分析族別", "製程流識別鍵", "品質特性");

DROP INDEX IF EXISTS idx_spc_study_stream_characteristic;
CREATE INDEX idx_spc_study_stream_characteristic
    ON "SPC研究" ("分析族別", "製程流識別鍵", "品質特性");

DROP INDEX IF EXISTS uq_spc_one_active_limit;
CREATE UNIQUE INDEX uq_spc_one_active_limit
    ON "SPC界限版本" ("分析族別", "製程流識別鍵", "品質特性")
    WHERE "狀態" = 'active';

COMMIT;
