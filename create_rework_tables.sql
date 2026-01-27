USE [品保資料庫]
GO

-- =====================================================
-- 重工品管資料庫表建立腳本
-- 建立日期: 2025-01-27
-- 版本: 1.0
-- 描述: 建立完整的重工品管管理系統資料表
-- =====================================================

PRINT '開始建立重工品管資料表...'
GO

-- 1. 建立重工申請單主檔
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '重工申請單')
BEGIN
    CREATE TABLE dbo.重工申請單 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        NCMR_ID INT,                    -- 關聯不合格品單
        申請單號 NVARCHAR(20) UNIQUE,    -- RW-YYYYMMDD-XXX 格式
        申請日期 DATETIME DEFAULT GETDATE(),
        申請人員 INT,                    -- 關聯品管人員
        部門 NVARCHAR(50),               -- 申請部門
        緊急程度 NVARCHAR(20) DEFAULT '普通', -- 緊急、重要、普通
        產品資訊 NVARCHAR(255),
        批號 NVARCHAR(100),
        重工數量 FLOAT,
        申請原因 NVARCHAR(MAX),          -- 重工理由
        預計完成日期 DATE,
        審核狀態 NVARCHAR(20) DEFAULT '待審核', -- 待審核、已核准、已拒絕
        審核人員 INT,                    -- 關聯品管人員
        審核時間 DATETIME,
        審核意見 NVARCHAR(MAX),
        狀態 NVARCHAR(20) DEFAULT '申請中', -- 申請中、已核准、執行中、已完成、已取消
        建立時間 DATETIME DEFAULT GETDATE(),
        更新時間 DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (NCMR_ID) REFERENCES dbo.不合格品單(識別碼)
    )
    PRINT '✓ 重工申請單表建立成功'
END
ELSE
BEGIN
    PRINT '! 重工申請單表已存在'
END
GO

-- 2. 建立重工執行記錄表
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '重工執行記錄')
BEGIN
    CREATE TABLE dbo.重工執行記錄 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        重工單號 INT,                    -- 關聯重工申請單
        執行部門 NVARCHAR(50),
        負責人員 INT,                    -- 關聯品管人員
        協同人員 NVARCHAR(255),          -- 協作人員清單
        開始時間 DATETIME,
        預計完成時間 DATETIME,
        實際完成時間 DATETIME,
        使用設備 NVARCHAR(255),          -- 設備清單
        重工方式 NVARCHAR(MAX),          -- 重工製程說明
        SOP編號 NVARCHAR(50),            -- 標準作業程序
        耗材記錄 NVARCHAR(MAX),          -- 使用材料清單
        執行狀況 NVARCHAR(MAX),          -- 執行過程記錄
        異常狀況 NVARCHAR(MAX),          -- 執行異常記錄
        完成數量 FLOAT,
        不良數量 FLOAT,
        良率 FLOAT,
        執行人員 INT,                    -- 實際執行人員
        建立時間 DATETIME DEFAULT GETDATE(),
        更新時間 DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (重工單號) REFERENCES dbo.重工申請單(識別碼)
    )
    PRINT '✓ 重工執行記錄表建立成功'
END
ELSE
BEGIN
    PRINT '! 重工執行記錄表已存在'
END
GO

-- 3. 建立重工品檢記錄表
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '重工品檢記錄')
BEGIN
    CREATE TABLE dbo.重工品檢記錄 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        重工單號 INT,                    -- 關聯重工申請單
        執行記錄ID INT,                  -- 關聯重工執行記錄
        檢驗日期 DATETIME DEFAULT GETDATE(),
        檢驗人員 INT,                    -- 關聯品管人員
        檢驗階段 NVARCHAR(20),           -- 重工前、重工中、重工後
        檢驗項目 NVARCHAR(255),          -- 檢驗項目清單
        檢驗標準 NVARCHAR(MAX),          -- 品質標準
        檢驗方法 NVARCHAR(MAX),          -- 檢驗方法
        檢驗數據 NVARCHAR(MAX),          -- 具體檢驗數值
        判定結果 NVARCHAR(20),           -- 合格、不合格、特採
        不良現象 NVARCHAR(MAX),          -- 不良描述
        改善建議 NVARCHAR(MAX),
        通過數量 FLOAT,
        不合格數量 FLOAT,
        重檢數量 FLOAT,
        檢驗結論 NVARCHAR(MAX),
        建立時間 DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (重工單號) REFERENCES dbo.重工申請單(識別碼),
        FOREIGN KEY (執行記錄ID) REFERENCES dbo.重工執行記錄(識別碼)
    )
    PRINT '✓ 重工品檢記錄表建立成功'
