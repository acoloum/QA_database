-- SPC 研究、事件與 OCAP 併發及狀態防護。
-- 執行前只做重複／非法資料檢查，不自動合併或刪除任何稽核證據。

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM "SPC研究"
        GROUP BY "資料來源", "研究類型", "製程流識別鍵", "品質特性"
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'SPC研究存在重複自然鍵，請先人工確認歷程後再執行 migration 37';
    END IF;

    IF EXISTS (
        SELECT 1 FROM "SPC事件"
        WHERE "狀態" NOT IN ('open', 'investigating', 'closed')
    ) THEN
        RAISE EXCEPTION 'SPC事件存在不支援狀態，請先人工確認後再執行 migration 37';
    END IF;

    IF EXISTS (
        SELECT 1 FROM "SPC異常處置"
        WHERE "狀態" NOT IN ('open', 'closed')
    ) THEN
        RAISE EXCEPTION 'SPC異常處置存在不支援狀態，請先人工確認後再執行 migration 37';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_spc_study_identity'
          AND conrelid = '"SPC研究"'::regclass
    ) THEN
        ALTER TABLE "SPC研究"
            ADD CONSTRAINT uq_spc_study_identity
            UNIQUE ("資料來源", "研究類型", "製程流識別鍵", "品質特性");
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_spc_event_status'
          AND conrelid = '"SPC事件"'::regclass
    ) THEN
        ALTER TABLE "SPC事件"
            ADD CONSTRAINT ck_spc_event_status
            CHECK ("狀態" IN ('open', 'investigating', 'closed'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_spc_ocap_status'
          AND conrelid = '"SPC異常處置"'::regclass
    ) THEN
        ALTER TABLE "SPC異常處置"
            ADD CONSTRAINT ck_spc_ocap_status
            CHECK ("狀態" IN ('open', 'closed'));
    END IF;
END $$;
