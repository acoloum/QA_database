-- 建立使用者表
USE [品保資料庫]
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '使用者')
BEGIN
    CREATE TABLE dbo.使用者 (
        識別碼 INT IDENTITY(1,1) PRIMARY KEY,
        使用者名稱 NVARCHAR(50) NOT NULL UNIQUE,
        密碼 NVARCHAR(100) NOT NULL,
        是否啟用 BIT DEFAULT 1,
        建立時間 DATETIME DEFAULT GETDATE(),
        最後登入時間 DATETIME NULL
    )
    PRINT '✓ 使用者表建立成功'
END
ELSE
BEGIN
    PRINT '! 使用者表已存在'
END
GO

-- 建立預設管理員帳號 (使用者名稱: admin, 密碼: admin)
INSERT INTO dbo.使用者 (使用者名稱, 密碼, 是否啟用)
SELECT 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 1
WHERE NOT EXISTS (SELECT * FROM dbo.使用者 WHERE 使用者名稱 = 'admin')
GO

-- 8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918 是 'admin' 的 SHA256 hash

PRINT '完成！預設管理員帳號：admin / admin'
GO