END
ELSE
BEGIN
    PRINT '! 重工品檢記錄表已存在'
END
GO

-- 4. 建立重工成本分析表
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '重工成本分析')
BEGIN
    CREATE TABLE dbo.重工成本分析 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        重工單號 INT,                    -- 關聯重工申請單
        成本類型 NVARCHAR(50),           -- 人工、材料、設備、其他
        成本項目 NVARCHAR(255),
        單位成本 FLOAT,
        數量 FLOAT,
        總成本 FLOAT,
        成本幣別 NVARCHAR(10) DEFAULT 'TWD',
        記錄日期 DATETIME DEFAULT GETDATE(),
        記錄人員 INT,                    -- 關聯品管人員
        備註 NVARCHAR(MAX),
        建立時間 DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (重工單號) REFERENCES dbo.重工申請單(識別碼)
    )
    PRINT '✓ 重工成本分析表建立成功'
END
ELSE
BEGIN
    PRINT '! 重工成本分析表已存在'
END
GO

-- 5. 建立重工效益評估表
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '重工效益評估')
BEGIN
    CREATE TABLE dbo.重工效益評估 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        重工單號 INT,                    -- 關聯重工申請單
        評估日期 DATETIME DEFAULT GETDATE(),
        評估人員 INT,                    -- 關聯品管人員
        重工前良率 FLOAT,
        重工後良率 FLOAT,
        良率提升 FLOAT,
        時間效益 FLOAT,                  -- 節省時間(小時)
        成本效益 FLOAT,                  -- 成本節省
        客戶滿意度 FLOAT,               -- 1-5分評分
        品質改善度 FLOAT,               -- 1-5分評分
        整體效益 NVARCHAR(MAX),          -- 綜合評估
        改善建議 NVARCHAR(MAX),
        預防措施 NVARCHAR(MAX),
        建立時間 DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (重工單號) REFERENCES dbo.重工申請單(識別碼)
    )
    PRINT '✓ 重工效益評估表建立成功'
END
ELSE
BEGIN
    PRINT '! 重工效益評估表已存在'
END
GO

-- =====================================================
-- 建立索引以提升查詢效能
-- =====================================================

PRINT '開始建立索引...'
GO

-- 重工申請單索引
CREATE INDEX IX_重工申請單_NCMR ON dbo.重工申請單(NCMR_ID);
CREATE INDEX IX_重工申請單_狀態 ON dbo.重工申請單(狀態);
CREATE INDEX IX_重工申請單_申請日期 ON dbo.重工申請單(申請日期);
CREATE INDEX IX_重工申請單_申請單號 ON dbo.重工申請單(申請單號);
GO

-- 重工執行記錄索引
CREATE INDEX IX_重工執行記錄_重工單號 ON dbo.重工執行記錄(重工單號);
CREATE INDEX IX_重工執行記錄_負責人員 ON dbo.重工執行記錄(負責人員);
CREATE INDEX IX_重工執行記錄_開始時間 ON dbo.重工執行記錄(開始時間);
GO

-- 重工品檢記錄索引
CREATE INDEX IX_重工品檢記錄_重工單號 ON dbo.重工品檢記錄(重工單號);
CREATE INDEX IX_重工品檢記錄_執行記錄ID ON dbo.重工品檢記錄(執行記錄ID);
CREATE INDEX IX_重工品檢記錄_檢驗日期 ON dbo.重工品檢記錄(檢驗日期);
GO

-- 重工成本分析索引
CREATE INDEX IX_重工成本分析_重工單號 ON dbo.重工成本分析(重工單號);
CREATE INDEX IX_重工成本分析_成本類型 ON dbo.重工成本分析(成本類型);
GO

-- 重工效益評估索引
CREATE INDEX IX_重工效益評估_重工單號 ON dbo.重工效益評估(重工單號);
GO

PRINT '✓ 所有索引建立完成'
GO

-- =====================================================
-- 建立觸發程序和約束
-- =====================================================

PRINT '開始建立觸發程序和約束...'
GO

-- 1. 自動產生重工單號的函數
IF EXISTS (SELECT * FROM sys.objects WHERE name = 'GenerateReworkNo' AND type = 'FN')
BEGIN
    DROP FUNCTION dbo.GenerateReworkNo
END
GO

CREATE FUNCTION dbo.GenerateReworkNo()
RETURNS NVARCHAR(20)
AS
BEGIN
    DECLARE @DatePrefix NVARCHAR(8)
    DECLARE @NextNumber INT
    DECLARE @ReworkNo NVARCHAR(20)
    
    SET @DatePrefix = CONVERT(NVARCHAR, GETDATE(), 112) -- YYYYMMDD
    
    -- 取得當日最大單號
    SELECT @NextNumber = ISNULL(MAX(CAST(SUBSTRING(申請單號, 12, 3) AS INT)), 0) + 1
    FROM dbo.重工申請單 
    WHERE 申請單號 LIKE 'RW-' + @DatePrefix + '%'
    
    SET @ReworkNo = 'RW-' + @DatePrefix + '-' + RIGHT('000' + CAST(@NextNumber AS NVARCHAR), 3)
    
    RETURN @ReworkNo
