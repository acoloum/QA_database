-- 修正機械性質追溯編號誤植：把被填進「T4爐號」的擠製編號搬回「擠製編號」。
--
-- 成因：Excel 匯入時，mechanical_import._t4_furnace_rows() 把「擠製日期/批號」列到
-- 「T4溫度/時間」列之間的所有列都當成 T4 爐號候選列，因此擠製標籤下方那一列未標籤的
-- 第二個擠製編號（如 052571 D50）被寫成 T4爐號。已於同一次變更改為以「T4爐具編號」
-- 標籤切分兩段區間，本腳本負責回頭修既有資料（受影響檢驗 ID 皆 <= 3318）。
--
-- 判定規則（三者同時成立才視為誤植）：
--   1. 不含 T4 爐別字樣（T40/T41/T42/T43…）— 真爐號一律帶此字樣
--   2. 不是「N號」— 早期資料的 T4 爐具編號就是「1號」「2號」
--   3. 具備擠製編號特徵：日期批號後接模具碼（D12、M5、C23…），或日期批號＋空白＋裸模號
-- 不符規則的殘留雜訊（如「80*70改」「0」「11090542」）一律不動，交由人工判讀。
--
-- 原始資料另存於「機械性質追溯編號_誤植修正備份」，可據以回復。

BEGIN;

DO $migration$
DECLARE
    misfiled_count BIGINT;
    duplicate_count BIGINT;
    moved_count BIGINT;
    leftover_count BIGINT;
