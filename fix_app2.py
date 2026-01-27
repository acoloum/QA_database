#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil

def restore_backup():
    """從備份恢復原始檔案"""
    backup_file = 'app.py.backup'
    target_file = 'app.py'
    
    if os.path.exists(backup_file):
        try:
            shutil.copy2(backup_file, target_file)
            print(f"從備份恢復成功")
            return True
        except Exception as e:
            print(f"恢復失敗: {e}")
            return False
    else:
        print("找不到備份檔案")
        return False

def fix_indentation():
    """修復縮進問題"""
    target_file = 'app.py'
    
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines, 1):
            # 修復第36行以後的縮進問題
            if 'for i in range(1, 6):' in line:
                fixed_line = line.replace('        ', '    ')
                print(f"修復第{i}行縮進")
                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)
        
        # 寫回修復後的內容
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))
        
        print("縮進修復完成")
        return True
        
    except Exception as e:
        print(f"修復失敗: {e}")
        return False

def check_syntax():
    """檢查Python語法"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        compile(content, 'app.py', 'exec')
        print("Python語法檢查通過")
        return True
    except SyntaxError as e:
        print(f"語法錯誤: {e}")
        print(f"行 {e.lineno}, 列 {e.offset}")
        return False
    except Exception as e:
        print(f"檢查失敗: {e}")
        return False

def main():
    print("開始修復app.py...")
    
    # 步驟1: 嘗試從備份恢復
    if restore_backup():
        if check_syntax():
            print("檔案恢復成功")
            return
    
    # 步驟2: 如果沒有備份，嘗試修復縮進
    print("嘗試修復縮進問題...")
    if fix_indentation():
        check_syntax()
    else:
        print("縮進修復失敗")

if __name__ == "__main__":
    main()