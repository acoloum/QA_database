-- 修正 CARA 遷移資料的欄位對應
-- 問題：遷移時內容寫進了 D3_暫時對策 / D4_真因分析，
--       但 CAPA 前端讀的是 D3_對策內容 / D4_根本原因。
-- 修正：將 CARA- 前綴記錄的資料搬到正確欄位。
BEGIN;

UPDATE "異常矯正單"
SET
    "D3_對策內容"  = COALESCE("D3_對策內容",  "D3_暫時對策"),
    "D4_根本原因"  = COALESCE("D4_根本原因",  "D4_真因分析")
WHERE "8D單號" LIKE 'CARA-%'
  AND (
      ("D3_對策內容" IS NULL AND "D3_暫時對策" IS NOT NULL)
   OR ("D4_根本原因" IS NULL AND "D4_真因分析" IS NOT NULL)
  );

COMMIT;
