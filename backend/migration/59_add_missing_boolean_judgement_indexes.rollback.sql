-- Migration 59 rollback：移除本次補建的兩個判定欄位索引。
DROP INDEX IF EXISTS "ix_出貨檢驗數據_是否超差";
DROP INDEX IF EXISTS "ix_爐溫測試_是否合格";
