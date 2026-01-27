# 最終修復腳本

try:
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("最終修復app.py...")
    
    # 簡化修復：直接替換有問題的內容
    # 修復第36行及以後的縮進問題
    content = content.replace(
        '        for i in range(1, 6):\n            for col in [\'外徑\', \'內徑\', \'厚度\']:\n                fields += [f"[{col}{i}-min]", f"[{col}{i}-max"]"]\n                params += [data.get(f\'{col}{i}-min\'), data.get(f\'{col}{i}-max\')]\n',
        '        for i in range(1, 6):\n            for col in [\'外徑\', \'內徑\', \'厚度\']:\n                fields += [f"[{col}{i}-min]", f"[{col}{i}-max"]"]\n                params += [data.get(f\'{col}{i}-min\'), data.get(f\'{col}{i}-max\')]\n'
    )
    
    # 修復第36行的縮進問題  
    content = content.replace(
        '            for col in [\'外徑\', \'內徑\', \'厚度\']:\n                fields += [f"[{col}{i}-min]", f"[{col}{i}-max"]"]\n                params += [data.get(f\'{col}{i}-min\'), data.get(f\'{col}{i}-max\')]\n',
        '            for i in range(1, 6):\n            for col in [\'外徑\', \'內徑\', \'厚度\']:\n                fields += [f"[{col}{i}-min]", f"[{col}{i}-max"]"]\n                params += [data.get(f\'{col}{i}-min\'), data.get(f\'{col}{i}-max\')]\n'
    )
    
    # 修復SQL部分的縮進問題
    content = content.replace(
        '                params.append(data.get(\'識別碼\'))',
        '                params.append(data.get(\'識別碼\'))'
    )
    
    # 修復第48-50行的縮進問題
    lines = content.split('\n')
    for i in range(47, 51):  # 第48-51行（索引47-50）
        if i < len(lines) and lines[i].startswith('            '):
            lines[i] = '        ' + lines[i].strip()
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print("✅ app.py最終修復完成!")
    
except Exception as e:
    print(f"修復失敗: {e}")