-- Migration 09: Redesign CAPA/8D Ecosystem
-- 涵蓋：擴充 CorrectiveAction、新增 CARARecord、CustomerComplaint、ActionTask、Attachment
-- 執行方式：psql -U postgres -d qa_database -f migration/09_redesign_capa_8d_ecosystem.sql

BEGIN;

-- ============================================================
-- 1. 擴充 NCMR（不合格品單）— 加關聯 CAPA 欄位
-- ============================================================
ALTER TABLE "不合格品單"
    ADD COLUMN IF NOT EXISTS "關聯CAPA_ID"   INTEGER,
    ADD COLUMN IF NOT EXISTS "關聯CAPA來源"  VARCHAR(20);


-- ============================================================
-- 2. 擴充 CorrectiveAction（異常矯正單）— CAPA 重設計
-- ============================================================

-- 2a. 源頭欄位
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "來源類型"  VARCHAR(20),   -- 'ncmr' | 'complaint'
    ADD COLUMN IF NOT EXISTS "來源ID"    INTEGER;

-- 2b. 嚴格度
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "嚴格度"  VARCHAR(20) DEFAULT '完整8D';

-- 2c. D0 立案
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D0_症狀描述"      TEXT,
    ADD COLUMN IF NOT EXISTS "D0_判斷準則"      JSONB,
    ADD COLUMN IF NOT EXISTS "D0_嚴重度"        VARCHAR(20),
    ADD COLUMN IF NOT EXISTS "D0_客戶要求結案日" DATE;

-- 2d. D1 結構化小組
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D1_Champion"  INTEGER REFERENCES "品管人員"("識別碼"),
    ADD COLUMN IF NOT EXISTS "D1_Leader"    INTEGER REFERENCES "品管人員"("識別碼"),
    ADD COLUMN IF NOT EXISTS "D1_成員"      JSONB;

-- 2e. D2 5W2H
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D2_What"    TEXT,
    ADD COLUMN IF NOT EXISTS "D2_Where"   TEXT,
    ADD COLUMN IF NOT EXISTS "D2_When"    TEXT,
    ADD COLUMN IF NOT EXISTS "D2_Who"     TEXT,
    ADD COLUMN IF NOT EXISTS "D2_Why"     TEXT,
    ADD COLUMN IF NOT EXISTS "D2_How"     TEXT,
    ADD COLUMN IF NOT EXISTS "D2_HowMany" TEXT;

-- 2f. D3 暫時對策
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D3_對策內容"   TEXT,
    ADD COLUMN IF NOT EXISTS "D3_生效日"     DATE,
    ADD COLUMN IF NOT EXISTS "D3_有效性驗證" TEXT;

-- 2g. D4 真因分析（結構化）
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D4_工具"      VARCHAR(20),
    ADD COLUMN IF NOT EXISTS "D4_5Why資料"  JSONB,
    ADD COLUMN IF NOT EXISTS "D4_魚骨圖資料" JSONB,
    ADD COLUMN IF NOT EXISTS "D4_根本原因"  TEXT;

-- 2h. D5 永久對策
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D5_對策內容"   TEXT,
    ADD COLUMN IF NOT EXISTS "D5_預計實施日" DATE,
    ADD COLUMN IF NOT EXISTS "D5_驗證計畫"   TEXT;

-- 2i. D6 實施驗證
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D6_實施日"   DATE,
    ADD COLUMN IF NOT EXISTS "D6_驗證結果" TEXT,
    ADD COLUMN IF NOT EXISTS "D6_驗證通過" BOOLEAN DEFAULT FALSE;

-- 2j. D7 橫展
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D7_橫展類型" JSONB;

-- 2k. D8 結案（結構化）
ALTER TABLE "異常矯正單"
    ADD COLUMN IF NOT EXISTS "D8_結案日期" DATE,
    ADD COLUMN IF NOT EXISTS "D8_結案確認" TEXT,
    ADD COLUMN IF NOT EXISTS "D8_團隊表揚" TEXT;

-- 索引
CREATE INDEX IF NOT EXISTS idx_capa_source ON "異常矯正單"("來源類型", "來源ID");
CREATE INDEX IF NOT EXISTS idx_capa_status ON "異常矯正單"("狀態");


