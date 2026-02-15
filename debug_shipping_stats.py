from app_postgresql import get_db_connection
import numpy as np
import decimal

def debug_stats():
    # Simulation parameters
    field = '外徑'
    vendor = '品岳'
    material = '6061-H'
    spec = '31.9*2.8*500'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print(f"Testing stats for: Vendor={vendor}, Material={material}, Spec={spec}, Field={field}")
        
        # 1. Check Tolerance Logic
        print("\n--- Checking Tolerance ---")
        cursor.execute("""
            SELECT T1."識別碼"
            FROM "廠商公差主檔" T1
            WHERE T1."材質" = %s
            LIMIT 1
        """, (material,))
        tol_main = cursor.fetchone()
        print(f"Tolerance Main ID: {tol_main[0] if tol_main else 'Not Found'}")
        
        if tol_main:
            cursor.execute("""
                SELECT "公差下限", "公差上限", "尺寸下限", "尺寸上限"
                FROM "廠商公差明細檔"
                WHERE "主檔ID" = %s AND "測量項目" = %s
            """, (tol_main[0], field))
            tol_detail = cursor.fetchone()
            print(f"Tolerance Detail: {tol_detail}")

        # 2. Check Data Query
        print("\n--- Checking Data Query ---")
        where = []
        params = []
        if vendor: where.append('V."廠商名稱" LIKE %s'); params.append(f"%{vendor}%")
        if material: where.append('T1."材質" LIKE %s'); params.append(f"%{material}%")
        if spec: where.append('T1."檢驗規格" LIKE %s'); params.append(f"%{spec}%")
        
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        
        sql = f"""
            SELECT T1.識別碼, T1.檢驗日期,
                   T1."{field}1-min", T1."{field}1-max",
                   T1."{field}2-min", T1."{field}2-max",
                   T1."{field}3-min", T1."{field}3-max"
            FROM "出貨檢驗數據" T1
            LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
            {where_sql}
        """
        print(f"SQL: {sql}")
        print(f"Params: {params}")
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        print(f"Found {len(rows)} rows")
        
        # 3. Process first row
        if rows:
            r = rows[0]
            print(f"First Row: {r}")
            vals = []
            valid_groups = 0
            # Check groups 1-3 (indexes 2-7)
            for i in range(2, 8, 2):
                v1 = r[i]
                v2 = r[i+1]
                print(f"  Group {(i-2)//2 + 1}: {v1}, {v2}")
                if v1 is not None and v2 is not None:
                     val = (float(v1) + float(v2)) / 2
                     vals.append(val)
                     valid_groups += 1
            print(f"  Valid Groups: {valid_groups}")
            
            # Test JSON Serialization
            import json
            class DecimalEncoder(json.JSONEncoder):
                def default(self, o):
                    if isinstance(o, decimal.Decimal):
                        return float(o)
                    return super(DecimalEncoder, self).default(o)
            
            try:
                # Flask's jsonify uses a different mechanism, but let's test basic json dump
                # In app_postgresql.py, does it handle Decimal?
                # It imports decimal but doesn't seem to set a default encoder in the snippet I saw.
                # However, psycopg2 might return Decimal.
                print("Testing Serialization...")
                json.dumps(vals) # vals are floats because of float() cast in loop
                print("Vals serialization OK")
                
                # Check r (raw row)
                # json.dumps(r) # This will fail if r contains Decimal and no encoder
            except Exception as e:
                print(f"Serialization Error: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    debug_stats()
