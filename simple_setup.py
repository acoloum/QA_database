import pyodbc

def create_tables():
    conn = None
    try:
        conn = pyodbc.connect(
            r"Driver={ODBC Driver 18 for SQL Server};"
            r"Server=localhost\SQLEXPRESS;"
            r"Database=品保資料庫;"
            r"Trusted_Connection=yes;"
            r"Encrypt=no;"
            r"TrustServerCertificate=yes;"
            r"Connection Timeout=30;"
        )
        cursor = conn.cursor()
        
        # 檢查資料表是否存在
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '重工申請單'")
        result = cursor.fetchone()
        
        if result[0] > 0:
            print("資料表已存在")
        else:
            # 建立重工申請單表
            cursor.execute("""
                CREATE TABLE dbo.重工申請單 (
                    識別碼 INT IDENTITY(1,1) PRIMARY KEY,
                    NCMR_ID INT,
                    申請單號 NVARCHAR(20) UNIQUE,
                    申請日期 DATETIME DEFAULT GETDATE(),
                    申請人員 INT,
                    部門 NVARCHAR(50),
                    緊急程度 NVARCHAR(20) DEFAULT '普通',
                    產品資訊 NVARCHAR(255),
                    批號 NVARCHAR(100),
                    重工數量 FLOAT,
                    申請原因 NVARCHAR(MAX),
                    預計完成日期 DATE,
                    審核狀態 NVARCHAR(20) DEFAULT '待審核',
                    審核人員 INT,
                    審核時間 DATETIME,
                    審核意見 NVARCHAR(MAX),
                    狀態 NVARCHAR(20) DEFAULT '申請中'
                )
            """)
            conn.commit()
            print("重工申請單表建立成功")
            
            # 建立其他必要的表
            tables_sql = [
                """
                CREATE TABLE dbo.重工執行記錄 (
                    識別碼 INT IDENTITY(1,1) PRIMARY KEY,
                    重工單號 INT,
                    執行部門 NVARCHAR(50),
                    負責人員 INT,
                    開始時間 DATETIME,
                    預計完成時間 DATETIME,
                    實際完成時間 DATETIME,
                    使用設備 NVARCHAR(255),
                    重工方式 NVARCHAR(MAX),
                    SOP編號 NVARCHAR(50),
                    耗材記錄 NVARCHAR(MAX),
                    執行狀況 NVARCHAR(MAX),
                    完成數量 FLOAT,
                    不良數量 FLOAT,
                    良率 FLOAT,
                    執行人員 INT
                )
                """,
                """
                CREATE TABLE dbo.重工品檢記錄 (
                    識別碼 INT IDENTITY(1,1) PRIMARY KEY,
                    重工單號 INT,
                    執行記錄ID INT,
                    檢驗日期 DATETIME DEFAULT GETDATE(),
                    檢驗人員 INT,
                    檢驗階段 NVARCHAR(20),
                    檢驗項目 NVARCHAR(255),
                    檢驗標準 NVARCHAR(MAX),
                    檢驗方法 NVARCHAR(MAX),
                    檢驗數據 NVARCHAR(MAX),
                    判定結果 NVARCHAR(20),
                    不良現象 NVARCHAR(MAX),
                    改善建議 NVARCHAR(MAX),
                    通過數量 FLOAT,
                    不合格數量 FLOAT,
                    重檢數量 FLOAT,
                    檢驗結論 NVARCHAR(MAX)
                )
                """,
                """
                CREATE TABLE dbo.重工成本分析 (
                    識別碼 INT IDENTITY(1,1) PRIMARY KEY,
                    重工單號 INT,
                    成本類型 NVARCHAR(50),
                    成本項目 NVARCHAR(255),
                    單位成本 FLOAT,
                    數量 FLOAT,
                    總成本 FLOAT,
                    成本幣別 NVARCHAR(10) DEFAULT 'TWD',
                    記錄日期 DATETIME DEFAULT GETDATE(),
                    記錄人員 INT,
                    備註 NVARCHAR(MAX)
                )
                """,
                """
                CREATE TABLE dbo.重工效益評估 (
                    識別碼 INT IDENTITY(1,1) PRIMARY KEY,
                    重工單號 INT,
                    評估日期 DATETIME DEFAULT GETDATE(),
                    評估人員 INT,
                    重工前良率 FLOAT,
                    重工後良率 FLOAT,
                    良率提升 FLOAT,
                    時間效益 FLOAT,
                    成本效益 FLOAT,
                    客戶滿意度 FLOAT,
                    品質改善度 FLOAT,
                    整體效益 NVARCHAR(MAX),
                    改善建議 NVARCHAR(MAX),
                    預防措施 NVARCHAR(MAX)
                )
                """
            ]
            
            table_names = ["重工執行記錄", "重工品檢記錄", "重工成本分析", "重工效益評估"]
            
            for i, sql in enumerate(tables_sql):
                try:
                    cursor.execute(sql)
                    conn.commit()
                    print(f"{table_names[i]}表建立成功")
                except Exception as e:
                    print(f"{table_names[i]}表建立失敗: {e}")
                    conn.rollback()
        
        print("資料表建立完成!")
        
    except Exception as e:
        print(f"錯誤: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_tables()