BEGIN;

DO $migration$
DECLARE
    old_exists BOOLEAN := to_regclass('"機械性質批次"') IS NOT NULL;
    new_exists BOOLEAN := to_regclass('"機械性質追溯編號"') IS NOT NULL;
    mismatch_count BIGINT;
    distinct_count BIGINT;
    migrated_count BIGINT;
    trace_index INTEGER;
BEGIN
    IF new_exists AND NOT old_exists THEN
        RAISE NOTICE '新表已存在且舊表已移除，Migration 42 已完成';
        RETURN;
    END IF;

    IF new_exists AND old_exists THEN
        RAISE EXCEPTION '新舊追溯編號資料表同時存在，請人工確認後再執行';
    END IF;

    IF NOT old_exists THEN
        RAISE EXCEPTION '找不到舊機械性質批次資料表，無法安全搬移';
    END IF;

    EXECUTE $sql$
        CREATE TABLE "機械性質追溯編號" (
            "識別碼" SERIAL PRIMARY KEY,
            "機械性質檢驗_ID" INTEGER NOT NULL
                REFERENCES "機械性質檢驗" ("識別碼") ON DELETE CASCADE,
            "類型" VARCHAR(20) NOT NULL,
            "序號" INTEGER NOT NULL,
            "編號" VARCHAR(100) NOT NULL,
            CONSTRAINT uq_mech_trace_seq
                UNIQUE ("機械性質檢驗_ID", "類型", "序號"),
            CONSTRAINT uq_mech_trace_value
                UNIQUE ("機械性質檢驗_ID", "類型", "編號"),
            CONSTRAINT ck_mech_trace_type
                CHECK ("類型" IN ('擠製編號', 'T4爐號')),
            CONSTRAINT ck_mech_trace_seq_positive CHECK ("序號" >= 1),
            CONSTRAINT ck_mech_trace_number
                CHECK (length(btrim("編號")) BETWEEN 1 AND 100)
        )
    $sql$;
    EXECUTE $sql$
        CREATE INDEX ix_mech_trace_test_id
        ON "機械性質追溯編號" ("機械性質檢驗_ID")
    $sql$;

    EXECUTE $sql$
        WITH first_values AS (
            SELECT DISTINCT ON ("機械性質檢驗_ID", btrim("擠製編號"))
                "機械性質檢驗_ID" AS test_id,
                btrim("擠製編號") AS number,
                "序號" AS old_seq,
                "識別碼" AS old_id
            FROM "機械性質批次"
            WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
            ORDER BY
                "機械性質檢驗_ID",
                btrim("擠製編號"),
                "序號",
                "識別碼"
        ),
        resequenced AS (
            SELECT
                test_id,
                number,
                CAST(
                    ROW_NUMBER() OVER (
                        PARTITION BY test_id ORDER BY old_seq, old_id
                    )
                    AS INTEGER
                ) AS new_seq
            FROM first_values
        )
        INSERT INTO "機械性質追溯編號"
            ("機械性質檢驗_ID", "類型", "序號", "編號")
        SELECT test_id, '擠製編號', new_seq, number
        FROM resequenced
    $sql$;

    EXECUTE $sql$
        WITH first_values AS (
            SELECT DISTINCT ON ("機械性質檢驗_ID", btrim("爐具編號"))
                "機械性質檢驗_ID" AS test_id,
                btrim("爐具編號") AS number,
                "序號" AS old_seq,
                "識別碼" AS old_id
            FROM "機械性質批次"
            WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
            ORDER BY
                "機械性質檢驗_ID",
                btrim("爐具編號"),
                "序號",
                "識別碼"
        ),
        resequenced AS (
            SELECT
                test_id,
                number,
                CAST(
                    ROW_NUMBER() OVER (
                        PARTITION BY test_id ORDER BY old_seq, old_id
                    )
                    AS INTEGER
                ) AS new_seq
            FROM first_values
        )
        INSERT INTO "機械性質追溯編號"
            ("機械性質檢驗_ID", "類型", "序號", "編號")
        SELECT test_id, 'T4爐號', new_seq, number
        FROM resequenced
    $sql$;

    EXECUTE $sql$
        SELECT COUNT(*) FROM (
            (
                SELECT
                    "機械性質檢驗_ID",
                    btrim("擠製編號") AS number
                FROM "機械性質批次"
                WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("擠製編號")
                EXCEPT
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號"
                WHERE "類型" = '擠製編號'
            )
            UNION ALL
            (
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號"
                WHERE "類型" = '擠製編號'
                EXCEPT
                SELECT
                    "機械性質檢驗_ID",
                    btrim("擠製編號")
                FROM "機械性質批次"
                WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("擠製編號")
            )
        ) AS differences
    $sql$ INTO mismatch_count;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION '擠製編號搬移集合不一致';
    END IF;

    EXECUTE $sql$
        SELECT COUNT(*) FROM (
            (
                SELECT
                    "機械性質檢驗_ID",
                    btrim("爐具編號") AS number
                FROM "機械性質批次"
                WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("爐具編號")
                EXCEPT
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號"
                WHERE "類型" = 'T4爐號'
            )
            UNION ALL
            (
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號"
                WHERE "類型" = 'T4爐號'
                EXCEPT
                SELECT
                    "機械性質檢驗_ID",
                    btrim("爐具編號")
                FROM "機械性質批次"
                WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("爐具編號")
            )
        ) AS differences
    $sql$ INTO mismatch_count;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION 'T4爐號搬移集合不一致';
    END IF;

    FOREACH trace_index IN ARRAY ARRAY[0, 1] LOOP
        IF trace_index = 0 THEN
            EXECUTE $sql$
                SELECT COUNT(*) FROM (
                    SELECT
                        "機械性質檢驗_ID",
                        btrim("擠製編號")
                    FROM "機械性質批次"
                    WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
                    GROUP BY "機械性質檢驗_ID", btrim("擠製編號")
                ) AS values
            $sql$ INTO distinct_count;
            EXECUTE $sql$
                SELECT COUNT(*) FROM "機械性質追溯編號"
                WHERE "類型" = '擠製編號'
            $sql$ INTO migrated_count;
        ELSE
            EXECUTE $sql$
                SELECT COUNT(*) FROM (
                    SELECT
                        "機械性質檢驗_ID",
                        btrim("爐具編號")
                    FROM "機械性質批次"
                    WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
                    GROUP BY "機械性質檢驗_ID", btrim("爐具編號")
                ) AS values
            $sql$ INTO distinct_count;
            EXECUTE $sql$
                SELECT COUNT(*) FROM "機械性質追溯編號"
                WHERE "類型" = 'T4爐號'
            $sql$ INTO migrated_count;
        END IF;
        IF distinct_count <> migrated_count THEN
            RAISE EXCEPTION
                '追溯編號筆數不一致：舊表 %，新表 %',
                distinct_count,
                migrated_count;
        END IF;
    END LOOP;

    EXECUTE 'DROP TABLE "機械性質批次"';
END
$migration$;

COMMIT;
