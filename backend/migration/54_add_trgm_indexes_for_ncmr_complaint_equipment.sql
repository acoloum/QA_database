-- ============================================================================
-- 54_add_trgm_indexes_for_ncmr_complaint_equipment.sql
-- 補齊 53 未涵蓋的模糊搜尋欄位（pg_trgm GIN）
--
-- 背景：53_add_trgm_search_indexes.sql 建立時，只涵蓋了出貨／巡檢／公差／機械
--       四個模組。之後新增的清單篩選（不合格品單、客訴紀錄、量測設備）同樣是
--       LIKE '%關鍵字%' 的前置萬用字元述詞，btree 索引無法服務，只會走 Seq Scan。
--
-- 作法：與 53 相同，改建 gin_trgm_ops 的 GIN 索引，查詢語意不需更動。
--
-- 對應的服務層篩選：
--   NcmrService.get_list          → vendor / material / product_info
--   ComplaintService.list         → customer / material / spec
--   MeasurementEquipmentService   → equipment_no / name / serial_no（關鍵字 q）
--   CalibrationService            → equipment_no / name（同一張量測設備表）
--
-- PostgreSQL 16；CREATE INDEX IF NOT EXISTS 可安全重複執行
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 不合格品單：NcmrService.get_list 的 vendor / material / product_info 模糊篩選
CREATE INDEX IF NOT EXISTS idx_ncmr_vendor_trgm
    ON 不合格品單 USING gin (廠商 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ncmr_material_trgm
    ON 不合格品單 USING gin (材質 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ncmr_product_info_trgm
    ON 不合格品單 USING gin (產品資訊 gin_trgm_ops);

-- 客訴紀錄：ComplaintService.list 的 customer / material / spec 模糊篩選
CREATE INDEX IF NOT EXISTS idx_complaint_customer_trgm
    ON 客訴紀錄 USING gin (客戶 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_complaint_material_trgm
    ON 客訴紀錄 USING gin (材質 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_complaint_spec_trgm
    ON 客訴紀錄 USING gin (規格 gin_trgm_ops);

-- 量測設備：關鍵字搜尋（設備編號／名稱／序號）與校驗清單的同欄位篩選
CREATE INDEX IF NOT EXISTS idx_equipment_no_trgm
    ON 量測設備 USING gin (設備編號 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_equipment_name_trgm
    ON 量測設備 USING gin (名稱 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_equipment_serial_trgm
    ON 量測設備 USING gin (序號 gin_trgm_ops);
