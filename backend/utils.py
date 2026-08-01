import inspect
import secrets
import hashlib
import jwt
import re
import decimal
import bcrypt
from datetime import datetime, timedelta, timezone, date
from functools import wraps
from flask import g, request, jsonify, session
from typing import List, Dict, Any, Optional, Union
from .config import SECRET_KEY, TOKEN_EXPIRATION_HOURS
from .errors import build_error_envelope

# ==================================================
# Databse Connection (for ID generation)
# ==================================================
from sqlalchemy import text
from .extensions import db

# ==================================================
# API 回傳格式 Helper
# ==================================================
def api_success(data=None, message: str = '操作成功', code: int = 200):
    """統一成功回傳格式"""
    return jsonify({'success': True, 'data': data, 'message': message}), code

def api_error(
    message: str,
    status: int = 400,
    *,
    code: str = "VALIDATION_ERROR",
    details=None,
):
    """統一錯誤回傳格式"""
    return jsonify(build_error_envelope(message, code, details)), status


def bounded_int(value, default: int, min_value: int, max_value: int) -> int:
    """將外部整數參數限制在指定範圍內，格式錯誤時回退預設值。"""
    try:
        parsed = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(parsed, max_value))


def parse_optional_int(value, field_name: str) -> Optional[int]:
    """解析可選整數參數；格式錯誤時回報明確欄位，避免落入 500。"""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 必須為整數")


def parse_optional_date(value, field_name: str) -> Optional[date]:
    """解析可選 YYYY-MM-DD 日期參數；格式錯誤時回報明確欄位。"""
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 日期格式錯誤，應為 YYYY-MM-DD")


def validate_excel_shape(df: Any, max_rows: int = 5000, max_columns: int = 200) -> None:
    """限制 Excel 匯入內容規模，避免小檔案但超大工作表拖垮匯入流程。"""
    rows, columns = df.shape
    if rows > max_rows:
        raise ValueError(f"Excel 列數超過 {max_rows} 筆限制")
    if columns > max_columns:
        raise ValueError(f"Excel 欄位數超過 {max_columns} 欄限制")


# ==================================================
# 狀態機驗證
# ==================================================
_STATUS_TRANSITIONS: dict = {
    'NCMR': {
        '待處理':   {'矯正中', '已結案'},
        '矯正中':   {'矯正完成', '已結案'},
        # 「CAR處理中」是舊版流程遺留的狀態值，語意等同現行的「矯正中」
        'CAR處理中': {'矯正完成', '已結案'},
        '矯正完成': {'已結案'},
        '已結案':   set(),
        'CAR已完成': set(),
    },
    'CAPA': {
        '進行中': {'已結案'},
        '已結案': set(),
    },
    '重工': {
        '申請中': {'執行中', '撤銷', '已核准', '已拒絕'},
        '已核准': {'執行中', '撤銷'},
        '已拒絕': set(),
        '執行中': {'已結案'},
        '已完成': {'已結案'},
        '已結案': set(),
        '撤銷':   set(),
    },
}

def validate_status_transition(model: str, current: str, new: str) -> None:
    """驗證狀態轉移合法性，不合法拋出 ValueError"""
    allowed = _STATUS_TRANSITIONS.get(model, {}).get(current, set())
    if new not in allowed:
        raise ValueError(f'非法狀態轉移：{model} {current!r} → {new!r}')


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

def generate_token(
    user_id: int,
    username: str,
    role: str,
    token_version: int,
) -> str:
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'token_version': token_version,
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
    decorated.__admin_required__ = True
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
        from .authentication import authenticate_request_token
        from .errors import AuthenticationError

        try:
            current_user, authenticated_user = authenticate_request_token(token)
        except AuthenticationError as error:
            return api_error(
                error.message,
                401,
                code=error.code,
                details=error.details,
            )
        request.user = authenticated_user.as_request_user()
        request.authenticated_user = authenticated_user
        g.current_user_model = current_user

        if _inject_user:
            return f(current_user, *args, **kwargs)

        return f(*args, **kwargs)
    return decorated


# ==================================================
# 細粒度權限控制
# ==================================================
def role_grants_permission(current_user, perm: str) -> bool:
    """舊 import path 相容 alias；實作集中於 authorization。"""
    from .authorization import role_grants_permission as grants
    return grants(current_user, perm)


def require_permission(perm: str):
    """單一權限相容 alias，不再依賴 route 函式參數。"""
    from .authorization import require_permission as centralized
    return centralized(perm)


