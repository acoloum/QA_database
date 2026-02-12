"""
PostgreSQL Schema 自動部署腳本
用途：自動執行所有 SQL 腳本建立資料庫結構
"""

import psycopg2
from psycopg2 import sql
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 加入上層目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 從配置檔案導入設定
try:
    from config import POSTGRESQL_CONFIG
    print("[OK] 成功載入配置檔案")
except ImportError:
    print("[ERROR] 無法載入 config.py，請確保檔案存在")
    sys.exit(1)


def execute_sql_file(cursor, file_path, description=""):
    """執行 SQL 檔案"""
    try:
        print(f"\n執行: {file_path.name}")
        if description:
            print(f"  說明: {description}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 移除可能的 BOM 標記
        if sql_content.startswith('\ufeff'):
            sql_content = sql_content[1:]
        
        # 執行 SQL
        cursor.execute(sql_content)
        print(f"  [OK] 執行成功")
        return True
        
    except psycopg2.Error as e:
        print(f"  [ERROR] SQL 執行失敗: {e}")
        return False
    except FileNotFoundError:
        print(f"  [ERROR] 檔案不存在: {file_path}")
        return False
    except Exception as e:
        print(f"  [ERROR] 未知錯誤: {e}")
        return False


def verify_tables(cursor):
    """驗證資料表是否建立成功"""
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print("\n" + "=" * 60)
        print(f"資料庫中的表格數量: {len(tables)}")
        print("=" * 60)
        
        if tables:
            print("\n已建立的資料表:")
            for idx, table in enumerate(tables, 1):
                print(f"  {idx}. {table[0]}")
        else:
            print("警告: 沒有找到任何資料表！")
        
        return len(tables) > 0
        
    except Exception as e:
        print(f"[ERROR] 驗證失敗: {e}")
        return False


def verify_indexes(cursor):
    """驗證索引是否建立成功"""
    try:
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname;
        """)
        indexes = cursor.fetchall()
        
        print(f"\n索引數量: {len(indexes)}")
        if indexes:
            print("已建立的索引:")
            current_table = None
            for schema, table, index in indexes:
                if table != current_table:
                    print(f"\n  [{table}]")
                    current_table = table
                print(f"    - {index}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 索引驗證失敗: {e}")
        return False


def verify_foreign_keys(cursor):
    """驗證外鍵約束"""
    try:
        cursor.execute("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            ORDER BY tc.table_name;
        """)
        fks = cursor.fetchall()
        
        print(f"\n外鍵約束數量: {len(fks)}")
        if fks:
            print("已建立的外鍵:")
            for table, col, ref_table, ref_col in fks:
                print(f"  {table}.{col} -> {ref_table}.{ref_col}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 外鍵驗證失敗: {e}")
        return False


def main():
    print("=" * 60)
    print("PostgreSQL Schema 自動部署")
    print("=" * 60)
    
    # 連接資料庫
    try:
        print("\n步驟 1: 連接到 PostgreSQL")
        print(f"  主機: {POSTGRESQL_CONFIG['host']}:{POSTGRESQL_CONFIG['port']}")
        print(f"  資料庫: {POSTGRESQL_CONFIG['database']}")
        
        conn = psycopg2.connect(**POSTGRESQL_CONFIG)
        conn.autocommit = False  # 使用事務
        cursor = conn.cursor()
        
        print("  [OK] 連接成功")
        
    except psycopg2.OperationalError as e:
        print(f"  [ERROR] 連接失敗: {e}")
        print("\n請確認:")
        print("  1. PostgreSQL 服務正在運行")
        print("  2. config.py 中的連接參數正確")
        print("  3. 資料庫 'qa_database' 已建立")
        print("  4. 密碼設定正確")
        sys.exit(1)
    
    # SQL 檔案列表
    migration_dir = Path(__file__).parent
    sql_files = [
        (migration_dir / '04_create_all_tables.sql', '建立所有基礎資料表'),
        (migration_dir / '02_create_tolerance_tables_pg.sql', '建立廠商公差表'),
        (migration_dir / '03_add_defect_reason_columns_pg.sql', '新增不良原因欄位'),
    ]
    
    # 執行 SQL 檔案
    print("\n步驟 2: 執行 SQL 腳本")
    success_count = 0
    
    try:
        for sql_file, description in sql_files:
            if sql_file.exists():
                if execute_sql_file(cursor, sql_file, description):
                    success_count += 1
                    conn.commit()  # 每個檔案成功後提交
                else:
                    print(f"  [WARNING] 跳過後續腳本")
                    conn.rollback()
                    # 繼續執行其他腳本
            else:
                print(f"\n[WARNING] 檔案不存在: {sql_file}")
        
        print(f"\n成功執行 {success_count}/{len(sql_files)} 個腳本")
        
    except Exception as e:
        print(f"\n[ERROR] 執行過程發生錯誤: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        sys.exit(1)
    
    # 驗證結果
    print("\n步驟 3: 驗證資料庫結構")
    
    verify_tables(cursor)
    verify_indexes(cursor)
    verify_foreign_keys(cursor)
    
    # 關閉連接
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("部署完成！")
    print("=" * 60)
    print("\n建議接下來:")
    print("  1. 使用 pgAdmin 檢視資料庫結構")
    print("  2. 執行 test_connection.py 驗證連接")
    print("  3. 開始資料遷移")


if __name__ == '__main__':
    main()
