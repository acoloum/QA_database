-- 機械性質檢驗：開放「韋伯氏硬度」與「真直度」兩個量測項目。
--
-- 背景：這兩項在廠商公差明細檔中已是獨立的項目名稱（韋伯氏硬度 HW、真直度 mm），
-- 但機械性質量測明細的 CHECK 約束只允許原本五個項目，欄位開出來也存不進去。
--
-- 真直度的公差**只有尺寸上限、從無下限**（0.07 / 0.15 / 0.3 / 1.0 mm），
-- 與模組原本的「單邊下限」判定方向相反，故量測明細另加「上限」欄位；
-- 既有五個項目的上限一律留空，判定行為完全不變。
--
-- 本 migration 不修剪既有資料；發現衝突資料會以明確錯誤中止，
-- 由資料負責人完成追溯與修正後再重跑。
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM "機械性質量測明細"
        WHERE "量測項目" NOT IN (
            'EC值', '硬度', '韋伯氏硬度', '真直度', '抗拉強度', '降伏強度', '伸長率'
        )
    ) THEN
        RAISE EXCEPTION 'migration 56 中止：機械性質量測明細存在非法量測項目，請先人工複核';
    END IF;
END $$;

ALTER TABLE "機械性質量測明細"
    ADD COLUMN IF NOT EXISTS "上限" NUMERIC(12, 4);

ALTER TABLE "機械性質量測明細"
    DROP CONSTRAINT IF EXISTS ck_mech_measurement_item;

ALTER TABLE "機械性質量測明細"
    ADD CONSTRAINT ck_mech_measurement_item
    CHECK ("量測項目" IN (
        'EC值', '硬度', '韋伯氏硬度', '真直度', '抗拉強度', '降伏強度', '伸長率'
    ));

-- 免測項目的 CHECK 刻意不動：韋伯氏硬度與真直度為「有公差才顯示」的選填項目，
-- 不列入完成判定，也就沒有標記免測的必要。既有約 3000 筆安泰紀錄都沒有這兩項
-- 數值，一旦納入必測會立刻全數變成 INCOMPLETE。

COMMIT;
