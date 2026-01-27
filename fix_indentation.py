# 修復第48-50行的縮進問題

try:
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 修復第48-50行的縮進（調整到正確位置）
    for i in range(47, 50):  # 第48-51行（索引47-50）
        if i < len(lines):
            line = lines[i]
            # 將縮進調整到正確位置
            if line.startswith('            '):
                lines[i] = '        ' + line.strip()
                print(f"Fixed indentation on line {i+1}")
    
    # 寫回修復後的內容
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Fixed indentation for lines 48-50")
    
except Exception as e:
    print(f"Fix failed: {e}")