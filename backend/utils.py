import secrets
import hashlib
import jwt
import re
import decimal
import bcrypt
from datetime import datetime, timedelta, timezone, date
from functools import wraps
from flask import request, jsonify, session
from typing import List, Dict, Any, Optional, Union
from .config import SECRET_KEY, TOKEN_EXPIRATION_HOURS

# ==================================================
# Databse Connection (for ID generation)
# ==================================================
from sqlalchemy import text
from .extensions import db

# ==================================================
# XSS Protection & Sanitization
# ==================================================
try:
    from markupsafe import escape as _escape
    def escape(s: Optional[Union[str, int, float]]) -> str:
        if s is None:
            return ''
        return _escape(str(s))
except ImportError:
    import html
    def escape(s: Optional[Union[str, int, float]]) -> str:
        if s is None:
            return ''
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')

def sanitize_html(text: Optional[Union[str, int, float]]) -> str:
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

def sanitize_input(data: Any) -> Any:
    """Recursively sanitize all string values in a dictionary/list"""
    if isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    elif isinstance(data, str):
        return sanitize_html(data)
    else:
        return data

def get_sanitized_json() -> Any:
    """Get and sanitize JSON data from request"""
    json_data = request.get_json(silent=True)
    if json_data:
        return sanitize_input(json_data)
    return json_data

# ==================================================
# CSRF Protection
# ==================================================
def generate_csrf_token() -> str:
    """Generate a CSRF token for the session"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token: Optional[str]) -> bool:
    """Validate CSRF token"""
    session_token = session.get('csrf_token')
    if not session_token or not token:
        return False
    return secrets.compare_digest(session_token, token)


# ==================================================
# Authentication
# ==================================================
def hash_password(password: str) -> str:
    """Hash password using bcrypt with random salt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash. Falls back to SHA256 for legacy migration."""
    # Try bcrypt first
    if hashed.startswith('$2b$') or hashed.startswith('$2a$'):
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    # Legacy SHA256 fallback for migration
    return hashlib.sha256(password.encode()).hexdigest() == hashed

def generate_token(user_id: int, username: str) -> str:
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def auth_required(f: Any) -> Any:
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
def generate_number(prefix: str, table_name: Optional[str] = None, number_field: Optional[str] = None) -> str:
    """
    統一編碼生成函數
    格式：PREFIX-YYYYMM-XXX (例：NCMR-202601-001)
    """
    year_month = datetime.now().strftime('%Y%m')
    
    if table_name and number_field:
        try:
            sql = f"""
                SELECT "{number_field}" 
                FROM "{table_name}" 
                WHERE "{number_field}" IS NOT NULL 
                AND "{number_field}" LIKE :pattern
                ORDER BY "{number_field}" DESC
            """
            pattern = f"{prefix}-{year_month}-%"
            # Use db.session.execute with text()
            result = db.session.execute(text(sql), {"pattern": pattern})
            results = result.fetchall()
            
            max_seq = 0
            
            if results:
                for row in results:
                    # row is a Row object/tuple, access by index 0
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
        except Exception as e:
            raise e
    else:
        return f"{prefix}-{year_month}-001"

def generate_ncmr_number() -> str:
    """生成NCMR編號"""
    return generate_number('NCMR', "不合格品單", 'NCMR單號')

def generate_8d_number() -> str:
    """生成8D編號"""
    return generate_number('CAPA', "異常矯正單", "8D單號")

def generate_car_number() -> str:
    """生成CAR編號"""
    return generate_number('CAR', "異常矯正單", 'CAR單號')


# ==================================================
# Formatting & Validation
# ==================================================
def format_value(val: Any) -> Any:
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

def validate_date_format(date_str: Optional[str]) -> bool:
    if not date_str:
        return True
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_inspection_data(data: Dict[str, Any]) -> List[str]:
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

def validate_patrol_data(data: Dict[str, Any]) -> List[str]:
    errors = []
    if not data.get('檢驗日期'):
        errors.append("檢驗日期為必填欄位")
    elif not validate_date_format(data.get('檢驗日期')):
        errors.append("檢驗日期格式錯誤，應為 YYYY-MM-DD")
    if not data.get('機台'):
        errors.append("機台為必填欄位")
    if not data.get('主機手'):
        errors.append("主機手為必填欄位")
    if not data.get('檢驗人員'):
        errors.append("檢驗人員為必填欄位")
    if not data.get('details') or len(data.get('details', [])) == 0:
        errors.append("明細資料為必填欄位")
    return errors

def handle_db_error(e: Exception) -> str:
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
