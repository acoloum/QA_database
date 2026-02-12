# -*- coding: utf-8 -*-
"""
PostgreSQL 連接測試腳本 (簡化版)
"""

import psycopg2
import sys
import os

# 加入上層目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import POSTGRESQL_CONFIG

def test():
    try:
        print("\n[1/4] 連接 PostgreSQL...")
        print(f"      主機: {POSTGRESQL_CONFIG['host']}:{POSTGRESQL_CONFIG['port']}")
        print(f"      資料庫: {POSTGRESQL_CONFIG['database']}")
        print(f"      使用者: {POSTGRESQL_CONFIG['user']}")
        
        conn = psycopg2.connect(**POSTGRESQL_CONFIG)
        cursor = conn.cursor()
        
        print("      [成功] 連接成功")
        
        print("\n[2/4] 檢查 PostgreSQL 版本...")
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"      {version[:60]}...")
        
        print("\n[3/4] 檢查資料表...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        print(f"      資料表數量: {len(tables)}")
        if tables:
            for table in tables:
                print(f"        - {table[0]}")
        else:
            print("        (尚無資料表)")
        
        print("\n[4/4] 檢查編碼...")
        cursor.execute("SHOW server_encoding;")
        encoding = cursor.fetchone()[0]
        print(f"      資料庫編碼: {encoding}")
        
        cursor.close()
        conn.close()
        
        print("\n[結果] 所有測試通過!")
        return True
        
    except Exception as e:
        print(f"\n[錯誤] {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print(" PostgreSQL 連接測試")
    print("=" * 60)
    success = test()
    sys.exit(0 if success else 1)
