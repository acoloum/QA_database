-- 使用者 token 即時撤銷版本；可安全重複執行。
BEGIN;

ALTER TABLE "使用者"
    ADD COLUMN IF NOT EXISTS "憑證版本" INTEGER;

UPDATE "使用者"
SET "憑證版本" = 0
WHERE "憑證版本" IS NULL;

ALTER TABLE "使用者"
    ALTER COLUMN "憑證版本" SET DEFAULT 0;

ALTER TABLE "使用者"
    ALTER COLUMN "憑證版本" SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_user_token_version_nonnegative'
          AND conrelid = '"使用者"'::regclass
    ) THEN
        ALTER TABLE "使用者"
            ADD CONSTRAINT ck_user_token_version_nonnegative
            CHECK ("憑證版本" >= 0);
    END IF;
END
$$;

COMMIT;

-- Rollback（需由維運人員在核准的回復窗口執行，順序不可顛倒）：
-- BEGIN;
-- ALTER TABLE "使用者"
--     DROP CONSTRAINT IF EXISTS ck_user_token_version_nonnegative;
-- ALTER TABLE "使用者"
--     DROP COLUMN IF EXISTS "憑證版本";
-- COMMIT;
