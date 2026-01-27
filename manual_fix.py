# 手動修復第36行縮進

try:
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 修復第36行的縮進（行號36，索引35）
    if len(lines) > 35:
        line_35 = lines[35]  # 第36行
        if '        for i in range(1, 6):' in line_35:
            # 修復為正確縮進
            fixed_line_35 = '    for i in range(1, 6):\n'
            lines[35] = fixed_line_35
            print("Fixed indentation on line 36")
    
    # 寫回修復後的內容
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Manual indentation fix completed")
    
except Exception as e:
    print(f"Manual fix failed: {e}")