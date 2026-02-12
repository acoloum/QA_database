-- ================================================
-- 品保資料庫完整 Schema - PostgreSQL 版本
-- 從 SQL Server 遷移轉換
-- ================================================

-- ================================================
-- 1. 基礎資料表
-- ================================================

-- 品管人員表
CREATE TABLE IF NOT EXISTS "品管人員" (
    "識別碼" SERIAL PRIMARY KEY,
    "姓名" VARCHAR(50) NOT NULL,
    "部門" VARCHAR(50),
    "職位" VARCHAR(50),
    "電話" VARCHAR(20),
    "電子郵件" VARCHAR(100),
    "是否啟用" BOOLEAN DEFAULT true,
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE "品管人員" IS '品管人員基礎資料';

-- 廠商資料表
CREATE TABLE IF NOT EXISTS "廠商資料" (
    "識別碼" SERIAL PRIMARY KEY,
    "廠商名稱" VARCHAR(100) NOT NULL UNIQUE,
    "廠商代碼" VARCHAR(50),
    "聯絡人" VARCHAR(50),
    "電話" VARCHAR(20),
    "傳真" VARCHAR(20),
    "地址" VARCHAR(200),
    "電子郵件" VARCHAR(100),
    "統一編號" VARCHAR(20),
    "備註" TEXT,
    "是否啟用" BOOLEAN DEFAULT true,
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE "廠商資料" IS '廠商基礎資料';

-- 擠壓機台表
CREATE TABLE IF NOT EXISTS "擠壓機台" (
    "識別碼" SERIAL PRIMARY KEY,
    "擠壓機編號" VARCHAR(50) NOT NULL UNIQUE,
    "機台名稱" VARCHAR(100),
    "製造商" VARCHAR(100),
    "購買日期" DATE,
    "規格" VARCHAR(200),
    "狀態" VARCHAR(20) DEFAULT '正常',
    "備註" TEXT,
    "是否啟用" BOOLEAN DEFAULT true
);

COMMENT ON TABLE "擠壓機台" IS '擠壓機台基礎資料';

-- 擠壓人員表
CREATE TABLE IF NOT EXISTS "擠壓人員" (
    "識別碼" SERIAL PRIMARY KEY,
    "員工姓名" VARCHAR(50) NOT NULL,
    "員工編號" VARCHAR(50),
    "部門" VARCHAR(50),
    "職位" VARCHAR(50),
    "技能等級" VARCHAR(20),
    "是否啟用" BOOLEAN DEFAULT true,
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE "擠壓人員" IS '擠壓作業人員資料';

-- 使用者表
CREATE TABLE IF NOT EXISTS "使用者" (
    "識別碼" SERIAL PRIMARY KEY,
    "使用者名稱" VARCHAR(50) NOT NULL UNIQUE,
    "密碼" VARCHAR(255) NOT NULL,
    "姓名" VARCHAR(50),
    "部門" VARCHAR(50),
    "角色" VARCHAR(20) DEFAULT '一般使用者',
    "是否啟用" BOOLEAN DEFAULT true,
    "最後登入時間" TIMESTAMP,
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE "使用者" IS '系統使用者';

-- ================================================
-- 2. 出貨檢驗數據表
-- ================================================
CREATE TABLE IF NOT EXISTS "出貨檢驗數據" (
    "識別碼" SERIAL PRIMARY KEY,
    "檢驗日期" DATE NOT NULL,
    "檢驗人員" INTEGER,
    "廠商名稱" INTEGER,
    "檢驗規格" VARCHAR(100),
    "材質" VARCHAR(50),
    "訂單號碼" VARCHAR(50),
    
    -- 外徑測量 (5組，每組 min/max)
    "外徑1-min" NUMERIC(10,4),
    "外徑1-max" NUMERIC(10,4),
    "外徑2-min" NUMERIC(10,4),
    "外徑2-max" NUMERIC(10,4),
    "外徑3-min" NUMERIC(10,4),
    "外徑3-max" NUMERIC(10,4),
    "外徑4-min" NUMERIC(10,4),
    "外徑4-max" NUMERIC(10,4),
    "外徑5-min" NUMERIC(10,4),
    "外徑5-max" NUMERIC(10,4),
    
    -- 內徑測量 (5組)
    "內徑1-min" NUMERIC(10,4),
    "內徑1-max" NUMERIC(10,4),
    "內徑2-min" NUMERIC(10,4),
    "內徑2-max" NUMERIC(10,4),
    "內徑3-min" NUMERIC(10,4),
    "內徑3-max" NUMERIC(10,4),
    "內徑4-min" NUMERIC(10,4),
    "內徑4-max" NUMERIC(10,4),
    "內徑5-min" NUMERIC(10,4),
    "內徑5-max" NUMERIC(10,4),
    
    -- 厚度測量 (5組)
    "厚度1-min" NUMERIC(10,4),
    "厚度1-max" NUMERIC(10,4),
    "厚度2-min" NUMERIC(10,4),
    "厚度2-max" NUMERIC(10,4),
    "厚度3-min" NUMERIC(10,4),
    "厚度3-max" NUMERIC(10,4),
    "厚度4-min" NUMERIC(10,4),
    "厚度4-max" NUMERIC(10,4),
    "厚度5-min" NUMERIC(10,4),
    "厚度5-max" NUMERIC(10,4),
    
    -- 其他測量項目 (5筆)
    "同心度1" NUMERIC(10,4),
    "同心度2" NUMERIC(10,4),
    "同心度3" NUMERIC(10,4),
    "同心度4" NUMERIC(10,4),
    "同心度5" NUMERIC(10,4),
    
    "長度1" NUMERIC(10,4),
    "長度2" NUMERIC(10,4),
    "長度3" NUMERIC(10,4),
    "長度4" NUMERIC(10,4),
    "長度5" NUMERIC(10,4),
    
    "硬度1" NUMERIC(10,4),
    "硬度2" NUMERIC(10,4),
    "硬度3" NUMERIC(10,4),
    "硬度4" NUMERIC(10,4),
    "硬度5" NUMERIC(10,4),
    
    "真直度1" NUMERIC(10,4),
    "真直度2" NUMERIC(10,4),
    "真直度3" NUMERIC(10,4),
    "真直度4" NUMERIC(10,4),
    "真直度5" NUMERIC(10,4),
    
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY ("檢驗人員") REFERENCES "品管人員"("識別碼"),
    FOREIGN KEY ("廠商名稱") REFERENCES "廠商資料"("識別碼")
);

COMMENT ON TABLE "出貨檢驗數據" IS '出貨檢驗測量數據';

-- ================================================
-- 3. 巡檢數據表
-- ================================================
CREATE TABLE IF NOT EXISTS "巡檢主檔" (
    "識別碼" SERIAL PRIMARY KEY,
    "檢驗日期" DATE NOT NULL,
    "機台" INTEGER,
    "主機手" INTEGER,
    "檢驗人員" INTEGER,
    "材質" VARCHAR(50),
    "擠壓規格" VARCHAR(100),
    "客戶名稱" INTEGER,
    "原料批號" VARCHAR(50),
    "備註" TEXT,
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY ("機台") REFERENCES "擠壓機台"("識別碼"),
    FOREIGN KEY ("主機手") REFERENCES "擠壓人員"("識別碼"),
    FOREIGN KEY ("檢驗人員") REFERENCES "品管人員"("識別碼"),
    FOREIGN KEY ("客戶名稱") REFERENCES "廠商資料"("識別碼")
);

COMMENT ON TABLE "巡檢主檔" IS '巡檢主資料';

CREATE TABLE IF NOT EXISTS "巡檢子檔" (
    "識別碼" SERIAL PRIMARY KEY,
    "主檔ID" INTEGER NOT NULL,
    "組別" VARCHAR(20) NOT NULL,
    "測量項目" VARCHAR(50) NOT NULL,
    "測量位置" VARCHAR(50),
    "最小值" NUMERIC(10,4),
    "最大值" NUMERIC(10,4),
    
    FOREIGN KEY ("主檔ID") REFERENCES "巡檢主檔"("識別碼") ON DELETE CASCADE
);

COMMENT ON TABLE "巡檢子檔" IS '巡檢測量明細';

-- ================================================
-- 4. NCMR 不合格品單
-- ================================================
CREATE TABLE IF NOT EXISTS "不合格品單" (
    "識別碼" SERIAL PRIMARY KEY,
    "NCMR單號" VARCHAR(50) UNIQUE,
    "發現日期" DATE,
    "發現人員" INTEGER,
    "廠商" VARCHAR(100),
    "產品資訊" VARCHAR(200),
    "材質" VARCHAR(50),
    "批號" VARCHAR(50),
    "不良數量" NUMERIC(10,2),
    "不良描述" TEXT,
    "不良原因大類" VARCHAR(10),
    "不良原因細項" VARCHAR(100),
    "判定結果" VARCHAR(20),
    "處理措施" TEXT,
    "狀態" VARCHAR(20) DEFAULT '待處理',
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "更新時間" TIMESTAMP,
    
    FOREIGN KEY ("發現人員") REFERENCES "品管人員"("識別碼")
);

COMMENT ON TABLE "不合格品單" IS 'NCMR 不合格品管理單';

-- ================================================
-- 5. 異常矯正單 (8D/CAR)
-- ================================================
CREATE TABLE IF NOT EXISTS "異常矯正單" (
    "識別碼" SERIAL PRIMARY KEY,
    "NCMR_ID" INTEGER,
    "8D單號" VARCHAR(50),
    "CAR單號" VARCHAR(50),
    "負責人員" INTEGER,
    "問題描述" TEXT,
    "根本原因" TEXT,
    "矯正措施" TEXT,
    "預防措施" TEXT,
    "狀態" VARCHAR(20) DEFAULT '進行中',
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "完成時間" TIMESTAMP,
    
    FOREIGN KEY ("NCMR_ID") REFERENCES "不合格品單"("識別碼"),
    FOREIGN KEY ("負責人員") REFERENCES "品管人員"("識別碼")
);

COMMENT ON TABLE "異常矯正單" IS '8D/CAR 異常矯正單';

-- ================================================
-- 6. 重工管理系統
-- ================================================
CREATE TABLE IF NOT EXISTS "重工申請單" (
    "識別碼" SERIAL PRIMARY KEY,
    "NCMR_ID" INTEGER,
    "申請單號" VARCHAR(50) UNIQUE,
    "申請人員" INTEGER,
    "申請日期" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "部門" VARCHAR(50),
    "緊急程度" VARCHAR(20) DEFAULT '普通',
    "產品資訊" VARCHAR(200),
    "批號" VARCHAR(50),
    "重工數量" NUMERIC(10,2),
    "申請原因" TEXT,
    "預計完成日期" DATE,
    "審核狀態" VARCHAR(20),
    "審核人員" INTEGER,
    "審核時間" TIMESTAMP,
    "審核意見" TEXT,
    "狀態" VARCHAR(20) DEFAULT '申請中',
    "實際完成日期" TIMESTAMP,
    "建立時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY ("NCMR_ID") REFERENCES "不合格品單"("識別碼"),
    FOREIGN KEY ("申請人員") REFERENCES "品管人員"("識別碼"),
    FOREIGN KEY ("審核人員") REFERENCES "品管人員"("識別碼")
);

COMMENT ON TABLE "重工申請單" IS '重工申請管理';

CREATE TABLE IF NOT EXISTS "重工執行記錄" (
    "識別碼" SERIAL PRIMARY KEY,
    "重工單號" INTEGER,
    "執行部門" VARCHAR(50),
    "負責人員" INTEGER,
    "協同人員" VARCHAR(200),
    "開始時間" TIMESTAMP,
    "預計完成時間" TIMESTAMP,
    "實際完成時間" TIMESTAMP,
    "使用設備" VARCHAR(200),
    "重工方式" TEXT,
    "SOP編號" VARCHAR(50),
    "耗材記錄" TEXT,
    "完成數量" NUMERIC(10,2),
    "不良數量" NUMERIC(10,2),
    "良率" NUMERIC(5,2),
    "執行狀況" TEXT,
    "異常狀況" TEXT,
    "執行人員" INTEGER,
    "記錄時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY ("重工單號") REFERENCES "重工申請單"("識別碼") ON DELETE CASCADE,
    FOREIGN KEY ("負責人員") REFERENCES "品管人員"("識別碼"),
    FOREIGN KEY ("執行人員") REFERENCES "品管人員"("識別碼")
);

COMMENT ON TABLE "重工執行記錄" IS '重工執行過程記錄';

CREATE TABLE IF NOT EXISTS "重工品檢記錄" (
    "識別碼" SERIAL PRIMARY KEY,
    "重工單號" INTEGER,
    "檢驗日期" DATE,
    "檢驗人員" INTEGER,
    "檢驗項目" VARCHAR(100),
    "檢驗標準" VARCHAR(200),
    "檢驗結果" VARCHAR(20),
    "不良數量" NUMERIC(10,2),
    "檢驗備註" TEXT,
    "記錄時間" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY ("重工單號") REFERENCES "重工申請單"("識別碼") ON DELETE CASCADE,
    FOREIGN KEY ("檢驗人員") REFERENCES "品管人員"("識別碼")
);

COMMENT ON TABLE "重工品檢記錄" IS '重工品質檢驗記錄';

CREATE TABLE IF NOT EXISTS "重工成本分析" (
    "識別碼" SERIAL PRIMARY KEY,
    "重工單號" INTEGER,
    "成本類型" VARCHAR(50),
    "成本項目" VARCHAR(100),
    "單位成本" NUMERIC(12,2),
    "數量" NUMERIC(10,2),
    "總成本" NUMERIC(12,2),
    "成本幣別" VARCHAR(10) DEFAULT 'TWD',
    "記錄人員" INTEGER,
    "記錄日期" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "備註" TEXT,
    
    FOREIGN KEY ("重工單號") REFERENCES "重工申請單"("識別碼") ON DELETE CASCADE,
    FOREIGN KEY ("記錄人員") REFERENCES "品管人員"("識別碼")
);

COMMENT ON TABLE "重工成本分析" IS '重工成本分析記錄';

-- ================================================
-- 7. 創建索引
-- ================================================

-- 出貨檢驗索引
CREATE INDEX IF NOT EXISTS "IX_出貨檢驗_檢驗日期" ON "出貨檢驗數據"("檢驗日期");
CREATE INDEX IF NOT EXISTS "IX_出貨檢驗_材質" ON "出貨檢驗數據"("材質");
CREATE INDEX IF NOT EXISTS "IX_出貨檢驗_廠商" ON "出貨檢驗數據"("廠商名稱");

-- 巡檢索引
CREATE INDEX IF NOT EXISTS "IX_巡檢主檔_檢驗日期" ON "巡檢主檔"("檢驗日期");
CREATE INDEX IF NOT EXISTS "IX_巡檢主檔_機台" ON "巡檢主檔"("機台");
CREATE INDEX IF NOT EXISTS "IX_巡檢子檔_主檔ID" ON "巡檢子檔"("主檔ID");

-- NCMR 索引
CREATE INDEX IF NOT EXISTS "IX_不合格品單_NCMR單號" ON "不合格品單"("NCMR單號");
CREATE INDEX IF NOT EXISTS "IX_不合格品單_發現日期" ON "不合格品單"("發現日期");
CREATE INDEX IF NOT EXISTS "IX_不合格品單_狀態" ON "不合格品單"("狀態");

-- 重工索引
CREATE INDEX IF NOT EXISTS "IX_重工申請單_申請單號" ON "重工申請單"("申請單號");
CREATE INDEX IF NOT EXISTS "IX_重工申請單_NCMR_ID" ON "重工申請單"("NCMR_ID");
CREATE INDEX IF NOT EXISTS "IX_重工申請單_狀態" ON "重工申請單"("狀態");

-- ================================================
-- 完成訊息
-- ================================================
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE '品保資料庫 Schema 建立完成！';
    RAISE NOTICE '已建立 15 個資料表和相關索引';
    RAISE NOTICE '============================================';
END $$;
