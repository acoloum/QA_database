-- ============================================================================
-- 53_add_trgm_search_indexes.sql
-- 模糊搜尋改用 pg_trgm GIN 索引
--
-- 背景：52_add_query_indexes.sql 為 材質/規格/廠商名稱 等欄位建了 btree 索引，
--       但服務層的篩選一律是 LIKE '%關鍵字%'（前置萬用字元），btree 無法服務這種
--       述詞，PostgreSQL 只會走 Seq Scan，索引形同虛設。
--
-- 作法：改建 pg_trgm 的 GIN 索引。gin_trgm_ops 同時支援 LIKE 與 ILIKE 的
--       任意位置比對，因此不需要更動查詢語意即可讓索引生效。
--
-- 保留 52 的 btree 索引：材質/規格 另有 DISTINCT + ORDER BY 用途
--       （見 tolerance_service.get_options），btree 在該路徑仍是最佳選擇。
--
-- PostgreSQL 16；CREATE INDEX IF NOT EXISTS 可安全重複執行
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 出貨檢驗數據：ShippingService.get_list / get_stats 的 material / spec 模糊篩選
CREATE INDEX IF NOT EXISTS idx_shipping_material_trgm
    ON 出貨檢驗數據 USING gin (材質 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_shipping_spec_trgm
    ON 出貨檢驗數據 USING gin (檢驗規格 gin_trgm_ops);

-- 廠商主檔：出貨清單以 Vendor.name 做模糊篩選（JOIN 後過濾）
CREATE INDEX IF NOT EXISTS idx_vendor_name_trgm
    ON 廠商資料 USING gin (廠商名稱 gin_trgm_ops);

-- 巡檢主檔：PatrolService 清單/統計/串流的 mat / spec 模糊篩選
CREATE INDEX IF NOT EXISTS idx_patrol_main_material_trgm
    ON 巡檢主檔 USING gin (材質 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_patrol_main_spec_trgm
    ON 巡檢主檔 USING gin (擠壓規格 gin_trgm_ops);

-- 廠商公差主檔：TolerantService 清單與查詢的 material / spec 模糊篩選
CREATE INDEX IF NOT EXISTS idx_vendor_tol_material_trgm
    ON 廠商公差主檔 USING gin (材質 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_vendor_tol_spec_trgm
    ON 廠商公差主檔 USING gin (規格 gin_trgm_ops);

-- 擠壓公差主檔：ExtrusionToleranceService 的 material / spec / vendor 模糊篩選
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_material_trgm
    ON 擠壓公差主檔 USING gin (材質 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_spec_trgm
    ON 擠壓公差主檔 USING gin (規格 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_vendor_trgm
    ON 擠壓公差主檔 USING gin (廠商 gin_trgm_ops);

-- 機械性質檢驗：MechanicalService 清單的 product_size / material 模糊篩選
CREATE INDEX IF NOT EXISTS idx_mechanical_product_size_trgm
    ON 機械性質檢驗 USING gin (產品尺寸 gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_mechanical_material_trgm
    ON 機械性質檢驗 USING gin (材質 gin_trgm_ops);
