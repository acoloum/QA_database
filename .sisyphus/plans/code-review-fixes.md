# 代碼審查修復計劃

## 概述

本計劃針對代碼審查中發現的問題進行修復，除第 7 項（動態資料庫欄位）外，其餘問題皆會處理。

## 修復範圍

### 後端修復 (Flask/Python)

| # | 問題 | 檔案 | 優先順序 |
|---|------|------|----------|
| 1 | [ ] 密碼雜湊改用 bcrypt (加入鹽值) | backend/utils.py | 🔴 高 |
| 2 | [ ] 移除預設 SECRET_KEY，無環境變數則拋出錯誤 | backend/config.py | 🔴 高 |
| 3 | [ ] 加入登入速率限制 (5次失敗鎖定15分鐘) | backend/routes/auth.py | 🔴 高 |
| 4 | [ ] 修復重複的 SQLALCHEMY_TRACK_MODIFICATIONS 設定 | backend/app.py | 🟡 中 |
| 5 | [ ] 使用 Python logging 框架取代檔案寫入 | backend/app.py | 🟡 中 |
| 6 | [ ] 修正錯誤詳情暴露問題 (debug=False 時隱藏) | backend/app.py | 🟡 中 |
| 7 | [ ] 改進例外處理，不直接輸出錯誤字串 | backend/routes/auth.py | 🟡 中 |
| 8 | [ ] 加入請求資料驗證 (使用 marshmallow) | backend/routes/ncmr.py | 🟡 中 |

### 前端修復 (React/TypeScript)

