-- §9.4：管制界限經確認後凍結；預期變更或無法歸因時重算並留紀錄
CREATE TABLE IF NOT EXISTS "SPC管制界限" (
    "識別碼"   SERIAL PRIMARY KEY,
    "資料來源" VARCHAR(20)  NOT NULL DEFAULT 'shipping',
    "廠商"     VARCHAR(100) NOT NULL DEFAULT '',
    "材質"     VARCHAR(100) NOT NULL DEFAULT '',
    "規格"     VARCHAR(100) NOT NULL DEFAULT '',
    "量測項目" VARCHAR(30)  NOT NULL,
    "X中心線"  NUMERIC(14,6) NOT NULL,
    "X上限"    NUMERIC(14,6) NOT NULL,
    "X下限"    NUMERIC(14,6) NOT NULL,
    "R中心線"  NUMERIC(14,6) NOT NULL,
    "R上限"    NUMERIC(14,6) NOT NULL,
    "R下限"    NUMERIC(14,6) NOT NULL DEFAULT 0,
    "子組大小" INTEGER NOT NULL DEFAULT 5,
    "備註"     VARCHAR(200),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "更新時間" TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_spc_limits UNIQUE ("資料來源","廠商","材質","規格","量測項目")
);
