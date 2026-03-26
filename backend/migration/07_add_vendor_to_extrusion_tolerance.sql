-- 在擠壓公差主檔加入廠商欄位
ALTER TABLE "擠壓公差主檔" ADD COLUMN IF NOT EXISTS "廠商" VARCHAR;