| # | 問題 | 檔案 | 優先順序 |
|---|------|------|----------|
| 9 | [ ] 移除 any 類型，改用明確介面 | src_frontend/src/hooks/*.ts | 🟡 中 |
| 10 | [ ] 修復 ToleranceResult 類型重複定義 | src_frontend/src/types/index.ts | 🟢 低 |
| 11 | [ ] 調整 staleTime (1小時 → 10分鐘) | src_frontend/src/hooks/useNCMR.ts | 🟢 低 |
| 12 | [ ] 區分 Toast 錯誤嚴重程度 | src_frontend/src/services/api.ts | 🟢 低 |

---

## 詳細修復內容

### 1. 密碼雜湊改用 bcrypt (backend/utils.py)

**現有程式碼：**
```python
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
```

**修改為：**
```python
import bcrypt

def hash_password(password: str) -> str:
    """使用 bcrypt 雜湊密碼，包含隨機鹽值"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """驗證密碼是否匹配"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
```

**需新增 dependency：** `bcrypt==4.2.1`

---

### 2. 移除預設 SECRET_KEY (backend/config.py)

**現有程式碼：**
```python
SECRET_KEY = os.getenv('SECRET_KEY', '<由部署環境注入>')
```

**修改為：**
```python
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY 環境變數未設定，請設定後再啟動應用程式")
```

---

### 3. 加入登入速率限制 (backend/routes/auth.py)

**現有程式碼：**
```python
@auth_bp.route('/api/login', methods=['POST'])
def login():
```

**修改為：**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@auth_bp.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")  # 5次失敗後鎖定1分鐘
def login():
```

**需新增 dependency：** `flask-limiter==3.5.1`

---

### 4. 修復重複設定 (backend/app.py)

**移除重複行：**
```python
# 刪除這行 (第20行)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
```

---

### 5. 使用正規 Logging 框架 (backend/app.py)

**現有程式碼：**
```python
with open('error.log', 'a') as f:
    f.write(f"[{datetime.now()}] DB_ERROR: {str(error)}\n")
```

**修改為：**
```python
import logging
from logging.handlers import RotatingFileHandler

# 設定日誌
if not app.debug:
    file_handler = RotatingFileHandler('logs/error.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.ERROR)
    app.logger.addHandler(file_handler)

# 在錯誤處理中使用
app.logger.error(f"Database error: {str(error)}")
```

---

### 6. 修正錯誤詳情暴露 (backend/app.py)

**修改 handle_generic_error：**
```python
@app.errorhandler(Exception)
def handle_generic_error(error):
    app.logger.error(traceback.format_exc())
    
    response = jsonify({
        "success": False,
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "伺服器發生未預期的錯誤"
        }
    })
    response.status_code = 500
    return response
```

---

### 7. 改進例外處理 (backend/routes/auth.py)

**修改 catch 區塊：**
```python
except Exception as e:
    app.logger.error(f"Login error: {str(e)}")
    return jsonify({"error": "登入過程發生錯誤，請稍後再試"}), 500
```

---

### 8. 加入 Input Validation (backend/routes/ncmr.py)

**新增驗證：**
```python
from marshmallow import Schema, fields, validate, ValidationError

class NCMRSchema(Schema):
    發現日期 = fields.Date(required=True)
    來源 = fields.String(required=True, validate=validate.Length(min=1, max=100))
    產品資訊 = fields.String(validate=validate.Length(max=500))
    產品數量 = fields.Integer(validate=validate.Range(min=0))
    廠商 = fields.String(validate=validate.Length(max=200))
    批號 = fields.String(validate=validate.Length(max=100))
    不良描述 = fields.String(validate=validate.Length(max=1000))
    不合格數量 = fields.Integer(validate=validate.Range(min=0))

@ncmr_bp.route('/api/ncmr/add', methods=['POST'])
@auth_required
def add_ncmr():
    schema = NCMRSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"error": "資料驗證失敗", "details": err.messages}), 400
```

**需新增 dependency：** `marshmallow==3.22.0`

---

### 9. 移除 any 類型 (前端 hooks)

**修改 useNCMR.ts：**
```typescript
// 定義明確的 API response 類型
interface NCMRListResponse {
    識別碼: number;
    單號: string;
    日期: string;
    // ... 其他欄位
}

export const useNCMRList = (status?: string) => {
    return useQuery({
        queryKey: ['ncmrList', status],
        queryFn: async () => {
            const params = status ? { status } : {};
            const res = await api.get<NCMRListResponse[]>('/ncmr', { params });
            return res.data.map((item) => ({
                id: item.識別碼,
                no: item.單號 || String(item.識別碼),
                // ...
            }));
        },
    });
};
```

---

### 10. 修復類型重複定義 (types/index.ts)

**合併重複的 ToleranceResult：**
```typescript
// 移除第 47-55 行的重複定義，只保留第 160-165 行的版本
// 統一使用：
export interface ToleranceResult {
    success: boolean;
    found: boolean;
    tolerances: ToleranceItem[];
    message?: string;
}
```

---

### 11. 調整 staleTime (useNCMR.ts)

```typescript
staleTime: 1000 * 60 * 10, // 10 分鐘
```

---

### 12. 區分 Toast 錯誤嚴重程度 (api.ts)

```typescript
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const { response } = error;

        if (response && response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
                toast.error('登入已過期，請重新登入');
            }
            return Promise.reject(error);
        }

        // 嚴重錯誤才顯示 toast
        if (response && response.status >= 500) {
            toast.error('伺服器錯誤，請稍後再試');
        } else if (response && response.data?.error) {
            // 一般錯誤不彈出 toast，讓元件自行處理
            console.error('API Error:', response.data.error);
        }

        return Promise.reject(error);
    }
);
```

---

## 依賴變更

### requirements.txt 新增
```
bcrypt==4.2.1
flask-limiter==3.5.1
marshmallow==3.22.0
```

---

## 驗證項目

修復完成後需驗證：
1. [ ] 使用者登入功能正常運作
2. [ ] 密碼雜湊正確 (bcrypt 格式)
3. [ ] 速率限制正常運作
4. [ ] 日誌正確寫入 logs/ 目錄
5. [ ] 錯誤訊息不暴露內部詳情
6. [ ] 前端編譯無 TypeScript 錯誤
