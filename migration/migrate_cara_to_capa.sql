-- 把 8 筆 CARA 資料 INSERT 到 CAPA（異常矯正單）表，保留 8D 單號為 'CARA-' 前綴以利追溯
-- 使用 NOT EXISTS 防止重複執行
-- 注意：CARA 的「結案時間」對應 CAPA 的「結案日期_舊」（兩者皆 timestamp）
BEGIN;

INSERT INTO "異常矯正單" (
    "8D單號", "狀態",
    "來源類型", "來源ID", "NCMR_ID",
    "嚴格度",
    "D2_What", "D2_Where", "D2_When", "D2_Who",
    "D2_Why", "D2_How", "D2_HowMany",
    "D2_問題描述",
    "D3_對策內容", "D3_生效日", "D3_有效性驗證", "D3_暫時對策",
    "D4_工具", "D4_5Why資料", "D4_魚骨圖資料", "D4_根本原因", "D4_真因分析",
    "D6_實施日", "D6_驗證結果", "D6_驗證通過", "D6_成效驗證",
    "D8_結案日期", "D8_結案確認",
    "負責人員", "D1_Leader",
    "建立時間", "結案日期_舊"
)
SELECT
    'CARA-' || c."CARA單號", c."狀態",
    'ncmr', c."NCMR_ID", c."NCMR_ID",
    '簡化5D',
    c."D2_What", c."D2_Where", c."D2_When", c."D2_Who",
    c."D2_Why", c."D2_How", c."D2_HowMany",
    c."D2_問題描述",
    c."D3_對策內容", c."D3_生效日", c."D3_有效性驗證", c."D3_暫時對策",
    c."D4_工具", c."D4_5Why資料", c."D4_魚骨圖資料", c."D4_根本原因", c."D4_真因分析",
    c."D6_實施日", c."D6_驗證結果", c."D6_驗證通過", c."D6_成效驗證",
    c."D8_結案日期", c."D8_結案確認",
    c."負責人員", c."D1_Leader",
    c."建立時間", c."結案時間"
FROM "矯正措施要求" c
WHERE NOT EXISTS (
    SELECT 1 FROM "異常矯正單" ca
    WHERE ca."8D單號" = 'CARA-' || c."CARA單號"
);

COMMIT;
