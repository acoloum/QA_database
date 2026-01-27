# 快速修復腳本

import sys
import re

# 讀取損壞的檔案
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修復 get_db_connection 函數
pattern = r'def get_db_connection\(\):.*?r"Connection Timeout=30;"'
replacement = '''def get_db_connection():
    # 嘗試不同的連線方式
    connection_strings = [
        # 嘗試方式1: Windows驗證
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
        r"Connection Timeout=30;"
    ]'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# 修復 submitApplication 函數中的NCMR_ID驗證
pattern = r'"NCMR_ID": parseInt\(document\.getElementById\("ncmrId"\)\.value\)'
replacement = '''"NCMR_ID": parseInt(document.getElementById('ncmrId').value || '0')'''

content = re.sub(pattern, replacement, content)

# 寫回修復的檔案
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("檔案修復完成！")