END
GO

-- 2. 自動產生重工單號的觸發程序
IF EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_重工申請單_GenerateNo')
BEGIN
    DROP TRIGGER dbo.TR_重工申請單_GenerateNo
END
GO

CREATE TRIGGER dbo.TR_重工申請單_GenerateNo
ON dbo.重工申請單
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON
    
    UPDATE dbo.重工申請單
    SET 申請單號 = dbo.GenerateReworkNo()
    WHERE 申請單號 IS NULL AND 識別碼 IN (SELECT 識別碼 FROM inserted)
END
GO

-- 3. 自動更新時間戳的觸發程序
IF EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_重工申請單_UpdateTime')
BEGIN
    DROP TRIGGER dbo.TR_重工申請單_UpdateTime
END
GO

CREATE TRIGGER dbo.TR_重工申請單_UpdateTime
ON dbo.重工申請單
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON
    
    IF UPDATE(狀態) OR UPDATE(審核狀態) OR UPDATE(審核意見)
    BEGIN
        UPDATE dbo.重工申請單
        SET 更新時間 = GETDATE()
        WHERE 識別碼 IN (SELECT 識別碼 FROM inserted)
    END
END
GO

-- 4. 自動計算良率的觸發程序
IF EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_重工執行記錄_CalculateYield')
BEGIN
    DROP TRIGGER dbo.TR_重工執行記錄_CalculateYield
END
GO

CREATE TRIGGER dbo.TR_重工執行記錄_CalculateYield
ON dbo.重工執行記錄
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON
    
    IF UPDATE(完成數量) OR UPDATE(不良數量)
    BEGIN
        UPDATE dbo.重工執行記錄
        SET 良率 = CASE 
            WHEN 完成數量 IS NULL OR 完成數量 = 0 THEN 0
            WHEN 不良數量 IS NULL THEN 100
            ELSE ROUND(((完成數量 - ISNULL(不良數量, 0)) / 完成數量) * 100, 2)
        END
        WHERE 識別碼 IN (SELECT 識別碼 FROM inserted)
    END
END
GO

-- 5. 資料完整性約束
ALTER TABLE dbo.重工申請單
ADD CONSTRAINT CK_重工申請單_重工數量 CHECK (重工數量 > 0),
    CONSTRAINT CK_重工申請單_緊急程度 CHECK (緊急程度 IN ('緊急', '重要', '普通')),
    CONSTRAINT CK_重工申請單_審核狀態 CHECK (審核狀態 IN ('待審核', '已核准', '已拒絕')),
    CONSTRAINT CK_重工申請單_狀態 CHECK (狀態 IN ('申請中', '已核准', '執行中', '已完成', '已取消'))
GO

ALTER TABLE dbo.重工執行記錄
ADD CONSTRAINT CK_重工執行記錄_良率 CHECK (良率 >= 0 AND 良率 <= 100),
    CONSTRAINT CK_重工執行記錄_數量 CHECK (完成數量 >= 0 AND 不良數量 >= 0)
GO

ALTER TABLE dbo.重工成本分析
ADD CONSTRAINT CK_重工成本分析_成本 CHECK (單位成本 >= 0 AND 數量 >= 0 AND 總成本 >= 0),
    CONSTRAINT CK_重工成本分析_類型 CHECK (成本類型 IN ('人工', '材料', '設備', '其他'))
GO

ALTER TABLE dbo.重工效益評估
ADD CONSTRAINT CK_重工效益評估_良率 CHECK (重工前良率 >= 0 AND 重工前良率 <= 100 AND 
                                       重工後良率 >= 0 AND 重工後良率 <= 100),
    CONSTRAINT CK_重工效益評估_評分 CHECK (客戶滿意度 >= 1 AND 客戶滿意度 <= 5 AND 
                                       品質改善度 >= 1 AND 品質改善度 <= 5)
GO

PRINT '✓ 所有觸發程序和約束建立完成'
GO

-- =====================================================
-- 建立檢視表方便查詢
-- =====================================================

PRINT '開始建立檢視表...'
GO

-- 1. 重工申請統計檢視表
IF EXISTS (SELECT * FROM sys.views WHERE name = 'V_重工申請統計')
BEGIN
    DROP VIEW dbo.V_重工申請統計
