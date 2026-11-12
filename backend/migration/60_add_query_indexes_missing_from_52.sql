-- ============================================================================
-- 60_add_query_indexes_missing_from_52.sql
-- 只補 52_add_query_indexes.sql 中「正式庫真正缺少」的 10 個查詢索引。
--
-- 背景：52 從未在正式庫套用。逐一比對 52 的 26 個索引後：
--   * 8 個已有同欄位的早期索引（migration 09 的 IX_巡檢主檔_檢驗日期、IX_出貨檢驗_廠商、
--     IX_重工申請單_NCMR_ID、IX_廠商公差主檔_廠商ID … 等），再建只會重複；
--   * 8 個材質／規格／廠商欄位已有 53 的 pg_trgm GIN 索引，這些欄位主要用 ilike 模糊查詢，
--     少數等值查詢 gin_trgm_ops 亦可支援（PostgreSQL 14+），且資料表很小；
--   * 剩下 10 個完全沒有可用索引，由本檔補建。
-- 正式庫因此不執行 52，以 --baseline 記為已套用，再套用本檔。
--
-- 52 本身有錯：識別字未加引號，PostgreSQL 會把 SPC事件、主檔ID 轉成小寫的 spc事件、主檔id，
-- 在任何 PostgreSQL 上都會以「relation does not exist」失敗——這也是它從未套用成功的原因。
-- 本檔所有識別字一律加雙引號。索引名稱、資料表與欄位與 52 相同，若某資料庫曾手動修正後
-- 套用過 52，遇到 IF NOT EXISTS 會直接略過。
-- ============================================================================

-- 巡檢主檔：依主機手／檢驗人員／客戶篩選
CREATE INDEX IF NOT EXISTS "idx_patrol_main_operator"  ON "巡檢主檔" ("主機手");
CREATE INDEX IF NOT EXISTS "idx_patrol_main_inspector" ON "巡檢主檔" ("檢驗人員");
CREATE INDEX IF NOT EXISTS "idx_patrol_main_customer"  ON "巡檢主檔" ("客戶名稱");

-- 出貨檢驗數據：依檢驗人員篩選
CREATE INDEX IF NOT EXISTS "idx_shipping_inspector"    ON "出貨檢驗數據" ("檢驗人員");

-- SPC 事件：依研究版本／樣本查詢
CREATE INDEX IF NOT EXISTS "idx_spc_event_study_version" ON "SPC事件" ("研究版本ID");
CREATE INDEX IF NOT EXISTS "idx_spc_event_sample"        ON "SPC事件" ("研究樣本ID");

-- 不合格品單：依發現人員篩選
CREATE INDEX IF NOT EXISTS "idx_ncmr_inspector"         ON "不合格品單" ("發現人員");

-- 不合格品處置：依關聯重工單查詢
CREATE INDEX IF NOT EXISTS "idx_ncmr_disp_rework"       ON "不合格品處置明細" ("關聯重工單ID");

-- 重工申請單：依材質查詢
CREATE INDEX IF NOT EXISTS "idx_rework_material"        ON "重工申請單" ("材質");

-- 擠壓公差明細：依主檔 JOIN
CREATE INDEX IF NOT EXISTS "idx_extrusion_tol_detail_main" ON "擠壓公差明細檔" ("主檔ID");
