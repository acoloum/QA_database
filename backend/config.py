import os


# Import original config to keep credentials valid
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from config import POSTGRESQL_CONFIG as ORIG_PG_CONFIG
    POSTGRESQL_CONFIG = ORIG_PG_CONFIG
except ImportError:
    # Fallback if cannot import
    POSTGRESQL_CONFIG = {
        'dbname': 'qa_system',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': 5432
    }


# Security Configuration
SECRET_KEY = 'qa-inspection-system-2026-secure-key-a7b9c3d5e1f2g4h6'
TOKEN_EXPIRATION_HOURS = 24
