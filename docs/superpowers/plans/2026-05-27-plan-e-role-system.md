# Plan E — 角色系統 + 操作審計日誌 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增細粒度角色權限系統（Role + permissions JSONB），並為所有 CRUD 操作加入審計日誌，符合 ISO/IATF 要求。

**Architecture:** `Role` 與 `AuditLog` 兩張新表；`User.role` 現有欄位用作 `role_code`；`require_permission(perm)` 裝飾器整合至現有 `auth_required` 流程；`log_audit()` 在各 service 的 create/update/delete 呼叫；前端 `AuthContext` 新增 `hasPermission()` 方法與 `permissions` 快取。

**Tech Stack:** Flask 3.1、SQLAlchemy、Flask-Migrate、PostgreSQL 16、React 19 TypeScript

**執行前提：** Plan A 已完成（utils.py 已有 `api_error` helper）

---

### Task 1：新增 Role + AuditLog 模型 + 遷移

**Files:**
- Modify: `backend/models.py`
- Run: `flask db migrate` + `flask db upgrade`

- [ ] **Step 1：在 models.py 的 User 類別之後插入 Role 模型**

在 `User` 類別結尾（`__repr__` 之後）、`Inspector` 類別之前插入：

```python
class Role(db.Model):
    __tablename__ = '角色'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    code = db.Column('角色代碼', db.String(30), unique=True, nullable=False)
    name = db.Column('角色名稱', db.String(50), nullable=False)
    permissions = db.Column('權限', JsonType, nullable=False, default=dict)

    def has_permission(self, perm: str) -> bool:
        return bool(self.permissions.get(perm))

    def __repr__(self):
        return f'<Role {self.code}>'
```

- [ ] **Step 2：在 Role 之後插入 AuditLog 模型**

```python
class AuditLog(db.Model):
    __tablename__ = '操作日誌'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    user_id = db.Column('使用者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    action = db.Column('操作類型', db.String(20), nullable=False)
    module = db.Column('模組', db.String(30), nullable=False)
    record_id = db.Column('資料ID', db.Integer, nullable=True)
    old_value = db.Column('操作前', JsonType, nullable=True)
    new_value = db.Column('操作後', JsonType, nullable=True)
    created_at = db.Column('建立時間', db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('idx_auditlog_module_record', '模組', '資料ID'),
        db.Index('idx_auditlog_user_created', '使用者ID', '建立時間'),
    )

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.module} {self.action} {self.record_id}>'
```

- [ ] **Step 3：產生並套用遷移**

```powershell
cd C:\QC_Database\backend
$env:FLASK_APP = "app.py"
flask db migrate -m "新增角色與操作日誌表"
flask db upgrade
```

預期輸出：`Running upgrade ... done`

- [ ] **Step 4：植入預設角色資料**

建立 `backend/seeds/seed_roles.py`：

```python
"""執行方式：cd C:\QC_Database && python -m backend.seeds.seed_roles"""
from backend.app import create_app
from backend.extensions import db
from backend.models import Role

ROLES = [
    {
        'code': 'inspector',
        'name': '檢驗員',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit_own': True, 'ncmr.view': True,
            'capa.view': True, 'rework.view': True,
            'shipping.create': True, 'shipping.edit_own': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit_own': True, 'patrol.view': True,
        }
    },
    {
        'code': 'qa_supervisor',
        'name': 'QA主管',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.view': True,
            'capa.create': True, 'capa.edit': True, 'capa.view': True,
            'rework.create': True, 'rework.approve': True, 'rework.view': True,
            'complaint.edit': True, 'complaint.view': True,
            'shipping.create': True, 'shipping.edit': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit': True, 'patrol.view': True,
        }
    },
    {
        'code': 'qc_manager',
        'name': '品管經理',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.delete': True, 'ncmr.view': True,
            'capa.create': True, 'capa.edit': True, 'capa.close': True, 'capa.view': True,
            'rework.create': True, 'rework.approve': True, 'rework.view': True,
            'complaint.create': True, 'complaint.edit': True, 'complaint.delete': True, 'complaint.view': True,
            'vendor.manage': True, 'report.view': True,
            'shipping.create': True, 'shipping.edit': True, 'shipping.delete': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit': True, 'patrol.delete': True, 'patrol.view': True,
        }
    },
    {
        'code': 'admin',
        'name': '系統管理員',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.delete': True, 'ncmr.view': True,
            'capa.create': True, 'capa.edit': True, 'capa.close': True, 'capa.view': True,
            'rework.create': True, 'rework.approve': True, 'rework.view': True,
            'complaint.create': True, 'complaint.edit': True, 'complaint.delete': True, 'complaint.view': True,
            'vendor.manage': True, 'report.view': True,
            'shipping.create': True, 'shipping.edit': True, 'shipping.delete': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit': True, 'patrol.delete': True, 'patrol.view': True,
            'user.manage': True,
        }
    },
]

def seed():
    app = create_app()
    with app.app_context():
        for r in ROLES:
            existing = Role.query.filter_by(code=r['code']).first()
            if existing:
                existing.name = r['name']
                existing.permissions = r['permissions']
            else:
                db.session.add(Role(**r))
        db.session.commit()
        print(f'已植入 {len(ROLES)} 個角色')

if __name__ == '__main__':
    seed()
```

