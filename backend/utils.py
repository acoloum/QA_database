import inspect
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

def generate_token(user_id: int, username: str, role: str = 'user') -> str:
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
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

def require_admin(f: Any) -> Any:
    """要求 JWT 中 role == 'admin' 的裝飾器，需緊接在 @auth_required 之後使用"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(request, 'user', {})
        if user.get('role') != 'admin':
            return jsonify({'error': '此操作需要管理員權限'}), 403
        return f(*args, **kwargs)
    return decorated

def auth_required(f: Any) -> Any:
    """JWT 驗證裝飾器。

    支援兩種路由風格：
    - 舊式：函式簽名不含 current_user，透過 request.user（dict）存取使用者
    - 新式：函式第一個參數為 current_user，自動注入 Inspector ORM 物件
    """
    # 預先判斷函式是否需要 current_user（避免每次請求都用 inspect）
    sig_params = list(inspect.signature(f).parameters.keys())
    _inject_user = bool(sig_params and sig_params[0] == 'current_user')

    @wraps(f)
    def decorated(*args, **kwargs):
        # 僅接受 Authorization header，禁止從 query string 取得 token
        # （URL token 會被記錄至 Nginx log、瀏覽器歷史及 Referer header）
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': '缺少認證 Token'}), 401
        if token.startswith('Bearer '):
            token = token[7:]
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': '無效或過期的 Token'}), 401
        request.user = payload

        if _inject_user:
            # 注入 User ORM 物件供新式路由使用
            from .models import User
            user_id = payload.get('id') or payload.get('user_id')
            current_user = User.query.get(user_id) if user_id else None
            return f(current_user, *args, **kwargs)

        return f(*args, **kwargs)
    return decorated


# ==================================================
# File Upload Validation (C-3)
# ==================================================
import os as _os

def validate_upload_file(file: Any, max_bytes: int = 10 * 1024 * 1024) -> Optional[str]:
    """
    驗證上傳檔案的副檔名與大小限制（出貨/巡檢匯入共用）
    回傳錯誤訊息字串；無錯誤則回傳 None
    """
    allowed_extensions = {'.xlsx', '.xls'}
    ext = _os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return f"不支援的檔案格式: {ext}，僅接受 .xlsx / .xls"
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > max_bytes:
        return f"檔案大小超過 {max_bytes // (1024 * 1024)}MB 限制"
    return None


# ==================================================
# Spec Nominal Parser (C-2)
# ==================================================
def parse_spec_nominals(spec: Optional[str]) -> Dict[str, float]:
    """
    從規格字串解析各尺寸名義值（shipping/patrol 共用）
    例：'31.9*2.2*589' → {'外徑': 31.9, '厚度': 2.2, '內徑': 27.5, '長度': 589.0}
    """
    result: Dict[str, float] = {}
    if not spec:
        return result
    s = str(spec).strip().replace('×', '*').replace('x', '*').replace('X', '*')
    while '**' in s:
        s = s.replace('**', '*')
    parts = s.split('*')
    try:
        nums = [float(p.strip()) for p in parts if p.strip()]
        if len(nums) >= 2:
            result['外徑'] = nums[0]
            val2 = nums[1]
            if val2 < (nums[0] / 2):
                result['厚度'] = val2
                result['內徑'] = nums[0] - (val2 * 2)
            else:
                result['內徑'] = val2
                result['厚度'] = (nums[0] - val2) / 2
            if len(nums) >= 3:
                result['長度'] = nums[2]
        elif len(nums) == 1:
            result['外徑'] = nums[0]
    except (ValueError, TypeError):
        pass
    return result


# ==================================================
# ID Generation
# ==================================================

# 允許使用 generate_number 的（資料表, 欄位）白名單，防止 SQL Injection
_NUMBER_FIELD_WHITELIST: Dict[str, str] = {
    "不合格品單":  "NCMR單號",
    "異常矯正單":  "8D單號",   # CAR 與 8D 共用同一張表，欄位不同
    "重工申請單":  "申請單號",
}
# 異常矯正單同時有 8D單號 與 CAR單號 兩個欄位，另外維護完整允許集合
_NUMBER_PAIR_WHITELIST: set = {
    ("不合格品單", "NCMR單號"),
    ("異常矯正單", "8D單號"),
    ("異常矯正單", "CAR單號"),
    ("重工申請單", "申請單號"),
}

def generate_number(prefix: str, table_name: Optional[str] = None, number_field: Optional[str] = None) -> str:
    """
    統一編碼生成函數
    格式：PREFIX-YYYYMM-XXX (例：NCMR-202601-001)
    """
    year_month = datetime.now().strftime('%Y%m')

    if table_name and number_field:
        # 白名單驗證：只允許已知的（資料表, 欄位）組合，防止 f-string 拼接注入
        if (table_name, number_field) not in _NUMBER_PAIR_WHITELIST:
            raise ValueError(f"不允許的資料表或欄位名稱：{table_name}.{number_field}")

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

    # 測量欄位數字格式驗證（嚴格 regex：杜絕 "40.06+" 等尾隨字元）
    measurement_fields = [
        # (field_prefix, suffix) - suffix 為空字串時為單一數值欄位
        ('外徑', 'min'), ('外徑', 'max'),
        ('內徑', 'min'), ('內徑', 'max'),
        ('厚度', 'min'), ('厚度', 'max'),
        ('同心度', ''), ('長度', ''), ('硬度', ''),
        ('真直度', ''), ('真圓度', ''),
    ]
    import re
    num_pattern = re.compile(r'^[+-]?\d+(\.\d+)?$')
    group_count = int(data.get('組數', 5)) if data.get('組數') else 5

    for i in range(1, group_count + 1):
        for prefix, suffix in measurement_fields:
            if suffix:
                key = f'{prefix}{i}-{suffix}'
            else:
                key = f'{prefix}{i}'
            val = data.get(key)
            if val is not None and val != '':
                if not num_pattern.match(str(val)):
                    display_name = f'{prefix}{i}{("-" + suffix) if suffix else ""}'
                    errors.append(f'「{display_name}」需為有效數字')

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

def handle_db_error(e: Exception) -> Dict[str, Any]:
    """處理資料庫錯誤，回傳結構成 {message, field?} 供前端欄位對應"""
    error_msg = str(e)
    # 嘗試從錯誤訊息中解析欄位名稱
    # 格式: ... "外徑1-min", '40.06+', ... → 取第一個遇到的欄位名稱
    field_name = None
    # 常見測量欄位模式
    import re
    patterns = [
        r'"([^"]*-min)"',
        r'"([^"]*-max)"',
        r'"(外徑\d+)"',
        r'"(內徑\d+)"',
        r'"(厚度\d+)"',
        r'"(同心度\d+)"',
        r'"(長度\d+)"',
        r'"(硬度\d+)"',
        r'"(真直度\d+)"',
        r'"(真圓度\d+)"',
    ]
    for p in patterns:
        m = re.search(p, error_msg)
        if m:
            field_name = m.group(1)
            break

    if 'FOREIGN KEY' in error_msg:
        return {"message": '關聯資料錯誤：請檢查相關資料是否存在'}
    elif 'UNIQUE' in error_msg:
        return {"message": '資料重複：此筆資料已存在'}
    elif 'NOT NULL' in error_msg:
        return {"message": '資料不完整：請填寫所有必填欄位'}
    elif 'InvalidTextRepresentation' in error_msg:
        if field_name:
            return {"message": f'「{field_name}」包含無效字元，請輸入純數字', "field": field_name}
        return {"message": '測量數值包含無效字元，請檢查是否輸入非數字內容'}
    elif 'timeout' in error_msg.lower():
        return {"message": '資料庫連線逾時，請稍後再試'}
    elif 'connection' in error_msg.lower():
        return {"message": '資料庫連線失敗，請檢查連線設定'}
    elif 'login' in error_msg.lower() or 'authentication' in error_msg.lower():
        return {"message": '資料庫認證失敗，請檢查連線設定'}
    else:
        return {"message": f'資料庫錯誤：{error_msg}'}
