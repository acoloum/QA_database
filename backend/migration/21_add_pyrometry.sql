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

COMMIT;