- [ ] **Step 5：建立 seeds/__init__.py**

建立空檔案 `backend/seeds/__init__.py`（內容為空）

- [ ] **Step 6：執行植入**

```powershell
cd C:\QC_Database
.\venv\Scripts\Activate.ps1
python -m backend.seeds.seed_roles
```

預期輸出：`已植入 4 個角色`

- [ ] **Step 7：Commit**

```powershell
git add backend/models.py backend/migrations/ backend/seeds/
git commit -m "feat(models): 新增 Role + AuditLog 模型，植入預設角色"
```

---

### Task 2：require_permission 裝飾器 + log_audit 函數

**Files:**
- Modify: `backend/utils.py`
- Test: `backend/tests/test_permissions.py`（新建）

- [ ] **Step 1：撰寫測試**

建立 `backend/tests/test_permissions.py`：

```python
import pytest
from unittest.mock import MagicMock, patch
from backend.app import create_app

@pytest.fixture
def app():
    return create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})

def test_require_permission_allows_when_has_perm(app):
    """有權限時裝飾器不攔截"""
    with app.app_context():
        from backend.utils import require_permission

        mock_role = MagicMock()
        mock_role.has_permission.return_value = True

        mock_user = MagicMock()
        mock_user.role = 'qc_manager'

        with patch('backend.utils.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_role

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                result = view(mock_user)
                assert result == ('ok', 200)

def test_require_permission_blocks_when_no_perm(app):
    """無權限時回傳 403"""
    with app.app_context():
        from backend.utils import require_permission

        mock_role = MagicMock()
        mock_role.has_permission.return_value = False

        mock_user = MagicMock()
        mock_user.role = 'inspector'

        with patch('backend.utils.Role') as MockRole:
            MockRole.query.filter_by.return_value.first.return_value = mock_role

            @require_permission('ncmr.delete')
            def view(current_user):
                return 'ok', 200

            with app.test_request_context():
                resp, code = view(mock_user)
                assert code == 403
```

- [ ] **Step 2：確認測試失敗**

```powershell
cd C:\QC_Database
python -m pytest backend/tests/test_permissions.py -v
```

預期：`ImportError: cannot import name 'require_permission'`

- [ ] **Step 3：在 utils.py 新增 require_permission + log_audit**

在 `require_admin` 函數之後插入：

```python
# ==================================================
# 細粒度權限控制
# ==================================================
def require_permission(perm: str):
    """裝飾器：驗證當前使用者是否具備指定細粒度權限。
    必須搭配 auth_required 使用，且路由函式第一個參數須為 current_user。
    """
    def decorator(f):
        @wraps(f)
        def wrapped(current_user, *args, **kwargs):
            if current_user is None:
                return jsonify({'success': False, 'error': '使用者不存在'}), 401
            from .models import Role
            role = Role.query.filter_by(code=current_user.role).first()
            if not role or not role.has_permission(perm):
                return jsonify({'success': False, 'error': '權限不足'}), 403
            return f(current_user, *args, **kwargs)
        return wrapped
    return decorator


# ==================================================
# 操作審計日誌
# ==================================================
def log_audit(user_id: Optional[int], action: str, module: str,
              record_id: Optional[int], old_val=None, new_val=None) -> None:
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
```

