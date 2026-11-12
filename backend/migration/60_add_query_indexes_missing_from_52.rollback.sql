-- Migration 60 rollback：移除本檔補建的 10 個查詢索引。
--
-- 注意：這些索引與 52 同名。已執行過 52 的資料庫（新安裝、CI）不要執行本檔，
-- 否則會連 52 建立的索引一起移除。只用於「以 --baseline 略過 52、再套用 60」的正式庫。
DROP INDEX IF EXISTS idx_patrol_main_operator;
DROP INDEX IF EXISTS idx_patrol_main_inspector;
DROP INDEX IF EXISTS idx_patrol_main_customer;
DROP INDEX IF EXISTS idx_shipping_inspector;
DROP INDEX IF EXISTS idx_spc_event_study_version;
DROP INDEX IF EXISTS idx_spc_event_sample;
DROP INDEX IF EXISTS idx_ncmr_inspector;
DROP INDEX IF EXISTS idx_ncmr_disp_rework;
DROP INDEX IF EXISTS idx_rework_material;
DROP INDEX IF EXISTS idx_extrusion_tol_detail_main;
