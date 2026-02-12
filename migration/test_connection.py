"""
PostgreSQL 連接測試腳本
用途：測試 PostgreSQL 連接是否成功並顯示資料庫資訊
"""

import psycopg2
from psycopg2 import sql
import sys

# 從配置檔案導入設定
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import POSTGRESQL_CONFIG
    print("成功載入配置檔案")
except ImportError:
    print("無法載入 config.py，請確保檔案存在")
    sys.exit(1)

def test_connection():
    """測試 PostgreSQL 連接"""
    try:
        print("\n正在連接到 PostgreSQL...")
        print(f"主機: {POSTGRESQL_CONFIG['host']}:{POSTGRESQL_CONFIG['port']}")
        print(f"資料庫: {POSTGRESQL_CONFIG['database']}")
        print(f"使用者: {POSTGRESQL_CONFIG['user']}")
        
        # 建立連接
        conn = psycopg2.connect(**POSTGRESQL_CONFIG)
        cursor = conn.cursor()
        
        print("\n✓ 連接成功！\n")
        
        # 測試 1：檢查 PostgreSQL 版本
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"PostgreSQL 版本:")
        print(f"  {version[:80]}...")
        
        # 測試 2：列出所有表格
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print(f"\n資料庫 '{POSTGRESQL_CONFIG['database']}' 中的表格數量: {len(tables)}")
        if tables:
            print("表格列表:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("  （尚無表格，請先執行 Schema 建立腳本）")
        
        # 測試 3：檢查編碼
        cursor.execute("SHOW server_encoding;")
        encoding = cursor.fetchone()[0]
        print(f"\n資料庫編碼: {encoding}")
        
        # 關閉連接
        cursor.close()
        conn.close()
        
        print("\n✓ 所有測試通過！")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n✗ 連接失敗：{e}")
        print("\n請檢查：")
        print("  1. PostgreSQL 服務是否正在運行")
        print("  2. config.py 中的連接參數是否正確")
        print("  3. 資料庫 'qa_database' 是否已建立")
        print("  4. 使用者密碼是否正確")
        return False
        
    except Exception as e:
        print(f"\n✗ 發生錯誤：{e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("PostgreSQL 連接測試")
    print("=" * 60)
    
    success = test_connection()
    
    if not success:
        print("\n建議：")
        print("  1. 使用 pgAdmin 或 SQL Shell (psql) 手動測試連接")
        print("  2. 確認 PostgreSQL 服務已啟動")
        print("  3. 檢查防火牆設定")
    
    sys.exit(0 if success else 1)
