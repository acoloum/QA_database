BEGIN;

CREATE TABLE IF NOT EXISTS "角色" (
    "識別碼"   SERIAL PRIMARY KEY,
    "角色代碼" VARCHAR(30) NOT NULL UNIQUE,
    "角色名稱" VARCHAR(50) NOT NULL,
    "權限"     JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS "操作日誌" (
    "識別碼"   SERIAL PRIMARY KEY,
    "使用者ID" INTEGER REFERENCES "使用者"("識別碼") ON DELETE SET NULL,
    "操作類型" VARCHAR(20) NOT NULL,
    "模組"     VARCHAR(30) NOT NULL,
    "資料ID"   INTEGER,
    "操作前"   JSONB,
    "操作後"   JSONB,
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auditlog_module_record ON "操作日誌"("模組", "資料ID");
CREATE INDEX IF NOT EXISTS idx_auditlog_user_created  ON "操作日誌"("使用者ID", "建立時間");

COMMIT;