- [ ] **Step 4：確認測試通過**

```powershell
python -m pytest backend/tests/test_permissions.py -v
```

預期：全部 PASSED

- [ ] **Step 5：Commit**

```powershell
git add backend/utils.py backend/tests/test_permissions.py
git commit -m "feat(utils): 新增 require_permission 裝飾器與 log_audit 函數"
```

---

### Task 3：NCMR 路由整合權限 + 審計日誌

**Files:**
- Modify: `backend/routes/ncmr.py`
- Modify: `backend/services/ncmr_service.py`

- [ ] **Step 1：讀取現有 ncmr.py 確認路由結構**

開啟 `backend/routes/ncmr.py`，找到以下路由：
- `POST /` — 新建 NCMR
- `PUT /<int:ncmr_id>` — 更新 NCMR
- `DELETE /<int:ncmr_id>` — 刪除 NCMR

- [ ] **Step 2：在 ncmr.py import 區新增**

在現有 `from ..utils import auth_required` 一行改為：

```python
from ..utils import auth_required, require_permission, log_audit
```

- [ ] **Step 3：POST 路由加入權限裝飾器**

找到新建路由（`@ncmr_bp.route('/', methods=['POST'])`），在 `@auth_required` 之後加入 `@require_permission('ncmr.create')`：

```python
@ncmr_bp.route('/', methods=['POST'])
@auth_required
@require_permission('ncmr.create')
def create_ncmr(current_user):
    ...
```

- [ ] **Step 4：DELETE 路由加入權限裝飾器**

找到刪除路由，加入 `@require_permission('ncmr.delete')`：

```python
@ncmr_bp.route('/<int:ncmr_id>', methods=['DELETE'])
@auth_required
@require_permission('ncmr.delete')
def delete_ncmr(current_user, ncmr_id):
    ...
```

- [ ] **Step 5：在 ncmr_service.py 的 create 方法末尾加入審計**

在 `db.session.commit()` 之前插入：

```python
from ..utils import log_audit
log_audit(
    user_id=getattr(current_user, 'id', None),
    action='create',
    module='NCMR',
    record_id=ncmr.id,
    new_val=ncmr_id_str,
)
```

> **注意：** ncmr_service.py 的方法可能不直接接收 current_user；若如此，改為在路由層的 create 路由中呼叫 `log_audit`，在 `NCMRService.create(data)` 回傳後：
> ```python
> result = NCMRService.create(data)
> log_audit(current_user.id, 'create', 'NCMR', result.get('id'), new_val={'ncmr_number': result.get('ncmr_number')})
> ```

- [ ] **Step 6：在 ncmr_service.py 的 delete 方法加入審計**

在軟刪除的 `db.session.commit()` 之前，插入：

```python
log_audit(user_id=None, action='delete', module='NCMR', record_id=ncmr_id,
          old_val={'status': ncmr.status})
```

> 若路由層有 current_user，在路由層呼叫審計更佳，傳入 `current_user.id`。

- [ ] **Step 7：Commit**

```powershell
git add backend/routes/ncmr.py backend/services/ncmr_service.py
git commit -m "feat(ncmr): 整合細粒度權限驗證與操作審計日誌"
```

---

### Task 4：CAPA / 重工 / 客訴路由整合權限

**Files:**
- Modify: `backend/routes/capa.py`
- Modify: `backend/routes/rework.py`
- Modify: `backend/routes/complaint.py`

- [ ] **Step 1：修改 capa.py**

找到以下路由，加入對應裝飾器：

```python
from ..utils import auth_required, require_permission, log_audit

# POST /  新建 CAPA
@capa_bp.route('/', methods=['POST'])
@auth_required
@require_permission('capa.create')
def create_capa(current_user):
    ...

# DELETE /<id>  刪除 CAPA
@capa_bp.route('/<int:ca_id>', methods=['DELETE'])
@auth_required
@require_permission('capa.close')
def delete_capa(current_user, ca_id):
    ...
```

