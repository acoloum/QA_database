"""
自動轉換 app.py 中的 SQL Server 語法為 PostgreSQL 語法
v4 - 簡單逐行處理
"""

import re
from pathlib import Path

def convert_line(line):
    """轉換單行程式碼"""
    original_line = line
    
    # 1. 替換 import
    if 'import pyodbc' in line:
        line = line.replace('import pyodbc', 'import psycopg2')
        return line
    
    # 2. 跳過註釋行和空行
    stripped = line.lstrip()
    if not stripped or stripped.startswith('#'):
        return line
    
    # 3. 檢查是否是 cursor.execute 或 cursor.executemany 行
    if 'cursor.execute' in line or 'cursor.executemany' in line:
        # 在 SQL 字串中進行替換
        # A. dbo.表名 -> "表名"
        line = re.sub(r'\bdbo\.(\w+)\b', r'"\1"', line)
        
        # B. [欄位名] -> "欄位名" (只在 SQL 字串中)
        # 需要小心不要替換 Python 的列表索引
        # 簡單判斷：如果在引號內且包含中文，很可能是 SQL 欄位名
        def replace_brackets_in_sql(match):
            content = match.group(1)
            # 替換 SQL 欄位名的方括號
            content = re.sub(r'\[([^\]]+)\]', r'"\1"', content)
            return f'"{content}"'
        
        # 替換雙引號字串中的方括號
        line = re.sub(r'"([^"]*\[[^"]*)"', replace_brackets_in_sql, line)
        # 替換單引號字串中的方括號  
        def replace_brackets_in_single_quote(m):
            content = m.group(1)
            content = re.sub(r'\[([^\]]+)\]', r'"\1"', content)
            return f'"{content}"'
        line = re.sub(r"'([^']*\[[^']*)'", replace_brackets_in_single_quote, line)
        
        # C. ? -> %s (參數佔位符)
        # 只在 SQL 字串內替換
        if '?' in line and ('execute' in line or 'executemany' in line):
            # 簡單替換：在引號內的 ? 都換成 %s
            line = line.replace('?', '%s')
        
        # D. OUTPUT INSERTED.欄位 -> RETURNING "欄位"
        line = re.sub(
            r'OUTPUT\s+INSERTED\.(\w+)',
            r'RETURNING "\1"',
            line,
            flags=re.IGNORECASE
        )
        
        # E. GETDATE() -> CURRENT_TIMESTAMP
        line = re.sub(r'\bGETDATE\s*\(\s*\)', 'CURRENT_TIMESTAMP', line, flags=re.IGNORECASE)
        
        # F. SET NOCOUNT ON
        line = re.sub(r'SET\s+NOCOUNT\s+ON\s*;?\s*', '', line, flags=re.IGNORECASE)
    
    # 4. 處理函數參數中的字串字面量
    # 'dbo.表名' -> '"表名"' (作為函數參數)
    if "'dbo." in line and not 'cursor.execute' in line:
        line = re.sub(r"'dbo\.(\w+)'", r'"\1"', line)
    
    # '[欄位名]' -> '"欄位名"' (作為函數參數)
    if "'" in line and '[' in line and not 'cursor.execute' in line:
        line = re.sub(r"'\[([^\]]+)\]'", r'"\1"', line)
    
    return line


def convert_get_db_connection(content):
    """替換 get_db_connection 函數"""
    old_func = """def get_db_connection():
    return pyodbc.connect(
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
        r"Connection Timeout=30;"
    )"""
    
    new_func = """def get_db_connection():
    from config import POSTGRESQL_CONFIG
    return psycopg2.connect(**POSTGRESQL_CONFIG)"""
    
    return content.replace(old_func, new_func)


def convert_sql_syntax(content):
    """轉換整個檔案"""
    
    # 先處理 get_db_connection 函數 (整塊替換)
    content = convert_get_db_connection(content)
    
    # 逐行處理其餘內容
    lines = content.splitlines(keepends=True)
    converted_lines = []
    
    for line in lines:
        converted_line = convert_line(line)
        converted_lines.append(converted_line)
    
    return ''.join(converted_lines)


def backup_file(file_path):
    """備份原始檔案"""
    backup_path = file_path.parent / 'backup' / file_path.name
    backup_path.parent.mkdir(exist_ok=True)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] 已備份: {backup_path}")


def main():
    app_file = Path(__file__).parent.parent / 'app.py'
    
    if not app_file.exists():
        print(f"[ERROR] 找不到檔案: {app_file}")
        return
    
    print("=" * 60)
    print("SQL Server → PostgreSQL 轉換工具 v4")
    print("=" * 60)
    
    print("\n[1/5] 備份原始檔案")
    backup_file(app_file)
    
    print("\n[2/5] 讀取 app.py")
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    total_lines = len(content.splitlines())
    print(f"      檔案大小: {len(content):,} 字元, {total_lines} 行")
    
    print("\n[3/5] 轉換 SQL 語法")
    converted_content = convert_sql_syntax(content)
    
    # 統計變更
    orig_lines = content.splitlines()
    conv_lines = converted_content.splitlines()
    changes = sum(1 for o, c in zip(orig_lines, conv_lines) if o != c)
    
    print(f"      變更行數: {changes} / {total_lines}")
    
    print(f"\n[4/5] 儲存結果")
    output_file = app_file.parent / 'app_postgresql.py'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(converted_content)
    
    print(f"      [OK] 已儲存: app_postgresql.py")
    
    print(f"\n[5/5] 驗證語法")
    import subprocess
    result = subprocess.run(
        ['python', '-m', 'py_compile', str(output_file)],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode == 0:
        print("      ✓ Python 語法檢查通過")
        print("\n" + "=" * 60)
        print("✓ 轉換成功!")
        print("=" * 60)
        print(f"\n下一步:")
        print(f"  python app_postgresql.py")
        print(f"\n或測試API:")
        print(f"  python migration/test_api.py")
    else:
        print("      ✗ 發現語法錯誤")
        errors = result.stderr.splitlines()
        print(f"\n錯誤訊息 (顯示前 15 行):")
        for i, line in enumerate(errors[:15], 1):
            if line.strip():
                print(f"  {line}")


if __name__ == '__main__':
    main()
