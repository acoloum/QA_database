import secrets
import hashlib
import jwt
import re
import decimal
import psycopg2
from datetime import datetime, timedelta, timezone, date
from functools import wraps
from flask import request, jsonify, session
from .config import SECRET_KEY, TOKEN_EXPIRATION_HOURS, POSTGRESQL_CONFIG

# ==================================================
# Databse Connection (for ID generation)
# ==================================================
def get_db_connection():
    # Avoid circular import if possible, or duplicate/import from database.py
    # Since utils might be imported by database.py (unlikely), but let's just import here
    from .database import get_db_connection as get_conn
    return get_conn()

# ==================================================
# XSS Protection & Sanitization
# ==================================================
try:
    from markupsafe import escape as _escape
    def escape(s):
        if s is None:
            return ''
        return _escape(str(s))
except ImportError:
    import html
    def escape(s):
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

def get_sanitized_json():
    """Get and sanitize JSON data from request"""
    json_data = request.get_json(silent=True)
    if json_data:
        return sanitize_input(json_data)
    return json_data

# ==================================================
# CSRF Protection
# ==================================================
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


# ==================================================
# Authentication
# ==================================================
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


# ==================================================
# ID Generation
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
            sql = f"""
                SELECT "{number_field}" 
                FROM "{table_name}" 
                WHERE "{number_field}" IS NOT NULL 
                AND "{number_field}" LIKE %s
                ORDER BY "{number_field}" DESC
            """
            pattern = f"{prefix}-{year_month}-%"
            cursor.execute(sql, (pattern,))
            
            results = cursor.fetchall()
            max_seq = 0
            
            if results:
                for row in results:
                    if row[0]:
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


# ==================================================
# Formatting & Validation
# ==================================================
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
