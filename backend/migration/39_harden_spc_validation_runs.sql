-- SPC 2026.2 軟體確效 FAIL 明細、結果約束與不可變證據保護。

BEGIN;

ALTER TABLE "SPC軟體確效執行"
    ADD COLUMN IF NOT EXISTS "差異明細" JSONB NOT NULL DEFAULT '[]'::jsonb;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM "SPC軟體確效執行"
        WHERE "執行結果" NOT IN ('PASS', 'FAIL')
    ) THEN
        RAISE EXCEPTION 'SPC 軟體確效存在 PASS/FAIL 以外結果，請先人工確認後再執行 migration 39';
    END IF;
    IF EXISTS (
        SELECT 1 FROM "SPC軟體確效執行"
        WHERE "差異明細" IS NULL
    ) THEN
        RAISE EXCEPTION 'SPC 軟體確效差異明細存在 NULL，請先人工確認後再執行 migration 39';
    END IF;
END $$;

ALTER TABLE "SPC軟體確效執行"
    ALTER COLUMN "差異明細" SET DEFAULT '[]'::jsonb,
    ALTER COLUMN "差異明細" SET NOT NULL;

ALTER TABLE "SPC軟體確效執行"
    DROP CONSTRAINT IF EXISTS ck_spc_validation_result;
ALTER TABLE "SPC軟體確效執行"
    ADD CONSTRAINT ck_spc_validation_result
    CHECK ("執行結果" IN ('PASS', 'FAIL'));

DROP TRIGGER IF EXISTS trg_spc_validation_run_immutable
    ON "SPC軟體確效執行";
CREATE TRIGGER trg_spc_validation_run_immutable
    BEFORE UPDATE OR DELETE ON "SPC軟體確效執行"
    FOR EACH ROW EXECUTE FUNCTION spc_block_immutable_change();

COMMIT;
