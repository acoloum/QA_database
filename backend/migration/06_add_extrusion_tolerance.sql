-- 建立擠壓公差主檔
CREATE TABLE IF NOT EXISTS "擠壓公差主檔" (
    "識別碼"   SERIAL PRIMARY KEY,
    "材質"     VARCHAR NOT NULL,
    "規格"     VARCHAR,
    "備註"     VARCHAR,
    "建立日期" DATE DEFAULT CURRENT_DATE
);

-- 建立擠壓公差明細檔
CREATE TABLE IF NOT EXISTS "擠壓公差明細檔" (
    "識別碼"   SERIAL PRIMARY KEY,
    "主檔ID"   INTEGER NOT NULL REFERENCES "擠壓公差主檔"("識別碼") ON DELETE CASCADE,
    "測量項目" VARCHAR NOT NULL,
    "測量位置" VARCHAR,
    "公差下限" NUMERIC,
    "公差上限" NUMERIC,
    "標準值"   NUMERIC,
    "單位"     VARCHAR DEFAULT 'mm'
);
