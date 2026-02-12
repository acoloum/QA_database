"""
驗證資料匯入結果
"""

import psycopg2
import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import POSTGRESQL_CONFIG

def verify_import():
    print("=" * 80)
    print("資料匯入驗證報告")
    print("=" * 80)
    
    conn = psycopg2.connect(**POSTGRESQL_CONFIG)
    cursor = conn.cursor()
    
    # 獲取所有表
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public' 
        AND table_type='BASE TABLE'
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n資料庫: qa_database")
    print(f"資料表總數: {len(tables)}")
    print("\n" + "=" * 80)
    
    total_records = 0
    
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        total_records += count
        
        status = "V" if count > 0 else " "
        print(f"[{status}] {table:<25} {count:>8,} 筆")
    
    print("=" * 80)
    print(f"總記錄數: {total_records:,} 筆")
    print("=" * 80)
    
    # 檢查關鍵資料表
    print("\n關鍵資料表檢查:")
    
    key_tables = ['出貨檢驗數據', '廠商資料', '使用者', '巡檢主檔']
    
    for table in key_tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"  OK {table}: {count} 筆")
        else:
            print(f"  WARNING {table}: 無資料")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("驗證完成")
    print("=" * 80)

if __name__ == '__main__':
    verify_import()