END
GO

CREATE VIEW dbo.V_重工申請統計
AS
SELECT 
    YEAR(申請日期) AS 年度,
    MONTH(申請日期) AS 月份,
    部門,
    緊急程度,
    狀態,
    COUNT(*) AS 申請數量,
    SUM(重工數量) AS 總重工數量,
    AVG(DATEDIFF(DAY, 申請日期, ISNULL(預計完成日期, 申請日期))) AS 平均預計天數
FROM dbo.重工申請單
GROUP BY YEAR(申請日期), MONTH(申請日期), 部門, 緊急程度, 狀態
GO

-- 2. 重工成本匯總檢視表
IF EXISTS (SELECT * FROM sys.views WHERE name = 'V_重工成本匯總')
BEGIN
    DROP VIEW dbo.V_重工成本匯總
END
GO

CREATE VIEW dbo.V_重工成本匯總
AS
SELECT 
    r.識別碼 AS 重工單號,
    r.申請單號,
    r.產品資訊,
    SUM(c.總成本) AS 總成本,
    SUM(CASE WHEN c.成本類型 = '人工' THEN c.總成本 ELSE 0 END) AS 人工成本,
    SUM(CASE WHEN c.成本類型 = '材料' THEN c.總成本 ELSE 0 END) AS 材料成本,
    SUM(CASE WHEN c.成本類型 = '設備' THEN c.總成本 ELSE 0 END) AS 設備成本,
    SUM(CASE WHEN c.成本類型 = '其他' THEN c.總成本 ELSE 0 END) AS 其他成本
FROM dbo.重工申請單 r
LEFT JOIN dbo.重工成本分析 c ON r.識別碼 = c.重工單號
GROUP BY r.識別碼, r.申請單號, r.產品資訊
GO

-- 3. 重工效益評估檢視表
IF EXISTS (SELECT * FROM sys.views WHERE name = 'V_重工效益評估')
BEGIN
    DROP VIEW dbo.V_重工效益評估
END
GO

CREATE VIEW dbo.V_重工效益評估
AS
SELECT 
    r.識別碼 AS 重工單號,
    r.申請單號,
    r.產品資訊,
    e.良率提升,
    e.時間效益,
    e.成本效益,
    e.客戶滿意度,
    e.品質改善度,
    (e.客戶滿意度 + e.品質改善度) / 2.0 AS 綜合評分
FROM dbo.重工申請單 r
LEFT JOIN dbo.重工效益評估 e ON r.識別碼 = e.重工單號
GO

PRINT '✓ 所有檢視表建立完成'
GO

-- =====================================================
-- 建立預設資料 (可選)
-- =====================================================

PRINT '開始建立預設資料...'
GO

-- 插入一些測試用的預設資料 (可選，實際部署時可移除)
IF NOT EXISTS (SELECT * FROM dbo.重工申請單 WHERE 申請單號 IS NOT NULL)
BEGIN
    -- 插入測試資料
    INSERT INTO dbo.重工申請單 (NCMR_ID, 申請人員, 部門, 緊急程度, 產品資訊, 批號, 重工數量, 申請原因, 預計完成日期, 狀態)
    VALUES 
        (1, 1, '生產部', '普通', '不銹鋼管 304-10x1.0', 'B202501001', 100, '尺寸偏差需重新加工', DATEADD(DAY, 3, GETDATE()), '申請中'),
        (2, 1, '品保部', '重要', '鋁管 6061-20x2.0', 'A202501002', 50, '表面刮傷需要拋光處理', DATEADD(DAY, 1, GETDATE()), '已核准')
    
    PRINT '✓ 測試資料建立完成'
END
GO

PRINT '========================================'
PRINT '重工品管資料庫表建立完成！'
PRINT '========================================'
PRINT ''
PRINT '已建立以下資料表：'
PRINT '1. 重工申請單'
PRINT '2. 重工執行記錄'
PRINT '3. 重工品檢記錄'
PRINT '4. 重工成本分析'
PRINT '5. 重工效益評估'
PRINT ''
PRINT '已建立以下索引：'
PRINT '- 各主要表關聯欄位索引'
PRINT '- 日期欄位索引'
PRINT '- 狀態欄位索引'
PRINT ''
PRINT '已建立以下觸發程序：'
PRINT '- 自動產生重工單號'
PRINT '- 自動更新時間戳'
PRINT '- 自動計算良率'
PRINT ''
PRINT '已建立以下檢視表：'
PRINT '- V_重工申請統計'
PRINT '- V_重工成本匯總'
PRINT '- V_重工效益評估'
PRINT ''
PRINT '資料庫結構已準備就緒，可以開始進行應用程式開發！'
PRINT '========================================'
GO