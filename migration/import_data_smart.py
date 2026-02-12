"""
智能資料匯入工具 - 自動處理欄位差異
只匯入 PostgreSQL schema 中存在的欄位，忽略多餘欄位
"""

import psycopg2
from psycopg2 import sql
import csv
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import POSTGRESQL_CONFIG


def get_table_columns(cursor, table_name):
    """獲取 PostgreSQL 表的所有欄位"""
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}' 
        AND table_schema = 'public'
        ORDER BY ordinal_position;
    """)
    return [row[0] for row in cursor.fetchall()]


def import_csv_smart(cursor, table_name, csv_file):
    """智能匯入：只匯入 schema 中存在的欄位"""
    
    print(f"\n匯入: {table_name}")
    print(f"  來源: {csv_file.name}")
    
    # 獲取 PostgreSQL 表的欄位
    pg_columns = get_table_columns(cursor, table_name)
    
    # 讀取 CSV
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        csv_headers = next(reader)  # 第一行是欄位名稱
        
        # 找出共同欄位（保持 CSV 中的順序）
        common_columns = [col for col in csv_headers if col in pg_columns]
        
        # 找出 CSV 中的欄位索引
        column_indices = [csv_headers.index(col) for col in common_columns]
        
        print(f"  PostgreSQL 欄位: {len(pg_columns)}")
        print(f"  CSV 欄位: {len(csv_headers)}")
        print(f"  共同欄位: {len(common_columns)}")
        
        # 顯示跳過的欄位
        skipped = [col for col in csv_headers if col not in pg_columns]
        if skipped:
            print(f"  跳過欄位: {', '.join(skipped)}")
        
        # 建立 INSERT 語句
        placeholders = ','.join(['%s'] * len(common_columns))
        columns_str = ','.join([f'"{col}"' for col in common_columns])
        
        insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
        
        # 讀取所有資料行
        rows = list(reader)
        total_rows = len(rows)
        
        if total_rows == 0:
            print(f"  [SKIP] CSV 檔案為空")
            return 0
        
        # 處理資料：只取共同欄位，空字串轉 None
        processed_rows = []
        for row in rows:
            processed_row = []
            for idx in column_indices:
                val = row[idx] if idx < len(row) else ''
                processed_row.append(val if val != '' else None)
            processed_rows.append(tuple(processed_row))
        
        # 批次執行
        try:
            cursor.executemany(insert_sql, processed_rows)
            print(f"  [OK] 成功匯入 {total_rows} 筆記錄")
            return total_rows
        except Exception as e:
            print(f"  [ERROR] 匯入失敗: {e}")
            return 0


def reset_sequence(cursor, table_name, id_column='識別碼'):
    """重設序列值"""
    try:
        cursor.execute(f'SELECT MAX("{id_column}") FROM "{table_name}"')
        max_id = cursor.fetchone()[0]
        
        if max_id is not None:
            cursor.execute(f'SELECT pg_get_serial_sequence(\'"{table_name}"\', \'{id_column}\')')
            seq_name = cursor.fetchone()[0]
            
            if seq_name:
                cursor.execute(f'SELECT setval(\'{seq_name}\', {max_id})')
                print(f"  序列 {id_column}: 設定為 {max_id}")
            else:
                print(f"  序列 {id_column}: 無序列，保持預設")
        else:
            print(f"  序列 {id_column}: 表為空，保持預設")
    except Exception as e:
        print(f"  序列重設警告: {e}")


def main():
    print("=" * 80)
    print("智能資料匯入工具")
    print("=" * 80)
    
    # 連接資料庫
    print("\n連接到 PostgreSQL...")
    conn = psycopg2.connect(**POSTGRESQL_CONFIG)
    cursor = conn.cursor()
    print("[OK] 連接成功")
    
    export_dir = Path(__file__).parent / 'exported_data'
    
    # 定義匯入順序（考慮外鍵依賴）
    import_order = [
        ('廠商資料', '識別碼'),
        ('廠商公差主檔', '識別碼'),
        ('廠商公差明細檔', '識別碼'),
        ('品管人員', '識別碼'),
        ('擠壓機台', '識別碼'),
        ('使用者', '識別碼'),
        ('出貨檢驗數據', '識別碼'),
        ('巡檢主檔', '識別碼'),
        ('巡檢子檔', '識別碼'),
        ('不合格品單', '識別碼'),
        ('異常矯正單', '識別碼'),
        ('重工申請單', '識別碼'),
        ('重工執行記錄', '識別碼'),
        ('重工品檢記錄', '識別碼'),
        ('重工成本分析', '識別碼'),
    ]
    
    print("\n開始匯入資料...")
    
    # 暫時停用外鍵約束（匯入時）
    print("\n[設定] 暫時停用外鍵約束...")
    cursor.execute("SET session_replication_role = 'replica';")
    
    total_imported = 0
    success_count = 0
    skip_count = 0
    
    for table_name, id_column in import_order:
        csv_file = export_dir / f"{table_name}.csv"
        
        if not csv_file.exists():
            print(f"\n[跳過] {table_name} - CSV 檔案不存在")
            skip_count += 1
            continue
        
        # 先清空表（避免重複）
        try:
            cursor.execute(f'TRUNCATE TABLE "{table_name}" CASCADE')
            print(f"\n[清空] {table_name}")
        except Exception as e:
            print(f"\n[警告] 無法清空 {table_name}: {e}")
            # 如果 TRUNCATE 失敗，嘗試 DELETE
            try:
                cursor.execute(f'DELETE FROM "{table_name}"')
                print(f"  使用 DELETE 清空")
            except Exception as e2:
                print(f"  [錯誤] 清空失敗: {e2}")
                conn.rollback()  # 回滾錯誤
                continue
        
        # 匯入資料
        imported = import_csv_smart(cursor, table_name, csv_file)
        
        if imported > 0:
            total_imported += imported
            success_count += 1
            
            # 重設序列
            reset_sequence(cursor, table_name, id_column)
    
    # 重新啟用外鍵約束
    print("\n[設定] 重新啟用外鍵約束...")
    cursor.execute("SET session_replication_role = 'origin';")
    
    # 提交事務
    print("\n正在提交事務...")
    conn.commit()
    print("[OK] 事務已提交")
    
    cursor.close()
    conn.close()
    
    # 顯示總結
    print("\n" + "=" * 80)
    print("匯入完成")
    print("=" * 80)
    print(f"成功匯入: {success_count}/{len(import_order)} 個表")
    print(f"總記錄數: {total_imported:,}")
    print(f"跳過表數: {skip_count}")
    
    print("\n下一步:")
    print("  1. 測試應用程式: python app_postgresql.py")
    print("  2. 驗證資料: python migration/test_simple.py")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n使用者中斷")
    except Exception as e:
        print(f"\n\n[錯誤] {e}")
        import traceback
        traceback.print_exc()
