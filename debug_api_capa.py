import json
from datetime import datetime, date
import decimal
from app_postgresql import get_db_connection

def format_value(val):
    if isinstance(val, (decimal.Decimal, float)):
        return float(val)
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d')
    if isinstance(val, date):  # 處理 date 類型
        return val.strftime('%Y-%m-%d')
    if isinstance(val, bytes):
        return val.hex()
    if isinstance(val, str):
        return val.strip()
    return val if val is not None else ""

def get_capa_list_debug():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        print("=== 模擬 GET /api/capa ===")
        sql = """
            SELECT T1."識別碼", T1."NCMR_ID", T1."8D單號", T1."CAR單號", 
                   T1."負責人員", T1."問題描述", T1."根本原因", T1."矯正措施", 
                   T1."預防措施", T1."狀態", 
                   T1."建立時間" AS "建立日期", 
                   T1."完成時間" AS "結案日期",
                   P."姓名" AS "負責人員姓名", N."來源", N."不良描述", 
                   N."廠商", N."材質", N."產品資訊" AS "規格", N."NCMR單號", 
                   N."發現日期" AS "ncmr_date"
            FROM "異常矯正單" T1
            LEFT JOIN "品管人員" P ON T1."負責人員" = P."識別碼"
            LEFT JOIN "不合格品單" N ON T1."NCMR_ID" = N."識別碼"
            WHERE T1."8D單號" IS NOT NULL
            ORDER BY T1."識別碼" DESC
        """
        cursor.execute(sql)
        cols = [c[0] for c in cursor.description]
        data = []
        for row in cursor.fetchall():
            try:
                item = dict(zip(cols, row))
                # 使用 format_value() 統一格式化所有值
                for key, val in item.items():
                    item[key] = format_value(val)
                data.append(item)
            except Exception as e:
                print(f"Row processing error: {e}")
                print(f"Row data: {row}")

        print(f"Successfully processed {len(data)} records.")
        print("First record sample:", json.dumps(data[0], indent=2, ensure_ascii=False) if data else "No data")
        
    except Exception as e:
        print(f"Global error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    get_capa_list_debug()
