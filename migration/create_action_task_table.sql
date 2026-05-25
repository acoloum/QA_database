-- 建立橫展任務資料表（ActionTask，與 CAPA D7 連動）
CREATE TABLE IF NOT EXISTS "橫展任務" (
    "識別碼"    SERIAL        PRIMARY KEY,
    "任務單號"  VARCHAR(50)   UNIQUE,
    "來源類型"  VARCHAR(30)   NOT NULL,
    "來源ID"    INTEGER       NOT NULL,
    "類別"      VARCHAR(50)   NOT NULL,
    "標題"      VARCHAR(200)  NOT NULL,
    "描述"      TEXT,
    "相關料號"  JSONB,
    "負責人"    INTEGER       REFERENCES "品管人員"("識別碼"),
    "應完成日"  DATE,
    "狀態"      VARCHAR(20)   DEFAULT 'pending',
    "完成證明"  TEXT,
    "豁免理由"  TEXT,
    "完成時間"  TIMESTAMP,
    "建立時間"  TIMESTAMP     DEFAULT NOW(),
    "更新時間"  TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_橫展任務_來源 ON "橫展任務" ("來源類型", "來源ID");
CREATE INDEX IF NOT EXISTS idx_橫展任務_狀態 ON "橫展任務" ("狀態");
