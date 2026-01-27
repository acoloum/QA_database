import pyodbc

def update_db():
    conn_str = (
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        with open('alter_ncmr_table.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
            
        batches = sql_script.split('GO')
        for batch in batches:
            if batch.strip():
                cursor.execute(batch)
                conn.commit()
                
        print("資料庫欄位更新完成！")
        conn.close()
    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == '__main__':
    update_db()
