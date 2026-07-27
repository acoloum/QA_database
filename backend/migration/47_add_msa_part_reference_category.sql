-- 計數型研究的參考真值是類別而非數值，補上對應欄位。
-- 同一零件只能有一種參考形式：數值參考值或參考分類。
BEGIN;

ALTER TABLE "MSA零件"
    ADD COLUMN "參考分類" VARCHAR(80);

ALTER TABLE "MSA零件"
    ADD CONSTRAINT ck_msa_part_single_reference CHECK (
        "參考值" IS NULL OR "參考分類" IS NULL
    );

COMMIT;