BEGIN
    IF to_regclass('"機械性質追溯編號"') IS NULL THEN
        RAISE EXCEPTION '找不到「機械性質追溯編號」資料表，請先執行 migration 42';
    END IF;

    LOCK TABLE "機械性質追溯編號" IN ACCESS EXCLUSIVE MODE;

    -- 誤植列：符合上述三項判定規則的 T4爐號列
    CREATE TEMP TABLE _misfiled ON COMMIT DROP AS
    SELECT
        t."識別碼"           AS trace_id,
        t."機械性質檢驗_ID"  AS test_id,
        t."序號"             AS old_seq,
        t."編號"             AS number
    FROM "機械性質追溯編號" t
    WHERE t."類型" = 'T4爐號'
      AND t."編號" !~* 'T4[0-9]'
      AND t."編號" !~ '^[0-9]+號$'
      AND (
            t."編號" ~ '[A-Za-z]\s*[0-9]'
         OR t."編號" ~ '^[0-9]{4,}(/[0-9]+)*\s+[0-9]+$'
      );

    SELECT COUNT(*) INTO misfiled_count FROM _misfiled;
    IF misfiled_count = 0 THEN
        RAISE NOTICE 'Migration 57：查無誤植列，已完成或無須修正';
        RETURN;
    END IF;

    -- 備份原始 (類型, 序號)，供回復與稽核
    CREATE TABLE IF NOT EXISTS "機械性質追溯編號_誤植修正備份" (
        "識別碼"            INTEGER NOT NULL,
        "機械性質檢驗_ID"   INTEGER NOT NULL,
        "原類型"            VARCHAR(20) NOT NULL,
        "原序號"            INTEGER NOT NULL,
        "編號"              VARCHAR(100) NOT NULL,
        "處置"              VARCHAR(20) NOT NULL,
        "修正時間"          TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    INSERT INTO "機械性質追溯編號_誤植修正備份"
        ("識別碼", "機械性質檢驗_ID", "原類型", "原序號", "編號", "處置")
    SELECT
        m.trace_id, m.test_id, 'T4爐號', m.old_seq, m.number,
        CASE WHEN EXISTS (
            SELECT 1 FROM "機械性質追溯編號" e
            WHERE e."機械性質檢驗_ID" = m.test_id
              AND e."類型" = '擠製編號'
              AND e."編號" = m.number
        ) THEN '刪除重複' ELSE '改為擠製編號' END
    FROM _misfiled m;

    -- 同一檢驗的擠製編號已有相同值時，只能刪除（uq_mech_trace_value 不允許重複）
    DELETE FROM "機械性質追溯編號" t
    USING _misfiled m
    WHERE t."識別碼" = m.trace_id
      AND EXISTS (
          SELECT 1 FROM "機械性質追溯編號" e
          WHERE e."機械性質檢驗_ID" = m.test_id
            AND e."類型" = '擠製編號'
            AND e."編號" = m.number
      );
    duplicate_count := misfiled_count - (SELECT COUNT(*) FROM "機械性質追溯編號" t
                                         JOIN _misfiled m ON m.trace_id = t."識別碼");

    -- 改類型；序號先接在既有擠製編號之後，稍後統一重編
    UPDATE "機械性質追溯編號" t
    SET "類型" = '擠製編號',
        "序號" = tail.base_seq + tail.offset_seq
    FROM (
        SELECT
            m.trace_id,
            COALESCE((
                SELECT MAX(e."序號") FROM "機械性質追溯編號" e
                WHERE e."機械性質檢驗_ID" = m.test_id AND e."類型" = '擠製編號'
            ), 0) AS base_seq,
            CAST(ROW_NUMBER() OVER (
                PARTITION BY m.test_id ORDER BY m.old_seq, m.trace_id
            ) AS INTEGER) AS offset_seq
        FROM _misfiled m
        WHERE EXISTS (SELECT 1 FROM "機械性質追溯編號" x WHERE x."識別碼" = m.trace_id)
    ) AS tail
    WHERE t."識別碼" = tail.trace_id;
    GET DIAGNOSTICS moved_count = ROW_COUNT;

    -- 受影響檢驗的兩種類型都重編序號為 1..n（uq_mech_trace_seq 逐列檢查，故先搬到
    -- 不可能碰撞的高位區間，再落回目標值）
    CREATE TEMP TABLE _touched ON COMMIT DROP AS
    SELECT DISTINCT test_id FROM _misfiled;

    UPDATE "機械性質追溯編號" t
    SET "序號" = t."序號" + 1000000
    FROM _touched u
    WHERE t."機械性質檢驗_ID" = u.test_id;

    UPDATE "機械性質追溯編號" t
    SET "序號" = renumbered.new_seq
    FROM (
        SELECT
            t2."識別碼" AS trace_id,
            CAST(ROW_NUMBER() OVER (
                PARTITION BY t2."機械性質檢驗_ID", t2."類型"
                ORDER BY t2."序號", t2."識別碼"
            ) AS INTEGER) AS new_seq
        FROM "機械性質追溯編號" t2
        JOIN _touched u ON u.test_id = t2."機械性質檢驗_ID"
    ) AS renumbered
    WHERE t."識別碼" = renumbered.trace_id;

    -- 驗證：不得再有符合判定規則的 T4爐號列
    SELECT COUNT(*) INTO leftover_count
    FROM "機械性質追溯編號" t
    WHERE t."類型" = 'T4爐號'
      AND t."編號" !~* 'T4[0-9]'
      AND t."編號" !~ '^[0-9]+號$'
      AND (
            t."編號" ~ '[A-Za-z]\s*[0-9]'
         OR t."編號" ~ '^[0-9]{4,}(/[0-9]+)*\s+[0-9]+$'
      );
    IF leftover_count <> 0 THEN
        RAISE EXCEPTION '仍有 % 筆誤植的 T4爐號未修正', leftover_count;
    END IF;

    -- 驗證：受影響檢驗的序號皆為 1..n 連續（API 更新時要求連續）
    IF EXISTS (
        SELECT 1
        FROM "機械性質追溯編號" t
        JOIN _touched u ON u.test_id = t."機械性質檢驗_ID"
        GROUP BY t."機械性質檢驗_ID", t."類型"
        HAVING MIN(t."序號") <> 1 OR MAX(t."序號") <> COUNT(*)
    ) THEN
        RAISE EXCEPTION '重編序號後仍有不連續的追溯編號';
    END IF;

    RAISE NOTICE
        'Migration 57：誤植 % 筆，改為擠製編號 % 筆，刪除重複 % 筆，影響檢驗 % 筆',
        misfiled_count, moved_count, duplicate_count,
        (SELECT COUNT(*) FROM _touched);
END
$migration$;

COMMIT;
