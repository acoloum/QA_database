SELECT
  ca."識別碼",
  ca."CAR單號",
  ca."狀態",
  ca."NCMR_ID",
  n."廠商" AS ncmr_vendor,
  ca."D2_問題描述",
  ca."D3_暫時對策",
  ca."D4_真因分析",
  ca."D6_成效驗證",
  ca."D8_結案確認",
  ca."負責人員",
  ca."建立時間"
FROM "異常矯正單" ca
LEFT JOIN "不合格品單" n ON ca."NCMR_ID" = n."識別碼"
WHERE ca."CAR單號" IS NOT NULL
ORDER BY ca."識別碼";
