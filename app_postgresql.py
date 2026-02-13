import os
import secrets

from flask import Flask, jsonify, request, send_file, session
from flask_cors import CORS
import psycopg2
import decimal
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone, date
from io import BytesIO
import openpyxl
import jwt
import hashlib
from functools import wraps
from config import POSTGRESQL_CONFIG
import re

# ==================================================
# XSS Protection Module
# ==================================================
try:
    from markupsafe import escape as _escape
    def escape(s):
        if s is None:
            return ''
        return _escape(str(s))
except ImportError:
    # Fallback if markupsafe not available
    import html
    def escape(s):
        """Escape HTML characters"""
        if s is None:
            return ''
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')

def sanitize_html(text):
    """Remove dangerous HTML tags while preserving safe formatting"""
    if text is None:
        return ''
    text = str(text)
    
    # Escape all HTML first
    escaped = escape(text)
    
    # Allow specific safe tags
    safe_patterns = [
        (r'&lt;br&gt;', '<br>'),
        (r'&lt;br/&gt;', '<br/>'),
        (r'&lt;strong&gt;', '<strong>'),
        (r'&lt;/strong&gt;', '</strong>'),
        (r'&lt;em&gt;', '<em>'),
        (r'&lt;/em&gt;', '</em>'),
    ]
    
    for pattern, replacement in safe_patterns:
        escaped = re.sub(pattern, replacement, escaped, flags=re.IGNORECASE)
    
    return escaped

def sanitize_input(data):
    """Recursively sanitize all string values in a dictionary/list"""
    if isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    elif isinstance(data, str):
        return sanitize_html(data)
    else:
        return data

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Session 密鑰
CORS(app, supports_credentials=True)  # 啟用 credentials 支援

# ==================================================
# XSS Protection Helper
# ==================================================
def get_sanitized_json():
    """Get and sanitize JSON data from request"""
    json_data = request.get_json(silent=True)
    if json_data:
        return sanitize_input(json_data)
    return json_data


# ==================================================
# CSRF Protection
# ==================================================
import secrets

# 簡單的 CSRF token 產生器 (生產環境可使用 flask-wtf)
def generate_csrf_token():
    """Generate a CSRF token for the session"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate CSRF token"""
    session_token = session.get('csrf_token')
    if not session_token or not token:
        return False
    return secrets.compare_digest(session_token, token)


SECRET_KEY = 'qa-inspection-system-2026-secure-key-a7b9c3d5e1f2g4h6'  # 已更換為安全密鑰
TOKEN_EXPIRATION_HOURS = 24

# ==================================================
# DB Connection (PostgreSQL)
# ==================================================
def get_db_connection():
    return psycopg2.connect(**POSTGRESQL_CONFIG)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token(user_id, username):
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': '缺少認證 Token'}), 401
        if token.startswith('Bearer '):
            token = token[7:]
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': '無效或過期的 Token'}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated

def handle_db_error(e):
    error_msg = str(e)
    if 'FOREIGN KEY' in error_msg:
        return '關聯資料錯誤：請檢查相關資料是否存在'
    elif 'UNIQUE' in error_msg:
        return '資料重複：此筆資料已存在'
    elif 'NOT NULL' in error_msg:
        return '資料不完整：請填寫所有必填欄位'
    elif 'timeout' in error_msg.lower():
        return '資料庫連線逾時，請稍後再試'
    elif 'connection' in error_msg.lower():
        return '資料庫連線失敗，請檢查連線設定'
    elif 'login' in error_msg.lower() or 'authentication' in error_msg.lower():
        return '資料庫認證失敗，請檢查連線設定'
    else:
        return f'資料庫錯誤：{error_msg}'

# ==================================================
# 【編碼生成】工具函數
# ==================================================
def generate_number(prefix, table_name=None, number_field=None):
    """
    統一編碼生成函數
    格式：PREFIX-YYYYMM-XXX (例：NCMR-202601-001)
    """
    year_month = datetime.now().strftime('%Y%m')
    
    if table_name and number_field:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 簡化查詢 - 使用純字串處理，欄位名稱加雙引號
            sql = f"""
                SELECT "{number_field}" 
                FROM "{table_name}" 
                WHERE "{number_field}" IS NOT NULL 
                AND "{number_field}" LIKE %s
                ORDER BY "{number_field}" DESC
            """
            pattern = f"{prefix}-{year_month}-%"
            cursor.execute(sql, (pattern,))
            
            # 取出所有匹配的記錄
            results = cursor.fetchall()
            max_seq = 0
            
            if results:
                for row in results:
                    if row[0]:
                        # 從完整編號中提取流水號部分
                        parts = row[0].split('-')
                        if len(parts) >= 3:
                            try:
                                seq = int(parts[-1])
                                max_seq = max(max_seq, seq)
                            except (ValueError, IndexError):
                                continue
            
            new_seq = str(max_seq + 1).zfill(3)
            return f"{prefix}-{year_month}-{new_seq}"
        finally:
            conn.close()
    else:
        # 簡單格式，用於測試或預覽
        return f"{prefix}-{year_month}-001"

def generate_ncmr_number():
    """生成NCMR編號"""
    return generate_number('NCMR', "不合格品單", 'NCMR單號')

def generate_8d_number():
    """生成8D編號"""
    return generate_number('CAPA', "異常矯正單", "8D單號")

def generate_car_number():
    """生成CAR編號"""
    return generate_number('CAR', "異常矯正單", 'CAR單號')

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

def validate_date_format(date_str):
    if not date_str:
        return True
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_inspection_data(data):
    errors = []
    if not data.get('檢驗日期'):
        errors.append("檢驗日期為必填欄位")
    elif not validate_date_format(data.get('檢驗日期')):
        errors.append("檢驗日期格式錯誤，應為 YYYY-MM-DD")
    if not data.get('廠商中文名稱'):
        errors.append("廠商為必填欄位")
    if not data.get('材質'):
        errors.append("材質為必填欄位")
    if not data.get('檢驗規格'):
        errors.append("檢驗規格為必填欄位")
    if not data.get('檢驗人員姓名'):
        errors.append("檢驗人員為必填欄位")
    return errors

def validate_patrol_data(data):
    errors = []
    if not data.get('檢驗日期'):
        errors.append("檢驗日期為必填欄位")
    elif not validate_date_format(data.get('檢驗日期')):
        errors.append("檢驗日期格式錯誤，應為 YYYY-MM-DD")
    if not data.get('機台'):
        errors.append("機台為必填欄位")
    if not data.get('檢驗人員'):
        errors.append("檢驗人員為必填欄位")
    if not data.get('details') or len(data.get('details', [])) == 0:
        errors.append("明細資料為必填欄位")
    return errors

# ==================================================
# 【基礎資料】API
# ==================================================
@app.route('/api/inspectors')
def get_inspectors():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 姓名 FROM "品管人員"''')
        inspectors = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(inspectors)
    finally:
        conn.close()

@app.route('/api/vendors')
def get_vendors():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 廠商名稱 FROM "廠商資料"''')
        vendors = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(vendors)
    finally:
        conn.close()

@app.route('/api/machines')
def get_machines():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 擠壓機編號 FROM "擠壓機台"''')
        machines = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(machines)
    finally:
        conn.close()

@app.route('/api/operators')
def get_operators():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 員工姓名 FROM "擠壓人員"''')
        operators = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(operators)
    finally:
        conn.close()

