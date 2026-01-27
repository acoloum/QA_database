import hashlib
import pyodbc

# 資料庫連線設定
SERVER = 'YOUR_SERVER_NAME'
DATABASE = 'YOUR_DATABASE_NAME'
USERNAME = 'YOUR_DB_USERNAME'
PASSWORD = 'YOUR_DB_PASSWORD'
DRIVER = 'ODBC Driver 18 for SQL Server'

def get_db_connection():
    conn_str = f'DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Connection Timeout=30;'
    return pyodbc.connect(conn_str)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 識別碼 FROM dbo.使用者 WHERE 使用者名稱 = ?",
            (username,)
        )
        if cursor.fetchone():
            print(f"使用者 '{username}' 已存在")
            return False

        cursor.execute(
            "INSERT INTO dbo.使用者 (使用者名稱, 密碼, 是否啟用) VALUES (?, ?, 1)",
            (username, hash_password(password))
        )
        conn.commit()
        print(f"✓ 使用者 '{username}' 建立成功")
        return True
    except Exception as e:
        conn.rollback()
        print(f"✗ 建立失敗: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("=== 建立使用者 ===")
    username = input("請輸入使用者名稱: ")
    password = input("請輸入密碼: ")
    confirm = input("請再次輸入密碼: ")
    
    if password != confirm:
        print("✗ 密碼不一致")
        exit(1)
    
    if create_user(username, password):
        print("完成！")
