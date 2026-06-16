-- 21_add_pyrometry.sql — CQI-9 爐溫測試模組
-- 執行：psql -U postgres -d qa_database -f backend/migration/21_add_pyrometry.sql

BEGIN;

-- ① 爐子設備主檔
CREATE TABLE IF NOT EXISTS "爐子設備" (
    "識別碼"      SERIAL PRIMARY KEY,
    "爐號"        VARCHAR(50)  NOT NULL UNIQUE,
    "名稱"        VARCHAR(100) NOT NULL,
    "製程類型"    VARCHAR(20),
    "TUS點數"     INTEGER DEFAULT 12,
    "SAT點數"     INTEGER DEFAULT 2,
    "TUS頻率_月"  INTEGER DEFAULT 3,
    "SAT頻率_月"  INTEGER DEFAULT 3,
    "TUS允許公差" NUMERIC(6,2),
    "SAT允許誤差" NUMERIC(6,2),
    "有效加熱區尺寸" VARCHAR(100),
    "儀器型式"    VARCHAR(10),
    "CQI9等級"    VARCHAR(10),
    "啟用狀態"    BOOLEAN NOT NULL DEFAULT TRUE,
    "備註"        TEXT,
    "建立時間"    TIMESTAMPTZ DEFAULT now(),
    "更新時間"    TIMESTAMPTZ DEFAULT now()
);

-- ② 爐溫測試主檔
CREATE TABLE IF NOT EXISTS "爐溫測試" (
    "識別碼"         SERIAL PRIMARY KEY,
    "爐子ID"         INTEGER NOT NULL REFERENCES "爐子設備"("識別碼"),
    "測試類型"       VARCHAR(10) NOT NULL,
    "季別"           VARCHAR(10),
    "測試日期"       DATE NOT NULL,
    "設定溫度"       NUMERIC(8,2) NOT NULL,
    "允許公差"       NUMERIC(6,2),
    "測試人員"       INTEGER REFERENCES "品管人員"("識別碼"),
    "測試儀器編號"   VARCHAR(100),
    "標準校正儀器編號" VARCHAR(100),
    "儀器校正到期日" DATE,
    "是否合格"       BOOLEAN DEFAULT FALSE,
    "TUS均勻度極差"  NUMERIC(8,2),
    "TUS最大正偏差"  NUMERIC(8,2),
    "TUS最大負偏差"  NUMERIC(8,2),
    "備註"           TEXT,
    "建立人"         INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間"       TIMESTAMPTZ DEFAULT now(),
    "更新時間"       TIMESTAMPTZ DEFAULT now(),
    "刪除時間"       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_pyro_furnace_type_date ON "爐溫測試" ("爐子ID","測試類型","測試日期");
CREATE INDEX IF NOT EXISTS idx_pyro_deleted ON "爐溫測試" ("刪除時間");

-- ③ TUS 量測點明細
CREATE TABLE IF NOT EXISTS "TUS量測點明細" (
    "識別碼"   SERIAL PRIMARY KEY,
    "測試ID"   INTEGER NOT NULL REFERENCES "爐溫測試"("識別碼") ON DELETE CASCADE,
    "點位"     VARCHAR(20),
    "熱電偶編號" VARCHAR(50),
    "修正值"   NUMERIC(8,2),
    "最高溫"   NUMERIC(8,2),
    "最低溫"   NUMERIC(8,2),
    "最大偏差" NUMERIC(8,2),
    "是否合格" BOOLEAN DEFAULT TRUE
);

-- ④ SAT 量測點明細
CREATE TABLE IF NOT EXISTS "SAT量測點明細" (
    "識別碼"           SERIAL PRIMARY KEY,
    "測試ID"           INTEGER NOT NULL REFERENCES "爐溫測試"("識別碼") ON DELETE CASCADE,
    "控溫區"           VARCHAR(20),
    "控制儀表讀值"     NUMERIC(8,2),
    "校正測試儀表讀值" NUMERIC(8,2),
    "差值"             NUMERIC(8,2),
    "修正值"           NUMERIC(8,2),
    "偏差"             NUMERIC(8,2),
    "是否合格"         BOOLEAN DEFAULT TRUE
);

COMMIT;