在 POST 路由成功建立後加入：
```python
log_audit(current_user.id, 'create', 'CAPA', result.get('id'),
          new_val={'source_type': data.get('source_type')})
```

- [ ] **Step 2：修改 rework.py**

找到審核路由（approve/reject），加入：

```python
from ..utils import auth_required, require_permission, log_audit

# PUT /<id>/approve 或對應的狀態更新
@rework_bp.route('/<int:rework_id>/approve', methods=['PUT'])
@auth_required
@require_permission('rework.approve')
def approve_rework(current_user, rework_id):
    ...
```

在路由成功後加入：
```python
log_audit(current_user.id, 'update', '重工', rework_id,
          old_val={'status': old_status}, new_val={'status': new_status})
```

- [ ] **Step 3：修改 complaint.py**

找到刪除路由，加入：

```python
from ..utils import auth_required, require_permission, log_audit

@complaint_bp.route('/<int:complaint_id>', methods=['DELETE'])
@auth_required
@require_permission('complaint.delete')
def delete_complaint(current_user, complaint_id):
    ...
    log_audit(current_user.id, 'delete', '客訴', complaint_id,
              old_val={'customer': complaint.customer})
    ...
```

- [ ] **Step 4：Commit**

```powershell
git add backend/routes/capa.py backend/routes/rework.py backend/routes/complaint.py
git commit -m "feat(routes): CAPA/重工/客訴加入細粒度權限與審計日誌"
```

---

### Task 5：審計日誌查詢 API

**Files:**
- Modify: `backend/routes/admin.py`

- [ ] **Step 1：新增審計日誌查詢路由**

在 `admin.py` 末尾加入：

```python
from ..models import AuditLog, User as UserModel

@admin_bp.route('/audit-logs', methods=['GET'])
@auth_required
@require_permission('user.manage')
def get_audit_logs(current_user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    module = request.args.get('module')
    user_id = request.args.get('user_id', type=int)

    q = AuditLog.query.order_by(AuditLog.created_at.desc())
    if module:
        q = q.filter(AuditLog.module == module)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    items = [
        {
            'id': log.id,
            'user_id': log.user_id,
            'username': log.user.username if log.user else '(已刪除)',
            'action': log.action,
            'module': log.module,
            'record_id': log.record_id,
            'old_value': log.old_value,
            'new_value': log.new_value,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        }
        for log in pagination.items
    ]
    return jsonify({'data': items, 'total': pagination.total, 'page': page, 'per_page': per_page})
```

確保 import 已加入 `require_permission`：
```python
from ..utils import auth_required, require_permission
```

- [ ] **Step 2：Commit**

```powershell
git add backend/routes/admin.py
git commit -m "feat(admin): 新增審計日誌查詢 API /api/admin/audit-logs"
```

---

### Task 6：角色管理 API

**Files:**
- Modify: `backend/routes/auth.py`（或 admin.py，看現有結構）

- [ ] **Step 1：讀取現有使用者管理路由**

開啟 `backend/routes/auth.py`，找到使用者列表與更新的路由（通常是 `GET /users`、`PUT /users/<id>`）。

- [ ] **Step 2：新增取得角色列表路由**

在 auth.py（或 admin.py）末尾加入：

```python
from ..models import Role

@auth_bp.route('/roles', methods=['GET'])
@auth_required
@require_permission('user.manage')
def list_roles(current_user):
    roles = Role.query.order_by(Role.code).all()
    return jsonify([
        {'code': r.code, 'name': r.name, 'permissions': r.permissions}
        for r in roles
    ])
```

- [ ] **Step 3：在使用者更新路由加入角色指派支援**

找到 `PUT /users/<user_id>` 路由，在更新欄位中加入：

```python
if 'role' in data:
    # 確認角色代碼存在
    role_exists = Role.query.filter_by(code=data['role']).first()
    if not role_exists:
        return api_error(f"角色代碼不存在：{data['role']}", 400)
    user.role = data['role']
```

- [ ] **Step 4：Commit**

