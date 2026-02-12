"""
PostgreSQL 資料匯入工具
用途：將 CSV 資料匯入 PostgreSQL
"""

import psycopg2
from psycopg2 import sql
import csv
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 加入上層目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import POSTGRESQL_CONFIG
except ImportError:
    print("[ERROR] 無法載入 config.py")
    sys.exit(1)


def import_csv_to_table(cursor, table_name, csv_file):
    """從 CSV 匯入資料到表格"""
    try:
        print(f"\n匯入: {table_name}")
        print(f"  來源: {csv_file.name}")
        
        # 讀取 CSV
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)  # 第一行是欄位名稱
            
            # 建立 INSERT 語句
            placeholders = ','.join(['%s'] * len(headers))
            columns = ','.join([f'"{col}"' for col in headers])
            
            insert_sql = f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})'
            
            # 批次匯入
            rows = list(reader)
            total_rows = len(rows)
            
            if total_rows == 0:
                print(f"  [SKIP] CSV 檔案為空")
                return 0
            
            # 處理資料：空字串轉 None
            processed_rows = []
            for row in rows:
                processed_row = [val if val != '' else None for val in row]
                processed_rows.append(processed_row)
            
            # 批次執行
            cursor.executemany(insert_sql, processed_rows)
            
            print(f"  [OK] 成功匯入 {total_rows} 筆記錄")
            return total_rows
            
    except psycopg2.IntegrityError as e:
        print(f"  [ERROR] 違反完整性約束: {e}")
        return -1
    except Exception as e:
        print(f"  [ERROR] 匯入失敗: {e}")
        return -1


def reset_sequences(cursor):
    """重設所有 SERIAL 序列的起始值"""
    try:
        print("\n重設序列起始值...")
        
        # 獲取所有使用 SERIAL 的表和欄位
        cursor.execute("""
            SELECT 
                table_name,
                column_name,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND column_default LIKE 'nextval%'
            ORDER BY table_name;
        """)
        
        sequences = cursor.fetchall()
        
        for table, column, default in sequences:
            # 提取序列名稱
            seq_name = default.split("'")[1]
            
            # 獲取當前最大值
            cursor.execute(f'SELECT MAX("{column}") FROM "{table}"')
            max_val = cursor.fetchone()[0]
            
            if max_val is not None:
                # 設定序列起始值為最大值+1
                cursor.execute(f"SELECT setval('{seq_name}', {max_val})")
                print(f"  {table}.{column}: 設定為 {max_val + 1}")
            else:
                print(f"  {table}.{column}: 表格為空，保持預設")
        
        print("[OK] 序列重設完成")
        
    except Exception as e:
        print(f"[ERROR] 序列重設失敗: {e}")


def main():
    print("=" * 60)
    print("PostgreSQL 資料匯入工具")
    print("=" * 60)
    
    # CSV 檔案目錄
    data_dir = Path(__file__).parent / 'exported_data'
    
    if not data_dir.exists():
        print(f"[ERROR] 找不到資料目錄: {data_dir}")
        print("請先執行 export_data.py 匯出 SQL Server 資料")
        return
    
    # 連接 PostgreSQL
    try:
        print("\n連接到 PostgreSQL...")
        conn = psycopg2.connect(**POSTGRESQL_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        print("[OK] 連接成功")
        
    except Exception as e:
        print(f"[ERROR] 連接失敗: {e}")
        return
    
    # 匯入順序（考慮外鍵依賴）
    import_order = [
        '品管人員',
        '廠商資料',
        '擠壓機台',
        '擠壓人員',
        '使用者',
        '出貨檢驗數據',
        '巡檢主檔',
        '巡檢子檔',
        '不合格品單',
        '異常矯正單',
        '重工申請單',
        '重工執行記錄',
        '重工品檢記錄',
        '重工成本分析',
        '廠商公差主檔',
        '廠商公差明細檔',
    ]
    
    # 匯入資料
    print("\n開始匯入資料...")
    total_records = 0
    success_count = 0
    
    try:
        for table_name in import_order:
            csv_file = data_dir / f"{table_name}.csv"
            
            if csv_file.exists():
                record_count = import_csv_to_table(cursor, table_name, csv_file)
                
                if record_count >= 0:
                    success_count += 1
                    total_records += record_count
                    conn.commit()  # 每個表成功後提交
                else:
                    print(f"  [WARNING] 匯入失敗，回滾此表")
                    conn.rollback()
            else:
                print(f"\n[SKIP] 找不到: {csv_file.name}")
        
        # 重設序列
        reset_sequences(cursor)
        conn.commit()
        
    except Exception as e:
        print(f"\n[ERROR] 匯入過程發生錯誤: {e}")
        conn.rollback()
    
    finally:
        cursor.close()
        conn.close()
    
    # 摘要
    print("\n" + "=" * 60)
    print("匯入完成！")
    print("=" * 60)
    print(f"成功匯入: {success_count}/{len(import_order)} 個表格")
    print(f"總記錄數: {total_records:,}")


if __name__ == '__main__':
    main()
