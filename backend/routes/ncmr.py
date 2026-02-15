from flask import Blueprint, jsonify, request
from datetime import datetime
from ..utils import (
    get_db_connection,
    format_value,
    auth_required,
    handle_db_error,
    generate_ncmr_number,
    generate_car_number,
    generate_8d_number,
    verify_token
)

ncmr_bp = Blueprint('ncmr', __name__)

# ==================================================
# 【不合格品管理】NCMR API
# ==================================================

@ncmr_bp.route('/api/ncmr', methods=['GET'])
def get_ncmr_list():
    status = request.args.get('status')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT T1."識別碼", T1."NCMR單號" AS 單號, 
                   T1."發現日期" AS 日期, 
                   T1."來源", 
                   T1."產品資訊", T1."產品數量", T1."材質", T1."廠商", T1."批號",
                   T1."不良描述", T1."不良數量" AS 不合格數量,
                   T1."判定結果", T1."狀態",
                   T1."不良原因大類", T1."不良原因細項",
                   P."姓名" AS 發現人員姓名,
                   (SELECT "狀態" FROM "異常矯正單" WHERE "NCMR_ID" = T1."識別碼" AND "CAR單號" IS NOT NULL ORDER BY "識別碼" DESC LIMIT 1) AS CAR狀態,
                   (SELECT "狀態" FROM "異常矯正單" WHERE "NCMR_ID" = T1."識別碼" AND "8D單號" IS NOT NULL ORDER BY "識別碼" DESC LIMIT 1) AS CAPA狀態,
                   (SELECT COUNT(*) FROM "重工執行記錄" WHERE "重工單號" IN (SELECT "識別碼" FROM "重工申請單" WHERE "NCMR_ID" = T1."識別碼")) AS 重工執行次數,
                   (SELECT "狀態" FROM "重工申請單" WHERE "NCMR_ID" = T1."識別碼" ORDER BY "識別碼" DESC LIMIT 1) AS 重工狀態
            FROM "不合格品單" T1
            LEFT JOIN "品管人員" P ON T1."發現人員" = P."識別碼"
        """
        params = []
        if status:
            sql += ' WHERE T1."狀態" = %s'
            params.append(status)
        
        sql += ' ORDER BY T1."識別碼" DESC'
        
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        data = []
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 使用 format_value() 統一格式化所有值
            for key, val in item.items():
                item[key] = format_value(val)
            data.append(item)
            
        return jsonify(data)
    finally:
        conn.close()

@ncmr_bp.route('/api/ncmr/add', methods=['POST'])
@auth_required
def add_ncmr():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 轉換發現人員 ID
        inspector_id = None
        if data.get('發現人員姓名'):
            cursor.execute('''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''', (data.get('發現人員姓名'),))
            row = cursor.fetchone()
            if row:
                inspector_id = row[0]
        
        # 生成NCMR編號
        ncmr_number = generate_ncmr_number()
        
        sql = """
            INSERT INTO "不合格品單" 
            ("NCMR單號", "發現日期", "來源", "產品資訊", "產品數量", "材質", "廠商", "批號", "不良描述", "不良數量", "發現人員", "判定結果", "狀態", "不良原因大類", "不良原因細項")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            ncmr_number,
            data.get('日期'),
            data.get('來源'),
            data.get('產品資訊'), 
            data.get('產品數量') if data.get('產品數量') != '' else None,
            data.get('材質'),
            data.get('廠商'),
            data.get('批號'),
            data.get('不良描述'),
            data.get('不合格數量') if data.get('不合格數量') != '' else None,
            inspector_id,
            data.get('判定結果'),
            data.get('狀態', '待處理'),
            data.get('不良原因大類'),
            data.get('不良原因細項')
        ))
        conn.commit()
        return jsonify({"success": True, "ncmr_number": ncmr_number})  # 返回新編號
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/ncmr/update', methods=['POST'])
@auth_required
def update_ncmr():
    """更新 NCMR 記錄"""
    data = request.json
    ncmr_id = data.get('識別碼')
    
    if not ncmr_id:
        return jsonify({"error": "缺少識別碼"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 轉換發現人員 ID
        inspector_id = None
        if data.get('發現人員姓名'):
            cursor.execute('''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''', (data.get('發現人員姓名'),))
            row = cursor.fetchone()
            if row:
                inspector_id = row[0]
        
        fields = []
        params = []
        
        # 可更新的欄位
        updateable_fields = {
            '"發現日期"': data.get('日期'),
            '"來源"': data.get('來源'),
            '"產品資訊"': data.get('產品資訊'),
            '"產品數量"': data.get('產品數量'),
            '"材質"': data.get('材質'),
            '"廠商"': data.get('廠商'),
            '"批號"': data.get('批號'),
            '"不良描述"': data.get('不良描述'),
            '"不良數量"': data.get('不合格數量'),
            '"判定結果"': data.get('判定結果'),
            '"狀態"': data.get('狀態'),
            '"不良原因大類"': data.get('不良原因大類'),
            '"不良原因細項"': data.get('不良原因細項')
        }
        
        for field, value in updateable_fields.items():
            if value is not None:
                fields.append(f"{field} = %s")
                params.append(value)
        
        if inspector_id is not None:
            fields.append('"發現人員" = %s')
            params.append(inspector_id)
        
        if not fields:
            return jsonify({"success": True})
        
        params.append(ncmr_id)
        sql = f'UPDATE "不合格品單" SET {", ".join(fields)} WHERE "識別碼" = %s'
        cursor.execute(sql, params)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/ncmr/delete', methods=['POST'])
@auth_required # Added auth_required for safety
def delete_ncmr():
    data = request.json
    ncmr_id = data.get('id')
    if not ncmr_id:
        return jsonify({"error": "缺少識別碼"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 先刪除關聯的異常矯正單 (CAR/CAPA)
        cursor.execute('''DELETE FROM "異常矯正單" WHERE "NCMR_ID" = %s''', (ncmr_id,))
        
        # 再刪除 NCMR 主檔
        cursor.execute('''DELETE FROM "不合格品單" WHERE 識別碼 = %s''', (ncmr_id,))

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/ncmr/source_info', methods=['GET'])
def get_source_info():
    source_type = request.args.get('type')
    source_id = request.args.get('id')
    
    if not source_type or not source_id:
        return jsonify({})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        info = {}
        if source_type == '巡檢':
            cursor.execute("""
                SELECT T.材質, T.擠壓規格, T.原料批號, C.廠商名稱 
                FROM "巡檢主檔" T
                LEFT JOIN "廠商資料" C ON T.客戶名稱 = C.識別碼
                WHERE T.識別碼 = %s
            """, (source_id,))
            row = cursor.fetchone()
            if row:
                info = {
                    "材質": row[0],
                    "產品資訊": row[1], # 規格
                    "批號": row[2],
                    "廠商": row[3]
                }
        elif source_type == '出貨檢':
            cursor.execute("""
                SELECT T.材質, T.檢驗規格, T.訂單號碼, V.廠商名稱 
                FROM "出貨檢驗數據" T
                LEFT JOIN "廠商資料" V ON T.廠商名稱 = V.識別碼
                WHERE T.識別碼 = %s
            """, (source_id,))
            row = cursor.fetchone()
            if row:
                info = {
                    "材質": row[0],
                    "產品資訊": row[1], # 規格
                    "批號": row[2], # 訂單號碼
                    "廠商": row[3]
                }
        return jsonify(info)
    finally:
        conn.close()


# ==================================================
# 【CAR矯正】API
# ==================================================

@ncmr_bp.route('/api/cara', methods=['GET'])
def get_cara_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT T1.*, T1."CAR單號" AS "單號", T1."NCMR_ID" AS "ncmr_id", 
                   N."NCMR單號" AS "ncmr_number", N."發現日期" AS "ncmr_date", N."來源" AS "ncmr_source",
                   N."不良描述" AS "ncmr_description", N."廠商" AS "ncmr_vendor", 
                   N."材質" AS "ncmr_material", N."產品資訊" AS "ncmr_product",
                   P."姓名" AS "負責人員姓名"
            FROM "異常矯正單" T1
            LEFT JOIN "不合格品單" N ON T1."NCMR_ID" = N."識別碼"
            LEFT JOIN "品管人員" P ON T1."負責人員" = P."識別碼"
            WHERE T1."CAR單號" IS NOT NULL
            ORDER BY T1."識別碼" DESC
        """
        cursor.execute(sql)
        cols = [c[0] for c in cursor.description]
        data = []
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 使用 format_value() 統一格式化所有值
            for key, val in item.items():
                item[key] = format_value(val)
            data.append(item)
        return jsonify(data)
    finally:
        conn.close()

@ncmr_bp.route('/api/cara/create', methods=['POST'])
def create_cara():
    data = request.json
    ncmr_id = data.get('ncmr_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查是否已存在CAR
        cursor.execute('''SELECT "識別碼" FROM "異常矯正單" WHERE "NCMR_ID" = %s AND "CAR單號" IS NOT NULL''', (ncmr_id,))
        if cursor.fetchone():
            return jsonify({"error": "此異常單已開立過CAR"}), 400
            
        # 獲取NCMR完整資訊
        cursor.execute(
            '''SELECT "NCMR單號" FROM "不合格品單" WHERE "識別碼" = %s''',
            (ncmr_id,)
        )
        ncmr = cursor.fetchone()
        ncmr_number = ncmr[0] if ncmr else ""
        
        # 生成CAR編號
        car_number = generate_car_number()
        
        # 建立CAR單
        cursor.execute("""
            INSERT INTO "異常矯正單" ("CAR單號", "NCMR_ID", "狀態")
            VALUES (%s, %s, '進行中')
        """, (car_number, ncmr_id))
        
        # 更新 NCMR 狀態
        cursor.execute('''UPDATE "不合格品單" SET "狀態" = 'CAR處理中' WHERE "識別碼" = %s''', (ncmr_id,))
        
        conn.commit()
        return jsonify({"success": True, "car_number": car_number, "ncmr_number": ncmr_number})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/cara/detail/<int:id>')
def get_cara_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 取得 CAR 詳細
        sql = """
            SELECT T1.*, T1."CAR單號" AS "單號", P."姓名" AS "負責人員姓名"
            FROM "異常矯正單" T1
            LEFT JOIN "品管人員" P ON T1."負責人員" = P."識別碼"
            WHERE T1."識別碼" = %s AND T1."CAR單號" IS NOT NULL
        """
        cursor.execute(sql, (id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到資料"}), 404
            
        cols = [c[0] for c in cursor.description]
        cara_data = dict(zip(cols, row))
        
        # 處理日期
        for date_col in ['建立日期', '結案日期']:
            if cara_data.get(date_col):
                cara_data[date_col] = cara_data[date_col].strftime('%Y-%m-%d')

        # 取得關聯的 NCMR 詳細
        cursor.execute("""
            SELECT n.*, p."姓名" AS "發現人員姓名", v."廠商名稱" AS "廠商中文名稱"
            FROM "不合格品單" n
            LEFT JOIN "品管人員" p ON n."發現人員" = p."識別碼"
            LEFT JOIN "廠商資料" v ON n."廠商" = v."廠商名稱"
            WHERE n."識別碼" = %s
        """, (cara_data.get('NCMR_ID'),))
        ncmr_row = cursor.fetchone()
        if ncmr_row:
            ncmr_cols = [c[0] for c in cursor.description]
            ncmr_data = dict(zip(ncmr_cols, ncmr_row))
            if ncmr_data.get('發現日期'): ncmr_data['發現日期'] = ncmr_data['發現日期'].strftime('%Y-%m-%d')
        else:
            ncmr_data = {}

        return jsonify({"cara": cara_data, "ncmr": ncmr_data})
    finally:
        conn.close()

@ncmr_bp.route('/api/cara/update', methods=['POST'])
def update_cara(): # Note: Route path matches original, but function name is update_cara
    data = request.json
    cara_id = data.get('識別碼')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        fields = []
        params = []
        
        # 處理負責人員
        if data.get('負責人員姓名'):
            cursor.execute('''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''', (data.get('負責人員姓名'),))
            row = cursor.fetchone()
            if row:
                fields.append('"負責人員" = %s')
                params.append(row[0])

        # 處理 CAR D 欄位
        d_fields_map = {
            'D2_問題描述': 'D2_問題描述',
            'D3_暫時對策': 'D3_暫時對策',
            'D4_真因分析': 'D4_真因分析',
            'D6_成效驗證': 'D6_成效驗證',
            'D7_預防再發': 'D7_預防再發',
            'D8_結案確認': 'D8_結案確認'
        }
        
        for db_field, frontend_field in d_fields_map.items():
            if frontend_field in data and data[frontend_field]:
                fields.append(f'"{db_field}" = %s')
                params.append(data[frontend_field])
        
        # 處理狀態
        if data.get('狀態'):
            fields.append('"狀態" = %s')
            params.append(data['狀態'])
                
        # 如果狀態改為已結案，更新結案日期和 NCMR 狀態
        if data.get('狀態') == '已結案':
            fields.append('"結案日期" = CURRENT_TIMESTAMP')
            # 先獲取 NCMR_ID，再更新 NCMR 狀態為 CAR已完成
            cursor.execute('''SELECT "NCMR_ID" FROM "異常矯正單" WHERE "識別碼" = %s''', (cara_id,))
            ncmr_result = cursor.fetchone()
            if ncmr_result:
                ncmr_id = ncmr_result[0]
                cursor.execute('''UPDATE "不合格品單" SET "狀態" = 'CAR已完成' WHERE "識別碼" = %s''', (ncmr_id,))
        
        if not fields:
            return jsonify({"success": True})
            
        params.append(cara_id)
        sql = f'UPDATE "異常矯正單" SET {", ".join(fields)} WHERE "識別碼" = %s'
        cursor.execute(sql, params)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/cara/delete', methods=['POST'])
@auth_required
def delete_cara():
    """刪除 CAR 記錄"""
    data = request.json
    cara_id = data.get('id')
    if not cara_id:
        return jsonify({"error": "缺少識別碼"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 刪除 CAR 記錄
        cursor.execute('''DELETE FROM "異常矯正單" WHERE "識別碼" = %s AND "CAR單號" IS NOT NULL''', (cara_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【異常矯正】CAPA API (8D)
# ==================================================

@ncmr_bp.route('/api/capa', methods=['GET'])
def get_capa_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
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
            item = dict(zip(cols, row))
            # 使用 format_value() 統一格式化所有值
            for key, val in item.items():
                item[key] = format_value(val)
            data.append(item)
        return jsonify(data)
    finally:
        conn.close()

@ncmr_bp.route('/api/capa/create', methods=['POST'])
def create_capa():
    data = request.json
    ncmr_id = data.get('ncmr_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查是否已存在
        cursor.execute('''SELECT "識別碼" FROM "異常矯正單" WHERE "NCMR_ID" = %s''', (ncmr_id,))
        if cursor.fetchone():
            return jsonify({"error": "此異常單已開立過矯正單"}), 400
            
        # 獲取NCMR完整資訊
        cursor.execute(
            '''SELECT "NCMR單號" FROM "不合格品單" WHERE "識別碼" = %s''',
            (ncmr_id,)
        )
        ncmr = cursor.fetchone()
        ncmr_number = ncmr[0] if ncmr else ""
        
        # 生成8D編號
        capa_number = generate_8d_number()
        
        # 建立矯正單
        cursor.execute("""
            INSERT INTO "異常矯正單" ("8D單號", "NCMR_ID", "狀態")
            VALUES (%s, %s, '進行中')
            RETURNING "識別碼"
        """, (capa_number, ncmr_id))
        new_id = cursor.fetchone()[0]
        
        # 更新 NCMR 狀態
        cursor.execute('''UPDATE "不合格品單" SET "狀態" = '矯正中' WHERE "識別碼" = %s''', (ncmr_id,))
        
        conn.commit()
        return jsonify({"success": True, "capa_number": capa_number, "ncmr_number": ncmr_number, "id": new_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/capa/detail/<int:id>')
def get_capa_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 取得 CAPA 詳細
        sql = """
            SELECT T1.*, P.姓名 AS 負責人員姓名
            FROM "異常矯正單" T1
            LEFT JOIN "品管人員" P ON T1.負責人員 = P.識別碼
            WHERE T1.識別碼 = %s
        """
        cursor.execute(sql, (id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到資料"}), 404
            
        cols = [c[0] for c in cursor.description]
        capa_data = dict(zip(cols, row))
        
        # 處理日期
        for date_col in ['建立日期', '結案日期']:
            if capa_data.get(date_col):
                capa_data[date_col] = capa_data[date_col].strftime('%Y-%m-%d')

        # 取得關聯的 NCMR 詳細
        cursor.execute("""
            SELECT n.*, p.姓名 AS 發現人員姓名, v.廠商名稱 AS 廠商中文名稱
            FROM "不合格品單" n
            LEFT JOIN "品管人員" p ON n.發現人員 = p.識別碼
            LEFT JOIN "廠商資料" v ON n.廠商 = v.廠商名稱
            WHERE n.識別碼 = %s
        """, (capa_data.get('NCMR_ID'),))
        ncmr_row = cursor.fetchone()
        if ncmr_row:
            ncmr_cols = [c[0] for c in cursor.description]
            ncmr_data = dict(zip(ncmr_cols, ncmr_row))
            if ncmr_data.get('發現日期'): ncmr_data['發現日期'] = ncmr_data['發現日期'].strftime('%Y-%m-%d')
        else:
            ncmr_data = {}

        return jsonify({"capa": capa_data, "ncmr": ncmr_data})
    finally:
        conn.close()

@ncmr_bp.route('/api/capa/update', methods=['POST'])
def update_capa():
    data = request.json
    capa_id = data.get('識別碼')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 處理負責人員
        if data.get('負責人員姓名'):
            cursor.execute('''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''', (data.get('負責人員姓名'),))
            row = cursor.fetchone()
            if row:
                data['負責人員'] = row[0]

        fields = []
        params = []
        
        # CAPA 可更新欄位
        updatable_fields = ['狀態', '負責人員', 'D1_小組成員', 'D2_問題描述', 'D3_暫時對策', 
                           'D4_真因分析', 'D5_永久對策', 'D6_成效驗證', 'D7_預防再發', 'D8_結案確認']
        
        for f in updatable_fields:
            if f in data and data[f] is not None:
                fields.append(f'"{f}" = %s')
                params.append(data[f])
        
        # 如果狀態改為已結案，更新結案日期和 NCMR 狀態
        if data.get('狀態') == '已結案':
            fields.append('"結案日期" = CURRENT_TIMESTAMP')
            # 更新 NCMR 狀態為 CAPA已完成
            cursor.execute('''UPDATE "不合格品單" SET "狀態" = 'CAPA已完成' WHERE "識別碼" = %s''', (data.get('NCMR_ID'),))
        
        if not fields:
            return jsonify({"success": True})
            
        params.append(capa_id)
        sql = f'UPDATE "異常矯正單" SET {", ".join(fields)} WHERE "識別碼" = %s'
        cursor.execute(sql, params)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/capa/delete', methods=['POST'])
@auth_required
def delete_capa():
    """刪除 CAPA 記錄"""
    data = request.json
    capa_id = data.get('id')
    if not capa_id:
        return jsonify({"error": "缺少識別碼"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 刪除 CAPA 記錄
        cursor.execute('''DELETE FROM "異常矯正單" WHERE "識別碼" = %s AND "8D單號" IS NOT NULL''', (capa_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@ncmr_bp.route('/api/ncmr/<int:ncmr_id>', methods=['GET'])
@auth_required
def get_ncmr_info(ncmr_id):
    """獲取NCMR詳細資訊"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT n.*, 
                   p."姓名" AS "發現人員姓名",
                   v."廠商名稱" AS "廠商中文名稱"
            FROM "不合格品單" n
            LEFT JOIN "品管人員" p ON n."發現人員" = p."識別碼"
            LEFT JOIN "廠商資料" v ON n."廠商" = v."廠商名稱"
            WHERE n."識別碼" = %s
        """
        cursor.execute(sql, (ncmr_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "找不到NCMR記錄"}), 404
            
        cols = [c[0] for c in cursor.description]
        item = {}
        for i, col in enumerate(cols):
            value = row[i]
            # 欄位名稱映射：資料庫欄位 -> 前端欄位
            field_mapping = {
                '發現日期': '日期',
                '不良數量': '不合格數量'
            }
            
            # 使用映射後的欄位名稱
            final_col = field_mapping.get(col, col)
            
            try:
                if value is None:
                    item[final_col] = ""
                elif isinstance(value, datetime):
                    if '時間' in final_col:
                        item[final_col] = value.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        item[final_col] = value.strftime('%Y-%m-%d')
                else:
                    # 如果是字串，先嘗試轉換為日期
                    if isinstance(value, str) and final_col == '日期':
                        try:
                            dt = datetime.strptime(value.strip(), '%Y-%m-%d')
                            item[final_col] = dt.strftime('%Y-%m-%d')
                        except ValueError:
                            item[final_col] = value.strip()
                    else:
                        item[final_col] = str(value) if hasattr(value, 'strip') else value
            except Exception as e:
                print(f"處理欄位 {final_col} 時出錯: {e}")
                item[final_col] = ""
        
        return jsonify(item)
        
    except Exception as e:
        return jsonify({"error": f"獲取NCMR資訊失敗: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()