-- ============================================================
-- 3. 新增 CARARecord（矯正措施要求）
-- ============================================================
CREATE TABLE IF NOT EXISTS "矯正措施要求" (
    "識別碼"      SERIAL PRIMARY KEY,
    "CARA單號"    VARCHAR(50) UNIQUE,
    "狀態"        VARCHAR(20) DEFAULT '進行中',

    -- 來源
    "NCMR_ID"    INTEGER REFERENCES "不合格品單"("識別碼"),
    "廠商"        VARCHAR(100),

    -- D2
    "D2_What"    TEXT, "D2_Where" TEXT, "D2_When" TEXT,
    "D2_Who"     TEXT, "D2_Why"   TEXT, "D2_How"  TEXT,
    "D2_HowMany" TEXT,
    "D2_問題描述" TEXT,  -- 舊版相容

    -- D3
    "D3_對策內容"   TEXT,
    "D3_生效日"     DATE,
    "D3_有效性驗證" TEXT,
    "D3_暫時對策"   TEXT,  -- 舊版相容

    -- D4
    "D4_工具"       VARCHAR(20),
    "D4_5Why資料"   JSONB,
    "D4_魚骨圖資料"  JSONB,
    "D4_根本原因"   TEXT,
    "D4_真因分析"   TEXT,  -- 舊版相容

    -- D6
    "D6_實施日"    DATE,
    "D6_驗證結果"  TEXT,
    "D6_驗證通過"  BOOLEAN DEFAULT FALSE,
    "D6_成效驗證"  TEXT,  -- 舊版相容

    -- D8
    "D8_結案日期"  DATE,
    "D8_結案確認"  TEXT,
    "D8_結案確認_舊" TEXT,  -- 舊版相容

    -- 負責人（舊版相容）
    "負責人員"    INTEGER REFERENCES "品管人員"("識別碼"),
    "D1_Leader"  INTEGER REFERENCES "品管人員"("識別碼"),

    -- 時間戳
    "建立時間"  TIMESTAMP DEFAULT NOW(),
    "結案時間"  TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cara_status ON "矯正措施要求"("狀態");
CREATE INDEX IF NOT EXISTS idx_cara_ncmr   ON "矯正措施要求"("NCMR_ID");


-- ============================================================
-- 4. 新增 CustomerComplaint（客訴紀錄）
-- ============================================================
CREATE TABLE IF NOT EXISTS "客訴紀錄" (
    "識別碼"      SERIAL PRIMARY KEY,
    "客訴單號"    VARCHAR(50) UNIQUE,
    "客戶"        VARCHAR(100) NOT NULL,
    "客訴日期"    DATE NOT NULL,
    "料號"        VARCHAR(100) NOT NULL,
    "不良描述"    TEXT NOT NULL,
    "客戶聯絡人"  VARCHAR(100),
    "嚴重度"      VARCHAR(20),
    "不良類別"    VARCHAR(100),

    -- 類型：'quality' | 'warranty' | 'field_failure'
    "客訴類型"    VARCHAR(30) NOT NULL DEFAULT 'quality',

    -- Warranty / Field Failure
    "失效裝置序號" VARCHAR(100),
    "使用環境"    TEXT,
    "失效時數"    FLOAT,

    -- 應答時效
    "初步回覆期限" DATE,
    "最終回覆期限" DATE,

    -- 回覆內容
    "初步回覆內容" TEXT,
    "初步回覆日期" TIMESTAMP,
    "最終回覆內容" TEXT,
    "最終回覆日期" TIMESTAMP,

    -- 滿意度
    "客戶滿意度"  INTEGER CHECK ("客戶滿意度" BETWEEN 1 AND 5),
    "滿意度備註"  TEXT,

    -- 重複警示
    "是否重複客訴"   BOOLEAN DEFAULT FALSE,
    "重複客訴參考單號" JSONB,

    -- 關聯 CAPA
    "關聯CAPA_ID"  INTEGER,

    -- 狀態：'待處理' | '處理中' | '已結案'
    "狀態"        VARCHAR(20) DEFAULT '待處理',

    -- 時間戳
    "建立人員"  INTEGER REFERENCES "品管人員"("識別碼"),
    "建立時間"  TIMESTAMP DEFAULT NOW(),
    "更新時間"  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_complaint_customer ON "客訴紀錄"("客戶");
CREATE INDEX IF NOT EXISTS idx_complaint_date     ON "客訴紀錄"("客訴日期");
CREATE INDEX IF NOT EXISTS idx_complaint_status   ON "客訴紀錄"("狀態");
CREATE INDEX IF NOT EXISTS idx_complaint_product  ON "客訴紀錄"("料號");


-- ============================================================
-- 5. 新增 ActionTask（橫展任務）
-- ============================================================
CREATE TABLE IF NOT EXISTS "橫展任務" (
    "識別碼"    SERIAL PRIMARY KEY,
    "任務單號"  VARCHAR(50) UNIQUE,

    -- 多型來源
    "來源類型"  VARCHAR(30) NOT NULL,   -- 'capa' | 'audit'
    "來源ID"   INTEGER NOT NULL,

    -- 任務內容
    "類別"   VARCHAR(50) NOT NULL,
    -- 'pfmea'|'control_plan'|'sop'|'training'|'cross_part'|'customer_notify'|'other'
    "標題"   VARCHAR(200) NOT NULL,
    "描述"   TEXT,
    "相關料號" JSONB,

    -- 指派
    "負責人"  INTEGER REFERENCES "品管人員"("識別碼"),

    -- 期限與狀態
    "應完成日" DATE,
    "狀態"    VARCHAR(20) DEFAULT 'pending',
    -- 'pending'|'in_progress'|'completed'|'waived'

    -- 完成資訊
    "完成證明" TEXT,
    "豁免理由" TEXT,
    "完成時間" TIMESTAMP,

    -- 時間戳
    "建立時間" TIMESTAMP DEFAULT NOW(),
    "更新時間" TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_source   ON "橫展任務"("來源類型", "來源ID");
CREATE INDEX IF NOT EXISTS idx_task_assignee ON "橫展任務"("負責人");
CREATE INDEX IF NOT EXISTS idx_task_status   ON "橫展任務"("狀態");


-- ============================================================
-- 6. 新增 Attachment（附件）
-- ============================================================
CREATE TABLE IF NOT EXISTS "附件" (
    "識別碼"   SERIAL PRIMARY KEY,

    -- 多型（entity_type + entity_id）
    "實體類型"  VARCHAR(30) NOT NULL,   -- 'capa'|'cara'|'task'|'complaint'
    "實體ID"   INTEGER NOT NULL,
    "D步驟"    INTEGER,                -- 0-8 for CAPA/CARA; NULL for task/complaint

    -- 檔案資訊
    "檔案名稱"  VARCHAR(255) NOT NULL,
    "檔案路徑"  VARCHAR(500) NOT NULL,
    "MIME類型"  VARCHAR(100),
    "檔案大小"  INTEGER,               -- bytes

    -- 上傳
    "上傳人員"  INTEGER REFERENCES "品管人員"("識別碼"),
    "上傳時間"  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attachment_entity ON "附件"("實體類型", "實體ID");
CREATE INDEX IF NOT EXISTS idx_attachment_step   ON "附件"("實體類型", "實體ID", "D步驟");


-- ============================================================
-- 7. 資料回填（既有 CAPA 資料）
-- ============================================================

-- 7a. 既有 CAPA：source_type/id 從 ncmr_id 帶入
UPDATE "異常矯正單"
SET "來源類型" = 'ncmr',
    "來源ID"   = "NCMR_ID"
WHERE "NCMR_ID" IS NOT NULL
  AND "來源類型" IS NULL;

-- 7b. 既有 CAPA：負責人 → D1_Leader
UPDATE "異常矯正單"
SET "D1_Leader" = "負責人員"
WHERE "負責人員" IS NOT NULL
  AND "D1_Leader" IS NULL;

-- 7c. 既有 CAPA：嚴格度預設完整8D
UPDATE "異常矯正單"
SET "嚴格度" = '完整8D'
WHERE "嚴格度" IS NULL;

-- 7d. 既有 CARA（若有舊資料在異常矯正單，需手動移至矯正措施要求）
--     此腳本不自動遷移，因 CARA 另有獨立舊表，請依實際情況操作

COMMIT;

-- ============================================================
-- 回滾腳本（如需回滾請手動執行）
-- ============================================================
-- BEGIN;
-- DROP TABLE IF EXISTS "附件";
-- DROP TABLE IF EXISTS "橫展任務";
-- DROP TABLE IF EXISTS "客訴紀錄";
-- DROP TABLE IF EXISTS "矯正措施要求";
-- ALTER TABLE "異常矯正單" DROP COLUMN IF EXISTS "來源類型", ... (略);
-- ALTER TABLE "不合格品單" DROP COLUMN IF EXISTS "關聯CAPA_ID", ...;
-- COMMIT;
