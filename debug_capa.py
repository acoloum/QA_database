from app_postgresql import get_db_connection

def debug_capa():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        print("=== 檢查異常矯正單 (CAPA) ===")
        cursor.execute('SELECT "識別碼", "8D單號", "NCMR_ID", "建立時間" FROM "異常矯正單"')
        rows = cursor.fetchall()
        print(f"總筆數: {len(rows)}")
        for row in rows:
            print(f"ID: {row[0]}, 8D單號: {row[1]}, NCMR_ID: {row[2]}, 時間: {row[3]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    debug_capa()