@app.route('/api/materials')
def get_materials():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT DISTINCT "材質" FROM "出貨檢驗數據" WHERE "材質" IS NOT NULL''')
        materials = [row[0].strip() for row in cursor.fetchall()]
        return jsonify(materials)
    finally:
        conn.close()

@app.route('/api/specs')
def get_specs():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT DISTINCT "檢驗規格" FROM "出貨檢驗數據" WHERE "檢驗規格" IS NOT NULL''')
        specs = [row[0].strip() for row in cursor.fetchall()]
        return jsonify(specs)
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】主資料
# ==================================================
@app.route('/api/data', methods=['GET'])
def get_data():
    args = request.args
    params = []
    where = []

    # 支援按 ID 查詢（優先處理）
    if args.get('id'):
        where.append("T1.識別碼 = %s")
        params.append(args['id'])
    else:
        # 一般查詢條件
        if args.get('vendor'):   where.append("V.廠商名稱 LIKE %s"); params.append(f"%{args['vendor']}%")
        if args.get('material'): where.append("T1.材質 LIKE %s");     params.append(f"%{args['material']}%")
        if args.get('spec'):     where.append("T1.檢驗規格 LIKE %s"); params.append(f"%{args['spec']}%")
        if args.get('start_date'): where.append("T1.檢驗日期 >= %s"); params.append(args['start_date'])
        if args.get('end_date'):   where.append("T1.檢驗日期 <= %s"); params.append(args['end_date'])

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T1.識別碼, T1.檢驗日期, T1.材質, T1.檢驗規格, T1.訂單號碼,
                   P.姓名 AS 檢驗人員, V.廠商名稱 AS 廠商中文名稱,
                   T1."外徑1-min", T1."外徑1-max", T1."外徑2-min", T1."外徑2-max",
                   T1."外徑3-min", T1."外徑3-max", T1."外徑4-min", T1."外徑4-max",
                   T1."外徑5-min", T1."外徑5-max",
                   T1."內徑1-min", T1."內徑1-max", T1."內徑2-min", T1."內徑2-max",
                   T1."內徑3-min", T1."內徑3-max", T1."內徑4-min", T1."內徑4-max",
                   T1."內徑5-min", T1."內徑5-max",
                   T1."厚度1-min", T1."厚度1-max", T1."厚度2-min", T1."厚度2-max",
                   T1."厚度3-min", T1."厚度3-max", T1."厚度4-min", T1."厚度4-max",
                   T1."厚度5-min", T1."厚度5-max",
                   T1.同心度1, T1.同心度2, T1.同心度3, T1.同心度4, T1.同心度5,
                   T1.長度1, T1.長度2, T1.長度3, T1.長度4, T1.長度5,
                   T1.硬度1, T1.硬度2, T1.硬度3, T1.硬度4, T1.硬度5,
                   T1.真直度1, T1.真直度2, T1.真直度3, T1.真直度4, T1.真直度5
              FROM "出貨檢驗數據" T1
              LEFT JOIN "品管人員" P ON T1.檢驗人員 = P.識別碼
              LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
              {where_sql}
              ORDER BY T1.識別碼 DESC
        """
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        all_data = []
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            for key, val in item.items():
                item[key] = format_value(val)
            
            # 確保檢驗日期是 YYYY-MM-DD 格式
            if item.get('檢驗日期'):
                date_val = item['檢驗日期']
                if isinstance(date_val, str):
                    # 如果已經是 YYYY-MM-DD 格式，直接使用
                    if len(date_val) == 10 and '-' in date_val:
                        pass
                    # 如果是 ISO 格式，取前面的日期部分
                    elif 'T' in date_val:
                        item['檢驗日期'] = date_val.split('T')[0]
                    # 其他格式，嘗試解析
                    else:
                        try:
                            from datetime import datetime
                            parsed = datetime.strptime(date_val[:10], '%Y-%m-%d')
                            item['檢驗日期'] = parsed.strftime('%Y-%m-%d')
                        except:
                            pass
            
            all_data.append(item)
            
        # 分頁處理
        total = len(all_data)
        page = int(request.args.get('page', 1))
        per_page = 10
        start = (page - 1) * per_page
        end = start + per_page
        
        return jsonify({
            "data": all_data[start:end],
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        })
    finally:
        conn.close()

# ==================================================
# Token 驗證 API (用於前端驗證 token 有效性)
# ==================================================
@app.route('/api/verify-token', methods=['GET'])
def verify_token_api():
    """驗證 Token 是否有效"""
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'valid': False, 'error': '缺少 Token'}), 401
    
    if token.startswith('Bearer '):
        token = token[7:]
    
    payload = verify_token(token)
    if payload:
        return jsonify({
            'valid': True,
            'username': payload.get('username'),
            'user_id': payload.get('user_id')
        })
    else:
        return jsonify({'valid': False, 'error': 'Token 無效或已過期'}), 401

# ==================================================
# CSRF Token API
# ==================================================
@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """取得 CSRF Token"""
    token = generate_csrf_token()
    return jsonify({'csrf_token': token})

@app.route('/api/stats', methods=['GET'])
@auth_required
def get_shipping_stats():
    """獲取出貨檢驗的 SPC 統計數據（含公差界限）"""
    field = request.args.get('field')
    if not field:
        field = '外徑'
        
    vendor = request.args.get('vendor')
    material = request.args.get('material')
    spec = request.args.get('spec')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    params = []
    where = []
    if vendor: where.append("V.廠商名稱 LIKE %s"); params.append(f"%{vendor}%")
    if material: where.append("T1.材質 LIKE %s"); params.append(f"%{material}%")
    if spec: where.append("T1.檢驗規格 LIKE %s"); params.append(f"%{spec}%")
    if start_date: where.append("T1.檢驗日期 >= %s"); params.append(start_date)
    if end_date: where.append("T1.檢驗日期 <= %s"); params.append(end_date)
    
    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢公差標準（如果有）
        tolerance_limits = {"USL": None, "LSL": None, "found": False}
        if material:
            cursor.execute("""
                SELECT T1."識別碼"
                FROM "廠商公差主檔" T1
                WHERE T1."材質" = %s
                ORDER BY T1."廠商ID" DESC NULLS LAST, T1."規格" DESC NULLS LAST
                LIMIT 1
            """, (material,))
            tol_main = cursor.fetchone()
            if tol_main:
                # 查找對應測量項目的公差
                cursor.execute("""
                    SELECT "公差下限", "公差上限", "尺寸下限", "尺寸上限"
                    FROM "廠商公差明細檔"
                    WHERE "主檔ID" = %s AND "測量項目" = %s
                    LIMIT 1
                """, (tol_main[0], field))
                tol_detail = cursor.fetchone()
                if tol_detail:
                    tolerance_limits["found"] = True
                    tolerance_limits["公差下限"] = float(tol_detail[0]) if tol_detail[0] is not None else None
                    tolerance_limits["公差上限"] = float(tol_detail[1]) if tol_detail[1] is not None else None
                    tolerance_limits["尺寸下限"] = float(tol_detail[2]) if tol_detail[2] is not None else None
                    tolerance_limits["尺寸上限"] = float(tol_detail[3]) if tol_detail[3] is not None else None
                    # 計算 USL/LSL (標準值 ± 公差)
                    if tol_detail[2] is not None and tol_detail[3] is not None:
                        tolerance_limits["LSL"] = float(tol_detail[2])
                        tolerance_limits["USL"] = float(tol_detail[3])
                    elif tol_detail[0] is not None and tol_detail[1] is not None:
                        # 如果沒有尺寸上下限，嘗試用公差計算
                        std_val = cursor.execute("""
                            SELECT "標準值" FROM "廠商公差明細檔" 
                            WHERE "主檔ID" = %s AND "測量項目" = %s LIMIT 1
                        """, (tol_main[0], field))
                        std_result = cursor.fetchone()
                        if std_result and std_result[0] is not None:
                            std = float(std_result[0])
                            tolerance_limits["LSL"] = std - float(tol_detail[0])
                            tolerance_limits["USL"] = std + float(tol_detail[1])
                        else:
                            tolerance_limits["LSL"] = None
                            tolerance_limits["USL"] = None
        sql = f"""
            SELECT T1.識別碼, T1.檢驗日期, T1.訂單號碼,
                   T1."{field}1-min", T1."{field}1-max",
                   T1."{field}2-min", T1."{field}2-max",
                   T1."{field}3-min", T1."{field}3-max",
                   T1."{field}4-min", T1."{field}4-max",
                   T1."{field}5-min", T1."{field}5-max"
            FROM "出貨檢驗數據" T1
            LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
            {where_sql}
            ORDER BY T1.識別碼 DESC
        """
        # 如果欄位不是 minmax 類型，SQL 會有不同
        is_minmax = field in ['外徑', '內徑', '厚度']
        if not is_minmax:
            sql = f"""
                SELECT T1.識別碼, T1.檢驗日期, T1.訂單號碼,
                       T1."{field}1", T1."{field}2", T1."{field}3", T1."{field}4", T1."{field}5"
                FROM "出貨檢驗數據" T1
                LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
                {where_sql}
                ORDER BY T1.識別碼 DESC
            """
        
        rows = cursor.execute(sql, params)
        rows = cursor.fetchall()
        total_rows = len(rows)
        if not rows:
            return jsonify({"labels": [], "avgs": [], "ranges": [], "x_cl":0, "x_ucl":0, "x_lcl":0, "r_cl":0, "r_ucl":0})

        labels = []
        ids = []
        dates = []
        avgs = []
        ranges = []
        ids_valid = []  # 只存有效數據的 ID
        dates_valid = []  # 只存有效數據的日期
        labels_valid = []  # 只存有效數據的標籤
        insufficient_data = []  # 標記數據不足的原始索引
        
        # 從後往前排（時間序）
        for idx, r in enumerate(rows[::-1]):
            vals = []
            valid_groups = 0  # 有效組數
            
            if is_minmax:
                # 每組取 (min + max) / 2，min 和 max 都必須有值才算有效
                for i in range(3, 13, 2):
                    if r[i] is not None and r[i+1] is not None and r[i] != '' and r[i+1] != '':
                        try:
                            val = (float(r[i]) + float(r[i+1])) / 2
                            vals.append(val)
                            valid_groups += 1
                        except (ValueError, TypeError):
                            pass
            else:
                for i in range(3, 8):
                    if r[i] is not None and r[i] != '':
                        try:
                            vals.append(float(r[i]))
                            valid_groups += 1
                        except (ValueError, TypeError):
                            pass
            
            # 原始索引（用於標記數據不足的項目）
            original_idx = len(rows) - 1 - idx
            
            # 如果有效組數 >= 3，才計入統計
            if valid_groups >= 3 and vals:
                vals_np = np.array(vals, dtype=float)
                avg_val = float(np.mean(vals_np))
                range_val = float(np.ptp(vals_np))
                avgs.append(avg_val)
                ranges.append(range_val)
                ids_valid.append(str(r[0]))
                dates_valid.append(str(r[1]) if r[1] else '')
                labels_valid.append(str(r[2]) if r[2] else str(r[0]))
            else:
                # 數據不足，記錄原始索引
                insufficient_data.append({
                    "id": str(r[0]),
                    "date": str(r[1]) if r[1] else '',
                    "valid_groups": valid_groups,
                    "original_idx": original_idx
                })

        # 計算管制界限 (n=5)
        # 使用固定管制界限方法：前20-25筆數據建立基準，超過25筆則只用前25筆
        # A2=0.577, D4=2.114, D3=0
        BASELINE_COUNT = 25  # 基準數據點數量
        
        if len(avgs) >= 5:  # 至少需要5筆數據才能計算管制界限
            # 取前N筆數據建立管制界限
            baseline_count = min(BASELINE_COUNT, len(avgs))
            baseline_avgs = avgs[:baseline_count]
            baseline_ranges = ranges[:baseline_count]
            
            x_cl = np.mean(baseline_avgs)
            r_cl = np.mean(baseline_ranges)
            x_ucl = x_cl + 0.577 * r_cl
            x_lcl = x_cl - 0.577 * r_cl
            r_ucl = 2.114 * r_cl
            
            # 確保LCL不為負值（對於正值測量）
            x_lcl = max(x_lcl, 0)
        else:
            x_cl = x_ucl = x_lcl = r_cl = r_ucl = 0
            baseline_count = 0

        return jsonify({
            "labels": labels_valid,
            "ids": ids_valid,
            "dates": dates_valid,
            "avgs": [float(x) for x in avgs],
            "ranges": [float(x) for x in ranges],
            "x_cl": float(x_cl),
            "x_ucl": float(x_ucl),
            "x_lcl": float(x_lcl),
            "r_cl": float(r_cl),
            "r_ucl": float(r_ucl),
            "baseline_count": baseline_count,
            "insufficient_data": insufficient_data,  # 數據不足的項目列表
            "total_rows": len(rows),
            "valid_count": len(avgs),
            "tolerance": tolerance_limits  # 公差界限資訊
        })
    except Exception as e:
        import traceback
        traceback.print_exc() # 將錯誤印到底層主控台，方便使用者查看
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】儲存與更新
# ================================================== 
@app.route('/api/add', methods=['POST'])
@app.route('/api/update', methods=['POST'])
def save_data():
    data = request.json
    is_update = request.path.endswith('update')

    errors = validate_inspection_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢驗人員 ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('檢驗人員姓名'),)
        )
        p = cursor.fetchone()
        p_id = p[0] if p else None

        # 廠商 ID
        cursor.execute(
            '''SELECT "識別碼" FROM "廠商資料" WHERE "廠商名稱" = %s''',
            (data.get('廠商中文名稱'),)
        )
        v = cursor.fetchone()
        v_id = v[0] if v else None

        fields = ["檢驗日期", "檢驗人員", "廠商名稱", "檢驗規格", "材質", "訂單號碼"]
        params = [
            data.get('檢驗日期'),
            p_id,
            v_id,
            data.get('檢驗規格'),
            data.get('材質'),
            data.get('訂單號碼')
        ]

        for i in range(1, 6):
            for col in ['外徑', '內徑', '厚度']:
                fields += [f'"{col}{i}-min"', f'"{col}{i}-max"']
                params += [data.get(f'{col}{i}-min'), data.get(f'{col}{i}-max')]

            for col in ['同心度', '長度', '硬度', '真直度']:
                fields.append(f'"{col}{i}"')
                params.append(data.get(f'{col}{i}'))

        if is_update:
            set_sql = ", ".join([f'{f}=%s' for f in fields])
            params.append(data.get('識別碼'))
            cursor.execute(
                f'UPDATE "出貨檢驗數據" SET {set_sql} WHERE "識別碼" = %s',
                params
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO "出貨檢驗數據"
                ({','.join(fields)})
                VALUES ({','.join(['%s' for _ in params])})
                """,
                params
            )

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】刪除
# ==================================================
@app.route('/api/delete', methods=['POST'])
def delete_data():
    data = request.json
    record_id = data.get('id')
    if not record_id:
        return jsonify({"error": "缺少記錄 ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''DELETE FROM "出貨檢驗數據" WHERE "識別碼" = %s''', (record_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】匯入 Excel
# ==================================================
@app.route('/api/import', methods=['POST', 'OPTIONS'])
def shipping_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    try:
        df = pd.read_excel(file, engine='openpyxl')
        print("Excel 列名:", df.columns.tolist())
        print("Excel 第一行:", df.iloc[0].to_dict() if len(df) > 0 else "空表格")
    except Exception as e:
        return jsonify({"error": f"檔案讀取失敗: {str(e)}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success_count = 0
        for row_num, row in enumerate(df.iterrows()):
            main_data = row[1].to_dict()
            for key, value in main_data.items():
                if pd.isna(value):
                    main_data[key] = None

            # 查找檢驗人員 ID
            inspector_name = main_data.get('檢驗人員')
            if pd.isna(inspector_name) or str(inspector_name).strip() == "":
                inspector_id = None
            else:
                inspector_str = str(inspector_name).strip()
                cursor.execute('''SELECT 識別碼 FROM "品管人員" WHERE 姓名 = %s''', (inspector_str,))
                i = cursor.fetchone()
                inspector_id = i[0] if i else None
                if not inspector_id:
                    cursor.execute('''SELECT "姓名" FROM "品管人員"''')
                    all_inspectors = [row[0] for row in cursor.fetchall()]
                    display_row_num = row_num + 2
                    return jsonify({"error": f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_str}'(repr: {repr(inspector_str)})。資料庫中的檢驗人員有：{', '.join(all_inspectors)}"}), 400

            # 查找廠商 ID
            vendor_name = main_data.get('廠商名稱')
            if pd.isna(vendor_name) or str(vendor_name).strip() == "":
                vendor_id = None
            else:
                vendor_str = str(vendor_name).strip()
                cursor.execute('''SELECT 識別碼 FROM "廠商資料" WHERE 廠商名稱 = %s''', (vendor_str,))
                v = cursor.fetchone()
                vendor_id = v[0] if v else None

            # 檢查必要欄位
            display_row_num = row_num + 2
            if not inspector_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'"}), 400
            if not vendor_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到廠商 '{vendor_name}'"}), 400

            # 準備插入數據
            fields = ["檢驗日期", "檢驗人員", "廠商名稱", "檢驗規格", "材質", "訂單號碼"]
            params = [
                main_data.get('檢驗日期'),
                inspector_id,
                vendor_id,
                main_data.get('檢驗規格'),
                main_data.get('材質'),
                main_data.get('訂單號碼')
            ]

            for i in range(1, 6):
                for col in ['外徑', '內徑', '厚度']:
                    fields += [f'"{col}{i}-min"', f'"{col}{i}-max"']
                    params += [main_data.get(f'{col}{i}-min'), main_data.get(f'{col}{i}-max')]

                for col in ['同心度', '長度', '硬度', '真直度']:
                    fields.append(f'"{col}{i}"')
                    params.append(main_data.get(f'{col}{i}'))

            cursor.execute(
                f"""
                INSERT INTO "出貨檢驗數據"
                ({','.join(fields)})
                VALUES ({','.join(['%s' for _ in params])})
                """,
                params
            )

            success_count += 1

        conn.commit()
        return jsonify({"success": True, "message": f"匯入成功，共 {success_count} 筆資料"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】Options
# ==================================================
@app.route('/api/patrol/options')
def patrol_options():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT "識別碼", "擠壓機編號" FROM "擠壓機台"''')
        machines = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
        
        cursor.execute('''SELECT "識別碼", "員工姓名" FROM "擠壓人員"''')
        operators = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
        
        cursor.execute('''SELECT "識別碼", "姓名" FROM "品管人員"''')
        inspectors = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
        
        cursor.execute('''SELECT "識別碼", "廠商名稱" FROM "廠商資料"''')
        customers = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
        
        return jsonify({
            "machines": machines,
            "operators": operators,
            "inspectors": inspectors,
            "customers": customers
        })
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】匯出 Excel
# ==================================================
@app.route('/api/export/excel')
def export_excel():
    args = request.args
    params = []
    where = []

    if args.get('vendor'):   where.append("V.廠商名稱 LIKE %s"); params.append(f"%{args['vendor']}%")
    if args.get('material'): where.append("T1.材質 LIKE %s");     params.append(f"%{args['material']}%")
    if args.get('spec'):     where.append("T1.檢驗規格 LIKE %s"); params.append(f"%{args['spec']}%")
    if args.get('start_date'): where.append("T1.檢驗日期 >= %s"); params.append(args['start_date'])
    if args.get('end_date'):   where.append("T1.檢驗日期 <= %s"); params.append(args['end_date'])

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT T1.識別碼, T1.檢驗日期, T1.材質, T1.檢驗規格, T1.訂單號碼,
                   P.姓名 AS 檢驗人員, V.廠商名稱 AS 廠商名稱,
                   T1."外徑1-min", T1."外徑1-max", T1."外徑2-min", T1."外徑2-max",
                   T1."外徑3-min", T1."外徑3-max", T1."外徑4-min", T1."外徑4-max",
                   T1."外徑5-min", T1."外徑5-max",
                   T1."內徑1-min", T1."內徑1-max", T1."內徑2-min", T1."內徑2-max",
                   T1."內徑3-min", T1."內徑3-max", T1."內徑4-min", T1."內徑4-max",
                   T1."內徑5-min", T1."內徑5-max",
                   T1."厚度1-min", T1."厚度1-max", T1."厚度2-min", T1."厚度2-max",
                   T1."厚度3-min", T1."厚度3-max", T1."厚度4-min", T1."厚度4-max",
                   T1."厚度5-min", T1."厚度5-max",
                   T1.同心度1, T1.同心度2, T1.同心度3, T1.同心度4, T1.同心度5,
                   T1.長度1, T1.長度2, T1.長度3, T1.長度4, T1.長度5,
                   T1.硬度1, T1.硬度2, T1.硬度3, T1.硬度4, T1.硬度5,
                   T1.真直度1, T1.真直度2, T1.真直度3, T1.真直度4, T1.真直度5
              FROM "出貨檢驗數據" T1
              LEFT JOIN "品管人員" P ON T1.檢驗人員 = P.識別碼
              LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
              {where_sql}
              ORDER BY T1.識別碼 DESC
          """
        sql = sql.format(where_sql=where_sql)
        rows = cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            df = pd.DataFrame(columns=['識別碼', '檢驗日期', '材質', '檢驗規格', '訂單號碼', '檢驗人員', '廠商名稱',
                                         '外徑1-最小', '外徑1-最大', '外徑2-最小', '外徑2-最大',
                                         '外徑3-最小', '外徑3-最大', '外徑4-最小', '外徑4-最大', '外徑5-最小', '外徑5-最大',
                                         '內徑1-最小', '內徑1-最大', '內徑2-最小', '內徑2-最大',
                                         '內徑3-最小', '內徑3-最大', '內徑4-最小', '內徑4-最大', '內徑5-最小', '內徑5-最大',
                                         '厚度1-最小', '厚度1-最大', '厚度2-最小', '厚度2-最大',
                                         '厚度3-最小', '厚度3-最大', '厚度4-最小', '厚度4-最大', '厚度5-最小', '厚度5-最大',
                                         '同心度1', '同心度2', '同心度3', '同心度4', '同心度5',
                                         '長度1', '長度2', '長度3', '長度4', '長度5',
                                         '硬度1', '硬度2', '硬度3', '硬度4', '硬度5',
                                         '真直度1', '真直度2', '真直度3', '真直度4', '真直度5'])
        else:
            cols = [c[0] for c in cursor.description]
            df = pd.DataFrame([list(r) for r in rows], columns=cols)

            if '檢驗日期' in df.columns:
                df['檢驗日期'] = pd.to_datetime(df['檢驗日期']).dt.strftime('%Y-%m-%d')

        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        return send_file(output, as_attachment=True, download_name='出貨檢驗數據.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    finally:
        conn.close()

# ==================================================
# 【巡檢】SPC
# ==================================================
@app.route('/api/patrol/spc')
def patrol_spc():
    item = request.args.get('item', '厚度')
    pos = request.args.get('pos', '')

    params = [item]
    where = ["T2.測量項目 = %s"]

    args = request.args
    if pos: where.append("T2.測量位置 = %s"); params.append(pos)
    if args.get('s_date'): where.append("T1.檢驗日期 >= %s"); params.append(args['s_date'])
    if args.get('e_date'): where.append("T1.檢驗日期 <= %s"); params.append(args['e_date'])
    if args.get('m_id'):   where.append("T1.機台 = %s");       params.append(args['m_id'])
    if args.get('op_id'):  where.append("T1.主機手 = %s");     params.append(args['op_id'])
    if args.get('mat'):    where.append("T1.材質 LIKE %s");    params.append(f"%{args['mat']}%")
    if args.get('spec'):   where.append("T1.擠壓規格 LIKE %s");params.append(f"%{args['spec']}%")

    where_sql = "WHERE " + " AND ".join(where)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T1."檢驗日期", T2."主檔ID", T2."組別", T2."最小值", T2."最大值"
            FROM "巡檢主檔" T1
            JOIN "巡檢子檔" T2 ON T1."識別碼" = T2."主檔ID"
            {where_sql}
            ORDER BY T1."識別碼" DESC
        """
        rows = cursor.execute(sql, params)
        rows = cursor.fetchall()
        if not rows:
            return jsonify({"labels": [], "avgs": [], "ranges": []})

        groups = {}
        for r in rows:
            # 過濾掉 None 值
            val1 = r[3]
            val2 = r[4]
            if val1 is None or val2 is None:
                continue
            key = f"{r[0].strftime('%m/%d')}-#{r[1]}-G{r[2]}"
            groups.setdefault(key, []).extend([float(val1), float(val2)])

        labels = list(groups.keys())
        avgs = [np.mean(groups[k]) for k in labels]
        ranges = [np.ptp(groups[k]) for k in labels]

        A2, D4, D3 = 0.483, 2.004, 0
        x_cl, r_cl = np.mean(avgs), np.mean(ranges)

        return jsonify({
            "labels": labels,
            "avgs": avgs,
            "ranges": ranges,
            "x_cl": x_cl,
            "x_ucl": x_cl + A2 * r_cl,
            "x_lcl": x_cl - A2 * r_cl,
            "r_cl": r_cl,
            "r_ucl": D4 * r_cl,
            "r_lcl": D3 * r_cl
        })
    finally:
        conn.close()
# ==================================================
# 【巡檢】明細資料
# ==================================================
@app.route('/api/patrol/detail/<int:id>')
def patrol_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 主檔
        cursor.execute(
            '''SELECT * FROM "巡檢主檔" WHERE "識別碼" = %s''',
            (id,)
        )
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "資料不存在"}), 404

        cols = [c[0] for c in cursor.description]
        main = {c: format_value(v) for c, v in zip(cols, row)}

        # 子檔
        details = []
        cursor.execute(
            """
            SELECT "組別", "測量項目", "測量位置", "最小值", "最大值"
            FROM "巡檢子檔"
            WHERE "主檔ID" = %s
            """,
            (id,)
        )
        for r in cursor.fetchall():
            group_val = str(r[0]).strip()
            # 如果組別是數字，轉換為 "第X組" 格式
            if group_val.isdigit():
                group_val = f"第{group_val}組"
            details.append({
                "group": group_val,
                "item": r[1].strip(),
                "pos": r[2].strip(),
                "min": float(r[3]) if r[3] is not None else None,
                "max": float(r[4]) if r[4] is not None else None
            })

        return jsonify({
            "main": main,
            "details": details
        })
    finally:
        conn.close()

# ==================================================
# 【巡檢】新增（支援 CORS preflight）
# ==================================================
@app.route('/api/patrol/add', methods=['POST', 'OPTIONS'])
def patrol_add():
    if request.method == 'OPTIONS':
        # 預檢請求，直接回 200
        return '', 200

    data = request.json
    errors = validate_patrol_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 新增主檔
        cursor.execute(
            """
            INSERT INTO "巡檢主檔" ("檢驗日期", "機台", "主機手", "檢驗人員", "材質", "擠壓規格", "客戶名稱", "原料批號")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING "識別碼"
            """,
            (
                data.get('檢驗日期'),
                data.get('機台'),
                data.get('主機手'),
                data.get('檢驗人員'),
                data.get('材質'),
                data.get('擠壓規格'),
                data.get('客戶名稱'),
                data.get('原料批號')
            )
        )
        patrol_id = cursor.fetchone()[0]

        # 新增子檔
        for d in data.get('details', []):
            # 將 "第1組" 轉換為數字 "1"
            group_raw = str(d.get('group', '')).strip()
            group_val = group_raw.replace('第', '').replace('組', '')
            group_val = group_val if group_val.isdigit() else 1

            cursor.execute(
                """
                INSERT INTO "巡檢子檔"
                ("主檔ID", "組別", "測量項目", "測量位置", "最小值", "最大值")
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    patrol_id,
                    group_val,
                    d.get('item'),
                    d.get('pos'),
                    d.get('min'),
                    d.get('max')
                )
            )

        conn.commit()
        return jsonify({"success": True, "id": patrol_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】更新
# ==================================================
@app.route('/api/patrol/update', methods=['POST'])
def patrol_update():
    data = request.json
    record_id = data.get('id')
    if not record_id:
        return jsonify({"error": "缺少記錄 ID"}), 400

    errors = validate_patrol_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE "巡檢主檔"
            SET "檢驗日期"=%s, "機台"=%s, "主機手"=%s, "檢驗人員"=%s, "材質"=%s, "擠壓規格"=%s, "客戶名稱"=%s, "原料批號"=%s
            WHERE "識別碼"=%s
            """,
            (
                data.get('檢驗日期'),
                data.get('機台'),
                data.get('主機手'),
                data.get('檢驗人員'),
                data.get('材質'),
                data.get('擠壓規格'),
                data.get('客戶名稱'),
                data.get('原料批號'),
                record_id
            )
        )

        cursor.execute('''DELETE FROM "巡檢子檔" WHERE "主檔ID" = %s''', (record_id,))



        for d in data.get('details', []):
            # 將 "第1組" 轉換為數字 "1"
            group_raw = str(d.get('group', '')).strip()
            group_val = group_raw.replace('第', '').replace('組', '')
            group_val = group_val if group_val.isdigit() else 1

            cursor.execute(
                """
                INSERT INTO "巡檢子檔"
                ("主檔ID", "組別", "測量項目", "測量位置", "最小值", "最大值")
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    record_id,
                    group_val,
                    d.get('item'),
                    d.get('pos'),
                    d.get('min'),
                    d.get('max')
                )
            )

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】刪除
# ==================================================
@app.route('/api/patrol/delete', methods=['POST'])
def patrol_delete():
    data = request.json
    record_id = data.get('id')
    if not record_id:
        return jsonify({"error": "缺少記錄 ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''DELETE FROM "巡檢子檔" WHERE "主檔ID" = %s''', (record_id,))
        cursor.execute('''DELETE FROM "巡檢主檔" WHERE "識別碼" = %s''', (record_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】歷史記錄
# ==================================================
@app.route('/api/patrol/history')
@auth_required
def patrol_history():
    args = request.args
    params = []
    where = []

    if args.get('s_date'): where.append("T.檢驗日期 >= %s"); params.append(args['s_date'])
    if args.get('e_date'): where.append("T.檢驗日期 <= %s"); params.append(args['e_date'])
    if args.get('m_id'):   where.append("T.機台 = %s");       params.append(args['m_id'])
    if args.get('op_id'):  where.append("T.主機手 = %s");     params.append(args['op_id'])
    if args.get('mat'):    where.append("T.材質 LIKE %s");    params.append(f"%{args['mat']}%")
    if args.get('spec'):   where.append("T.擠壓規格 LIKE %s");params.append(f"%{args['spec']}%")

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T.識別碼, T.檢驗日期, M.擠壓機編號, OP.員工姓名, T.材質, T.擠壓規格
            FROM "巡檢主檔" T
            LEFT JOIN "擠壓機台" M ON T.機台 = M.識別碼
            LEFT JOIN "擠壓人員" OP ON T.主機手 = OP.識別碼
            {where_sql}
            ORDER BY T.識別碼 DESC
        """
        cursor.execute(sql, params)
        data = []
        for row in cursor.fetchall():
            date_value = row[1]
            if date_value:
                if hasattr(date_value, 'strftime'):
                    date_str = date_value.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_value).split()[0]
            else:
                date_str = ''
            data.append({
                'id': row[0],
                'date': date_str,
                'm_name': row[2],
                'op_name': row[3],
                'mat': row[4],
                'spec': row[5]
            })
        return jsonify({"data": data})
    finally:
        conn.close()

# ==================================================
# 【巡檢】匯出 Excel
# ==================================================
@app.route('/api/patrol/export')
def patrol_export():
    args = request.args
    params, where = [], []

    if args.get('s_date'): where.append("T.檢驗日期 >= %s"); params.append(args['s_date'])
    if args.get('e_date'): where.append("T.檢驗日期 <= %s"); params.append(args['e_date'])
    if args.get('m_id'):   where.append("T.機台 = %s");       params.append(args['m_id'])
    if args.get('op_id'):  where.append("T.主機手 = %s");     params.append(args['op_id'])
    if args.get('mat'):    where.append("T.材質 LIKE %s");    params.append(f"%{args['mat']}%")
    if args.get('spec'):   where.append("T.擠壓規格 LIKE %s");params.append(f"%{args['spec']}%")

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T.識別碼, T.檢驗日期, M.擠壓機編號, OP.員工姓名,
                   T.材質, T.擠壓規格, C.廠商名稱, T.原料批號, P.姓名
            FROM "巡檢主檔" T
            LEFT JOIN "擠壓機台" M ON T.機台 = M.識別碼
            LEFT JOIN "擠壓人員" OP ON T.主機手 = OP.識別碼
            LEFT JOIN "品管人員" P ON T.檢驗人員 = P.識別碼
            LEFT JOIN "廠商資料" C ON T.客戶名稱 = C.識別碼
            {where_sql}
            ORDER BY T.識別碼 DESC
        """
        rows = cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            df = pd.DataFrame(columns=['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員'])
        else:
            export_data = []
            for row in rows:
                record_id = row[0]
                main_data = list(row)

                cursor.execute(
                    """
                    SELECT "組別", "測量項目", "測量位置", "最小值", "最大值"
                    FROM "巡檢子檔"
                    WHERE "主檔ID" = %s
                    ORDER BY "組別", "測量項目", "測量位置"
                    """,
                    (record_id,)
                )
                details = cursor.fetchall()

                measurements = {}
                for d in details:
                    group_raw = str(d[0]).strip()
                    group_name = group_raw if "組" in group_raw else f"第{group_raw}組"
                    item = str(d[1]).strip() if d[1] else ""
                    pos = str(d[2]).strip() if d[2] else ""

                    try:
                        min_val = float(d[3]) if d[3] is not None and d[3] != "" else ""
                        max_val = float(d[4]) if d[4] is not None and d[4] != "" else ""
                    except (ValueError, TypeError):
                        min_val = ""
                        max_val = ""

                    key = f"{group_name}_{item}_{pos}"
                    measurements[key] = {"min": min_val, "max": max_val}

                unique_groups = []
                for d in details:
                    group_raw = str(d[0]).strip()
                    group_name = group_raw if "組" in group_raw else f"第{group_raw}組"
                    if group_name not in unique_groups:
                        unique_groups.append(group_name)

                if not unique_groups:
                    unique_groups = ["第1組"]

                for group in unique_groups:
                    group_name = group
                    row_data = main_data.copy()

                    for item in ["外徑", "內徑", "厚度"]:
                        for pos in ["前段", "中段", "後段"]:
                            key = f"{group_name}_{item}_{pos}"
                            min_val = measurements.get(key, {}).get("min", "")
                            max_val = measurements.get(key, {}).get("max", "")
                            row_data.append(min_val)
                            row_data.append(max_val)

                    export_data.append(row_data)

            cols = ['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員']
            for _ in unique_groups:
                cols.extend([
                    "外徑前段最小", "外徑前段最大",
                    "外徑中段最小", "外徑中段最大",
                    "外徑後段最小", "外徑後段最大",
                    "內徑前段最小", "內徑前段最大",
                    "內徑中段最小", "內徑中段最大",
                    "內徑後段最小", "內徑後段最大",
                    "厚度前段最小", "厚度前段最大",
                    "厚度中段最小", "厚度中段最大",
                    "厚度後段最小", "厚度後段最大"
                ])

            df = pd.DataFrame(export_data, columns=cols)

        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        return send_file(output, as_attachment=True, download_name='巡檢數據.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    finally:
        conn.close()

# ==================================================
# 【巡檢】匯入 Excel
# ==================================================
@app.route('/api/patrol/import', methods=['POST', 'OPTIONS'])
def patrol_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    try:
        df = pd.read_excel(file, engine='openpyxl')
    except Exception as e:
        return jsonify({"error": f"檔案讀取失敗: {str(e)}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success_count = 0
        for row_num, row in enumerate(df.iterrows()):
            main_data = row[1].to_dict()

            # 查找機台 ID
            machine_name = main_data.get('擠壓機編號')
            if pd.isna(machine_name) or str(machine_name).strip() == "":
                machine_id = None
            else:
                machine_str = str(machine_name).strip()
                cursor.execute('''SELECT 識別碼 FROM "擠壓機台" WHERE 擠壓機編號 = %s''', (machine_str,))
                m = cursor.fetchone()
                machine_id = m[0] if m else None

            # 查找員工 ID
            operator_name = main_data.get('員工姓名')
            if pd.isna(operator_name) or str(operator_name).strip() == "":
                operator_id = None
            else:
                operator_str = str(operator_name).strip()
                cursor.execute('''SELECT 識別碼 FROM "擠壓人員" WHERE 員工姓名 = %s''', (operator_str,))
                o = cursor.fetchone()
                operator_id = o[0] if o else None

            # 查找客戶 ID
            customer_name = main_data.get('客戶名稱')
            if pd.isna(customer_name) or str(customer_name).strip() == "":
                customer_id = None
            else:
                customer_str = str(customer_name).strip()
                cursor.execute('''SELECT 識別碼 FROM "廠商資料" WHERE 廠商名稱 = %s''', (customer_str,))
                c = cursor.fetchone()
                customer_id = c[0] if c else None

            # 查找檢驗人員 ID
            inspector_name = main_data.get('檢驗人員')
            if pd.isna(inspector_name) or str(inspector_name).strip() == "":
                inspector_id = None
            else:
                inspector_str = str(inspector_name).strip()
                cursor.execute('''SELECT 識別碼 FROM "品管人員" WHERE 姓名 = %s''', (inspector_str,))
                i = cursor.fetchone()
                inspector_id = i[0] if i else None

            # 檢查必要欄位
            display_row_num = row_num + 2
            if not machine_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到機台 '{machine_name}'"}), 400
            if not operator_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到員工 '{operator_name}'"}), 400
            if not inspector_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'"}), 400

            cursor.execute(
                """
                INSERT INTO "巡檢主檔"
                (檢驗日期, 機台, 主機手, 材質, 擠壓規格, 客戶名稱, 原料批號, 檢驗人員)
                RETURNING 識別碼
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    main_data.get('檢驗日期'),
                    machine_id,
                    operator_id,
                    main_data.get('材質'),
                    main_data.get('擠壓規格'),
                    customer_id,
                    main_data.get('原料批號'),
                    inspector_id
                )
            )
            patrol_id = cursor.fetchone()[0]

            measurement_cols = [
                ("外徑前段最小", "外徑", "前段", "min"),
                ("外徑前段最大", "外徑", "前段", "max"),
                ("外徑中段最小", "外徑", "中段", "min"),
                ("外徑中段最大", "外徑", "中段", "max"),
                ("外徑後段最小", "外徑", "後段", "min"),
                ("外徑後段最大", "外徑", "後段", "max"),
                ("內徑前段最小", "內徑", "前段", "min"),
                ("內徑前段最大", "內徑", "前段", "max"),
                ("內徑中段最小", "內徑", "中段", "min"),
                ("內徑中段最大", "內徑", "中段", "max"),
                ("內徑後段最小", "內徑", "後段", "min"),
                ("內徑後段最大", "內徑", "後段", "max"),
                ("厚度前段最小", "厚度", "前段", "min"),
                ("厚度前段最大", "厚度", "前段", "max"),
                ("厚度中段最小", "厚度", "中段", "min"),
                ("厚度中段最大", "厚度", "中段", "max"),
                ("厚度後段最小", "厚度", "後段", "min"),
                ("厚度後段最大", "厚度", "後段", "max")
            ]

            measurements = {}
            for col_name, item, pos, min_max in measurement_cols:
                val = main_data.get(col_name)
                if pd.isna(val) == False and str(val).strip() != "":
                    key = f"{item}_{pos}"
                    if key not in measurements:
                        measurements[key] = {"min": "", "max": ""}
                    measurements[key][min_max] = str(val)

            for key, vals in measurements.items():
                item, pos = key.split("_")
                min_val = vals["min"]
                max_val = vals["max"]

                if min_val == "" and max_val == "":
                    continue

                min_val = float(min_val) if min_val != "" else None
                max_val = float(max_val) if max_val != "" else None

                cursor.execute(
                    """
                    INSERT INTO "巡檢子檔"
                    (主檔ID, 組別, 測量項目, 測量位置, 最小值, 最大值)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (patrol_id, "1", item, pos, min_val, max_val)
                )

            success_count += 1

        conn.commit()
        return jsonify({"success": True, "message": f"匯入成功，共 {success_count} 筆資料"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【認證】登入
# ==================================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username') or data.get('account')  # Accept both username and account
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT \"識別碼\", \"密碼\", \"是否啟用\" FROM \"使用者\" WHERE \"使用者名稱\" = %s",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "使用者名稱或密碼錯誤"}), 401

        user_id, stored_password, is_active = row
        if hash_password(password) != stored_password:
            return jsonify({"error": "使用者名稱或密碼錯誤"}), 401

        if not is_active:
            return jsonify({"error": "帳號已被停用"}), 401

        token = generate_token(user_id, username)
        return jsonify({"token": token, "username": username, "user_id": user_id})
    finally:
        conn.close()

# ==================================================
# 【重工品管】API
# ==================================================

@app.route('/api/rework/applications', methods=['GET'])
@auth_required
def get_rework_applications():
    """獲取重工申請列表"""
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    rework_id = request.args.get('rework_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT r.*, 
                   p1."姓名" AS "申請人員姓名",
                   p2."姓名" AS "審核人員姓名",
                   n."不良描述" AS "ncmr_description",
                   n."NCMR單號" AS "ncmr_number"
            FROM "重工申請單" r
            LEFT JOIN "品管人員" p1 ON r."申請人員" = p1."識別碼"
            LEFT JOIN "品管人員" p2 ON r."審核人員" = p2."識別碼"
            LEFT JOIN "不合格品單" n ON r."NCMR_ID" = n."識別碼"
        """
        params = []
        conditions = []
        
        if rework_id:
            conditions.append('r."識別碼" = %s')
            params.append(rework_id)
        if status:
            conditions.append('r."狀態" = %s')
            params.append(status)
        if start_date:
            conditions.append('r."申請日期" >= %s')
            params.append(start_date)
        if end_date:
            conditions.append('r."申請日期" <= %s')
            params.append(end_date)
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
            
        sql += ' ORDER BY r."申請日期" DESC'
        
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

def generate_rework_number():
    """生成重工單號"""
    return generate_number('RW', "重工申請單", '申請單號')

@app.route('/api/rework/apply', methods=['POST'])
@auth_required
def apply_rework():
    """提交重工申請"""
    data = request.json
    
    # 清理數據 - 移除可能的文件上傳字段
    if isinstance(data, dict):
        data_copy = {}
        for key, value in data.items():
            # 移除任何可能的文件字段或非標準字段
            if key not in ['不合格品管理.png', 'file', 'upload'] and not key.endswith('[]'):
                data_copy[key] = value
        data = data_copy
    
    # 驗證必填欄位
    errors = []
    if not data.get('NCMR_ID'):
        errors.append("NCMR_ID為必填欄位")
    if not data.get('申請人員姓名'):
        errors.append("申請人員為必填欄位")
    if not data.get('重工數量'):
        errors.append("重工數量為必填欄位")
    if not data.get('申請原因'):
        errors.append("申請原因為必填欄位")
        
    # 數值驗證
    try:
        if data.get('重工數量'):
            float(data.get('重工數量'))
    except (ValueError, TypeError):
        errors.append("重工數量必須是數字")
        
    if errors:
        print(f"重工申請驗證錯誤: {errors}")
        print(f"收到的數據: {data}")
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取申請人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('申請人員姓名'),)
        )
        applicant = cursor.fetchone()
        if not applicant:
            return jsonify({"error": "找不到申請人員"}), 400
        applicant_id = applicant[0]
        
        # 獲取完整NCMR資訊（包含新編號）
        cursor.execute(
            """
            SELECT "識別碼", "NCMR單號", "判定結果", "狀態", "不良描述", "產品資訊", "材質", "廠商"
            FROM "不合格品單" 
            WHERE "識別碼" = %s
            """,
            (data.get('NCMR_ID'),)
        )
        ncmr = cursor.fetchone()
        if not ncmr:
            return jsonify({"error": "找不到對應的NCMR記錄"}), 400
            
        ncmr_id, ncmr_number, determination, ncmr_status, bad_desc, product_info, material, vendor = ncmr
        if determination != '重工':
            return jsonify({"error": "此NCMR的判定結果不是重工，無法申請重工"}), 400
            
        rework_number = generate_rework_number()
            
        sql = """
            INSERT INTO "重工申請單" 
            ("NCMR_ID", "申請單號", "申請人員", "部門", "緊急程度", "產品資訊", "批號", 
             "重工數量", "申請原因", "預計完成日期", "狀態")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '申請中')
            RETURNING "識別碼";
        """
        cursor.execute(sql, (
            data.get('NCMR_ID'),
            rework_number,
            applicant_id,
            data.get('部門', ''),
            data.get('緊急程度', '普通'),
            product_info,
            data.get('批號', ''),
            data.get('重工數量'),
            data.get('申請原因'),
            data.get('預計完成日期')
        ))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "無法取得產生的重工單 ID"}), 500
        rework_id = row[0]
        
        # 自動更新NCMR狀態為轉重工
        cursor.execute(
            '''UPDATE "不合格品單" SET "狀態" = '轉重工' WHERE "識別碼" = %s''',
            (data.get('NCMR_ID'),)
        )
        
        conn.commit()
        return jsonify({"success": True, "rework_id": rework_id, "ncmr_number": ncmr_number})
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"重工申請失敗: {str(e)}")
        return jsonify({"error": f"資料庫執行錯誤: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/rework/approve', methods=['POST'])
@auth_required
def approve_rework():
    """審核重工申請"""
    data = request.json
    rework_id = data.get('rework_id')
    action = data.get('action')  # 'approve' 或 'reject'
    opinion = data.get('opinion', '')
    reviewer_name = data.get('審核人員姓名')
    
    if not rework_id or not action or not reviewer_name:
        return jsonify({"error": "缺少必要參數"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取審核人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (reviewer_name,)
        )
        reviewer = cursor.fetchone()
        if not reviewer:
            return jsonify({"error": "找不到審核人員"}), 400
        reviewer_id = reviewer[0]
        
        # 更新審核狀態
        if action == 'approve':
            new_status = '已核准'
        elif action == 'reject':
            new_status = '已拒絕'
        else:
            return jsonify({"error": "無效的審核動作"}), 400
            
        sql = """
            UPDATE "重工申請單" 
            SET 審核狀態 = %s, 審核人員 = %s, 審核時間 = CURRENT_TIMESTAMP, 
                審核意見 = %s, 狀態 = %s
            WHERE 識別碼 = %s
        """
        cursor.execute(sql, (new_status, reviewer_id, opinion, new_status, rework_id))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rework/executions', methods=['GET'])
@auth_required
def get_rework_executions():
    """獲取重工執行記錄"""
    rework_number = request.args.get('rework_id')  # 這是重工單號，如 "RW-202602-001"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 如果提供了重工單號，先查詢對應的識別碼
        rework_db_id = None
        if rework_number:
            cursor.execute(
                '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
                (rework_number,)
            )
            result = cursor.fetchone()
            if result:
                rework_db_id = result[0]
        
        sql = """
            SELECT e."識別碼", e."重工單號", e."執行部門", e."負責人員", e."協同人員",
                   e."開始時間", e."預計完成時間", e."實際完成時間", e."使用設備",
                   e."重工方式", e."SOP編號", e."耗材記錄", e."完成數量", e."不良數量",
                   e."良率", e."執行狀況", e."異常狀況", e."執行人員",
                   p1."姓名" AS 負責人員姓名,
                   p2."姓名" AS 執行人員姓名
            FROM "重工執行記錄" e
            LEFT JOIN "品管人員" p1 ON e."負責人員" = p1."識別碼"
            LEFT JOIN "品管人員" p2 ON e."執行人員" = p2."識別碼"
        """
        params = []
        if rework_db_id:
            sql += ' WHERE e."重工單號" = %s'
            params.append(rework_db_id)
            
        sql += ' ORDER BY e."識別碼" DESC'
        
        cursor.execute(sql, params or [])
        cols = [c[0] for c in cursor.description]
        print(f"查詢欄位: {cols}")  # 除錯
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            print(f"資料項: {item}")  # 除錯
            print(f"良率值: {item.get('良率')}, 實際完成時間值: {item.get('實際完成時間')}")  # 除錯
            # 格式化日期
            for date_field in ['開始時間', '預計完成時間', '實際完成時間']:
                if item.get(date_field):
                    item[date_field] = item[date_field].strftime('%Y-%m-%d %H:%M:%S')
            data.append(item)
            
        print(f"返回資料: {data}")  # 除錯
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"獲取執行記錄錯誤: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/rework/execute', methods=['POST'])
@auth_required
def execute_rework():
    """記錄重工執行"""
    data = request.json
    
    # 驗證必填欄位
    errors = []
    if not data.get('重工單號'):
        errors.append("重工單號為必填欄位")
    if not data.get('負責人員姓名'):
        errors.append("負責人員為必填欄位")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取負責人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('負責人員姓名'),)
        )
        executor = cursor.fetchone()
        if not executor:
            return jsonify({"error": "找不到負責人員"}), 400
        executor_id = executor[0]
        
        sql = """
            INSERT INTO "重工執行記錄" 
            ("重工單號", "執行部門", "負責人員", "協同人員", "開始時間", 
             "預計完成時間", "實際完成時間", "使用設備", "重工方式", "SOP編號", "耗材記錄", 
             "完成數量", "不良數量", "良率", "執行狀況", "異常狀況", "執行人員")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        start_time = data.get('開始時間')
        if start_time:
            start_time = start_time.replace('T', ' ')
            
        end_time = data.get('預計完成時間')
        if end_time:
            end_time = end_time.replace('T', ' ')
            
        actual_end_time = data.get('實際完成時間')
        if actual_end_time:
            actual_end_time = actual_end_time.replace('T', ' ')
        
        # 計算良率
        complete_qty = float(data.get('完成數量', 0) or 0)
        defect_qty = float(data.get('不良數量', 0) or 0)
        yield_rate = None
        if complete_qty > 0:
            yield_rate = ((complete_qty - defect_qty) / complete_qty) * 100

        # 獲取重工申請單的識別碼（INTEGER）
        rework_number = data.get('重工單號')
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
            (rework_number,)
        )
        rework_result = cursor.fetchone()
        if not rework_result:
            return jsonify({"error": "找不到重工申請單"}), 400
        rework_db_id = rework_result[0]

        cursor.execute(sql, (
            rework_db_id,
            data.get('執行部門', ''),
            executor_id,
            data.get('協同人員', ''),
            start_time or None,
            end_time or None,
            actual_end_time or None,
            data.get('使用設備', ''),
            data.get('重工方式', ''),
            data.get('SOP編號', ''),
            data.get('耗材記錄', ''),
            complete_qty,
            defect_qty,
            yield_rate,
            data.get('執行狀況', ''),
            data.get('異常狀況', ''),
            executor_id
        ))
        
        # 更新重工申請單狀態為執行中
        cursor.execute(
            '''UPDATE "重工申請單" SET "狀態" = '執行中' WHERE "識別碼" = %s''',
            (rework_db_id,)
        )
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        print(f"Error in execute_rework: {str(e)}")
        print(f"Data received: {data}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close() 

@app.route('/api/rework/inspections', methods=['GET'])
@auth_required
def get_rework_inspections():
    """獲取重工品檢記錄"""
    rework_number = request.args.get('rework_id')  # 這是重工單號，如 "RW-202602-001"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 如果提供了重工單號，先查詢對應的識別碼
        rework_db_id = None
        if rework_number:
            cursor.execute(
                '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
                (rework_number,)
            )
            result = cursor.fetchone()
            if result:
                rework_db_id = result[0]
        
        sql = """
            SELECT i.*, p."姓名" AS "檢驗人員姓名"
            FROM "重工品檢記錄" i
            LEFT JOIN "品管人員" p ON i."檢驗人員" = p."識別碼"
        """
        params = []
        if rework_db_id:
            sql += ' WHERE i."重工單號" = %s'
            params.append(rework_db_id)
            
        sql += ' ORDER BY i."檢驗日期" DESC'
        
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 格式化日期
            if item.get('檢驗日期'):
                item['檢驗日期'] = item['檢驗日期'].strftime('%Y-%m-%d %H:%M:%S')
            if item.get('建立時間'):
                item['建立時間'] = item['建立時間'].strftime('%Y-%m-%d %H:%M:%S')
            data.append(item)
            
        return jsonify(data)
    finally:
        conn.close()

@app.route('/api/rework/inspect', methods=['POST'])
@auth_required
def inspect_rework():
    """記錄重工品檢"""
    data = request.json
    
    # 驗證必填欄位
    errors = []
    if not data.get('重工單號'):
        errors.append("重工單號為必填欄位")
    if not data.get('檢驗人員姓名'):
        errors.append("檢驗人員為必填欄位")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取重工申請單的識別碼（INTEGER）
        rework_number = data.get('重工單號')
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
            (rework_number,)
        )
        rework_result = cursor.fetchone()
        if not rework_result:
            return jsonify({"error": "找不到重工申請單"}), 400
        rework_db_id = rework_result[0]
        
        # 獲取檢驗人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('檢驗人員姓名'),)
        )
        inspector = cursor.fetchone()
        if not inspector:
            return jsonify({"error": "找不到檢驗人員"}), 400
        inspector_id = inspector[0]
        
        sql = """
            INSERT INTO "重工品檢記錄" 
            ("重工單號", "檢驗日期", "檢驗人員", "檢驗項目", "檢驗標準", "檢驗結果", "不良數量", "檢驗備註")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            rework_db_id,
            data.get('檢驗日期'),
            inspector_id,
            data.get('檢驗項目', ''),
            data.get('檢驗標準', ''),
            data.get('檢驗結果', '合格'),
            data.get('不良數量', 0),
            data.get('檢驗備註', '')
        ))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/rework/inspection/<int:inspection_id>', methods=['GET'])
@auth_required
def get_inspection(inspection_id):
    """獲取單筆品檢記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT i.*, p."姓名" AS "檢驗人員姓名"
            FROM "重工品檢記錄" i
            LEFT JOIN "品管人員" p ON i."檢驗人員" = p."識別碼"
            WHERE i."識別碼" = %s
            """,
            (inspection_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到品檢記錄"}), 404
        
        cols = [c[0] for c in cursor.description]
        item = dict(zip(cols, row))
        
        # 格式化日期
        if item.get('檢驗日期'):
            item['檢驗日期'] = item['檢驗日期'].strftime('%Y-%m-%d')
        
        return jsonify(item)
    finally:
        conn.close()



@app.route('/api/rework/inspection/<int:inspection_id>', methods=['PUT'])
@auth_required
def update_inspection(inspection_id):
    """更新品檢記錄"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取檢驗人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('檢驗人員姓名'),)
        )
        inspector = cursor.fetchone()
        if not inspector:
            return jsonify({"error": "找不到檢驗人員"}), 400
        inspector_id = inspector[0]
        
        cursor.execute(
            """
            UPDATE "重工品檢記錄" 
            SET "檢驗日期" = %s, "檢驗人員" = %s, "檢驗項目" = %s, 
                "檢驗標準" = %s, "檢驗結果" = %s, "不良數量" = %s, "檢驗備註" = %s
            WHERE "識別碼" = %s
            """,
            (
                data.get('檢驗日期'),
                inspector_id,
                data.get('檢驗項目', ''),
                data.get('檢驗標準', ''),
                data.get('檢驗結果', '合格'),
                data.get('不良數量', 0),
                data.get('檢驗備註', ''),
                inspection_id
            )
        )
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/rework/inspection/<int:inspection_id>', methods=['DELETE'])
@auth_required
def delete_inspection(inspection_id):
    """刪除品檢記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''DELETE FROM "重工品檢記錄" WHERE "識別碼" = %s''',
            (inspection_id,)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/rework/close', methods=['POST'])
@auth_required
def close_rework():
    """結案重工申請"""
    data = request.json
    rework_id = data.get('rework_id')
    
    if not rework_id:
        return jsonify({"error": "缺少重工單號參數"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查當前狀態
        cursor.execute('''SELECT "狀態" FROM "重工申請單" WHERE "識別碼" = %s''', (rework_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到該重工單"}), 404
            
        current_status = row[0]
        if current_status == '已完成':
            return jsonify({"error": "該重工單已結案"}), 400
            
        # 更新狀態
        cursor.execute(
            """
            UPDATE "重工申請單" 
            SET "狀態" = '已完成', "實際完成日期" = CURRENT_TIMESTAMP
            WHERE "識別碼" = %s
            """,
            (rework_id,)
        )
        
        # 更新 NCMR 狀態為重工已完成
        cursor.execute('''SELECT "NCMR_ID" FROM "重工申請單" WHERE "識別碼" = %s''', (rework_id,))
        ncmr_result = cursor.fetchone()
        if ncmr_result:
            ncmr_id = ncmr_result[0]
            cursor.execute('''UPDATE "不合格品單" SET "狀態" = '重工已完成' WHERE "識別碼" = %s''', (ncmr_id,))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rework/delete', methods=['POST'])
@auth_required
def delete_rework():
    """刪除重工申請"""
    data = request.json
    rework_id = data.get('rework_id')
    
    if not rework_id:
        return jsonify({"error": "缺少重工單號參數"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 刪除相關的執行記錄
        cursor.execute('''DELETE FROM "重工執行記錄" WHERE "重工單號" = %s''', (rework_id,))
        # 刪除相關的品檢記錄
        cursor.execute('''DELETE FROM "重工品檢記錄" WHERE "重工單號" = %s''', (rework_id,))
        # 刪除相關的成本記錄
        cursor.execute('''DELETE FROM "重工成本分析" WHERE "重工單號" = %s''', (rework_id,))
        # 刪除重工申請單
        cursor.execute('''DELETE FROM "重工申請單" WHERE "識別碼" = %s''', (rework_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rework/costs', methods=['GET'])
@auth_required
def get_rework_costs():
    """獲取重工成本記錄"""
    rework_number = request.args.get('rework_id')  # 這是重工單號，如 "RW-202602-001"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 如果提供了重工單號，先查詢對應的識別碼
        rework_db_id = None
        if rework_number:
            cursor.execute(
                '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
                (rework_number,)
            )
            result = cursor.fetchone()
            if result:
                rework_db_id = result[0]
        
        sql = """
            SELECT c.*, p."姓名" AS "記錄人員姓名"
            FROM "重工成本分析" c
            LEFT JOIN "品管人員" p ON c."記錄人員" = p."識別碼"
        """
        params = []
        if rework_db_id:
            sql += ' WHERE c."重工單號" = %s'
            params.append(rework_db_id)
            
        sql += ' ORDER BY c."記錄日期" DESC'
        
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 格式化日期
            if item.get('記錄日期'):
                item['記錄日期'] = item['記錄日期'].strftime('%Y-%m-%d %H:%M:%S')
            data.append(item)
            
        return jsonify(data)
    finally:
        conn.close()

@app.route('/api/rework/cost', methods=['POST'])
@auth_required
def add_rework_cost():
    """新增重工成本記錄"""
    data = request.json
    
    # 驗證必填欄位
    errors = []
    if not data.get('重工單號'):
        errors.append("重工單號為必填欄位")
    if not data.get('成本類型'):
        errors.append("成本類型為必填欄位")
    if not data.get('成本項目'):
        errors.append("成本項目為必填欄位")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取重工申請單的識別碼（INTEGER）
        rework_number = data.get('重工單號')
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
            (rework_number,)
        )
        rework_result = cursor.fetchone()
        if not rework_result:
            return jsonify({"error": "找不到重工申請單"}), 400
        rework_db_id = rework_result[0]
        
        sql = """
            INSERT INTO "重工成本分析" 
            ("重工單號", "成本類型", "成本項目", "單位成本", "數量", "總成本", 
             "成本幣別", "記錄人員", "備註")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # 獲取記錄人員 ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('記錄人員姓名'),)
        )
        record_person = cursor.fetchone()
        record_person_id = record_person[0] if record_person else None

        cursor.execute(sql, (
            rework_db_id,
            data.get('成本類型'),
            data.get('成本項目'),
            data.get('單位成本', 0),
            data.get('數量', 0),
            data.get('總成本', 0),
            data.get('成本幣別', 'TWD'),
            record_person_id,
            data.get('備註', '')
        ))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/rework/cost/<int:cost_id>', methods=['GET'])
@auth_required
def get_cost(cost_id):
    """獲取單筆成本記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT c.*, p."姓名" AS "記錄人員姓名"
            FROM "重工成本分析" c
            LEFT JOIN "品管人員" p ON c."記錄人員" = p."識別碼"
            WHERE c."識別碼" = %s
            """,
            (cost_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到成本記錄"}), 404
        
        cols = [c[0] for c in cursor.description]
        item = dict(zip(cols, row))
        
        # 格式化日期
        if item.get('記錄日期'):
            item['記錄日期'] = item['記錄日期'].strftime('%Y-%m-%d')
        
        return jsonify(item)
    finally:
        conn.close()



@app.route('/api/rework/cost/<int:cost_id>', methods=['PUT'])
@auth_required
def update_cost(cost_id):
    """更新成本記錄"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取記錄人員 ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('記錄人員姓名'),)
        )
        record_person = cursor.fetchone()
        record_person_id = record_person[0] if record_person else None
        
        # 重新計算總成本
        unit_cost = float(data.get('單位成本', 0) or 0)
        qty = float(data.get('數量', 0) or 0)
        total_cost = unit_cost * qty
        
        cursor.execute(
            """
            UPDATE "重工成本分析" 
            SET "成本類型" = %s, "成本項目" = %s, "單位成本" = %s, 
                "數量" = %s, "總成本" = %s, "記錄人員" = %s, "備註" = %s
            WHERE "識別碼" = %s
            """,
            (
                data.get('成本類型'),
                data.get('成本項目'),
                unit_cost,
                qty,
                total_cost,
                record_person_id,
                data.get('備註', ''),
                cost_id
            )
        )
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/rework/cost/<int:cost_id>', methods=['DELETE'])
@auth_required
def delete_cost(cost_id):
    """刪除成本記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''DELETE FROM "重工成本分析" WHERE "識別碼" = %s''',
            (cost_id,)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/ncmr/<int:ncmr_id>', methods=['GET'])
@auth_required
def get_ncmr_info(ncmr_id):
    """獲取NCMR詳細資訊用於轉重工"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT n.*, 
                   p.姓名 AS 發現人員姓名,
                   v.廠商名稱 AS 廠商中文名稱
            FROM "不合格品單" n
            LEFT JOIN "品管人員" p ON n.發現人員 = p.識別碼
            LEFT JOIN "廠商資料" v ON n.廠商 = v.廠商名稱
            WHERE n.識別碼 = %s
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
        print(f"NCMR API Error: {str(e)}")
        print(f"Error type: {type(e)}")
        return jsonify({"error": f"獲取NCMR資訊失敗: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/rework/statistics', methods=['GET'])
@auth_required
def get_rework_statistics():
    """獲取重工統計數據"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        params = []
        where_clause = ""
        
        if start_date:
            where_clause += " AND 申請日期 >= %s"
            params.append(start_date)
        if end_date:
            where_clause += " AND 申請日期 <= %s"
            params.append(end_date)
            
        # 基本統計
        stats = {}
        
        # 申請數量統計
        sql = """
            SELECT 
                COUNT(*) as 總申請數,
                SUM(CASE WHEN 狀態 = '已完成' THEN 1 ELSE 0 END) as 完成數,
                SUM(CASE WHEN 狀態 = '執行中' THEN 1 ELSE 0 END) as 執行中數,
                SUM(CASE WHEN 狀態 = '已核准' THEN 1 ELSE 0 END) as 已核准數,
                SUM(CASE WHEN 審核狀態 = '已拒絕' THEN 1 ELSE 0 END) as 拒絕數,
                SUM(COALESCE(重工數量, 0)) as 總重工數量
            FROM "重工申請單" 
            WHERE 1=1 {where_clause}
        """
        cursor.execute(sql.format(where_clause=where_clause), params)
        
        result = cursor.fetchone()
        if result:
            stats['application_stats'] = {
                'total_applications': result[0],
                'completed': result[1],
                'in_progress': result[2],
                'approved': result[3],
                'rejected': result[4],
                'total_rework_quantity': float(result[5]) if result[5] else 0
            }
        
        # 移除成本統計功能
        # sql = """
        #     SELECT 
        #             COUNT(*) as 記錄數,
        #             SUM(COALESCE(總成本, 0)) as 總成本,
        #             SUM(CASE WHEN 成本類型 = '人工' THEN COALESCE(總成本, 0) ELSE 0 END) as 人工成本,
        #             SUM(CASE WHEN 成本類型 = '材料' THEN COALESCE(總成本, 0) ELSE 0 END) as 材料成本,
        #             SUM(CASE WHEN 成本類型 = '設備' THEN COALESCE(總成本, 0) ELSE 0 END) as 設備成本
        #     FROM "重工成本分析" c
        #     INNER JOIN "重工申請單" r ON c.重工單號 = r.識別碼
        #     WHERE 1=1 {where_clause}
        # """
        # cursor.execute(sql.format(where_clause=where_clause), params)
        # 
        # result = cursor.fetchone()
        # if result:
        #     stats['cost_stats'] = {
        #         'total_records': result[0],
        #         'total_cost': float(result[1]) if result[1] else 0,
        #         'labor_cost': float(result[2]) if result[2] else 0,
        #         'material_cost': float(result[3]) if result[3] else 0,
        #         'equipment_cost': float(result[4]) if result[4] else 0
        #     }
        stats['cost_stats'] = {
            'total_records': 0,
            'total_cost': 0,
            'labor_cost': 0,
            'material_cost': 0,
            'equipment_cost': 0
        }
        
        # 部門統計
        sql = """
            SELECT 
                部門,
                COUNT(*) as 申請數,
                SUM(COALESCE(重工數量, 0)) as 重工數量
            FROM "重工申請單" 
            WHERE 1=1 {where_clause}
            GROUP BY 部門
            ORDER BY 申請數 DESC
        """
        cursor.execute(sql.format(where_clause=where_clause), params)
        
        dept_stats = []
        for row in cursor.fetchall():
            dept_stats.append({
                'department': row[0],
                'count': row[1],
                'quantity': float(row[2]) if row[2] else 0
            })
        stats['department_stats'] = dept_stats
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【使用者管理】新增使用者
# ==================================================
@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT "識別碼" FROM "使用者" WHERE "使用者名稱" = %s''',
            (username,)
        )
        if cursor.fetchone():
            return jsonify({"error": "使用者名稱已存在"}), 400

        cursor.execute(
            '''INSERT INTO "使用者" ("使用者名稱", "密碼", "是否啟用") VALUES (%s, %s, 1)''',
            (username, hash_password(password))
        )
        conn.commit()
        return jsonify({"success": True, "message": "使用者建立成功"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【認證】驗證 Token
# ==================================================
@app.route('/api/verify')
@auth_required
def verify():
    return jsonify({"valid": True, "user": request.user})

# ==================================================
# 【不合格品管理】NCMR API
# ==================================================
@app.route('/api/ncmr', methods=['GET'])
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

@app.route('/api/ncmr/add', methods=['POST'])
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
            data.get('產品數量'),
            data.get('材質'),
            data.get('廠商'),
            data.get('批號'),
            data.get('不良描述'),
            data.get('不合格數量'),
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
        print(f"NCMR add error: {e}")  # Log the error
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/ncmr/update', methods=['POST'])
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

@app.route('/api/capa/update', methods=['POST'])
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

@app.route('/api/cara/delete', methods=['POST'])
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

@app.route('/api/capa/delete', methods=['POST'])
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
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/ncmr/source_info', methods=['GET'])
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



@app.route('/api/ncmr/delete', methods=['POST'])
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



# ==================================================
# 【異常矯正】CAPA API
# ==================================================

# ==================================================
# 【CAR矯正】API
# ==================================================
@app.route('/api/cara', methods=['GET'])
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

@app.route('/api/cara/create', methods=['POST'])
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

@app.route('/api/cara/detail/<int:id>')
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
        ncmr_cols = [c[0] for c in cursor.description]
        ncmr_data = dict(zip(ncmr_cols, ncmr_row))
        if ncmr_data.get('發現日期'): ncmr_data['發現日期'] = ncmr_data['發現日期'].strftime('%Y-%m-%d')

        return jsonify({"cara": cara_data, "ncmr": ncmr_data})
    finally:
        conn.close()

@app.route('/api/cara/update', methods=['POST'])
def update_cara():
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

@app.route('/api/capa', methods=['GET'])
def get_capa_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT T1.*, P."姓名" AS "負責人員姓名", N."來源", N."不良描述", 
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
            if item.get('建立日期'): item['建立日期'] = item['建立日期'].strftime('%Y-%m-%d')
            if item.get('結案日期'): item['結案日期'] = item['結案日期'].strftime('%Y-%m-%d')
            data.append(item)
        return jsonify(data)
    finally:
        conn.close()

@app.route('/api/capa/create', methods=['POST'])
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
        """, (capa_number, ncmr_id))
        
        # 更新 NCMR 狀態
        cursor.execute('''UPDATE "不合格品單" SET "狀態" = '矯正中' WHERE "識別碼" = %s''', (ncmr_id,))
        
        conn.commit()
        return jsonify({"success": True, "capa_number": capa_number, "ncmr_number": ncmr_number})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/capa/detail/<int:id>')
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
        ncmr_cols = [c[0] for c in cursor.description]
        ncmr_data = dict(zip(ncmr_cols, ncmr_row))
        if ncmr_data.get('發現日期'): ncmr_data['發現日期'] = ncmr_data['發現日期'].strftime('%Y-%m-%d')

        return jsonify({"capa": capa_data, "ncmr": ncmr_data})
    finally:
        conn.close()

# ==================================================
# 【廠商公差管理】API
# ==================================================
@app.route('/api/tolerance/search', methods=['GET'])
@auth_required
def search_tolerance():
    """查詢公差資料"""
    args = request.args
    params = []
    where = []
    
    if args.get('material'):
        where.append('T1."材質" LIKE %s')
        params.append(f"%{args['material']}%")
    if args.get('vendor_id'):
        where.append('T1."廠商ID" = %s')
        params.append(args['vendor_id'])
    if args.get('spec'):
        where.append('T1."規格" LIKE %s')
        params.append(f"%{args['spec']}%")
    
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    
    # 分頁參數
    page = int(args.get('page', 1))
    page_size = int(args.get('page_size', 20))
    offset = (page - 1) * page_size
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢總筆數
        count_sql = f"""
            SELECT COUNT(*) 
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            {where_sql}
        """
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]
        
        # 查詢分頁資料
        sql = f"""
            SELECT T1."識別碼", T1."材質", T1."規格", T1."廠商ID", V."廠商名稱",
                   T1."備註", T1."建立日期"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            {where_sql}
            ORDER BY T1."識別碼" DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(sql, params + [page_size, offset])
        cols = [c[0] for c in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            for key, val in item.items():
                item[key] = format_value(val)
            results.append(item)
        
        return jsonify({
            "success": True, 
            "data": results, 
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/<int:id>', methods=['GET'])
@auth_required
def get_tolerance_detail(id):
    """獲取單筆公差詳細資料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢主檔
        cursor.execute("""
            SELECT T1."識別碼", T1."材質", T1."規格", T1."廠商ID", V."廠商名稱",
                   T1."備註", T1."建立日期"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            WHERE T1."識別碼" = %s
        """, (id,))
        
        main_row = cursor.fetchone()
        if not main_row:
            return jsonify({"error": "找不到該筆公差資料"}), 404
        
        cols = [c[0] for c in cursor.description]
        main_data = dict(zip(cols, main_row))
        for key, val in main_data.items():
            main_data[key] = format_value(val)
        
        # 查詢明細
        cursor.execute("""
            SELECT "識別碼", "測量項目", "測量位置", "尺寸下限", "尺寸上限",
                   "公差下限", "公差上限", "標準值", "單位", "備註"
            FROM "廠商公差明細檔"
            WHERE "主檔ID" = %s
            ORDER BY "識別碼"
        """, (id,))
        
        details = []
        cols = [c[0] for c in cursor.description]
        for row in cursor.fetchall():
            detail = dict(zip(cols, row))
            for key, val in detail.items():
                detail[key] = format_value(val)
            details.append(detail)
        
        return jsonify({"success": True, "main": main_data, "details": details})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/add', methods=['POST'])
@auth_required
def add_tolerance():
    """新增公差資料"""
    data = request.json
    
    if not data.get('材質'):
        return jsonify({"error": "材質為必填欄位"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 插入主檔（不記錄建立人員）
        cursor.execute("""
            INSERT INTO "廠商公差主檔" ("材質", "規格", "廠商ID", "備註")
            VALUES (%s, %s, %s, %s)
        """, (
            data.get('材質'),
            data.get('規格'),
            data.get('廠商ID'),
            data.get('備註')
        ))
        
        # 獲取新插入的主檔ID
        cursor.execute('''SELECT lastval()''')
        main_id = cursor.fetchone()[0]
        
        # 插入明細
        details = data.get('details', [])
        for detail in details:
            cursor.execute("""
                INSERT INTO "廠商公差明細檔" 
                ("主檔ID", "測量項目", "測量位置", "尺寸下限", "尺寸上限", "公差下限", "公差上限", "標準值", "單位", "備註")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                main_id,
                detail.get('測量項目'),
                detail.get('測量位置'),
                detail.get('尺寸下限'),
                detail.get('尺寸上限'),
                detail.get('公差下限'),
                detail.get('公差上限'),
                detail.get('標準值'),
                detail.get('單位', 'mm'),
                detail.get('備註')
            ))
        
        conn.commit()
        return jsonify({"success": True, "id": int(main_id)})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/update/<int:id>', methods=['POST'])
@auth_required
def update_tolerance(id):
    """更新公差資料"""
    data = request.json
    
    if not data.get('材質'):
        return jsonify({"error": "材質為必填欄位"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 更新主檔（不記錄更新人員）
        cursor.execute("""
            UPDATE "廠商公差主檔"
            SET "材質" = %s, "規格" = %s, "廠商ID" = %s, "備註" = %s
            WHERE "識別碼" = %s
        """, (
            data.get('材質'),
            data.get('規格'),
            data.get('廠商ID'),
            data.get('備註'),
            id
        ))
        
        # 刪除舊明細
        cursor.execute('''DELETE FROM "廠商公差明細檔" WHERE "主檔ID" = %s''', (id,))
        
        # 插入新明細
        details = data.get('details', [])
        for detail in details:
            cursor.execute("""
                INSERT INTO "廠商公差明細檔" 
                ("主檔ID", "測量項目", "測量位置", "尺寸下限", "尺寸上限", "公差下限", "公差上限", "標準值", "單位", "備註")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id,
                detail.get('測量項目'),
                detail.get('測量位置'),
                detail.get('尺寸下限'),
                detail.get('尺寸上限'),
                detail.get('公差下限'),
                detail.get('公差上限'),
                detail.get('標準值'),
                detail.get('單位', 'mm'),
                detail.get('備註')
            ))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/delete/<int:id>', methods=['POST'])
@auth_required
def delete_tolerance(id):
    """刪除公差資料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''DELETE FROM "廠商公差主檔" WHERE "識別碼" = %s''', (id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/options', methods=['GET'])
def get_tolerance_options():
    """獲取公差選項資料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取材質列表
        cursor.execute('''SELECT DISTINCT "材質" FROM "廠商公差主檔" WHERE "材質" IS NOT NULL ORDER BY "材質"''')
        materials = [row[0] for row in cursor.fetchall()]
        
        # 獲取規格列表
        cursor.execute('''SELECT DISTINCT "規格" FROM "廠商公差主檔" WHERE "規格" IS NOT NULL AND "規格" != '' ORDER BY "規格"''')
        specs = [row[0] for row in cursor.fetchall()]
        
        # 獲取廠商列表
        cursor.execute('''SELECT "識別碼", "廠商名稱" FROM "廠商資料" ORDER BY "廠商名稱"''')
        vendors = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        
        # 獲取測量項目列表
        cursor.execute('''SELECT DISTINCT "測量項目" FROM "廠商公差明細檔" WHERE "測量項目" IS NOT NULL ORDER BY "測量項目"''')
        measure_items = [row[0] for row in cursor.fetchall()]
        
        return jsonify({
            "materials": materials,
            "specs": specs,
            "vendors": vendors,
            "measureItems": measure_items
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/export', methods=['GET'])
@auth_required
def export_tolerance_excel():
    """匯出公差資料為 Excel"""
    args = request.args
    params = []
    where = []
    
    if args.get('material'):
        where.append('T1."材質" LIKE %s')
        params.append(f"%{args['material']}%")
    if args.get('vendor_id'):
        where.append('T1."廠商ID" = %s')
        params.append(args['vendor_id'])
    if args.get('spec'):
        where.append('T1."規格" LIKE %s')
        params.append(f"%{args['spec']}%")
    
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢主檔和明細
        sql = f"""
            SELECT T1."識別碼", T1."材質", T1."規格", V."廠商名稱",
                   T2."測量項目", T2."測量位置", T2."尺寸下限", T2."尺寸上限",
                   T2."公差下限", T2."公差上限", T2."標準值", T2."單位", T2."備註"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            LEFT JOIN "廠商公差明細檔" T2 ON T1."識別碼" = T2."主檔ID"
            {where_sql}
            ORDER BY T1."識別碼", T2."識別碼"
        """
        cursor.execute(sql, params)
        
        rows = cursor.fetchall()
        if not rows:
            df = pd.DataFrame(columns=['識別碼', '材質', '規格', '廠商名稱', '測量項目', '測量位置', 
                                       '尺寸下限', '尺寸上限', '公差下限', '公差上限', '標準值', '單位', '備註'])
        else:
            cols = [c[0] for c in cursor.description]
            df = pd.DataFrame([list(r) for r in rows], columns=cols)
        
        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        
        return send_file(output, as_attachment=True, download_name='廠商公差資料.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@app.route('/api/tolerance/check', methods=['GET', 'OPTIONS'])
def check_tolerance():
    """根據廠商+材質+規格查詢公差標準，用於出貨檢驗驗證
    優先順序：
    1. 相同廠商 + 相同材質 + 相同規格（完全匹配）
    2. 相同廠商 + 相同材質 + 規格部分匹配（檢驗規格以公差表規格開頭）
    3. 相同廠商 + 相同材質 + 無規格（通用）
    4. 無廠商（通用） + 相同材質 + 相同規格
    5. 無廠商（通用） + 相同材質 + 規格部分匹配
    6. 無廠商（通用） + 相同材質 + 無規格
    """
    # 處理 CORS 預檢請求
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # 驗證認證
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': '缺少認證 Token'}), 401
    if token.startswith('Bearer '):
        token = token[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({'error': '無效或過期的 Token'}), 401
    request.user = payload
    
    vendor_id = request.args.get('vendor_id')
    material = request.args.get('material')
    spec = request.args.get('spec')

    if not material:
        return jsonify({"success": False, "error": "材質為必填參數"}), 400
    
    # 將 vendor_id 轉換為整數（URL 參數是字串）
    if vendor_id:
        try:
            vendor_id = int(vendor_id)
        except (ValueError, TypeError):
            vendor_id = None

    # 正規化規格字串（移除多餘空白、統一分隔符）
    def normalize_spec(spec_str):
        """正規化規格字串"""
        # 資料庫 NULL 值會變成 Python None
        if spec_str is None:
            return ''
        # 字串處理
        if isinstance(spec_str, str):
            spec_str = spec_str.strip().replace('×', '*').replace('x', '*')
            # 移除多餘的*
            while '**' in spec_str:
                spec_str = spec_str.replace('**', '*')
            # 處理字串 "None" 或 "NULL" 
            if spec_str.upper() in ('NONE', 'NULL', ''):
                return ''
            return spec_str.strip()
        return ''

    input_spec = normalize_spec(spec)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢所有符合材質條件的公差主檔
        sql = """
            SELECT T1."識別碼", T1."材質", T1."規格", T1."廠商ID", V."廠商名稱"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            WHERE T1."材質" = %s
        """
        params = [material]
        cursor.execute(sql, params)
        candidates = cursor.fetchall()

        # 分類候選記錄
        priority1_exact = []    # 有廠商 + 完全匹配
        priority2_partial = []  # 有廠商 + 規格部分匹配（開頭匹配）
        priority3_generic = []  # 有廠商 + 無規格
        priority4_exact = []    # 無廠商 + 完全匹配
        priority5_partial = []  # 無廠商 + 規格部分匹配
        priority6_generic = []  # 無廠商 + 無規格

        for row in candidates:
            tol_id = row[0]
            tol_material = row[1]
            tol_spec = row[2]
            tol_vendor_id = row[3]
            tol_vendor_name = row[4]

            normalized_spec = normalize_spec(tol_spec)
            has_vendor = tol_vendor_id is not None
            has_spec = normalized_spec != ''

            # 判斷匹配類型
            # 檢查廠商ID是否匹配（P1-P3需要廠商ID完全相同）
            vendor_match = (tol_vendor_id == vendor_id) if (tol_vendor_id is not None and vendor_id is not None) else False
            
            if vendor_match:
                # 廠商匹配的記錄 (Priority 1-3)
                if has_spec and normalized_spec == input_spec:
                    # 完全匹配
                    priority1_exact.append(row)
                elif has_spec and input_spec.startswith(normalized_spec + '*'):
                    # 規格部分匹配
                    priority2_partial.append(row)
                elif not has_spec:
                    # 無規格（通用）
                    priority3_generic.append(row)
            elif not has_vendor:
                # 無廠商的記錄 (Priority 4-6)
                if has_spec and normalized_spec == input_spec:
                    priority4_exact.append(row)
                elif has_spec and input_spec.startswith(normalized_spec + '*'):
                    priority5_partial.append(row)
                elif not has_spec:
                    priority6_generic.append(row)
            else:
                # 有廠商但不匹配的記錄（跳過）
                pass

        # 按優先順序選擇
        matched_row = None
        for idx, priority_list in enumerate([priority1_exact, priority2_partial, priority3_generic,
                                             priority4_exact, priority5_partial, priority6_generic]):
            if priority_list:
                matched_row = priority_list[0]
                break

        if not matched_row:
            return jsonify({"success": True, "found": False, "message": "找不到對應的公差標準"})

        main_row = matched_row
        
        if not main_row:
            return jsonify({"success": True, "found": False, "message": "找不到對應的公差標準"})
        
        main_id = main_row[0]
        
        # 查詢明細公差資料
        cursor.execute("""
            SELECT "測量項目", "測量位置", "尺寸下限", "尺寸上限", 
                   "公差下限", "公差上限", "標準值", "單位"
            FROM "廠商公差明細檔"
            WHERE "主檔ID" = %s
            ORDER BY "識別碼"
        """, (main_id,))
        
        details = []
        for row in cursor.fetchall():
            details.append({
                "項目": row[0],
                "位置": row[1] or '',
                "尺寸下限": float(row[2]) if row[2] is not None else None,
                "尺寸上限": float(row[3]) if row[3] is not None else None,
                "公差下限": float(row[4]) if row[4] is not None else None,
                "公差上限": float(row[5]) if row[5] is not None else None,
                "標準值": float(row[6]) if row[6] is not None else None,
                "單位": row[7] or 'mm'
            })
        
        return jsonify({
            "success": True, 
            "found": True,
            "tolerance_id": main_id,
            "material": main_row[1],
            "spec": main_row[2],
            "vendor_id": main_row[3],
            "vendor_name": main_row[4].strip() if main_row[4] else '',
            "tolerances": details
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()


@app.route('/api/tolerance/import', methods=['POST'])
@auth_required
def import_tolerance_excel():
    """從 Excel 匯入公差資料"""
    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400
    
    try:
        df = pd.read_excel(file, engine='openpyxl')
    except Exception as e:
        return jsonify({"error": f"檔案讀取失敗: {str(e)}"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        user_id = request.user.get('user_id')
        success_count = 0
        current_main_id = None
        current_material = None
        current_spec = None
        
        for idx, row in df.iterrows():
            row_data = row.to_dict()
            
            # 將 NaN 轉為 None
            for key in row_data:
                if pd.isna(row_data[key]):
                    row_data[key] = None
            
            material = row_data.get('材質')
            spec = row_data.get('規格')
            vendor_name = row_data.get('廠商名稱')
            
            # 如果材質或規格改變，創建新的主檔
            if material and (material != current_material or spec != current_spec):
                # 查找廠商ID
                vendor_id = None
                if vendor_name:
                    cursor.execute('''SELECT "識別碼" FROM "廠商資料" WHERE "廠商名稱" = %s''', (vendor_name,))
                    v = cursor.fetchone()
                    vendor_id = v[0] if v else None
                
                # 插入主檔
                cursor.execute("""
                    INSERT INTO "廠商公差主檔" ("材質", "規格", "廠商ID")
                    VALUES (%s, %s, %s)
                """, (material, spec, vendor_id))
                
                cursor.execute('''SELECT lastval()''')
                current_main_id = cursor.fetchone()[0]
                current_material = material
                current_spec = spec
            
            # 插入明細
            if current_main_id:
                cursor.execute("""
                    INSERT INTO "廠商公差明細檔" 
                    ("主檔ID", "測量項目", "測量位置", "尺寸下限", "尺寸上限", "公差下限", "公差上限", "標準值", "單位", "備註")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    current_main_id,
                    row_data.get('測量項目'),
                    row_data.get('測量位置'),
                    row_data.get('尺寸下限'),
                    row_data.get('尺寸上限'),
                    row_data.get('公差下限'),
                    row_data.get('公差上限'),
                    row_data.get('標準值'),
                    row_data.get('單位', 'mm'),
                    row_data.get('備註')
                ))
                success_count += 1
        
        conn.commit()
        return jsonify({"success": True, "message": f"成功匯入 {success_count} 筆明細資料"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()
# ==================================================
# 啟動伺服器 (生產環境使用 Waitress)
# ==================================================
if __name__ == '__main__':
    try:
        from waitress import serve
        print("=" * 60)
        print(">>> 品保資料庫系統啟動中...")
        print(">>> 伺服器地址: http://0.0.0.0:5000")
        print(">>> 支援並發: 8 個執行緒")
        print(">>> 認證機制: JWT Token (24小時有效)")
        print("=" * 60)
        serve(app, host='0.0.0.0', port=5000, threads=8)
    except ImportError:
        print("警告: 未安裝 waitress，使用開發伺服器")
        print("請執行: pip install waitress")
        print("=" * 60)
        app.run(debug=False, host='0.0.0.0', port=5000)
