-- ============================================================================
-- 52_add_query_indexes.sql
-- 熱門查詢欄位補索引：加速巡檢/出貨/NCMR/重工/公差等常用篩選與關聯 JOIN
-- PostgreSQL 16；CREATE INDEX IF NOT EXISTS 可安全重複執行
-- 對應 backend/models.py 中新增的 index=True 欄位（SQLite 測試庫由 create_all 自動建立）
-- ============================================================================

-- 巡檢主檔：依日期/機台/主機手/檢驗人員/材質/規格/客戶篩選
CREATE INDEX IF NOT EXISTS idx_patrol_main_date      ON 巡檢主檔 (檢驗日期);
CREATE INDEX IF NOT EXISTS idx_patrol_main_machine   ON 巡檢主檔 (機台);
CREATE INDEX IF NOT EXISTS idx_patrol_main_operator  ON 巡檢主檔 (主機手);
CREATE INDEX IF NOT EXISTS idx_patrol_main_inspector ON 巡檢主檔 (檢驗人員);
CREATE INDEX IF NOT EXISTS idx_patrol_main_material  ON 巡檢主檔 (材質);
CREATE INDEX IF NOT EXISTS idx_patrol_main_spec      ON 巡檢主檔 (擠壓規格);
CREATE INDEX IF NOT EXISTS idx_patrol_main_customer  ON 巡檢主檔 (客戶名稱);

-- 巡檢子檔：依主檔 JOIN
CREATE INDEX IF NOT EXISTS idx_patrol_detail_main    ON 巡檢子檔 (主檔ID);

-- 出貨檢驗數據：依規格/檢驗人員/廠商篩選
CREATE INDEX IF NOT EXISTS idx_shipping_spec         ON 出貨檢驗數據 (檢驗規格);
CREATE INDEX IF NOT EXISTS idx_shipping_inspector    ON 出貨檢驗數據 (檢驗人員);
CREATE INDEX IF NOT EXISTS idx_shipping_vendor       ON 出貨檢驗數據 (廠商名稱);

-- SPC 事件：依研究版本/樣本查詢
CREATE INDEX IF NOT EXISTS idx_spc_event_study_version ON SPC事件 (研究版本ID);
CREATE INDEX IF NOT EXISTS idx_spc_event_sample        ON SPC事件 (研究樣本ID);

-- 不合格品單：依材質/發現人員篩選
CREATE INDEX IF NOT EXISTS idx_ncmr_material          ON 不合格品單 (材質);
CREATE INDEX IF NOT EXISTS idx_ncmr_inspector         ON 不合格品單 (發現人員);

-- 不合格品處置：依關聯重工單查詢
CREATE INDEX IF NOT EXISTS idx_ncmr_disp_rework       ON 不合格品處置明細 (關聯重工單ID);

-- 重工申請單：依 NCMR/材質查詢
CREATE INDEX IF NOT EXISTS idx_rework_ncmr            ON 重工申請單 (NCMR_ID);
CREATE INDEX IF NOT EXISTS idx_rework_material        ON 重工申請單 (材質);

-- 廠商公差：依廠商/材質/規格查詢
CREATE INDEX IF NOT EXISTS idx_vendor_tol_vendor      ON 廠商公差主檔 (廠商ID);
CREATE INDEX IF NOT EXISTS idx_vendor_tol_material    ON 廠商公差主檔 (材質);
CREATE INDEX IF NOT EXISTS idx_vendor_tol_spec        ON 廠商公差主檔 (規格);
CREATE INDEX IF NOT EXISTS idx_vendor_tol_detail_main ON 廠商公差明細檔 (主檔ID);

-- 擠壓公差：依材質/規格/廠商查詢
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_material    ON 擠壓公差主檔 (材質);
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_spec        ON 擠壓公差主檔 (規格);
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_vendor      ON 擠壓公差主檔 (廠商);
CREATE INDEX IF NOT EXISTS idx_extrusion_tol_detail_main ON 擠壓公差明細檔 (主檔ID);
