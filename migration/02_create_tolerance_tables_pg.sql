-- ================================================
-- 廠商公差管理系統 - PostgreSQL 資料庫表格建立腳本
-- 從 SQL Server 遷移轉換
-- ================================================

-- ================================================
-- 1. 創建主檔表格
-- ================================================
CREATE TABLE IF NOT EXISTS "廠商公差主檔" (
    "識別碼" SERIAL PRIMARY KEY,
    "材質" VARCHAR(50) NOT NULL,
    "規格" VARCHAR(100),
    "廠商ID" INTEGER,
    "備註" VARCHAR(500),
    "建立日期" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "建立人員" INTEGER,
    "更新日期" TIMESTAMP,
    "更新人員" INTEGER
);

COMMENT ON TABLE "廠商公差主檔" IS '廠商公差管理 - 主檔資料';

-- ================================================
-- 2. 創建明細檔表格
-- ================================================
CREATE TABLE IF NOT EXISTS "廠商公差明細檔" (
    "識別碼" SERIAL PRIMARY KEY,
    "主檔ID" INTEGER NOT NULL,
    "測量項目" VARCHAR(50) NOT NULL,
    "測量位置" VARCHAR(50),
    "尺寸下限" NUMERIC(18,4),
    "尺寸上限" NUMERIC(18,4),
    "公差下限" NUMERIC(18,4),
    "公差上限" NUMERIC(18,4),
    "標準值" NUMERIC(18,4),
    "單位" VARCHAR(20) DEFAULT 'mm',
    "備註" VARCHAR(200)
);

COMMENT ON TABLE "廠商公差明細檔" IS '廠商公差管理 - 明細資料';

-- ================================================
-- 3. 創建外鍵約束
-- ================================================
-- 注意：這些外鍵需要在對應的表（廠商資料、品管人員）建立後才能啟用
-- 如果表尚未建立，請先註解掉這些約束

-- ALTER TABLE "廠商公差主檔"
--     ADD CONSTRAINT "FK_廠商公差主檔_廠商" 
--     FOREIGN KEY ("廠商ID") 
--     REFERENCES "廠商資料"("識別碼");

-- ALTER TABLE "廠商公差主檔"
--     ADD CONSTRAINT "FK_廠商公差主檔_建立人員" 
--     FOREIGN KEY ("建立人員") 
--     REFERENCES "品管人員"("識別碼");

-- ALTER TABLE "廠商公差主檔"
--     ADD CONSTRAINT "FK_廠商公差主檔_更新人員" 
--     FOREIGN KEY ("更新人員") 
--     REFERENCES "品管人員"("識別碼");

ALTER TABLE "廠商公差明細檔"
    ADD CONSTRAINT "FK_廠商公差明細檔_主檔" 
    FOREIGN KEY ("主檔ID") 
    REFERENCES "廠商公差主檔"("識別碼") 
    ON DELETE CASCADE;

-- ================================================
-- 4. 創建索引以提升查詢效能
-- ================================================
CREATE INDEX IF NOT EXISTS "IX_廠商公差主檔_材質" 
    ON "廠商公差主檔"("材質");

CREATE INDEX IF NOT EXISTS "IX_廠商公差主檔_廠商ID" 
    ON "廠商公差主檔"("廠商ID");

CREATE INDEX IF NOT EXISTS "IX_廠商公差明細檔_主檔ID" 
    ON "廠商公差明細檔"("主檔ID");

CREATE INDEX IF NOT EXISTS "IX_廠商公差明細檔_測量項目" 
    ON "廠商公差明細檔"("測量項目");

-- ================================================
-- 完成訊息
-- ================================================
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE '資料庫表格建立完成！';
    RAISE NOTICE '表格：廠商公差主檔、廠商公差明細檔';
    RAISE NOTICE '============================================';
END $$;
