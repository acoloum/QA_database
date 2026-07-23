-- 機械性質 Phase 1：補強已套用舊版 migration 40 的資料庫約束。
-- 本 migration 不修剪既有資料；若發現衝突資料，會以明確錯誤中止，
-- 由資料負責人完成追溯與修正後再重跑。
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM "機械性質批次"
        GROUP BY "機械性質檢驗_ID", "序號"
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質批次存在同一檢驗內重複序號，請先人工複核';
    END IF;
    IF EXISTS (SELECT 1 FROM "機械性質批次" WHERE "序號" < 1) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質批次存在小於 1 的序號，請先人工複核';
    END IF;
    IF EXISTS (
        SELECT 1 FROM "機械性質量測明細"
        WHERE "量測項目" NOT IN ('EC值', '硬度', '抗拉強度', '降伏強度', '伸長率')
    ) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質量測明細存在非法量測項目，請先人工複核';
    END IF;
    IF EXISTS (
        SELECT 1 FROM "機械性質量測明細"
        WHERE "測量位置" NOT IN ('爐門', '爐頂')
    ) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質量測明細存在非法測量位置，請先人工複核';
    END IF;
    IF EXISTS (
        SELECT 1 FROM "機械性質量測明細"
        WHERE "取樣序" NOT IN (1, 2)
    ) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質量測明細存在非法取樣序，請先人工複核';
    END IF;
    IF EXISTS (
        SELECT 1 FROM "機械性質檢驗"
        WHERE length("T4溫度時間") > 100 OR length("T6溫度時間") > 100
    ) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質檢驗存在超過 100 字元的溫度時間，請先人工複核';
    END IF;
    IF EXISTS (
        SELECT 1 FROM "機械性質批次"
        WHERE length("擠製編號") > 100 OR length("爐具編號") > 100
    ) THEN
        RAISE EXCEPTION 'migration 41 中止：機械性質批次存在超過 100 字元的編號，請先人工複核';
    END IF;
END $$;

ALTER TABLE "機械性質檢驗"
    ALTER COLUMN "T4溫度時間" TYPE VARCHAR(100),
    ALTER COLUMN "T6溫度時間" TYPE VARCHAR(100);
ALTER TABLE "機械性質批次"
    ALTER COLUMN "擠製編號" TYPE VARCHAR(100),
    ALTER COLUMN "爐具編號" TYPE VARCHAR(100);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_mech_batch_seq'
          AND conrelid = '"機械性質批次"'::regclass
    ) THEN
        ALTER TABLE "機械性質批次"
            ADD CONSTRAINT uq_mech_batch_seq UNIQUE ("機械性質檢驗_ID", "序號");
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_mech_batch_seq_positive'
          AND conrelid = '"機械性質批次"'::regclass
    ) THEN
        ALTER TABLE "機械性質批次"
            ADD CONSTRAINT ck_mech_batch_seq_positive CHECK ("序號" >= 1);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_mech_measurement_item'
          AND conrelid = '"機械性質量測明細"'::regclass
    ) THEN
        ALTER TABLE "機械性質量測明細"
            ADD CONSTRAINT ck_mech_measurement_item
            CHECK ("量測項目" IN ('EC值', '硬度', '抗拉強度', '降伏強度', '伸長率'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_mech_measurement_location'
          AND conrelid = '"機械性質量測明細"'::regclass
    ) THEN
        ALTER TABLE "機械性質量測明細"
            ADD CONSTRAINT ck_mech_measurement_location
            CHECK ("測量位置" IN ('爐門', '爐頂'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_mech_measurement_sample'
          AND conrelid = '"機械性質量測明細"'::regclass
    ) THEN
        ALTER TABLE "機械性質量測明細"
            ADD CONSTRAINT ck_mech_measurement_sample CHECK ("取樣序" IN (1, 2));
    END IF;
END $$;

COMMIT;
