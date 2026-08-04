-- ============================================================================
-- 55_add_fk_indexes.sql
-- 補上「子表反查主表」與「清單篩選」用的外鍵索引
--
-- PostgreSQL 不會自動替 FOREIGN KEY 欄位建索引，以下欄位都是 eager load
-- （selectinload / subqueryload 產生的 WHERE fk IN (...)）、串聯刪除或清單篩選
-- 的實際述詞，缺索引時每次都退化成全表掃描。
--
-- 已被既有唯一約束「前導欄」涵蓋者不再重複建立（例如 SPC研究版本.研究ID 已由
-- uq_spc_study_version 涵蓋、SPC異常處置.事件ID 本身即 UNIQUE），避免重複索引
-- 徒增寫入成本。純顯示用的稽核欄位（建立者ID／核准者ID／送審者ID／更新者ID）
-- 從未作為查詢述詞，亦不建索引。
--
-- 對應 backend/models.py 各模型的 __table_args__，索引名稱與該處一致
-- （SQLite 測試庫由 create_all() 依同名建立）。
-- PostgreSQL 16；CREATE INDEX IF NOT EXISTS 可安全重複執行。
-- ============================================================================

-- 矯正措施：NCMR 清單以 subqueryload 反查（WHERE NCMR_ID IN (...)）
CREATE INDEX IF NOT EXISTS idx_capa_ncmr                         ON "異常矯正單" ("NCMR_ID");

-- 重工子表：清單／明細 selectinload 與串聯刪除皆以主單反查
CREATE INDEX IF NOT EXISTS idx_rework_exec_request               ON "重工執行記錄" ("重工單號");
CREATE INDEX IF NOT EXISTS idx_rework_insp_request               ON "重工品檢記錄" ("重工單號");
CREATE INDEX IF NOT EXISTS idx_rework_cost_request               ON "重工成本分析" ("重工單號");

-- 熱處理量測點：報表與明細載入以測試單反查
CREATE INDEX IF NOT EXISTS idx_tus_point_test                    ON "TUS量測點明細" ("測試ID");
CREATE INDEX IF NOT EXISTS idx_sat_point_test                    ON "SAT量測點明細" ("測試ID");

-- 橫展任務：任務清單與「我的任務」依負責人篩選
CREATE INDEX IF NOT EXISTS idx_task_assignee                     ON "橫展任務" ("負責人");

-- MSA：以下欄位皆非既有唯一約束的前導欄
CREATE INDEX IF NOT EXISTS idx_msa_study_equipment_equipment     ON "MSA研究設備" ("設備ID");
CREATE INDEX IF NOT EXISTS idx_msa_observation_import_batch      ON "MSA觀測" ("匯入批次ID");
CREATE INDEX IF NOT EXISTS idx_msa_result_version_plan_version   ON "MSA結果版本" ("計畫版本ID");
CREATE INDEX IF NOT EXISTS idx_msa_decision_result_version       ON "MSA工作流決策" ("結果版本ID");
