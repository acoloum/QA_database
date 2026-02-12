#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試公差比對邏輯
"""

import psycopg2

# 連線資料庫
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='qa_database',
    user='postgres',
    password='swordfish1'
)

# 解析規格字串，取出外徑×內徑（不含長度）
def parse_base_spec(spec_str):
    """解析規格，取出外徑×內徑（不含長度）"""
    if not spec_str:
        return None
    parts = spec_str.replace('×', '*').replace('x', '*').split('*')
    # 只取前兩個部分（外徑×內徑），忽略長度
    if len(parts) >= 2:
        return f"{parts[0].strip()}*{parts[1].strip()}"
    return spec_str.strip()

# 測試案例
test_cases = [
    # (檢驗規格, 應該匹配公差ID)
    ('34*26.3*267', 32),  # ID 5211
    ('36*26.3*267', 33),  # ID 5212
    ('34*26.3', 32),      # 完全匹配
    ('36*26.3', 33),      # 完全匹配
]

cursor = conn.cursor()

# 查詢所有候選公差
cursor.execute('SELECT "識別碼", "材質", "規格" FROM "廠商公差主檔" WHERE "識別碼" IN (32, 33)')
candidates = cursor.fetchall()

print("=== 公差表候選資料 ===")
for row in candidates:
    print(f"ID={row[0]}, 規格='{row[2]}'")
    print(f"  解析後: '{parse_base_spec(row[2])}'")

print("\n=== Test Results ===")
for test_spec, expected_id in test_cases:
    input_base_spec = parse_base_spec(test_spec)
    matched = None

    for row in candidates:
        tol_spec = row[2] if row[2] else ''
        tol_base_spec = parse_base_spec(tol_spec)

        # 完全匹配
        if tol_spec == test_spec:
            matched = row
            print(f"[OK] Exact match: '{test_spec}' -> ID {row[0]}")
            break

        # 解析後匹配
        if input_base_spec and tol_base_spec and tol_base_spec == input_base_spec:
            if tol_spec and tol_spec.strip() != '':
                matched = row
                print(f"[OK] OD*ID match: '{test_spec}' -> '{input_base_spec}' -> ID {row[0]}")
                break

    if matched:
        result = "[PASS]" if matched[0] == expected_id else f"[FAIL] Expected ID {expected_id}"
        print(f"  {result}")
    else:
        print(f"[FAIL] '{test_spec}' no match found")

conn.close()
