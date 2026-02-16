import os


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
SECRET_KEY = os.getenv('SECRET_KEY', 'qa-inspection-system-2026-secure-key-a7b9c3d5e1f2g4h6')
TOKEN_EXPIRATION_HOURS = 24


# SQLAlchemy Configuration
SQLALCHEMY_DATABASE_URI = f"postgresql://{POSTGRESQL_CONFIG['user']}:{POSTGRESQL_CONFIG['password']}@{POSTGRESQL_CONFIG['host']}:{POSTGRESQL_CONFIG['port']}/{POSTGRESQL_CONFIG['database']}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
