# 修復SQL部分縮進問題的簡化腳本

try:
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到問題的SQL部分並修復
    lines = content.split('\n')
    fixed_content = []
    in_sql_section = False
    brace_count = 0
    
    for line in lines:
        # 檢測SQL部分
        if 'cursor.execute(' in line:
            in_sql_section = True
            brace_count += line.count('{') - line.count('}')
        elif in_sql_section:
            brace_count += line.count('{') - line.count('}')
            
            # 如果大括號已平衡，退出SQL部分
            if brace_count <= 0:
                in_sql_section = False
            
            # 修復縮進問題
            if 'params.append(data.get(\'識別碼\'))' in line:
                fixed_line = line.replace('                params.append(data.get(\'識別碼\'))', '                params.append(data.get(\'識別碼\'))')
                fixed_content.append(fixed_line)
                print(f"Fixed line: {fixed_line.strip()}")
            else:
                fixed_content.append(line)
        else:
            fixed_content.append(line)
    
    # 寫入修復後的內容
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_content))
    
    print("SQL indentation fix completed")
    
except Exception as e:
    print(f"Fix failed: {e}")