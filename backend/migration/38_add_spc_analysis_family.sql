-- SPC 2026.2 分析族別與族別化唯一鍵。
-- 執行前僅檢查資料，不自動合併、刪除或改寫既有研究與界限歷程。

BEGIN;

ALTER TABLE "SPC研究" ADD COLUMN IF NOT EXISTS "分析族別" VARCHAR(20);
ALTER TABLE "SPC界限版本" ADD COLUMN IF NOT EXISTS "分析族別" VARCHAR(20);

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

UPDATE "SPC研究" SET "分析族別" = 'variable' WHERE "分析族別" IS NULL;
UPDATE "SPC界限版本" SET "分析族別" = 'variable' WHERE "分析族別" IS NULL;

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

ALTER TABLE "SPC研究" ALTER COLUMN "分析族別" SET NOT NULL;
ALTER TABLE "SPC界限版本" ALTER COLUMN "分析族別" SET NOT NULL;

ALTER TABLE "SPC研究" DROP CONSTRAINT IF EXISTS uq_spc_study_identity;
ALTER TABLE "SPC研究" ADD CONSTRAINT uq_spc_study_identity
    UNIQUE ("資料來源", "研究類型", "分析族別", "製程流識別鍵", "品質特性");

DROP INDEX IF EXISTS uq_spc_one_active_limit;
CREATE UNIQUE INDEX uq_spc_one_active_limit
    ON "SPC界限版本" ("分析族別", "製程流識別鍵", "品質特性")
    WHERE "狀態" = 'active';

COMMIT;
