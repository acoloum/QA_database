-- Migration 20：新增不合格品處置明細子表（IATF 16949 §8.7）
-- 套用：psql -U postgres -d qa_database -f backend/migration/20_add_ncmr_disposition.sql
BEGIN;

CREATE TABLE IF NOT EXISTS "不合格品處置明細" (
    "識別碼"           SERIAL PRIMARY KEY,
    "NCMR_ID"          INTEGER NOT NULL REFERENCES "不合格品單"("識別碼"),
    "處置類型"         VARCHAR(20) NOT NULL,
    "處置數量"         INTEGER NOT NULL,
    "處置人"           INTEGER REFERENCES "品管人員"("識別碼"),
    "處置時間"         TIMESTAMP DEFAULT NOW(),
    "備註"             TEXT,
    "關聯重工單ID"     INTEGER REFERENCES "重工申請單"("識別碼"),
    "合格數"           INTEGER,
    "不合格數"         INTEGER,
    "是否超出客戶規格" BOOLEAN DEFAULT FALSE,
    "授權狀態"         VARCHAR(10),
    "授權文號"         VARCHAR(100),
    "授權有效期"       DATE,
    "授權數量上限"     INTEGER,
    "未授權放行理由"   TEXT,
    "是否風險項"       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS "idx_ncmr_disp_ncmr" ON "不合格品處置明細" ("NCMR_ID");
CREATE INDEX IF NOT EXISTS "idx_ncmr_disp_risk" ON "不合格品處置明細" ("是否風險項");

COMMIT;
