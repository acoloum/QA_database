"""
分析 CSV 和 PostgreSQL schema 的差異，並生成智能匯入腳本
"""

import psycopg2
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
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}' 
        AND table_schema = 'public'
        ORDER BY ordinal_position;
    """)
    return {row[0]: row[1] for row in cursor.fetchall()}

def get_csv_columns(csv_file):
    """獲取 CSV 檔案的欄位"""
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        return next(reader)

def analyze_differences():
    """分析所有待匯入表的欄位差異"""
    
    conn = psycopg2.connect(**POSTGRESQL_CONFIG)
    cursor = conn.cursor()
    
    export_dir = Path(__file__).parent / 'exported_data'
    
    # 需要檢查的表
    tables_to_check = [
        '出貨檢驗數據',
        '巡檢子檔',
        '不合格品單',
        '異常矯正單'
    ]
    
    print("=" * 80)
    print("欄位差異分析報告")
    print("=" * 80)
    
    for table in tables_to_check:
        csv_file = export_dir / f"{table}.csv"
        
        if not csv_file.exists():
            print(f"\n[跳過] {table} - CSV 檔案不存在")
            continue
        
        print(f"\n{'=' * 80}")
        print(f"表名: {table}")
        print(f"{'=' * 80}")
        
        # 獲取 PostgreSQL 欄位
        pg_columns = get_table_columns(cursor, table)
        
        # 獲取 CSV 欄位
        csv_columns = get_csv_columns(csv_file)
        
        print(f"\nPostgreSQL 欄位數: {len(pg_columns)}")
        print(f"CSV 欄位數: {len(csv_columns)}")
        
        # 找出只在 CSV 中的欄位
        csv_only = [col for col in csv_columns if col not in pg_columns]
        
        # 找出只在 PostgreSQL 中的欄位
        pg_only = [col for col in pg_columns if col not in csv_columns]
        
        # 共同欄位
        common = [col for col in csv_columns if col in pg_columns]
        
        if csv_only:
            print(f"\n⚠️  只在 CSV 中的欄位 ({len(csv_only)} 個):")
            for col in csv_only:
                print(f"    - {col}")
        
        if pg_only:
            print(f"\n⚠️  只在 PostgreSQL 中的欄位 ({len(pg_only)} 個):")
            for col in pg_only:
                print(f"    - {col} ({pg_columns[col]})")
        
        print(f"\n✓ 共同欄位 ({len(common)} 個):")
        for col in common[:5]:  # 只顯示前5個
            print(f"    - {col}")
        if len(common) > 5:
            print(f"    ... 以及其他 {len(common) - 5} 個欄位")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)

if __name__ == '__main__':
    analyze_differences()
