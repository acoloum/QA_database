import os
from dotenv import load_dotenv
from sqlalchemy import URL

# Load .env file
load_dotenv()


# Database Configuration - Support environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'qa_database')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

POSTGRESQL_CONFIG = {
    'database': DB_NAME,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'host': DB_HOST,
    'port': int(DB_PORT)
}


# Security Configuration
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Please set it in your .env file or environment. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
TOKEN_EXPIRATION_HOURS = int(os.getenv('TOKEN_EXPIRATION_HOURS', '24'))

# 請求與代理邊界：由 Nginx 與 Flask 同時限制上傳大小，避免只依賴單一層。
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
TRUSTED_PROXY_COUNT = int(os.getenv('TRUSTED_PROXY_COUNT', '0'))
RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')

# CORS 白名單：以逗號分隔的允許來源清單（可透過環境變數覆寫）
ALLOWED_ORIGINS = os.getenv(
    'ALLOWED_ORIGINS',
    'http://localhost:5173,http://localhost:8080'
).split(',')


# SQLAlchemy Configuration
SQLALCHEMY_DATABASE_URI = URL.create(
    "postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# SQLAlchemy Engine Options - Connection Pool
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,           # 連線池大小 (預設 5)
    'pool_pre_ping': True,     # 檢查連線有效性
    'pool_recycle': 3600,      # 每小時回收連線
    'max_overflow': 5,         # 允許額外連線 (超過 pool_size)
}
