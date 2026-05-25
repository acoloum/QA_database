-- 將舊版 CARA 資料（存在異常矯正單）遷移到新表 矯正措施要求
-- 只遷移尚未存在於新表的單號（冪等操作）

INSERT INTO "矯正措施要求" (
    "CARA單號",
    "狀態",
    "NCMR_ID",
    "廠商",
    "D2_問題描述",
    "D3_暫時對策",
    "D4_真因分析",
    "D6_成效驗證",
    "D8_結案確認",
    "D1_Leader",
    "建立時間",
    "結案時間"
)
SELECT
    ca."CAR單號",
    ca."狀態",
    ca."NCMR_ID",
    n."廠商",
    ca."D2_問題描述",
    ca."D3_暫時對策",
    ca."D4_真因分析",
    ca."D6_成效驗證",
    ca."D8_結案確認",
    ca."負責人員",
    ca."建立時間",
    ca."結案日期_舊"
FROM "異常矯正單" ca
LEFT JOIN "不合格品單" n ON ca."NCMR_ID" = n."識別碼"
WHERE ca."CAR單號" IS NOT NULL
  AND ca."CAR單號" NOT IN (
      SELECT "CARA單號" FROM "矯正措施要求" WHERE "CARA單號" IS NOT NULL
  );
