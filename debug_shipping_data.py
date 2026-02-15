from app_postgresql import get_db_connection
import json

def check_shipping_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get sample valid data
        print("=== Checking Sample Data ===")
        cursor.execute('SELECT "廠商名稱", "材質", "檢驗規格" FROM "出貨檢驗數據" LIMIT 5')
        rows = cursor.fetchall()
        for row in rows:
            print(f"VendorID: {row[0]}, Material: {row[1]}, Spec: {row[2]}")
            
        # Get Vendor Name for first row
        if rows:
            vendor_id = rows[0][0]
            cursor.execute('SELECT "廠商名稱" FROM "廠商資料" WHERE "識別碼" = %s', (vendor_id,))
            vendor_name = cursor.fetchone()
            print(f"Vendor Name for ID {vendor_id}: {vendor_name[0] if vendor_name else 'Unknown'}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_shipping_data()
