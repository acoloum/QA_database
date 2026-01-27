#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

def restore_app():
    """從備份恢復app.py"""
    try:
        # 先嚗試從備份恢復
        if os.path.exists('app.py.bak'):
            import shutil
            shutil.copy2('app.py.bak', 'app.py')
            print("✅ 已從備份恢復: app.py.bak")
            return True
        
        # 如果沒有備份，創建一個基本的可運行版本
        print("創建基本可運行版本...")
        basic_app_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_required, current_user
import pyodbc
import datetime
import json
import hashlib

# 基本配置
app = Flask(__name__)
CORS(app, resources={r"/*/*": {"origins": ["*"]}})
app.secret_key = 'dev_key_123456'
login_manager = LoginManager()

# 連線字符串
def get_db_connection():
    return pyodbc.connect(
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
        r"Connection Timeout=30;"
    )

@app.route('/')
def index():
    return "基本服務運行中..."

@app.route('/test/db')
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.不合格品單")
        result = cursor.fetchone()
        conn.close()
        return jsonify({"success": True, "count": result[0]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/inspectors')
def get_inspectors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 識別碼, 姓名 FROM dbo.品管人員")
        result = cursor.fetchall()
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

'''
        
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(basic_app_content)
        
        print("✅ 創建基本可運行版本: app_simple.py")
        return True
        
    except Exception as e:
        print(f"❌ 恢復失敗: {e}")
        return False

if __name__ == '__main__':
    restore_app()