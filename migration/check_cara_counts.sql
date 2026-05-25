SELECT
  (SELECT COUNT(*) FROM "矯正措施要求") AS cara_record_count,
  (SELECT COUNT(*) FROM "異常矯正單" WHERE "CAR單號" IS NOT NULL) AS old_cara_count;
