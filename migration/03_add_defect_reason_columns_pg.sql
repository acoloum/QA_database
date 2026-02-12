-- ================================================
-- 新增不良原因欄位到 NCMR 表 - PostgreSQL 版本
-- 從 SQL Server 遷移轉換
-- ================================================

-- 檢查並新增欄位：不良原因大類
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = '不合格品單' 
        AND column_name = '不良原因大類'
    ) THEN
        ALTER TABLE "不合格品單"
        ADD COLUMN "不良原因大類" VARCHAR(10);
        
        RAISE NOTICE '已新增欄位: 不良原因大類';
    ELSE
        RAISE NOTICE '欄位已存在: 不良原因大類';
    END IF;
END $$;

-- 檢查並新增欄位：不良原因細項
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = '不合格品單' 
        AND column_name = '不良原因細項'
    ) THEN
        ALTER TABLE "不合格品單"
        ADD COLUMN "不良原因細項" VARCHAR(100);
        
        RAISE NOTICE '已新增欄位: 不良原因細項';
    ELSE
        RAISE NOTICE '欄位已存在: 不良原因細項';
    END IF;
END $$;

-- 驗證欄位是否新增成功
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = '不合格品單' 
  AND column_name IN ('不良原因大類', '不良原因細項')
ORDER BY ordinal_position;

-- 完成訊息
DO $$
BEGIN
    RAISE NOTICE '欄位新增完成！';
END $$;
