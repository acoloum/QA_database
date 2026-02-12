"""
SQL Server 資料匯出工具
用途：從 SQL Server 匯出所有表的資料為 CSV 格式
"""

import pyodbc
import csv
from pathlib import Path
from datetime import datetime


def get_sqlserver_connection():
    """連接到 SQL Server"""
    return pyodbc.connect(
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
        r"Connection Timeout=30;"
    )


def get_all_tables(cursor):
    """獲取所有表名"""
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        AND TABLE_SCHEMA = 'dbo'
        ORDER BY TABLE_NAME
    """)
    return [row[0] for row in cursor.fetchall()]


def export_table_to_csv(cursor, table_name, output_dir):
    """匯出單個表為 CSV"""
    try:
        print(f"\n匯出: {table_name}")
        
        # 查詢所有資料
        cursor.execute(f"SELECT * FROM dbo.[{table_name}]")
        
        # 獲取欄位名稱
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        print(f"  記錄數: {len(rows)}")
        
        if len(rows) == 0:
            print(f"  [SKIP] 表格為空")
            return 0
        
        # 建立 CSV 檔案
        csv_file = output_dir / f"{table_name}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 寫入標題
            writer.writerow(columns)
            
            # 寫入資料
            for row in rows:
                # 處理特殊資料型別
                processed_row = []
                for value in row:
                    if value is None:
                        processed_row.append('')
                    elif isinstance(value, datetime):
                        processed_row.append(value.strftime('%Y-%m-%d %H:%M:%S'))
                    elif isinstance(value, bytes):
                        processed_row.append(value.hex())
                    else:
                        processed_row.append(str(value))
                
                writer.writerow(processed_row)
        
        print(f"  [OK] 已儲存: {csv_file.name}")
        return len(rows)
        
    except Exception as e:
        print(f"  [ERROR] 匯出失敗: {e}")
        return -1


def main():
    print("=" * 60)
    print("SQL Server 資料匯出工具")
    print("=" * 60)
    
    # 建立輸出目錄
    output_dir = Path(__file__).parent / 'exported_data'
    output_dir.mkdir(exist_ok=True)
    print(f"\n輸出目錄: {output_dir}")
    
    # 連接 SQL Server
    try:
        print("\n連接到 SQL Server...")
        conn = get_sqlserver_connection()
        cursor = conn.cursor()
        print("[OK] 連接成功")
        
    except Exception as e:
        print(f"[ERROR] 連接失敗: {e}")
        print("\n請確認:")
        print("  1. SQL Server Express 正在運行")
        print("  2. 資料庫 '品保資料庫' 存在")
        print("  3. Windows 整合驗證可用")
        return
    
    # 獲取所有表
    print("\n獲取表格清單...")
    tables = get_all_tables(cursor)
    print(f"[OK] 找到 {len(tables)} 個表格")
    
    # 匯出每個表
    print("\n開始匯出資料...")
    total_records = 0
    success_count = 0
    
    for table in tables:
        record_count = export_table_to_csv(cursor, table, output_dir)
        if record_count >= 0:
            success_count += 1
            total_records += record_count
    
    # 關閉連接
    cursor.close()
    conn.close()
    
    # 摘要
    print("\n" + "=" * 60)
    print("匯出完成！")
    print("=" * 60)
    print(f"成功匯出: {success_count}/{len(tables)} 個表格")
    print(f"總記錄數: {total_records:,}")
    print(f"輸出目錄: {output_dir}")
    
    # 建立匯入腳本提示
    print("\n接下來:")
    print(f"  1. 檢查 {output_dir} 中的 CSV 檔案")
    print(f"  2. 執行 import_data.py 匯入到 PostgreSQL")


if __name__ == '__main__':
    main()
