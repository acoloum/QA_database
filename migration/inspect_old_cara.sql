SELECT
  "識別碼",
  "CAR單號",
  "狀態",
  "NCMR_ID",
  "廠商名稱",
  "D2_問題描述",
  "D3_暫時對策",
  "D4_根本原因",
  "D6_成效驗證",
  "D8_結案確認",
  "負責人員",
  "建立時間"
FROM "異常矯正單"
WHERE "CAR單號" IS NOT NULL
ORDER BY "識別碼";
