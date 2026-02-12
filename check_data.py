import sys
import psycopg2

sys.stdout.reconfigure(encoding='utf-8')

conn = psycopg2.connect('host=localhost port=5432 dbname=qa_database user=postgres password=swordfish1')

cursor = conn.cursor()

# Get column names for 出貨檢驗數據
cursor.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = '出貨檢驗數據'
    ORDER BY ordinal_position
""")
print("=== 出貨檢驗數據欄位 ===")
for row in cursor.fetchall():
    print(row[0])

# Check inspection records
cursor.execute('SELECT * FROM "出貨檢驗數據" WHERE "識別碼" IN (5211, 5212)')
print("\n=== 檢驗資料 ID 5211, 5212 ===")
for row in cursor.fetchall():
    print(row)

conn.close()
