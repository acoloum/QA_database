#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
conn = psycopg2.connect('host=localhost port=5432 dbname=qa_database user=postgres password=swordfish1')
cursor = conn.cursor()

# Check record ID 5386
print('=== 檢驗資料 ID 5386 ===')
cursor.execute('SELECT * FROM "出貨檢驗數據" WHERE "識別碼" = 5386')
row = cursor.fetchone()
print(row)
print()

if row:
    material = row[6]  # 材質
    spec = row[5]      # 檢驗規格
    vendor = row[4]    # 廠商名稱
    print(f'材質: {material}')
    print(f'規格: {spec}')
    print(f'廠商: {vendor}')
    print()
    
    # Get vendor ID
    cursor.execute('SELECT "識別碼" FROM "廠商資料" WHERE "廠商名稱" = %s', (vendor,))
    vendor_row = cursor.fetchone()
    vendor_id = vendor_row[0] if vendor_row else None
    print(f'廠商ID: {vendor_id}')
    print()
    
    # Check tolerance records for this material
    print('=== 公差主檔 (相同材質) ===')
    cursor.execute('SELECT * FROM "廠商公差主檔" WHERE "材質" = %s', (material,))
    for tol in cursor.fetchall():
        print(f'ID={tol[0]}, 材質={tol[1]}, 規格={tol[2]}, 廠商ID={tol[3]}')

conn.close()
