-- ================================================
-- PostgreSQL 資料庫建立腳本
-- 目的：建立品保資料庫，設定 UTF-8 編碼
-- ================================================

-- 連接到 postgres 預設資料庫後執行以下語句

-- 建立資料庫（如果已存在會報錯，可手動刪除後重建）
CREATE DATABASE qa_database
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'zh_TW.UTF-8'
    LC_CTYPE = 'zh_TW.UTF-8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    TEMPLATE = template0;

COMMENT ON DATABASE qa_database IS '品保資料庫 - 從 SQL Server 遷移';

-- 切換到新資料庫後執行以下語句
\c qa_database

-- 設定 search_path（保持與 SQL Server 的 dbo schema 相似性）
-- 可選：建立 dbo schema 或直接使用 public
CREATE SCHEMA IF NOT EXISTS public;

-- 設定預設 schema
ALTER DATABASE qa_database SET search_path TO public;

-- 啟用必要的擴充功能（如果需要）
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID 支援
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- 加密函數

COMMENT ON SCHEMA public IS '品保資料庫主要 schema';
