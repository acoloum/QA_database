
USE [品保資料庫]
GO

-- 1. 建立不合格品單 (NCMR) 表
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '不合格品單')
BEGIN
    CREATE TABLE dbo.不合格品單 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        日期 DATE DEFAULT GETDATE(),
        來源 NVARCHAR(20), -- 巡檢, 出貨檢, 客訴, 進料
        來源單號 INT,      -- 對應來源表的 ID
        產品資訊 NVARCHAR(255), -- 材質/規格
        批號 NVARCHAR(100),
        不良描述 NVARCHAR(MAX),
        不合格數量 FLOAT,
        發現人員 INT,      -- 關聯至 品管人員
        判定結果 NVARCHAR(50), -- 特採, 重工, 報廢, 退貨
        狀態 NVARCHAR(20) DEFAULT '待處理', -- 待處理, 已結案, 轉CAPA
        建立時間 DATETIME DEFAULT GETDATE()
    )
    PRINT '✓ 不合格品單 (NCMR) 表建立成功'
END
ELSE
BEGIN
    PRINT '! 不合格品單 (NCMR) 表已存在'
END
GO

-- 2. 建立異常矯正單 (CAPA) 表
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '異常矯正單')
BEGIN
    CREATE TABLE dbo.異常矯正單 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        NCMR_ID INT,       -- 關聯至 不合格品單
        負責人員 INT,      -- 關聯至 品管人員
        D1_小組成員 NVARCHAR(255),
        D2_問題描述 NVARCHAR(MAX),
        D3_暫時對策 NVARCHAR(MAX),
        D4_真因分析 NVARCHAR(MAX),
        D5_永久對策 NVARCHAR(MAX),
        D6_成效驗證 NVARCHAR(MAX),
        D7_預防再發 NVARCHAR(MAX),
        D8_結案確認 NVARCHAR(MAX),
        狀態 NVARCHAR(20) DEFAULT '進行中', -- 進行中, 已結案
        建立日期 DATETIME DEFAULT GETDATE(),
        結案日期 DATETIME,
        FOREIGN KEY (NCMR_ID) REFERENCES dbo.不合格品單(識別碼)
    )
    PRINT '✓ 異常矯正單 (CAPA) 表建立成功'
END
ELSE
BEGIN
    PRINT '! 異常矯正單 (CAPA) 表已存在'
END
GO
