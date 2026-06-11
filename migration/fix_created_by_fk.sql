-- 客訴紀錄.建立人員 和 附件.上傳人員 應指向「使用者」表（登入帳號），
-- 而非「品管人員」表（生產線人員）。

ALTER TABLE "客訴紀錄"
    DROP CONSTRAINT "客訴紀錄_建立人員_fkey",
    ADD CONSTRAINT "客訴紀錄_建立人員_fkey"
        FOREIGN KEY ("建立人員") REFERENCES "使用者"("識別碼") ON DELETE SET NULL;

ALTER TABLE "附件"
    DROP CONSTRAINT "附件_上傳人員_fkey",
    ADD CONSTRAINT "附件_上傳人員_fkey"
        FOREIGN KEY ("上傳人員") REFERENCES "使用者"("識別碼") ON DELETE SET NULL;
