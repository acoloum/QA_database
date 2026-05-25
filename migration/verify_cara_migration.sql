SELECT "識別碼", "CARA單號", "狀態", "廠商", "NCMR_ID",
       LEFT("D2_問題描述", 30) AS d2_preview
FROM "矯正措施要求"
ORDER BY "識別碼";
