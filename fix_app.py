#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
from datetime import datetime

def restore_backup():
    """從備份恢復原始檔案"""
    backup_file = 'app.py.backup'
    target_file = 'app.py'
    
    if os.path.exists(backup_file):
        try:
            shutil.copy2(backup_file, target_file)
            print(f"✅ 已從備份恢復: {backup_file} -> {target_file}")
            return True
        except Exception as e:
            print(f"❌ 恢復失敗: {e}")
            return False
    else:
        print("❌ 找不到備份檔案")
        return False

def fix_syntax():
    """修復語法問題"""
    target_file = 'app.py'
    
    # 創建臨時修復檔案
    with open(target_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修復第36行的縮進問題
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines, 1):
        if 'for i in range(1, 6):' in line and 'IndentationError' in str(i):
            fixed_line = line.replace('        ', '    ')
            fixed_lines.append(fixed_line)
            print(f"修復第{i}行縮進")
        else:
            fixed_lines.append(line)
    
    # 寫入修復後的內容
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    
    print(f"✅ 已修復檔案: {target_file}")
    return True

def check_syntax():
    """檢查Python語法"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 嘗試編譯檢查
        compile(content, 'app.py', 'exec')
        print("✅ Python語法檢查通過")
        return True
    except SyntaxError as e:
        print(f"❌ 語法錯誤: {e}")
        print(f"   行 {e.lineno}, 列 {e.offset}")
        return False
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False

def main():
    print("🔧 開始修復Python檔案...")
    print(f"📅 工作目錄: {os.getcwd()}")
    
    # 步驟1: 嘗試從備份恢復
    if restore_backup():
        if check_syntax():
            print("✅ 檔案已成功恢復並通過語法檢查")
            return
    
    # 步驟2: 如果沒有備份，嘗試修復
    print("🔍 沒有備份，嘗試修復語法...")
    if fix_syntax():
        if check_syntax():
            print("✅ 檔案已成功修復並通過語法檢查")
            return
    
    print("❌ 修復失敗，請手動檢查檔案")

if __name__ == "__main__":
    main()