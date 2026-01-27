#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fix_app_file():
    """修復app.py的語法和縮進問題"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("Reading app.py...")
        
        # 找到所有有問題的for迴圈並修復
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines, 1):
            # 檢查是否是需要修復的for迴圈
            if 'for i in range(1, 6):' in line:
                # 提取循環主體
                parts = line.split(':', 1)
                if len(parts) >= 2:
                    for_body = parts[1].strip()
                    indented_for_body = '\n'.join(['    ' + line for line in for_body.split('\n')])
                    fixed_line = parts[0] + ':' + indented_for_body
                    fixed_lines.append(fixed_line)
                    print(f"Fixed indentation on line {i}")
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        # 寫回修復的內容
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))
        
        print("app.py fix completed successfully!")
        return True
        
    except Exception as e:
        print(f"Fix failed: {e}")
        return False

def check_syntax():
    """檢查Python語法"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 嘗試編譯檢查
        compile(content, 'app.py', 'exec')
        print("Python syntax check passed!")
        return True
    except SyntaxError as e:
        print(f"Syntax error: {e}")
        print(f"Line {e.lineno}, Column {e.offset}")
        return False
    except Exception as e:
        print(f"Syntax check failed: {e}")
        return False

if __name__ == '__main__':
    fix_app_file()
    check_syntax()