-- 45_harden_msa_equipment_constraints.sql
-- 強化 MSA 量測設備量程順序；若既有資料違規，VALIDATE 會中止整筆交易。

BEGIN;

ALTER TABLE "量測設備"
    ADD CONSTRAINT ck_equipment_range_order
    CHECK (
        "量程下限" IS NULL
        OR "量程上限" IS NULL
        OR "量程下限" <= "量程上限"
    )
    NOT VALID;

ALTER TABLE "量測設備"
    VALIDATE CONSTRAINT ck_equipment_range_order;

COMMIT;
