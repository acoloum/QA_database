-- backend/migration/35_add_patrol_spc_columns.sql
-- 巡檢 SPC 合規擴充：
--   §6.6 離群值排除（巡檢子檔量測明細）
--   §9.4 管制界限凍結新增「位置」維度（巡檢特有的前/中/後段，出貨無此維度固定為空字串）

ALTER TABLE "巡檢子檔" ADD COLUMN IF NOT EXISTS "排除統計" BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "巡檢子檔" ADD COLUMN IF NOT EXISTS "排除原因" VARCHAR(200);

ALTER TABLE "SPC管制界限" ADD COLUMN IF NOT EXISTS "位置" VARCHAR(20) NOT NULL DEFAULT '';
ALTER TABLE "SPC管制界限" DROP CONSTRAINT IF EXISTS uq_spc_limits;
ALTER TABLE "SPC管制界限" ADD CONSTRAINT uq_spc_limits UNIQUE ("資料來源","廠商","材質","規格","量測項目","位置");
