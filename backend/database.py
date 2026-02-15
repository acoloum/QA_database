import psycopg2
from .config import POSTGRESQL_CONFIG

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    return psycopg2.connect(**POSTGRESQL_CONFIG)