```powershell
git add backend/routes/auth.py
git commit -m "feat(auth): 新增角色列表查詢，使用者更新支援角色指派"
```

---

### Task 7：前端 AuthContext 加入 hasPermission

**Files:**
- Modify: `src_frontend/src/types/index.ts`
- Modify: `src_frontend/src/context/authContextDefinition.ts`
- Modify: `src_frontend/src/context/AuthContext.tsx`

- [ ] **Step 1：修改 types/index.ts**

找到 `User` interface，加入 `permissions` 欄位：

```typescript
export interface User {
    user_id: string;
    username: string;
    role: string;
    permissions?: Record<string, boolean>;
}
```

找到 `VerifyTokenResponse`，加入 `permissions` 欄位：

```typescript
export interface VerifyTokenResponse {
    valid: boolean;
    username: string;
    user_id: string;
    role: string;
    permissions?: Record<string, boolean>;
}
```

- [ ] **Step 2：修改 authContextDefinition.ts**

在 `AuthContextType` 加入 `hasPermission` 方法：

```typescript
export interface AuthContextType extends AuthState {
    login: (token: string, username: string, userId: string, role?: string, permissions?: Record<string, boolean>) => void;
    logout: () => void;
    checkAuth: () => Promise<void>;
    hasPermission: (perm: string) => boolean;
}
```

- [ ] **Step 3：修改 AuthContext.tsx**

更新 `login` 函數與 `checkAuth` 以傳遞 permissions，並新增 `hasPermission` 實作：

```typescript
const login = (token: string, username: string, userId: string, role: string = 'user', permissions: Record<string, boolean> = {}) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('username', username);
    setUser({ username, user_id: userId, role, permissions });
    setIsAuthenticated(true);
};

const hasPermission = (perm: string): boolean => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    return user.permissions?.[perm] === true;
};
```

在 `checkAuth` 的成功分支更新 setUser 呼叫：

```typescript
setUser({
    username: response.data.username,
    user_id: response.data.user_id,
    role: response.data.role ?? 'user',
    permissions: response.data.permissions ?? {},
});
```

在 `AuthContext.Provider` value 加入 `hasPermission`：

```typescript
<AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout, checkAuth, hasPermission }}>
```

- [ ] **Step 4：更新後端 /api/verify-token 回傳 permissions**

找到 `backend/routes/auth.py` 中的 `/verify-token` 路由，在回傳 JSON 中加入 permissions：

```python
from ..models import Role

# 在 verify-token 回傳時
role_obj = Role.query.filter_by(code=payload.get('role', 'user')).first()
permissions = role_obj.permissions if role_obj else {}

return jsonify({
    'valid': True,
    'username': payload.get('username'),
    'user_id': str(payload.get('user_id')),
    'role': payload.get('role', 'user'),
    'permissions': permissions,
})
```

- [ ] **Step 5：TypeScript 編譯確認**

```powershell
cd C:\QC_Database\src_frontend
npm run build
```

預期：無 TypeScript 錯誤

- [ ] **Step 6：Commit**

```powershell
git add src_frontend/src/types/index.ts src_frontend/src/context/ backend/routes/auth.py
git commit -m "feat(frontend): AuthContext 新增 hasPermission，verify-token 回傳 permissions"
```

---

### Task 8：前端使用者管理頁新增角色指派

**Files:**
- Modify: `src_frontend/src/pages/` 中的使用者管理頁面（通常為 `UsersPage.tsx` 或 `AdminPage.tsx`）

- [ ] **Step 1：找到使用者管理頁面**

```powershell
Get-ChildItem C:\QC_Database\src_frontend\src\pages -Recurse -Filter "*.tsx" | Select-Object Name
```

找出含有使用者列表的頁面（應含 `UserRecord` 型別或 username 表格）。

- [ ] **Step 2：新增取得角色列表的 hook**

在對應頁面或 `src_frontend/src/hooks/useAuth.ts`（若存在）中新增：

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';

export interface RoleOption {
    code: string;
    name: string;
}

