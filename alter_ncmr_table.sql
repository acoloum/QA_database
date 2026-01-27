
USE [品保資料庫]
GO

IF NOT EXISTS(SELECT 1 FROM sys.columns WHERE Name = N'廠商' AND Object_ID = Object_ID(N'dbo.不合格品單'))
BEGIN
    ALTER TABLE dbo.不合格品單 ADD 廠商 NVARCHAR(100);
    PRINT '✓ 已新增 [廠商] 欄位'
END

IF NOT EXISTS(SELECT 1 FROM sys.columns WHERE Name = N'材質' AND Object_ID = Object_ID(N'dbo.不合格品單'))
BEGIN
    ALTER TABLE dbo.不合格品單 ADD 材質 NVARCHAR(100);
    PRINT '✓ 已新增 [材質] 欄位'
END
GO
