#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fix_app_file():
    """修復app.py的語法和縮進問題"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("開始修復app.py...")
        
        # 找到有問題的for迴圈並修復
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines, 1):
            # 修復for i in range(1, 6): 後面的縮進
            if 'for i in range(1, 6):' in line:
                # 計簡修復：將這部分縮進調整到正確位置
                indented_line = '        for i in range(1, 6):\n' + '            for col in [\'外徑\', \'內徑\', \'厚度\']:\n' + '                fields += [f"[{col}{i}-min]", f"[{col}{i}-max]"]\n' + '                params += [data.get(f\'{col}{i}-min\'), data.get(f\'{col}{i}-max\')]'
                fixed_lines.append(indented_line)
                print(f"修復第{i}行")
            else:
                fixed_lines.append(line)
        
        # 寫入修復後的內容
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))
        
        print("✅ app.py修復完成")
        return True
        
    except Exception as e:
        print(f"❌ 修復失敗: {e}")
        return False

if __name__ == '__main__':
    fix_app_file()