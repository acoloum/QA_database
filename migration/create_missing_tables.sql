-- 建立客訴紀錄資料表
CREATE TABLE IF NOT EXISTS "客訴紀錄" (
    "識別碼"          SERIAL        PRIMARY KEY,
    "客訴單號"        VARCHAR(50)   UNIQUE,
    "客戶"            VARCHAR(100)  NOT NULL,
    "客訴日期"        DATE          NOT NULL,
    "料號"            VARCHAR(100)  NOT NULL,
    "不良描述"        TEXT          NOT NULL,
    "客戶聯絡人"      VARCHAR(100),
    "嚴重度"          VARCHAR(20),
    "不良類別"        VARCHAR(100),
    "客訴類型"        VARCHAR(30)   NOT NULL DEFAULT 'quality',
    "失效裝置序號"    VARCHAR(100),
    "使用環境"        TEXT,
    "失效時數"        FLOAT,
    "初步回覆期限"    DATE,
    "最終回覆期限"    DATE,
    "初步回覆內容"    TEXT,
    "初步回覆日期"    TIMESTAMP,
    "最終回覆內容"    TEXT,
    "最終回覆日期"    TIMESTAMP,
    "客戶滿意度"      INTEGER,
    "滿意度備註"      TEXT,
    "是否重複客訴"    BOOLEAN       DEFAULT FALSE,
    "重複客訴參考單號" JSONB,
    "關聯CAPA_ID"     INTEGER,
    "狀態"            VARCHAR(20)   DEFAULT '待處理',
    "建立人員"        INTEGER       REFERENCES "品管人員"("識別碼"),
    "建立時間"        TIMESTAMP     DEFAULT NOW(),
    "更新時間"        TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_客訴紀錄_日期   ON "客訴紀錄" ("客訴日期");
CREATE INDEX IF NOT EXISTS idx_客訴紀錄_狀態   ON "客訴紀錄" ("狀態");

-- 建立附件資料表
CREATE TABLE IF NOT EXISTS "附件" (
    "識別碼"   SERIAL        PRIMARY KEY,
    "實體類型" VARCHAR(30)   NOT NULL,
    "實體ID"   INTEGER       NOT NULL,
    "D步驟"    INTEGER,
    "檔案名稱" VARCHAR(255)  NOT NULL,
    "檔案路徑" VARCHAR(500)  NOT NULL,
    "MIME類型" VARCHAR(100),
    "檔案大小" INTEGER,
    "上傳人員" INTEGER       REFERENCES "品管人員"("識別碼"),
    "上傳時間" TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_附件_實體 ON "附件" ("實體類型", "實體ID");

-- 建立矯正措施要求資料表（CARA，對供應商）
CREATE TABLE IF NOT EXISTS "矯正措施要求" (
    "識別碼"        SERIAL        PRIMARY KEY,
    "CARA單號"      VARCHAR(50)   UNIQUE,
    "狀態"          VARCHAR(20)   DEFAULT '進行中',
    "NCMR_ID"       INTEGER       REFERENCES "不合格品單"("識別碼"),
    "廠商"          VARCHAR(100),
    -- D2
    "D2_What"       TEXT,
    "D2_Where"      TEXT,
    "D2_When"       TEXT,
    "D2_Who"        TEXT,
    "D2_Why"        TEXT,
    "D2_How"        TEXT,
    "D2_HowMany"    TEXT,
    "D2_問題描述"   TEXT,
    -- D3
    "D3_對策內容"   TEXT,
    "D3_生效日"     DATE,
    "D3_有效性驗證" TEXT,
    "D3_暫時對策"   TEXT,
    -- D4
    "D4_工具"       VARCHAR(20),
    "D4_5Why資料"   JSONB,
    "D4_魚骨圖資料" JSONB,
    "D4_根本原因"   TEXT,
    "D4_真因分析"   TEXT,
    -- D6
    "D6_實施日"     DATE,
    "D6_驗證結果"   TEXT,
    "D6_驗證通過"   BOOLEAN       DEFAULT FALSE,
    "D6_成效驗證"   TEXT,
    -- D8
    "D8_結案日期"   DATE,
    "D8_結案確認"   TEXT,
    "D8_結案確認_舊" TEXT,
    -- 負責人
    "負責人員"      INTEGER       REFERENCES "品管人員"("識別碼"),
    "D1_Leader"     INTEGER       REFERENCES "品管人員"("識別碼"),
    -- 時間戳
    "建立時間"      TIMESTAMP     DEFAULT NOW(),
    "結案時間"      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_矯正措施要求_狀態 ON "矯正措施要求" ("狀態");
