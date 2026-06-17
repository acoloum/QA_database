-- 23_add_thermocouple_cal.sql — 熱電偶線校正主檔 + seed 220716（CLT4819-111, TYPE K）
-- 執行：psql -U postgres -d qa_database -f backend/migration/23_add_thermocouple_cal.sql

BEGIN;

-- ① 熱電偶主檔
CREATE TABLE IF NOT EXISTS "熱電偶" (
    "識別碼"   SERIAL PRIMARY KEY,
    "編號"     VARCHAR(50) NOT NULL UNIQUE,
    "型式"     VARCHAR(20),
    "校正日期" DATE,
    "到期日"   DATE,
    "啟用狀態" BOOLEAN NOT NULL DEFAULT TRUE,
    "備註"     TEXT,
    "建立時間" TIMESTAMPTZ DEFAULT now(),
    "更新時間" TIMESTAMPTZ DEFAULT now()
);

-- ② 熱電偶校正點（每筆=某標準溫度的器差值）
CREATE TABLE IF NOT EXISTS "熱電偶校正點" (
    "識別碼"   SERIAL PRIMARY KEY,
    "熱電偶ID" INTEGER NOT NULL REFERENCES "熱電偶"("識別碼") ON DELETE CASCADE,
    "標準溫度" NUMERIC(8,2) NOT NULL,
    "器差值"   NUMERIC(8,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_thermocouple_cal ON "熱電偶校正點" ("熱電偶ID","標準溫度");

-- ③ seed 熱電偶 220716（TYPE K）
INSERT INTO "熱電偶" ("編號","型式","校正日期","啟用狀態","備註")
SELECT '220716','TYPE K','2022-08-05',TRUE,'CLT4819-111 CLC科技檢校中心校正報告'
WHERE NOT EXISTS (SELECT 1 FROM "熱電偶" WHERE "編號"='220716');

-- ④ seed 校正曲線（器示值−標準值）
INSERT INTO "熱電偶校正點" ("熱電偶ID","標準溫度","器差值")
SELECT t."識別碼", v.std, v.err
FROM "熱電偶" t
CROSS JOIN (VALUES
    (100.01, 0.42),
    (200.00, 0.65),
    (300.10, 0.80),
    (450.30, 1.14),
    (600.27, 1.16)
) AS v(std, err)
WHERE t."編號"='220716'
  AND NOT EXISTS (SELECT 1 FROM "熱電偶校正點" cp WHERE cp."熱電偶ID"=t."識別碼");

COMMIT;