def require_perm(perm: str):
    """舊式名稱相容 alias，與 require_permission 共用同一實作。"""
    from .authorization import require_perm as centralized
    return centralized(perm)


# ==================================================
# 操作審計日誌
# ==================================================
def log_audit(user_id, action: str, module: str,
              record_id=None, old_val=None, new_val=None) -> None:
    """將操作寫入審計日誌（在現有 db.session 中新增，由呼叫方負責 commit）"""
    from .models import AuditLog
    entry = AuditLog(
        user_id=user_id,
        action=action,
        module=module,
        record_id=record_id,
        old_value=old_val,
        new_value=new_val,
    )
    db.session.add(entry)


# ==================================================
# File Upload Validation (C-3)
# ==================================================
import os as _os

def validate_upload_file(
    file: Any,
    max_bytes: int = 10 * 1024 * 1024,
    allowed_extensions: Optional[set[str]] = None,
) -> Optional[str]:
    """
    驗證上傳檔案的副檔名與大小限制（出貨/巡檢匯入共用）
    回傳錯誤訊息字串；無錯誤則回傳 None
    """
    allowed_extensions = allowed_extensions or {'.xlsx', '.xls'}
    ext = _os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        allowed_text = " / ".join(sorted(allowed_extensions))
        return f"不支援的檔案格式: {ext}，僅接受 {allowed_text}"
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > max_bytes:
        return f"檔案大小超過 {max_bytes // (1024 * 1024)}MB 限制"
    return None


# ==================================================
# 規格字串正規化（公差比對共用）
# ==================================================
def normalize_spec_for_match(spec: Optional[str]) -> str:
    """正規化規格字串供公差比對：統一分隔符號並把數值段轉為標準數值寫法。

    公差比對是逐段字串相等，因此「4」與「4.0」原本被視為不同段而配對失敗——
    早期公差建檔把 4.0 記成 4，出貨規格卻寫 4.0（或反之），導致該規格查不到
    任何公差、所有項目靜默不判定。此處把每個數值段以 float 再輸出標準寫法
    （4.0→4、2.50→2.5、.5→0.5），使兩種寫法正規化後相同。

    非數值段（如 Ø44 之類）維持原樣僅去空白與大寫化，避免誤改。
    """
    if not spec:
        return ''
    text = str(spec).strip().replace('×', '*').replace('x', '*').replace('X', '*')
    while '**' in text:
        text = text.replace('**', '*')
    text = re.sub(r'\s+', '', text)
    if text.upper() in ('NONE', 'NULL', ''):
        return ''
    segments = []
    for part in text.split('*'):
        if not part:
            continue
        try:
            # %g 會去掉尾隨 0（4.0→4、2.50→2.5），並保留必要精度
            segments.append(f'{float(part):g}')
        except ValueError:
            segments.append(part.upper())
    return '*'.join(segments)


# ==================================================
# Spec Nominal Parser (C-2)
# ==================================================
def parse_spec_nominals(spec: Optional[str]) -> Dict[str, float]:
    """
    從規格字串解析各尺寸名義值（shipping/patrol 共用）

    支援兩種格式：
      三段式 '外徑*厚度或內徑*長度'（如 '31.9*2.2*589'）：第二值以外徑一半為界推斷是厚度或內徑，
             再幾何回推另一項。
      四段式 '外徑*內徑*厚度*長度'（如 '33*26.5*2.0*244'）：內徑與厚度皆為明列值，直接讀取，
             不再幾何回推（避免把明寫的厚度誤算成 (外徑-內徑)/2）。
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
        if len(nums) >= 4:
            # 四段式：外徑*內徑*厚度*長度，內徑與厚度直接取用明列值
            result['外徑'] = nums[0]
            result['內徑'] = nums[1]
            result['厚度'] = nums[2]
            result['長度'] = nums[3]
        elif len(nums) >= 2:
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

def acquire_number_lock(lock_key: str) -> None:
    """在 PostgreSQL 交易中取得單號產生鎖，避免多人同時產生重複序號。"""
    bind = db.session.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        db.session.execute(text('SELECT pg_advisory_xact_lock(hashtext(:lock_key))'), {
            'lock_key': lock_key,
        })

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
            acquire_number_lock(f'{table_name}.{number_field}.{prefix}.{year_month}')
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
    if isinstance(date_str, (date, datetime)):
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
        return {"message": '資料庫操作失敗'}
