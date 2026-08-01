"""
PostgreSQL 資料庫連接配置
用途：統一管理資料庫連接參數，支援 SQL Server 和 PostgreSQL
"""

import os
from typing import Literal
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

# 資料庫類型
DB_TYPE: Literal['sqlserver', 'postgresql'] = 'postgresql'  # 切換資料庫類型

# ===================================================
# SQL Server 配置（舊系統）
# ===================================================
SQLSERVER_CONFIG = {
    'driver': 'ODBC Driver 18 for SQL Server',
    'server': r'localhost\SQLEXPRESS',
    'database': '品保資料庫',
    'trusted_connection': 'yes',
    'encrypt': 'no',
    'trust_server_certificate': 'yes',
    'connection_timeout': 30,
}

# ===================================================
# PostgreSQL 配置（新系統）
# ===================================================
POSTGRESQL_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'qa_database'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),  # 請設定密碼或使用環境變數
}

# ===================================================
# 應用程式配置
# ===================================================
SECRET_KEY = os.getenv('SECRET_KEY')
TOKEN_EXPIRATION_HOURS = 24

# ===================================================
# 取得當前資料庫配置
# ===================================================
def get_db_config():
    """根據 DB_TYPE 返回對應的資料庫配置"""
    if DB_TYPE == 'postgresql':
        return POSTGRESQL_CONFIG
    else:
        return SQLSERVER_CONFIG


# ===================================================
# 環境變數設定範例（.env 檔案）
# ===================================================
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=qa_database
# DB_USER=postgres
# DB_PASSWORD=your_secure_password_here