export function useRoles() {
    return useQuery<RoleOption[]>({
        queryKey: ['roles'],
        queryFn: async () => {
            const res = await api.get<RoleOption[]>('/auth/roles');
            return res.data;
        },
    });
}

export function useUpdateUserRole() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ userId, role }: { userId: number; role: string }) =>
            api.put(`/auth/users/${userId}`, { role }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
    });
}
```

- [ ] **Step 3：在使用者管理頁加入角色下拉選單**

在使用者表格的每一列加入角色欄位，找到現有的 role 顯示區塊（通常是 `<Badge>` 或純文字），改為下拉選單（僅限 admin 可操作）：

```tsx
import { useRoles, useUpdateUserRole } from '../../hooks/useAuth';
import { useAuth } from '../../context/useAuth';

// 在元件內：
const { hasPermission } = useAuth();
const { data: roles = [] } = useRoles();
const updateRole = useUpdateUserRole();

// 在表格列中（user 型別為 UserRecord）：
<Form.Select
    size="sm"
    value={user.role}
    disabled={!hasPermission('user.manage')}
    onChange={(e) => updateRole.mutate({ userId: user.id, role: e.target.value })}
>
    {roles.map(r => (
        <option key={r.code} value={r.code}>{r.name}</option>
    ))}
</Form.Select>
```

- [ ] **Step 4：TypeScript 編譯 + lint**

```powershell
cd C:\QC_Database\src_frontend
npm run build
npm run lint
```

預期：無錯誤、無警告

- [ ] **Step 5：Commit**

```powershell
git add src_frontend/src/
git commit -m "feat(users): 使用者管理頁新增角色指派下拉選單"
```

---

### Task 9：整合測試

**Files:**
- Test: `backend/tests/test_services/test_audit_log.py`（新建）

- [ ] **Step 1：撰寫審計日誌整合測試**

建立 `backend/tests/test_services/test_audit_log.py`：

```python
import pytest
from datetime import date
from backend.extensions import db as _db
from backend.models import AuditLog, User, Role

@pytest.fixture
def roles(app):
    with app.app_context():
        qc_manager = Role(
            code='qc_manager',
            name='品管經理',
            permissions={'ncmr.delete': True}
        )
        inspector = Role(
            code='inspector',
            name='檢驗員',
            permissions={'ncmr.delete': False}
        )
        _db.session.add_all([qc_manager, inspector])
        _db.session.commit()
        yield
        _db.session.rollback()

def test_log_audit_creates_record(app, roles):
    with app.app_context():
        from backend.utils import log_audit
        log_audit(user_id=1, action='create', module='NCMR',
                  record_id=99, new_val={'ncmr_number': 'TEST-001'})
        _db.session.commit()

        log = AuditLog.query.filter_by(module='NCMR', record_id=99).first()
        assert log is not None
        assert log.action == 'create'
        assert log.new_value == {'ncmr_number': 'TEST-001'}

def test_require_permission_blocks_wrong_role(app, roles):
    with app.app_context():
        from backend.utils import require_permission

        inspector_user = User(username='tester', password='x', role='inspector')
        _db.session.add(inspector_user)
        _db.session.commit()

        @require_permission('ncmr.delete')
        def protected(current_user):
            return 'ok', 200

        resp, code = protected(inspector_user)
        assert code == 403

def test_require_permission_allows_correct_role(app, roles):
    with app.app_context():
        from backend.utils import require_permission

        manager_user = User(username='manager', password='x', role='qc_manager')
        _db.session.add(manager_user)
        _db.session.commit()

        @require_permission('ncmr.delete')
        def protected(current_user):
            return 'ok', 200

        resp, code = protected(manager_user)
        assert code == 200
        assert resp == 'ok'
```

- [ ] **Step 2：執行測試**

```powershell
cd C:\QC_Database
python -m pytest backend/tests/test_services/test_audit_log.py -v
```

預期：全部 PASSED

- [ ] **Step 3：Commit**

```powershell
git add backend/tests/test_services/test_audit_log.py
git commit -m "test(role-system): 新增審計日誌與權限驗證整合測試"
```

---

### Task 10：推送

- [ ] **Push to GitHub**

```powershell
cd C:\QC_Database
git push origin master
```
