"""
PostgreSQL 轉換腳本 - 最終解決方案
使用三個單引號包裹 SQL，避免與內部引號衝突
"""

import re
from pathlib import Path

def convert_sql_syntax(content):
    """轉換 SQL Server 語法為 PostgreSQL"""
    
    # 1. 替換 import
    content = content.replace('import pyodbc', 'import psycopg2')
    
    # 2. 替換 get_db_connection 函數
    old_connection = r"""def get_db_connection():
    return pyodbc.connect(
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
        r"Connection Timeout=30;"
    )"""
    
    new_connection = """def get_db_connection():
    from config import POSTGRESQL_CONFIG
    from dotenv import load_dotenv
    load_dotenv()
    return psycopg2.connect(**POSTGRESQL_CONFIG)"""
    
    content = content.replace(old_connection, new_connection)
    
    # 3. 轉換所有 cursor.execute 語句
    def convert_execute_sql(match):
        prefix = match.group(1)  # cursor.execute( 或 cursor.executemany(
        sql = match.group(2)     # SQL 內容
        suffix = match.group(3)  # 後續部分 (, 或 ))
        
        # 在 SQL 內部進行轉換
        # A. dbo.表名 -> "表名"
        sql = re.sub(r'\bdbo\.(\w+)\b', r'"\1"', sql)
        
        # B. [欄位名] -> "欄位名"
        sql = re.sub(r'\[([^\]]+)\]', r'"\1"', sql)
        
        # C. ? -> %s
        sql = sql.replace('?', '%s')
        
        # D. OUTPUT INSERTED.欄位 -> RETURNING "欄位"
        sql = re.sub(r'OUTPUT\s+INSERTED\.(\w+)', r'RETURNING "\1"', sql, flags=re.IGNORECASE)
        
        # E. GETDATE() -> CURRENT_TIMESTAMP
        sql = re.sub(r'\bGETDATE\s*\(\s*\)', 'CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE)
        
        # F. SET NOCOUNT ON
        sql = re.sub(r'SET\s+NOCOUNT\s+ON\s*;?\s*', '', sql, flags=re.IGNORECASE)
        
        # 使用三個單引號包裹 SQL
        # 優點：SQL 標識符用 "雙引號"，SQL 字串用 '單引號'，都不會與 ''' 衝突
        return f"{prefix}'''{sql}'''{suffix}"
    
    # 匹配所有 cursor.execute("...") 語句
    content = re.sub(
        r'(cursor\.(?:execute|executemany)\s*\()"([^"]+)"(\s*(?:,|\)))',
        convert_execute_sql,
        content
    )
    
    # 4. 處理函數參數中的表名和欄位名（非 execute 語句中的）
    # 'dbo.表名' -> '"表名"'
    content = re.sub(r"'dbo\.(\w+)'", r'"\1"', content)
    
    # '[欄位]' -> '"欄位"'
    content = re.sub(r"'\[([^\]]+)\]'", r'"\1"', content)
    
    return content


def main():
    app_file = Path(__file__).parent.parent / 'app.py'
    output_file = Path(__file__).parent.parent / 'app_postgresql.py'
    
    print("=" * 70)
    print("PostgreSQL 轉換 - 使用三單引號策略")
    print("=" * 70)
    
    print("\n[1/4] 讀取 app.py")
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    total_lines = len(content.splitlines())
    print(f"      檔案大小: {len(content):,} 字元, {total_lines:,} 行")
    
    print("\n[2/4] 執行語法轉換")
    converted = convert_sql_syntax(content)
    
    changes = sum(1 for o, c in zip(content.split('\n'), converted.split('\n')) if o != c)
    print(f"      變更行數: {changes:,}")
    
    print("\n[3/4] 儲存到 app_postgresql.py")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(converted)
    print("      [OK] 檔案已儲存")
    
    print("\n[4/4] 驗證 Python 語法")
    import subprocess
    result = subprocess.run(
        ['python', '-m', 'py_compile', str(output_file)],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode == 0:
        print("      [✓] Python 語法檢查通過!")
        print("\n" + "=" * 70)
        print("✓ 轉換成功完成")
        print("=" * 70)
        print(f"\n輸出檔案: {output_file}")
        print(f"\n下一步:")
        print(f"  1. 啟動應用程式: python app_postgresql.py")
        print(f"  2. 測試 API: python migration/test_api.py")
        return True
    else:
        print("      [✗] 發現語法錯誤")
        print("\n錯誤詳情:")
        error_lines = result.stderr.split('\n')
        for i, line in enumerate(error_lines[:15], 1):
            if line.strip():
                print(f"  {line}")
        
        # 分析錯誤並給建議
        print("\n分析:")
        if 'unterminated string' in result.stderr:
            print("  - 發現未結束的字串，可能是引號嵌套問題")
        if 'invalid syntax' in result.stderr:
            print("  - 發現語法錯誤，檢查 SQL 語句轉換")
        
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
