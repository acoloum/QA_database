"""
後處理腳本：修復 app_postgresql.py 中的引號嵌套問題
策略：將 cursor.execute 的 SQL 字串改為三引號形式
"""

import re
from pathlib import Path

def fix_execute_statements(content):
    """修復 cursor.execute 語句中的引號問題"""
    
    # 策略：將 cursor.execute("...") 改為 cursor.execute('''...''')
    # 這樣內部的 "表名" 就不需要轉義了
    
    def replace_double_quote_sql(match):
        """替換雙引號 SQL 為三引號"""
        indent = match.group(1)  # 縮排
        method = match.group(2)  # execute 或 executemany
        sql = match.group(3)     # SQL 內容
        rest = match.group(4)    # 後續參數
        
        # 如果 SQL 包含雙引號標識符，改用三引號
        if '"' in sql:
            return f'{indent}cursor.{method}("""{sql}"""{rest}'
        else:
            # 沒有雙引號，保持原樣
            return match.group(0)
    
    # 匹配 cursor.execute("...") 或 cursor.executemany("...")
    # 模式：捕獲縮排、方法名、SQL內容、後續參數
    pattern = r'^(\s*)cursor\.(execute|executemany)\("([^"]*(?:"[^"]*"[^"]*)*)"(\s*,|\s*\))'
    
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        # 檢查是否是 cursor.execute 開頭的行
        if 'cursor.execute' in line and '"' in line:
            # 嘗試簡單的模式匹配
            match = re.match(r'^(\s*)cursor\.(execute|executemany)\("(.+)"(\s*,.*|\s*\).*)$', line)
            if match:
                indent = match.group(1)
                method = match.group(2)
                sql = match.group(3)
                rest = match.group(4)
                
                # 檢查 SQL 中是否包含未轉義的雙引號（PostgreSQL 標識符）
                # 如果有，改用三引號
                if '"' in sql and not r'\"' in sql:
                    line = f'{indent}cursor.{method}("""{sql}"""{rest}'
            
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)


def fix_generate_number_calls(content):
    """修復 generate_number 調用中的引號問題"""
    # generate_number('PREFIX', "表名", "欄位名")
    # 這些已經是正確的格式，不需要修改
    return content


def main():
    app_file = Path(__file__).parent.parent / 'app_postgresql.py'
    
    if not app_file.exists():
        print(f"[ERROR] 找不到 app_postgresql.py")
        return
    
    print("=" * 60)
    print("修復 app_postgresql.py 引號問題")
    print("=" * 60)
    
    print("\n[1/4] 讀取檔案")
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"      檔案大小: {len(content):,} 字元")
    
    print("\n[2/4] 修復 cursor.execute 語句")
    fixed_content = fix_execute_statements(content)
    
    # 統計修改
    changes = sum(1 for o, f in zip(content.split('\n'), fixed_content.split('\n')) if o != f)
    print(f"      修改行數: {changes}")
    
    print("\n[3/4] 儲存修復後的檔案")
    with open(app_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("      [OK] 已儲存")
    
    print("\n[4/4] 驗證 Python 語法")
    import subprocess
    result = subprocess.run(
        ['python', '-m', 'py_compile', str(app_file)],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode == 0:
        print("      [成功] 語法檢查通過!")
        print("\n" + "=" * 60)
        print("修復完成")
        print("=" * 60)
    else:
        print("      [失敗] 仍有語法錯誤")
        print("\n錯誤詳情:")
        for line in result.stderr.split('\n')[:10]:
            if line.strip():
                print(f"  {line}")


if __name__ == '__main__':
    main()
