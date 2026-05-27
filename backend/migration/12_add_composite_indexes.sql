-- Migration 12: 新增 NCMR / CAPA / 重工 / 客訴複合索引
-- 提升依狀態、日期、來源篩選的查詢效能

-- NCMR：狀態 + 發現日期
CREATE INDEX IF NOT EXISTS idx_ncmr_status_date
    ON 不合格品單 (狀態, 發現日期);

-- CorrectiveAction（異常矯正單）：來源類型 + 來源ID
CREATE INDEX IF NOT EXISTS idx_capa_source
    ON "異常矯正單" ("來源類型", "來源ID");

-- CorrectiveAction（異常矯正單）：狀態 + D0 客戶要求結案日
CREATE INDEX IF NOT EXISTS idx_capa_status_deadline
    ON "異常矯正單" ("狀態", "D0_客戶要求結案日");

-- ReworkRequest（重工申請單）：狀態 + 申請日期
CREATE INDEX IF NOT EXISTS idx_rework_status_created
    ON 重工申請單 (狀態, 申請日期);

-- CustomerComplaint（客訴紀錄）：是否重複客訴 + 客訴日期
CREATE INDEX IF NOT EXISTS idx_complaint_repeat_date
    ON 客訴紀錄 (是否重複客訴, 客訴日期);
