-- Migration 11: 客訴欄位重構
-- DROP 料號、客戶聯絡人；ADD 材質、規格、擠製編號

ALTER TABLE 客訴紀錄
    DROP COLUMN IF EXISTS 料號,
    DROP COLUMN IF EXISTS 客戶聯絡人,
    ADD COLUMN IF NOT EXISTS 材質     VARCHAR(100),
    ADD COLUMN IF NOT EXISTS 規格     VARCHAR(200),
    ADD COLUMN IF NOT EXISTS 擠製編號  JSONB DEFAULT '[]'::jsonb;
