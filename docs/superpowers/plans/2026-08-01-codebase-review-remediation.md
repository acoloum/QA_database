# 全庫審查修復 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依已批准規格，完整修復全庫審查確認的安全、授權、交易、輸入、日期、查詢、前端狀態、模組結構與測試閘門問題，並留下可重現的驗證證據。

**Architecture:** 先建立共用安全、錯誤、授權、日期與交易 seam，再讓各領域路由只負責 HTTP 解析、將型別化資料交給 service。資料庫交易由 service 擁有；前端以 React Query、reducer 與通用權限元件消費穩定介面。最後在相容性測試保護下拆分 ORM 與校正內部實作。

**Tech Stack:** Python 3.12、Flask 3.1、SQLAlchemy、Marshmallow、PyJWT、PostgreSQL 16、pytest、React 19、TypeScript、TanStack React Query、Vitest、React Testing Library、ESLint、Docker Compose、Nginx。

## Global Constraints

- 所有工作在 `C:\QC_Database\.worktrees\codebase-review-all`、分支 `fix/codebase-review-all` 進行。
- 每個行為修復遵循 RED → GREEN → REFACTOR；先執行新測試並確認因預期缺陷失敗，再修改正式碼。
- 使用者已批准純設定檔 TDD 例外：Docker、Nginx、npm script、pytest 設定與 CI workflow 不寫原始碼文字斷言，改以 `docker compose config`、`nginx -t`、實際 lint warning fixture、`pytest --markers` 與 `actionlint` 驗證 artifact 行為。
- route 不得直接 `db.session.commit()`；一個 mutation 只允許一個 service 擁有 commit。
- 後端授權是正式控制點；前端隱藏或停用按鈕只改善體驗。
- 不輪替正式憑證、不重寫 Git 歷史、不 force-push；只移除目前追蹤樹的秘密並提供 runbook。
- 不改資料表名、既有欄位名、relationship 語意與 event listener 行為；唯一預期 schema 變更是 migration 50 的 `使用者.憑證版本`。Migration 51 只回填角色 JSON 權限，不變更 schema。
- 不因環境缺少 PostgreSQL、Docker 或 live service 把 skip 說成通過；分開回報「已通過」、「跳過」與「未執行」。
- 每次提交前執行該任務窄測試與 `git diff --check`；最後才跑完整閘門。

---

## 檔案與模組地圖

### 新增檔案

- `backend/authentication.py`：JWT 簽章驗證後載入目前 User，建立 `AuthenticatedUser`。
- `backend/authorization.py`：集中權限 decorator、NCMR 本人編輯判斷與路由權限矩陣。
- `backend/request_context.py`：correlation id 的建立、取得與回應 header。
- `backend/schemas/ncmr.py`、`backend/schemas/__init__.py`：NCMR create/update Marshmallow 契約。
- `backend/services/audit_service.py`：只 `add/flush`、不自行 commit 的稽核寫入介面。
- `backend/services/date_range.py`：日期解析與 Date/DateTime 半開區間。
- `backend/services/calibration_reading_payload.py`：校正讀值 payload 正規化。
- `backend/services/calibration_reading_apply.py`：校正讀值計算輸入與 ORM 套用。
- `backend/models/{base,auth_audit,inspection,spc,calibration,msa,quality_workflow,pyrometry,mechanical}.py` 與 `backend/models/__init__.py`：模型分域與相容重匯出。
- `backend/migration/50_add_user_token_version.sql`：token 撤銷版本欄位、約束與 rollback 說明。
- `backend/scripts/scan_tracked_secrets.py`：只讀掃描 Git 追蹤內容。
- `backend/tests/test_repository_security.py`、`test_security_headers.py`、`test_migration_50.py`、`test_model_registry.py`、`test_route_error_contract.py`。
- `src_frontend/src/components/PermissionRoute.tsx` 與測試。
- `src_frontend/src/components/PermissionAction.tsx` 與測試。
- `src_frontend/src/pages/pyrometry/pyrometryTestFormState.ts`、`src_frontend/src/pages/mechanical/mechanicalTestFormState.ts`。
- `.env.docker.example`、`.github/workflows/quality-gates.yml`、`pytest.ini`、`docs/runbooks/credential-rotation.md`。

### 修改重點

- 安全與認證：`.gitignore`、`.dockerignore`、`Dockerfile`、`docker-compose.yml`、`nginx/default.conf`、`backend/config.py`、`backend/utils.py`、`backend/routes/auth.py`、使用者管理 service/route。
- 授權與交易：`backend/routes/{ncmr,capa,complaint,rework,shipping,patrol,tolerance,extrusion_tolerance,task,pyrometry,mechanical,quality_analytics,vendor_performance,admin}.py` 及對應 services。
- 查詢：`backend/services/{dashboard_service,vendor_performance_service,quality_analytics_service}.py`。
- 前端：`src_frontend/src/App.tsx`、`services/api.ts`、各領域 page/modal/hook、`eslint.config.js`。
- 結構：`backend/models.py` 最後由 `backend/models/` package 取代；所有既有 `from backend.models import X` 保持有效。

---

### Task 1: 移除追蹤秘密並使 Docker fail closed

**Files:**
- Create: `.env.docker.example`
- Modify: `.dockerignore`
- Create: `backend/scripts/scan_tracked_secrets.py`
- Create: `backend/tests/test_repository_security.py`
- Modify: `.gitignore`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Delete from Git index: `.env.docker`
- Delete from Git index: `.claude/settings.local.json`

- [ ] **Step 1: 寫入會失敗的追蹤樹安全測試**

```python
def test_tracked_files_do_not_contain_secrets(repo_root):
    result = subprocess.run(
        [sys.executable, "backend/scripts/scan_tracked_secrets.py"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_compose_requires_secrets(repo_root):
    missing = subprocess.run(
        ["docker", "compose", "config"], cwd=repo_root,
        env=without_env("DB_PASSWORD", "SECRET_KEY"), text=True, capture_output=True,
    )
    assert missing.returncode != 0
    assert "is required" in missing.stderr

    rendered = subprocess.run(
        ["docker", "compose", "config"], cwd=repo_root,
        env=with_test_secrets(), text=True, capture_output=True,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "127.0.0.1:5432" in rendered.stdout
```

- [ ] **Step 2: 執行 RED 測試並確認它指出 JWT、PGPASSWORD、固定 fallback 與 Dockerfile copy**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_repository_security.py -q`

Expected: FAIL；至少列出 `.claude/settings.local.json`、`.env.docker`、`docker-compose.yml` 或 `Dockerfile`。

- [ ] **Step 3: 實作只掃描 Git 追蹤檔的 scanner**

```python
PATTERNS = {
    "JWT": re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
    "PGPASSWORD": re.compile(r"PGPASSWORD\s*=", re.IGNORECASE),
    "固定 SECRET_KEY": re.compile(r"SECRET_KEY\s*[:=]\s*[^$<\s][^\r\n]+"),
    "私鑰": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

tracked = subprocess.check_output(
    ["git", "ls-files", "-z"], text=False
).split(b"\0")
```

Scanner 不排除任何文字型追蹤檔；pattern 本身以字串片段組合（例如 `"PGPASS" + "WORD"`）避免自我命中，測試中的假秘密也以片段組合。任何命中逐行輸出 `path:line:rule` 並回傳 1；無法解碼的二進位檔只略過內容掃描並計入掃描摘要。

- [ ] **Step 4: 移除秘密與固定 fallback**

```yaml
POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
DB_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
SECRET_KEY: ${SECRET_KEY:?SECRET_KEY is required}
ports:
  - "127.0.0.1:5432:5432"
```

從 Dockerfile 刪除 `COPY .env.docker ./.env`；`.dockerignore` 加入 `.env*`、`.claude/`、`.git/`、`.worktrees/`，再以 `!.env.docker.example` 允許範本。`.gitignore` 加入 `.env.docker` 與 `.claude/settings.local.json`。

- [ ] **Step 5: 建立只有 placeholder 的環境範本**

```dotenv
DB_HOST=db
DB_PORT=5432
DB_NAME=qa_database
DB_USER=postgres
DB_PASSWORD=<請由部署環境注入>
SECRET_KEY=<請使用至少32位元組隨機值>
```

- [ ] **Step 6: 驗證 scanner、Compose 展開失敗與成功路徑**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_repository_security.py -q`

Expected: PASS。

Run: `Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue; Remove-Item Env:SECRET_KEY -ErrorAction SilentlyContinue; docker compose config`

Expected: FAIL，訊息包含 `DB_PASSWORD is required` 或 `SECRET_KEY is required`。

Run: `$env:DB_PASSWORD='test-only-password'; Set-Item -Path Env:SECRET_KEY -Value 'test-only-secret-key-32-bytes-minimum'; docker compose config --quiet`

Expected: exit 0。

- [ ] **Step 7: 提交**

```powershell
git add .gitignore .dockerignore .env.docker.example Dockerfile docker-compose.yml backend/scripts/scan_tracked_secrets.py backend/tests/test_repository_security.py
git add -u .env.docker .claude/settings.local.json
git diff --check
git commit -m "安全：移除追蹤秘密並強制部署注入"
```

---

### Task 2: 統一錯誤 envelope、correlation id、安全 header 與 DB URL

**Files:**
- Create: `backend/request_context.py`
- Create: `backend/tests/test_security_headers.py`
- Create: `backend/tests/test_route_error_contract.py`
- Modify: `backend/errors.py`
- Modify: `backend/utils.py`
- Modify: `backend/app.py`
- Modify: `backend/config.py`
- Modify: `backend/tests/test_api_helpers.py`
- Modify: `backend/tests/test_errors.py`
- Modify: `nginx/default.conf`
- Modify: `src_frontend/src/services/api.ts`
- Modify: `src_frontend/src/services/api.test.ts`

- [ ] **Step 1: 先鎖定穩定錯誤與 correlation contract**

```python
def test_unexpected_error_is_sanitized(client, monkeypatch):
    monkeypatch.setattr(DashboardService, "get_todos", Mock(side_effect=RuntimeError("password=secret")))
    response = client.get("/api/dashboard/todos", headers=auth_headers())
    body = response.get_json()
    assert response.status_code == 500
    assert body == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "伺服器內部錯誤"},
    }
    assert "password=secret" not in response.get_data(as_text=True)
    assert response.headers["X-Correlation-ID"]
```

另測傳入合法 `X-Correlation-ID` 被沿用、非法或超長值被替換，以及所有回應帶安全 headers。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_api_helpers.py backend/tests/test_errors.py backend/tests/test_route_error_contract.py backend/tests/test_security_headers.py -q`

Expected: FAIL；目前 `api_error()` 與 route 仍可能回字串 error，且沒有 correlation/header。

- [ ] **Step 3: 實作唯一錯誤建立函式**

```python
def api_error(message: str, status: int = 400, *, code: str = "VALIDATION_ERROR", details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return jsonify({"success": False, "error": error}), status
```

`APIError.to_dict()` 使用相同 shape；500 handler 用 `current_app.logger.exception("未處理 API 例外 correlation_id=%s", get_correlation_id())` 記錄 traceback，但固定回 `INTERNAL_ERROR`。

- [ ] **Step 4: 建立 request context 與安全 headers**

```python
CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

def before_request_context():
    supplied = request.headers.get("X-Correlation-ID", "")
    g.correlation_id = supplied if CORRELATION_ID.fullmatch(supplied) else uuid.uuid4().hex

def add_response_headers(response):
    response.headers["X-Correlation-ID"] = g.correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response
```

Nginx 加相同防線與 CSP：`default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'`。不在 HTTP 環境加 HSTS。

- [ ] **Step 5: 使用 SQLAlchemy URL 組合 PostgreSQL URI**

```python
from sqlalchemy import URL

SQLALCHEMY_DATABASE_URI = URL.create(
    "postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)
```

測試密碼 `p@ss:w/rd` 保留在 `URL.password`，且 render 後正確 percent encode。

- [ ] **Step 6: 前端只解析正式 envelope，保留一個 legacy string 過渡分支**

403 只建立 `ApiError`，不移除 token；401 才清除登入狀態。測試明確斷言 403 後 `authToken` 仍存在。

- [ ] **Step 7: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_api_helpers.py backend/tests/test_errors.py backend/tests/test_route_error_contract.py backend/tests/test_security_headers.py -q`

Run: `npm test -- --run src/services/api.test.ts` (workdir `src_frontend`)

Expected: 全部 PASS。

```powershell
git add backend/request_context.py backend/errors.py backend/utils.py backend/app.py backend/config.py backend/tests/test_api_helpers.py backend/tests/test_errors.py backend/tests/test_route_error_contract.py backend/tests/test_security_headers.py nginx/default.conf src_frontend/src/services/api.ts src_frontend/src/services/api.test.ts
git diff --check
git commit -m "安全：統一錯誤契約與請求追蹤"
```

---

### Task 3: 加入 token version 與目前帳號驗證

**Files:**
- Create: `backend/authentication.py`
- Create: `backend/services/user_service.py`
- Create: `backend/migration/50_add_user_token_version.sql`
- Create: `backend/tests/test_migration_50.py`
- Modify: `backend/models.py`
- Modify: `backend/utils.py`
- Modify: `backend/routes/auth.py`
- Modify: `backend/tests/test_auth.py`
- Modify: `src_frontend/src/hooks/useAdmin.ts`
- Modify: `src_frontend/src/pages/admin/UserManagementPage.tsx`
- Create: `src_frontend/src/pages/admin/UserManagementPage.test.tsx`

- [ ] **Step 1: 寫停用、降權、版本不符與舊 token 的回歸測試**

```python
@pytest.mark.parametrize("mutation", ["deactivate", "activate", "change_role", "reset_password"])
def test_account_change_revokes_existing_token(client, db_session, user, mutation):
    token = generate_token(user.id, user.username, user.role, user.token_version)
    apply_account_change(user, mutation)
    db_session.commit()
    response = client.get("/api/verify-token", headers=bearer(token))
    assert response.status_code == 401

def test_legacy_token_without_version_is_rejected(client, user):
    token = encode_legacy_token(user)
    assert client.get("/api/verify-token", headers=bearer(token)).status_code == 401
```

代表性 GET 與 NCMR mutation 都要測停用後 401 且資料不變。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_auth.py backend/tests/test_migration_50.py -q`

Expected: FAIL；User 無 `token_version`，停用帳號舊 JWT 仍可使用。

- [ ] **Step 3: 實作 migration 50**

```sql
ALTER TABLE "使用者" ADD COLUMN IF NOT EXISTS "憑證版本" INTEGER;
UPDATE "使用者" SET "憑證版本" = 0 WHERE "憑證版本" IS NULL;
ALTER TABLE "使用者" ALTER COLUMN "憑證版本" SET DEFAULT 0;
ALTER TABLE "使用者" ALTER COLUMN "憑證版本" SET NOT NULL;
ALTER TABLE "使用者" ADD CONSTRAINT ck_user_token_version_nonnegative CHECK ("憑證版本" >= 0);
```

Model 欄位為 `token_version = db.Column('憑證版本', db.Integer, nullable=False, default=0, server_default='0')`。Migration 以 `DO $$` 檢查 constraint 是否已存在；檔末附 rollback SQL：先 drop constraint，再 drop column。測試驗證首次套用、重複安全檢查、NOT NULL 與非負約束。

- [ ] **Step 4: 建立目前使用者認證 seam**

```python
@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: str
    permissions: Mapping[str, bool]
    inspector_id: int | None

def authenticate_request_token(token: str) -> tuple[User, AuthenticatedUser]:
    claims = decode_and_validate_signature(token)
    if "token_version" not in claims:
        raise AuthenticationError("登入憑證已失效")
    user = db.session.get(User, claims["user_id"])
    if user is None or not user.is_active or user.token_version != claims["token_version"]:
        raise AuthenticationError("登入憑證已失效")
    return user, authenticated_user_from_model(user)
```

`generate_token()` 必填 `token_version`；JWT 內的 role 不再是授權來源。`auth_required` 與 `/api/verify-token` 都呼叫此介面。

- [ ] **Step 5: 所有帳號安全狀態改變都增加版本**

`UserService.set_active()`、`set_role()`、`reset_password()` 均執行 `user.token_version += 1`，並與該異動及 audit 同一 transaction commit。新增 `PUT /api/users/<int:user_id>/password`，只允許 `user.manage`，body 固定為 `{ "password": "至少8字元" }`；管理頁提供重設入口。系統目前沒有本人修改密碼 endpoint，因此本任務不虛構另一條未經產品設計的本人流程；未來新增時必須呼叫相同 `UserService.reset_password()`。

- [ ] **Step 6: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_auth.py backend/tests/test_permissions.py backend/tests/test_migration_50.py -q`

Expected: PASS。

```powershell
git add backend/authentication.py backend/services/user_service.py backend/models.py backend/utils.py backend/routes/auth.py backend/migration/50_add_user_token_version.sql backend/tests/test_auth.py backend/tests/test_permissions.py backend/tests/test_migration_50.py src_frontend/src/hooks/useAdmin.ts src_frontend/src/pages/admin/UserManagementPage.tsx src_frontend/src/pages/admin/UserManagementPage.test.tsx
git diff --check
git commit -m "安全：以帳號版本即時撤銷登入憑證"
```

---

### Task 4: 集中後端權限矩陣並封住所有 mutation

**Files:**
- Create: `backend/authorization.py`
- Create: `backend/migration/51_backfill_route_permissions.sql`
- Create: `backend/tests/test_migration_51.py`
- Modify: `backend/utils.py`
- Modify: `backend/seeds/seed_roles.py`
- Modify: `backend/routes/ncmr.py`
- Modify: `backend/routes/capa.py`
- Modify: `backend/routes/complaint.py`
- Modify: `backend/routes/rework.py`
- Modify: `backend/routes/admin.py`
- Modify: `backend/routes/attachment.py`
- Modify: `backend/routes/calibration_templates.py`
- Modify: `backend/routes/calibrations.py`
- Modify: `backend/routes/extrusion_tolerance.py`
- Modify: `backend/routes/measurement_equipment.py`
- Modify: `backend/routes/mechanical.py`
- Modify: `backend/routes/msa.py`
- Modify: `backend/routes/patrol.py`
- Modify: `backend/routes/pyrometry.py`
- Modify: `backend/routes/quality_analytics.py`
- Modify: `backend/routes/shipping.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `backend/routes/task.py`
- Modify: `backend/routes/tolerance.py`
- Modify: `backend/routes/vendor_performance.py`
- Modify: `backend/tests/test_permission_gating.py`
- Modify: `backend/tests/test_permissions.py`

- [ ] **Step 1: 用 parameterized 測試列出正式矩陣**

```python
MUTATION_CASES = [
    ("post", "/api/ncmr/add", "ncmr.create", ncmr_payload),
    ("post", "/api/capa/create", "capa.create", capa_payload),
    ("post", "/api/complaints", "complaint.create", complaint_payload),
    ("put", "/api/complaints/1", "complaint.edit", complaint_payload),
    ("post", "/api/rework/apply", "rework.create", rework_payload),
    ("post", "/api/rework/approve", "rework.approve", approve_payload),
    ("post", "/api/rework/close", "rework.approve", close_payload),
]
```

每個 case 建只有 `.view` 的角色，斷言 403 且對應資料表 row count/snapshot 不變；每個領域 GET 另測缺 `.view` 為 403。

- [ ] **Step 2: 寫 NCMR `edit_own` 邊界測試**

```python
def can_edit_ncmr(user, ncmr):
    return has_permission(user, "ncmr.edit") or (
        has_permission(user, "ncmr.edit_own")
        and user.inspector_id is not None
        and user.inspector_id == ncmr.inspector_id
    )
```

測本人可編輯、他人 403、`inspector_id is None` 不能誤配、admin 仍須為目前啟用帳號。

- [ ] **Step 3: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_permission_gating.py backend/tests/test_permissions.py -q`

Expected: FAIL；目前 view-only 角色仍可呼叫部分 mutation。

- [ ] **Step 4: 實作集中 decorator**

```python
def require_permissions(*permissions: str, mode: Literal["all", "any"] = "all"):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            current_user = g.current_user_model
            checks = [role_grants_permission(current_user, p) for p in permissions]
            allowed = all(checks) if mode == "all" else any(checks)
            if not allowed:
                raise AuthorizationError("權限不足", details={"required": list(permissions)})
            return view(*args, **kwargs)
        return wrapped
    return decorator
```

Task 3 的 `auth_required` 必須先設定 `g.current_user_model`，並依 route 原簽名決定是否注入 ORM User；因此權限 decorator 對新舊 route 都不改呼叫參數。`require_permission()` 與 `require_perm()` 只做相容 alias。NCMR 更新在 schema 取得 `識別碼`、載入 active NCMR 後呼叫 `can_edit_ncmr()`，再進 service mutation。

- [ ] **Step 5: 套用已批准矩陣**

- NCMR：view/create/edit 或 edit_own/delete/disposition。
- CAPA：view/create/edit/close；刪除也用 `capa.close`。
- 客訴：view/create/edit/delete；open CAPA 需 `complaint.edit` + `capa.create`，open rework 需 `complaint.edit` + `rework.create`。
- 重工：view/create/approve/delete；execution/cost/inspection 寫入用 `rework.create`，其刪除用 `rework.delete`。
- 出貨、巡檢與 pyrometry 使用既有同名權限；Tolerance GET/export/check 用 `tolerance.view`、mutation 用既有 `tolerance.manage`；Mechanical GET/stats/spec/options 用 `mechanical.view`、create/import 用 `mechanical.create`、update 用 `mechanical.edit`、delete 用 `mechanical.delete`；Quality Analytics GET 用 `analytics.view`；Vendor Performance GET/history 用 `vendor.view`、refresh 用既有 `vendor.manage`；Task GET/gate 用 `task.view`、mutation 使用既有 `task.create/edit/delete`。

Migration 51 與 `seed_roles.py` 同步新增權限：inspector 取得 `tolerance.view`、`mechanical.view/create`、`task.view`；qa_supervisor 取得 `tolerance.view`、`mechanical.view/create/edit`、`task.view`；qc_manager/admin 取得 `tolerance.view`、`mechanical.view/create/edit/delete`、`task.view`、`analytics.view`、`vendor.view`。Migration 51 使用 PostgreSQL JSONB `permissions || patch` 依 role code 合併，不覆蓋自訂權限；rollback 只移除上述新 keys。`test_migration_51.py` 驗證 merge 保留既有自訂 key 並可安全重跑。

- [ ] **Step 6: 掃描不可有未受保護 mutation**

新增 AST 測試：掃描 `backend/routes/*.py`，對 `POST/PUT/PATCH/DELETE` route 驗證 decorators 含 `require_permission(s)`、`require_admin` 或列在只讀/登入類例外白名單；白名單只允許 `/api/auth/login`、CSRF 與 health endpoint。

- [ ] **Step 7: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_permission_gating.py backend/tests/test_permissions.py backend/tests/test_auth.py backend/tests/test_migration_51.py backend/tests/test_services/test_complaint_routes.py backend/tests/test_services/test_rework.py -q`

Expected: PASS。

```powershell
git add backend/authorization.py backend/utils.py backend/routes backend/seeds/seed_roles.py backend/migration/51_backfill_route_permissions.sql backend/tests/test_permission_gating.py backend/tests/test_permissions.py backend/tests/test_auth.py backend/tests/test_migration_51.py backend/tests/test_services/test_complaint_routes.py backend/tests/test_services/test_rework.py
git diff --check
git commit -m "安全：集中路由權限並封鎖越權寫入"
```

---

### Task 5: 建立前端 PermissionRoute 與動作 gate

**Files:**
- Create: `src_frontend/src/components/PermissionRoute.tsx`
- Create: `src_frontend/src/components/PermissionRoute.test.tsx`
- Create: `src_frontend/src/components/PermissionAction.tsx`
- Create: `src_frontend/src/components/PermissionAction.test.tsx`
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/App.test.tsx`
- Modify: `src_frontend/src/pages/ncmr/NCMRPage.tsx`
- Modify: `src_frontend/src/pages/capa/CAPAPage.tsx`
- Modify: `src_frontend/src/pages/complaint/ComplaintPage.tsx`
- Modify: `src_frontend/src/pages/rework/ReworkPage.tsx`
- Modify: `src_frontend/src/pages/rework/ReworkListTable.tsx`
- Modify: `src_frontend/src/pages/rework/ReworkModalHost.tsx`
- Modify: `src_frontend/src/pages/rework/useReworkActions.ts`
- Modify: `src_frontend/src/pages/shipping/ShippingPage.tsx`
- Modify: `src_frontend/src/pages/patrol/PatrolPage.tsx`
- Modify: `src_frontend/src/pages/tolerance/TolerancePage.tsx`
- Modify: `src_frontend/src/pages/extrusion-tolerance/ExtrusionTolerancePage.tsx`
- Modify: `src_frontend/src/pages/vendor/VendorPerformancePage.tsx`
- Modify: `src_frontend/src/pages/mechanical/MechanicalTestListPage.tsx`
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestListPage.tsx`
- Modify: `src_frontend/src/pages/task/TaskListPage.tsx`

- [ ] **Step 1: 寫路由與按鈕 RED 測試**

```tsx
it('缺少權限時導回儀表板且不呈現頁面', async () => {
  authMock.mockReturnValue(authenticatedWithout('ncmr.view'));
  window.history.replaceState({}, '', '/ncmr');
  render(<App />);
  expect(await screen.findByRole('heading', { name: '儀表板路由頁面' })).toBeInTheDocument();
});

it('缺少寫入權限時停用動作並顯示理由', () => {
  render(<PermissionAction permission="ncmr.delete"><button>刪除</button></PermissionAction>);
  expect(screen.getByRole('button', { name: '刪除' })).toBeDisabled();
  expect(screen.getByText('需要 ncmr.delete 權限')).toBeInTheDocument();
});
```

- [ ] **Step 2: 執行 RED 測試**

Run: `npm test -- --run src/components/PermissionRoute.test.tsx src/components/PermissionAction.test.tsx src/App.test.tsx` (workdir `src_frontend`)

Expected: FAIL；通用元件尚不存在，且多數路由只受 ProtectedRoute 保護。

- [ ] **Step 3: 實作通用元件**

```tsx
export function PermissionRoute({ permission, children }: Props) {
  const { isLoading, isAuthenticated, hasPermission } = useAuth();
  if (isLoading) return <div role="status">載入中</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return hasPermission(permission) ? children : <Navigate to="/" replace />;
}
```

`PermissionAction` 對支援 `disabled` 的 child clone `disabled` 與 `aria-describedby`；不支援時不 render，並讓 caller 明確選 `mode="hide"`。

- [ ] **Step 4: 依後端矩陣保護頁面與動作**

App 路由使用：NCMR `ncmr.view`、CAPA `capa.view`、重工 `rework.view`、客訴 `complaint.view`、出貨 `shipping.view`、巡檢 `patrol.view`、Tolerance `tolerance.view`、pyrometry `pyrometry.view`、mechanical `mechanical.view`、quality analytics `analytics.view`、廠商績效 `vendor.view`、Task `task.view`、SPC `spc.view`、MSA `msa.view`、校正 `calibration.view`。

- [ ] **Step 5: 驗證 401/403 前端行為**

Run: `npm test -- --run src/components/PermissionRoute.test.tsx src/components/PermissionAction.test.tsx src/App.test.tsx src/components/Sidebar.test.tsx src/services/api.test.ts`

Expected: PASS；403 不登出、401 才登出。

- [ ] **Step 6: 提交**

```powershell
git add src_frontend/src/components/PermissionRoute.tsx src_frontend/src/components/PermissionRoute.test.tsx src_frontend/src/components/PermissionAction.tsx src_frontend/src/components/PermissionAction.test.tsx src_frontend/src/App.tsx src_frontend/src/App.test.tsx src_frontend/src/pages src_frontend/src/components src_frontend/src/services/api.test.ts
git diff --check
git commit -m "前端：統一頁面與操作權限提示"
```

---

### Task 6: 修正 NCMR 輸入契約

**Files:**
- Create: `backend/schemas/__init__.py`
- Create: `backend/schemas/ncmr.py`
- Modify: `backend/routes/ncmr.py`
- Modify: `backend/services/ncmr_service.py`
- Modify: `backend/tests/test_services/test_ncmr.py`
- Modify: `backend/tests/test_permission_gating.py`

- [ ] **Step 1: 寫合法日期成功與錯誤 body 失敗測試**

```python
@pytest.mark.parametrize("body,status", [
    (None, 400),
    ([], 400),
    ({"date": "2026-02-30"}, 422),
    ({"date": "2026-08-01", "quantity": -1}, 422),
    ({"date": "2026-08-01", "unknown": "x"}, 422),
])
def test_ncmr_create_rejects_invalid_contract(client, body, status):
    response = client.post("/api/ncmr/add", json=body, headers=ncmr_creator_headers())
    assert response.status_code == status
    assert response.get_json()["error"]["code"] in {"INVALID_JSON_BODY", "VALIDATION_ERROR"}
```

合法 payload 測 `NCMR.date` 是 `datetime.date`，回 201 且不再 500。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_ncmr.py -q`

Expected: FAIL；route 丟棄 `load()` 結果，合法日期字串到 Date column 造成 500。

- [ ] **Step 3: 實作 create/update schema**

```python
class NCMRCreateSchema(Schema):
    class Meta:
        unknown = RAISE
    date = fields.Date(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=0))
    vendor = fields.String(load_default=None, allow_none=True)
    description = fields.String(required=True, validate=validate.Length(min=1, max=5000))

class NCMRUpdateSchema(NCMRCreateSchema):
    ncmr_id = fields.Integer(required=True, validate=validate.Range(min=1))
```

create/update schema 明列 `日期`、`建立日期`、`來源`、`廠商`、`材質`、`批號`、`產品資訊`、`產品數量`、`不良描述`、`不合格數量`、`發現人員姓名`、`判定結果`、`狀態`、`不良原因大類`、`不良原因細項`；update 另要求 `識別碼`。日期用 `fields.Date`，數量與 `識別碼` 用 `fields.Integer`，選填字串保留 `allow_none`；不以 `_coerce_date()` 將錯誤值改成 None。

- [ ] **Step 4: route 只傳 load 結果**

```python
payload = request.get_json(silent=True)
if not isinstance(payload, dict):
    raise APIError("請求內容必須是 JSON 物件", "INVALID_JSON_BODY", 400)
data = NCMRCreateSchema().load(payload)
result = NCMRService.create(data, actor_id=current_user.id)
```

Marshmallow `ValidationError.messages` 放入 `details`，status 422。

- [ ] **Step 5: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_ncmr.py backend/tests/test_permission_gating.py -q`

Expected: PASS。

```powershell
git add backend/schemas backend/routes/ncmr.py backend/services/ncmr_service.py backend/tests/test_services/test_ncmr.py backend/tests/test_permission_gating.py
git diff --check
git commit -m "修復：正規化 NCMR 建立與更新輸入"
```

---

### Task 7: 使 NCMR、處置與來源開立交易原子化

**Files:**
- Create: `backend/services/audit_service.py`
- Modify: `backend/services/ncmr_service.py`
- Modify: `backend/services/capa_service.py`
- Modify: `backend/routes/ncmr.py`
- Modify: `backend/tests/test_services/test_audit_log.py`
- Modify: `backend/tests/test_services/test_ncmr.py`
- Modify: `backend/tests/test_services/test_ncmr_disposition.py`
- Modify: `backend/tests/test_services/test_open_capa_soft_delete.py`

- [ ] **Step 1: 寫 audit 失敗必須 rollback 的 RED 測試**

```python
def test_delete_ncmr_rolls_back_when_audit_fails(client, db_session, ncmr, monkeypatch):
    monkeypatch.setattr(AuditService, "record", Mock(side_effect=RuntimeError("audit down")))
    response = client.post("/api/ncmr/delete", json={"id": ncmr.id}, headers=deleter_headers())
    db_session.expire_all()
    assert response.status_code == 500
    assert db_session.get(NCMR, ncmr.id).deleted_at is None
    assert AuditLog.query.filter_by(module="NCMR", record_id=ncmr.id).count() == 0
```

同樣覆蓋 create/update、三種 disposition mutation 與 open CAPA。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_audit_log.py backend/tests/test_services/test_ncmr.py backend/tests/test_services/test_ncmr_disposition.py backend/tests/test_services/test_open_capa_soft_delete.py -q`

Expected: FAIL；業務異動先 commit，audit 失敗後仍保留。

- [ ] **Step 3: 實作不 commit 的 AuditService**

```python
class AuditService:
    @staticmethod
    def record(*, actor_id: int, action: str, module: str, record_id: int | None,
               old_value: Mapping | None = None, new_value: Mapping | None = None) -> AuditLog:
        entry = AuditLog(
            user_id=actor_id,
            action=action,
            module=module,
            record_id=record_id,
            old_value=_json_value(old_value),
            new_value=_json_value(new_value),
        )
        db.session.add(entry)
        db.session.flush()
        return entry
```

- [ ] **Step 4: service 擁有唯一 transaction**

```python
@staticmethod
def delete(ncmr_id: int, *, actor_id: int) -> None:
    try:
        ncmr = NCMR.active_query().filter_by(id=ncmr_id).with_for_update().one_or_none()
        if ncmr is None:
            raise NotFoundError("NCMR 不存在")
        old = NCMRService.audit_snapshot(ncmr)
        ncmr.soft_delete(actor_id)
        AuditService.record(actor_id=actor_id, action="delete", module="NCMR",
                            record_id=ncmr.id, old_value=old, new_value={"deleted": True})
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
```

create/update/dispositions/open CAPA 採同一形式；route 刪除所有 `log_audit()` 與 `db.session.commit()`。

- [ ] **Step 5: 加 AST 防線**

`test_route_modules_do_not_commit` 掃描 `backend/routes/*.py`，禁止 `db.session.commit()`；後續 Task 8 全部遷移完成前，暫時白名單只列尚未遷移的 `capa.py`、`complaint.py`、`rework.py`，Task 8 移除白名單。

- [ ] **Step 6: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_audit_log.py backend/tests/test_services/test_ncmr.py backend/tests/test_services/test_ncmr_disposition.py backend/tests/test_services/test_open_capa_soft_delete.py -q`

Expected: PASS。

```powershell
git add backend/services/audit_service.py backend/services/ncmr_service.py backend/services/capa_service.py backend/routes/ncmr.py backend/tests/test_services/test_audit_log.py backend/tests/test_services/test_ncmr.py backend/tests/test_services/test_ncmr_disposition.py backend/tests/test_services/test_open_capa_soft_delete.py
git diff --check
git commit -m "修復：使 NCMR 與稽核寫入保持原子性"
```

---

### Task 8: 將 CAPA、客訴、重工與其他 route commit 移入 service

**Files:**
- Modify: `backend/services/capa_service.py`
- Modify: `backend/services/complaint_service.py`
- Modify: `backend/services/rework_service.py`
- Modify: `backend/routes/capa.py`
- Modify: `backend/routes/complaint.py`
- Modify: `backend/routes/rework.py`
- Modify: `backend/tests/test_services/test_capa_workflow.py`
- Modify: `backend/tests/test_services/test_complaint_routes.py`
- Modify: `backend/tests/test_services/test_rework.py`
- Modify: `backend/tests/test_route_error_contract.py`

- [ ] **Step 1: 為每個受稽核 mutation 加 rollback 測試**

至少覆蓋 CAPA close/delete、complaint delete/open-capa/open-rework、rework apply/approve/close/delete，以及 execution/cost/inspection create/update/delete。每個測試 mock `AuditService.record` 失敗，斷言 500、業務 row/snapshot 不變、AuditLog 無新增。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_capa_workflow.py backend/tests/test_services/test_complaint_routes.py backend/tests/test_services/test_rework.py -q`

Expected: FAIL；現有 route/service commit 邊界不一致。

- [ ] **Step 3: 把 actor_id 納入 service mutation 介面**

```python
CAPAService.close(capa_id, confirmation, recognition, *, actor_id)
CAPAService.delete(capa_id, *, actor_id)
ComplaintService.delete(complaint_id, *, actor_id)
ComplaintService.open_capa(complaint_id, *, actor_id)
ComplaintService.open_rework(complaint_id, *, actor_id)
ReworkService.create_application(data, *, actor_id)
ReworkService.approve_application(data, *, actor_id)
ReworkService.close_rework(data, *, actor_id)
ReworkService.delete_rework(rework_id, *, actor_id)
```

每個 service 使用 `try/except Exception: rollback; raise`，在 commit 前呼叫 `AuditService.record`；route 只回傳 service result。

- [ ] **Step 4: 清空 route commit 掃描白名單**

Run: `rg -n "db\.session\.commit\(" backend/routes -g "*.py"`

Expected: 無輸出、exit 1。

AST 測試不再允許任何 route commit。

- [ ] **Step 5: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_capa_workflow.py backend/tests/test_services/test_complaint_routes.py backend/tests/test_services/test_rework.py backend/tests/test_route_error_contract.py -q`

Expected: PASS。

```powershell
git add backend/routes backend/services backend/tests/test_services/test_capa_workflow.py backend/tests/test_services/test_complaint_routes.py backend/tests/test_services/test_rework.py backend/tests/test_route_error_contract.py
git diff --check
git commit -m "修復：統一工作流程交易與稽核邊界"
```

---

### Task 9: 移除 route 例外洩漏並建立 domain error mapping

**Files:**
- Modify: `backend/errors.py`
- Modify: `backend/routes/admin.py`
- Modify: `backend/routes/attachment.py`
- Modify: `backend/routes/auth.py`
- Modify: `backend/routes/calibration_adapters.py`
- Modify: `backend/routes/capa.py`
- Modify: `backend/routes/complaint.py`
- Modify: `backend/routes/extrusion_tolerance.py`
- Modify: `backend/routes/mechanical.py`
- Modify: `backend/routes/ncmr.py`
- Modify: `backend/routes/patrol.py`
- Modify: `backend/routes/pyrometry.py`
- Modify: `backend/routes/quality_analytics.py`
- Modify: `backend/routes/rework.py`
- Modify: `backend/routes/shipping.py`
- Modify: `backend/routes/task.py`
- Modify: `backend/routes/tolerance.py`
- Modify: `backend/routes/vendor_performance.py`
- Modify: `backend/services/extrusion_tolerance_service.py`
- Modify: `backend/services/ncmr_service.py`
- Modify: `backend/services/patrol_service.py`
- Modify: `backend/services/pyrometry_service.py`
- Modify: `backend/services/rework_service.py`
- Modify: `backend/services/shipping_service.py`
- Modify: `backend/services/tolerance_service.py`
- Modify: `backend/tests/test_route_error_contract.py`
- Modify: `backend/tests/test_pyrometry_route_errors.py`
- Modify: `backend/tests/test_rework_route_errors.py`

- [ ] **Step 1: 建立 AST 與代表性 HTTP RED 測試**

AST 禁止：

```python
return api_error(str(e), 500)
return jsonify({"error": str(e)}), 500
raise e
```

HTTP 測試對 shipping、patrol、NCMR、CAPA、complaint、rework、task、tolerance、mechanical、vendor performance 各 mock 一個未預期例外，斷言固定 500 envelope 且不含原訊息。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_route_error_contract.py backend/tests/test_pyrometry_route_errors.py backend/tests/test_rework_route_errors.py -q`

Expected: FAIL；目前多個 route 回 `str(e)`。

- [ ] **Step 3: 建立正式 domain errors**

```python
class ConflictError(APIError):
    def __init__(self, message, details=None):
        super().__init__(message, "CONFLICT", 409, details)

class AuthorizationError(APIError):
    def __init__(self, message="權限不足", details=None):
        super().__init__(message, "FORBIDDEN", 403, details)
```

Validation/NotFound/Conflict/Authorization 可由全域 handler 直接映射；services 將預期 `ValueError` 改為對應 domain error，未預期例外不在 route 捕捉。

- [ ] **Step 4: 逐檔清理 routes**

只有需要關閉檔案、刪除暫存檔或 rollback 的地方保留 `except Exception`，完成補償後用裸 `raise`。所有報表 `send_file` 產生器錯誤也交給 global handler，不回內部訊息。

- [ ] **Step 5: 驗證零命中與路由測試**

Run: `rg -n "api_error\(str\(|jsonify\(\{['\"]error['\"]:\s*str\(|raise e$" backend/routes -g "*.py"`

Expected: 無輸出。

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_route_error_contract.py backend/tests/test_pyrometry_route_errors.py backend/tests/test_rework_route_errors.py backend/tests/test_errors.py -q`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add backend/errors.py backend/routes backend/services backend/tests
git diff --check
git commit -m "安全：避免 API 回傳內部例外資訊"
```

---

### Task 10: 修正 Dashboard 日期邊界並完成 service seam

**Files:**
- Create: `backend/services/date_range.py`
- Modify: `backend/services/dashboard_service.py`
- Modify: `backend/routes/admin.py`
- Modify: `backend/tests/test_dashboard_trends.py`
- Modify: `backend/tests/test_route_parameter_bounds.py`

- [ ] **Step 1: 寫結束日中午、月底、跨年與錯誤範圍測試**

```python
def test_datetime_on_end_date_is_included(client, db_session):
    db_session.add(CorrectiveAction(created_at=datetime(2026, 8, 31, 12, 0), status="進行中"))
    db_session.commit()
    body = client.get(
        "/api/dashboard/stats?start_date=2026-08-01&end_date=2026-08-31",
        headers=dashboard_headers(),
    ).get_json()
    assert body["capa_count"] == 1
```

另測 start>end 回 400、超過 366 天回 400、soft-delete 不計、Date 欄位包含 end_date。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_dashboard_trends.py backend/tests/test_route_parameter_bounds.py -q`

Expected: FAIL；目前 DateTime 使用 `<= end_date` 排除當日中午後資料。

- [ ] **Step 3: 實作日期視窗 value object**

```python
@dataclass(frozen=True)
class DateWindow:
    start_date: date
    end_date: date

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start_date, time.min)

    @property
    def end_exclusive(self) -> datetime:
        return datetime.combine(self.end_date + timedelta(days=1), time.min)

    def datetime_filters(self, column):
        return column >= self.start_at, column < self.end_exclusive

    def date_filters(self, column):
        return column >= self.start_date, column <= self.end_date
```

`parse_date_window(args, max_days=366)` 負責格式、順序與跨度驗證。

- [ ] **Step 4: 將 admin.py 的 stats 查詢搬進既有 DashboardService**

新增 `DashboardService.get_stats(window, comparison=None)`；route 只 parse、呼叫、回傳。保留既有 `get_trends/get_todos` 公開介面。

- [ ] **Step 5: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_dashboard_trends.py backend/tests/test_route_parameter_bounds.py -q`

Expected: PASS。

```powershell
git add backend/services/date_range.py backend/services/dashboard_service.py backend/routes/admin.py backend/tests/test_dashboard_trends.py backend/tests/test_route_parameter_bounds.py
git diff --check
git commit -m "修復：統一儀表板日期視窗與統計服務"
```

---

### Task 11: 將廠商績效改為嚴格月份與集合式讀寫

**Files:**
- Modify: `backend/services/vendor_performance_service.py`
- Modify: `backend/routes/vendor_performance.py`
- Modify: `backend/tests/test_services/test_vendor_performance.py`
- Modify: `backend/tests/test_permission_gating.py`
- Modify: `src_frontend/src/hooks/useVendorPerformance.ts`
- Create: `src_frontend/src/hooks/useVendorPerformance.test.tsx`
- Modify: `src_frontend/src/pages/vendor/VendorPerformancePage.tsx`
- Create: `src_frontend/src/pages/vendor/VendorPerformancePage.test.tsx`

- [x] **Step 1: 寫月份、純讀與 query count RED 測試**

```python
@pytest.mark.parametrize("period", ["abc", "2026-00", "2026-13", "2026-1", "26-01"])
def test_invalid_period_returns_400_without_write(client, period, db_session):
    before = VendorPerformance.query.count()
    response = client.get(f"/api/vendor-performance?period={period}", headers=viewer_headers())
    assert response.status_code == 400
    assert VendorPerformance.query.count() == before

def test_list_query_count_is_constant(app, vendors):
    with count_sql(app) as small:
        VendorPerformanceService.calculate_period(parse_period("2026-08"))
    create_more_vendors(20)
    with count_sql(app) as large:
        VendorPerformanceService.calculate_period(parse_period("2026-08"))
    assert large <= small + 1
```

GET 測試 monkeypatch `db.session.commit` 為會拋錯，仍須 200，證明純讀不 commit。

- [x] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_vendor_performance.py -q`

Expected: FAIL；月份 slice 可接受無效值，GET 逐廠商查詢並寫 snapshot。

- [x] **Step 3: 實作嚴格月份與集合式計算**

```python
PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

def parse_period(value: str) -> PeriodWindow:
    match = PERIOD_RE.fullmatch(value)
    if not match:
        raise ValidationError("period 必須為 YYYY-MM")
    start = date(int(match.group(1)), int(match.group(2)), 1)
    end = start + relativedelta(months=1)
    return PeriodWindow(value=value, start=start, end_exclusive=end)
```

以三個集合查詢取得 shipping、CAPA、complaint 聚合，再在 Python 只對聚合 row 計分。`list_by_period()` 回即時計算結果、不 add、不 commit。

- [x] **Step 4: 新增明確 refresh mutation**

`POST /api/vendor-performance/refresh`，body `{ "period": "2026-08" }`，需 `vendor.manage`。service 以 `(vendor_id, period)` 唯一鍵 bulk upsert，單一 transaction commit；競爭衝突 rollback 後回 409。

- [x] **Step 5: 前端 refresh 後精確 invalidation**

mutation success 只 invalidates `['vendor-performance', period]` 與該 period ranking；history query key 含 vendor id 與 months。

- [x] **Step 6: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_vendor_performance.py backend/tests/test_permission_gating.py -q`

Run: `npm test -- --run src/hooks/useVendorPerformance.test.tsx src/pages/vendor/VendorPerformancePage.test.tsx` (workdir `src_frontend`)

Expected: PASS。

```powershell
git add backend/services/vendor_performance_service.py backend/routes/vendor_performance.py backend/tests/test_services/test_vendor_performance.py backend/tests/test_permission_gating.py src_frontend/src/hooks/useVendorPerformance.ts src_frontend/src/hooks/useVendorPerformance.test.tsx src_frontend/src/pages/vendor/VendorPerformancePage.tsx src_frontend/src/pages/vendor/VendorPerformancePage.test.tsx
git diff --check
git commit -m "效能：以集合式查詢重整廠商績效"
```

---

### Task 12: 將 Quality Analytics 聚合下推資料庫

**Files:**
- Modify: `backend/services/quality_analytics_service.py`
- Modify: `backend/routes/quality_analytics.py`
- Modify: `backend/tests/test_services/test_quality_analytics.py`
- Modify: `backend/tests/test_route_parameter_bounds.py`

- [x] **Step 1: 寫結果等價、邊界與禁止完整 ORM 載入測試**

```python
def test_pareto_uses_grouped_columns_only(db_session, seeded_ncmrs, monkeypatch):
    statements = []
    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        rows = QualityAnalyticsService.defect_pareto(window, top_n=10)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert [row["category"] for row in rows] == ["尺寸", "外觀"]
    assert all("不良描述" not in statement for statement in statements)
    assert any("GROUP BY" in statement.upper() for statement in statements)
```

另測 SQLite/PostgreSQL month expression、CAPA aging bucket、overdue limit 1..100、top_n 1..50、日期範圍最多 366 天。

- [x] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_quality_analytics.py backend/tests/test_route_parameter_bounds.py -q`

Expected: FAIL；Pareto/trend/repeat 仍 `.all()` 完整 ORM 後 Python 聚合。

- [x] **Step 3: 改為欄位級 GROUP BY**

```python
rows = db.session.query(
    NCMR.defect_category.label("category"),
    func.count(NCMR.id).label("count"),
).filter(*active_window_filters).group_by(NCMR.defect_category).order_by(
    func.count(NCMR.id).desc(), NCMR.defect_category.asc()
).limit(top_n).all()
```

月份 adapter 重用 `DashboardService` 可抽出的 `_month_expr`，移到 `date_range.py` 的 `month_bucket(column)`，SQLite 用 `strftime`、PostgreSQL 用 `to_char`。CAPA aging 以 `case()` + `avg()` 聚合；逾期只 select 顯示欄位並 limit。

- [x] **Step 4: vendor ranking 重用 VendorPerformanceService**

只呼叫 `VendorPerformanceService.list_by_period(parse_period(period))`，不複製評分公式；route 使用 bounded parser 並只捕捉 ValidationError。

- [x] **Step 5: 驗證與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_quality_analytics.py backend/tests/test_route_parameter_bounds.py -q`

Expected: PASS。

```powershell
git add backend/services/quality_analytics_service.py backend/services/date_range.py backend/routes/quality_analytics.py backend/tests/test_services/test_quality_analytics.py backend/tests/test_route_parameter_bounds.py
git diff --check
git commit -m "效能：將品質分析聚合下推資料庫"
```

---

### Task 13: 重整 React Query、表單 session 與 lint 閘門

**Files:**
- Modify: `src_frontend/src/pages/rework/useReworkPageData.ts`
- Create: `src_frontend/src/pages/rework/useReworkPageData.test.tsx`
- Modify: `src_frontend/src/components/rework/useReworkMutations.ts`
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`
- Create: `src_frontend/src/pages/pyrometry/pyrometryTestFormState.ts`
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestForm.test.tsx`
- Modify: `src_frontend/src/pages/mechanical/MechanicalTestForm.tsx`
- Create: `src_frontend/src/pages/mechanical/mechanicalTestFormState.ts`
- Modify: `src_frontend/src/pages/mechanical/MechanicalTestForm.test.tsx`
- Modify: `src_frontend/src/components/msa/MsaBlindEntry.tsx`
- Create: `src_frontend/src/components/msa/MsaBlindEntry.test.tsx`
- Modify: `src_frontend/package.json`

- [ ] **Step 1: 寫 Rework Query RED 測試**

```tsx
const wrapper = createQueryWrapper();
const { result } = renderHook(
  () => useReworkPageData({ statusFilter: '待審核', startDate: '', endDate: '' }),
  { wrapper },
);
await waitFor(() => expect(result.current.isSuccess).toBe(true));
expect(api.get).toHaveBeenCalledWith('/rework/applications?status=待審核');
expect(api.get).toHaveBeenCalledWith('/rework/statistics');
```

mutation 測試斷言只 invalidate `['rework','applications']` 與 `['rework','statistics']`，不使用寬 prefix 清全部 cache。

- [ ] **Step 2: 寫三個表單 session RED 測試**

- Pyrometry：載入 edit data 只 dispatch 一次 `hydrate`，使用者未修改欄位保持原值。
- Mechanical：`testId` 從 1 變 2 時以 `key={testId ?? 'new'}` 重建 session；不在 effect 逐欄 setState。
- MSA blind entry：task key 改變時輸入值清空且焦點移到第一格；同 task re-render 不清空使用者輸入。

- [ ] **Step 3: 執行 RED 測試與 lint 基線**

Run: `npm test -- --run src/pages/rework/useReworkPageData.test.tsx src/pages/pyrometry/PyrometryTestForm.test.tsx src/pages/mechanical/MechanicalTestForm.test.tsx src/components/msa/MsaBlindEntry.test.tsx` (workdir `src_frontend`)

Run: `npm run lint -- --max-warnings=0` (workdir `src_frontend`)

Expected: 新增的狀態測試 FAIL；目前 lint 基線 PASS 且為 0 warnings。若此時 lint 非 0，先記錄實際檔案與 rule，再納入本任務修復，不沿用舊審查數字。

- [ ] **Step 4: 以 useQuery 取代自建 server state**

```tsx
const applications = useQuery({
  queryKey: ['rework', 'applications', { statusFilter, startDate, endDate }],
  queryFn: () => api.get<ReworkApplication[]>(url).then(r => r.data),
});
const statistics = useQuery({
  queryKey: ['rework', 'statistics'],
  queryFn: () => api.get<ReworkStatistics>('/rework/statistics').then(r => r.data),
});
return {
  applications: applications.data ?? [],
  stats: statistics.data ?? null,
  loading: applications.isLoading || statistics.isLoading,
  loadData: () => Promise.all([applications.refetch(), statistics.refetch()]),
};
```

- [ ] **Step 5: 表單改 reducer/keyed session**

Pyrometry reducer 只提供 `hydrate`、`setField`、`reset`；Mechanical 外層用 keyed `MechanicalTestFormSession`；MSA 外層用 `<BlindEntrySession key={task.id}>`，唯一 effect 只呼叫 `inputRef.current?.focus()`。

- [ ] **Step 6: 將零 warning 寫入正式 lint 命令**

把 `package.json` 的 lint script 固定為：

```json
"lint": "eslint . --max-warnings=0"
```

Pyrometry/Mechanical reducer 與 mapper 放在本任務新增的 `.ts` 檔，`MsaBlindEntry.tsx` 只 export component；若新增型別邊界，使用 unknown 與 type guard，不加入 any。

- [ ] **Step 7: 驗證與提交**

Run: `npm test -- --run src/pages/rework/useReworkPageData.test.tsx src/components/rework/useReworkMutations.test.tsx src/pages/pyrometry/PyrometryTestForm.test.tsx src/pages/mechanical/MechanicalTestForm.test.tsx src/components/msa/MsaBlindEntry.test.tsx` (workdir `src_frontend`)

Run: `npm run lint -- --max-warnings=0` (workdir `src_frontend`)

Expected: 全部 PASS，0 errors、0 warnings。

```powershell
git add src_frontend/src src_frontend/package.json
git diff --check
git commit -m "重構：統一前端查詢與表單狀態"
```

---

### Task 14: 深化 CalibrationService.save_readings 內部模組

**Files:**
- Create: `backend/services/calibration_reading_payload.py`
- Create: `backend/services/calibration_reading_apply.py`
- Modify: `backend/services/calibration_service.py`
- Modify: `backend/tests/test_services/test_calibration_readings.py`
- Modify: `backend/tests/test_services/test_calibration_drafts.py`
- Modify: `backend/tests/test_calibration_routes.py`

- [ ] **Step 1: 鎖定公開介面與行為 parity**

```python
def test_save_readings_public_signature_is_stable():
    signature = inspect.signature(CalibrationService.save_readings)
    assert list(signature.parameters) == ["calibration_id", "payload", "actor_id"]
```

以既有 single、paired、unknown point、submitted record、legacy summary cases 做 characterization tests；測原始讀值、計算證據與 summary 完全相同。

- [ ] **Step 2: 執行現有測試確認 GREEN 基線，再加私有模組 RED 單元測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_calibration_readings.py backend/tests/test_services/test_calibration_drafts.py backend/tests/test_calibration_routes.py -q`

Expected: 既有測試 PASS；新增 normalization/apply 單元測試因模組不存在 FAIL。

- [ ] **Step 3: 抽出深模組資料結構**

```python
@dataclass(frozen=True)
class NormalizedCalibrationPoint:
    point_id: int
    reference_value: Decimal | None
    expanded_uncertainty: Decimal | None
    coverage_factor: Decimal | None
    rule: CalibrationPointRule
    readings: tuple[CalibrationReadingInput, ...]

def normalize_points_payload(
    payload: Mapping[str, object],
    existing_points: Mapping[int, EquipmentCalibrationPoint],
) -> tuple[NormalizedCalibrationPoint, ...]:
    return CalibrationReadingPayloadNormalizer(existing_points).normalize(payload)
```

`CalibrationReadingPayloadNormalizer.normalize()` 完整搬移現有 `_MAX_POINTS`、完整 point matrix、未知欄位、重複 point、完整 trial matrix、必要示值與 paired standard reading 驗證；Decimal 仍呼叫既有 `_optional_decimal` 等價純函式。`calibration_reading_apply.apply_readings()` 接受已正規化 tuple，呼叫既有 `calibration_calculation.calculate_point()`、upsert reading 與 evidence，回傳 `ReadingApplyResult`。`save_readings()` 仍是唯一公開入口：鎖 record → normalize → apply → audit → commit。私有模組不讀 Flask request、不自行 commit。

- [ ] **Step 4: 驗證全校正讀值鏈**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_calibration_readings.py backend/tests/test_services/test_calibration_drafts.py backend/tests/test_services/test_calibration_calculation.py backend/tests/test_services/test_calibration_workflow.py backend/tests/test_calibration_routes.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/services/calibration_reading_payload.py backend/services/calibration_reading_apply.py backend/services/calibration_service.py backend/tests/test_services/test_calibration_readings.py backend/tests/test_services/test_calibration_drafts.py backend/tests/test_calibration_routes.py
git diff --check
git commit -m "重構：深化校正讀值保存模組"
```

---

### Task 15: 在 metadata parity 保護下拆分 74 個 model-related classes

**Files:**
- Create: `backend/tests/test_model_registry.py`
- Create: `backend/models/base.py`
- Create: `backend/models/auth_audit.py`
- Create: `backend/models/inspection.py`
- Create: `backend/models/spc.py`
- Create: `backend/models/calibration.py`
- Create: `backend/models/msa.py`
- Create: `backend/models/quality_workflow.py`
- Create: `backend/models/pyrometry.py`
- Create: `backend/models/mechanical.py`
- Create: `backend/models/__init__.py`
- Delete: `backend/models.py`

- [ ] **Step 1: 建立 registry 與 metadata characterization test**

```python
EXPECTED_MODELS = {
    mapper.class_.__name__: {
        "table": mapper.local_table.name,
        "columns": tuple(column.name for column in mapper.columns),
        "relationships": tuple(sorted(mapper.relationships.keys())),
        "constraints": tuple(sorted(constraint_signature(c) for c in mapper.local_table.constraints)),
    }
    for mapper in db.Model.registry.mappers
}

def test_models_public_exports_match_registry():
    assert set(EXPECTED_MODELS) == set(models.MODEL_EXPORTS) - {"SoftDeleteMixin"}
    assert len(EXPECTED_MODELS) == 73
    assert len(models.MODEL_EXPORTS) == 74
```

74 個公開 model-related classes 包含 73 個 SQLAlchemy mapper 與 `SoftDeleteMixin`。將拆分前產生的 `EXPECTED_MODEL_SIGNATURES` 以純 Python literal 固定在 test file；不可在拆分後動態從新模型生成 expected。

- [ ] **Step 2: 執行拆分前 characterization tests**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_model_registry.py backend/tests/test_services/test_spc_models.py backend/tests/test_services/test_calibration_models.py backend/tests/test_services/test_msa_models.py backend/tests/test_services/test_mechanical_models.py -q`

Expected: PASS，並確認 74 個模型簽章已鎖定。

- [ ] **Step 3: 依下列固定邊界移動類別與 listeners**

- `base.py`：`utc_now`、`SoftDeleteMixin`。
- `auth_audit.py`：`User`、`Role`、`AuditLog`、`Inspector`、`Vendor`、`Machine`、`Operator`。
- `inspection.py`：`PatrolMain`、`PatrolDetail`、`ShippingData`、`ShippingMeasurement`。
- `spc.py`：`SPCCache`、`SpcControlLimit`、`SpcStudy`、`SpcStudyVersion`、`SpcStudySample`、`SpcLimitVersion`、`SpcEvent`、`SpcOcap`、`SpcValidationRun` 與 SPC immutable listeners。
- `calibration.py`：CalibrationTemplate 到 EquipmentImportRow 的 13 個模型，以及 template/calibration/reference snapshot listeners。
- `msa.py`：MsaCriteriaProfile 到 MsaValidationRun 的 13 個模型，以及 frozen evidence/plan/result listeners。
- `quality_workflow.py`：四個 tolerance 模型、`NCMR`、`NcmrDisposition`、`CorrectiveAction`、四個 Rework 模型、`CustomerComplaint`、`ActionTask`、`Attachment`、`VendorPerformance`。
- `pyrometry.py`：`Furnace`、`PyrometryTest`、`TusPoint`、`SatPoint`、`Recorder`、`RecorderCalPoint`、`Thermocouple`、`ThermocoupleCalPoint`。
- `mechanical.py`：`MechanicalTest`、`MechanicalTraceNumber`、`MechanicalMeasurement`、`MechanicalWaivedItem`。

跨模組 relationship 保持字串名稱，避免 import cycle；listeners 與其目標 class 放同檔，並確保只註冊一次。

- [ ] **Step 4: 建立相容重匯出**

```python
MODEL_EXPORTS = (
    "SoftDeleteMixin", "User", "Role", "AuditLog", "Inspector", "Vendor", "Machine", "Operator",
    "PatrolMain", "PatrolDetail", "ShippingData", "ShippingMeasurement", "SPCCache", "SpcControlLimit",
    "SpcStudy", "SpcStudyVersion", "SpcStudySample", "SpcLimitVersion", "SpcEvent", "SpcOcap",
    "SpcValidationRun", "CalibrationTemplate", "CalibrationTemplateVersion", "CalibrationTemplatePoint",
    "MeasurementEquipment", "MeasurementEquipmentLink", "EquipmentCalibrationRecord",
    "EquipmentCalibrationPoint", "EquipmentCalibrationReading", "CalibrationReferenceSnapshot",
    "EquipmentCorrectionPoint", "EquipmentStatusEvent", "EquipmentImportBatch", "EquipmentImportRow",
    "MsaCriteriaProfile", "MsaCriteriaVersion", "MsaStudy", "MsaStudyEquipment", "MsaPlanVersion",
    "MsaPart", "MsaAppraiser", "MsaObservationImportBatch", "MsaObservation", "MsaResultVersion",
    "MsaWorkflowDecision", "MsaRestudyRequest", "MsaValidationRun", "VendorToleranceMain",
    "VendorToleranceDetail", "ExtrusionToleranceMain", "ExtrusionToleranceDetail", "NCMR",
    "NcmrDisposition", "CorrectiveAction", "ReworkRequest", "ReworkExecution", "ReworkInspection",
    "ReworkCost", "CustomerComplaint", "ActionTask", "Attachment", "VendorPerformance", "Furnace",
    "PyrometryTest", "TusPoint", "SatPoint", "Recorder", "RecorderCalPoint", "Thermocouple",
    "ThermocoupleCalPoint", "MechanicalTest", "MechanicalTraceNumber", "MechanicalMeasurement",
    "MechanicalWaivedItem",
)

__all__ = ["utc_now", *MODEL_EXPORTS]
```

不得用 wildcard import；既有 `from backend.models import X` 全數維持。

- [ ] **Step 5: 執行 parity、event listener 與完整模型測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_model_registry.py backend/tests/test_services/test_spc_models.py backend/tests/test_services/test_calibration_models.py backend/tests/test_services/test_calibration_templates.py backend/tests/test_services/test_msa_models.py backend/tests/test_services/test_msa_workflow.py backend/tests/test_services/test_mechanical_models.py backend/tests/test_migration_41.py backend/tests/test_migration_42.py -q`

Expected: PASS；table/column/constraint/relationship signatures 完全相同，immutable listeners 仍阻止更新與刪除。

- [ ] **Step 6: 驗證 imports 與提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -c "from backend import models; print(len(models.__all__), len(models.MODEL_EXPORTS))"`

Expected: `75 74`（`utc_now` 加 74 個 model-related class exports；其中 73 個是 mapper）。

```powershell
git add backend/models backend/tests/test_model_registry.py
git rm backend/models.py
git diff --check
git commit -m "重構：依領域拆分資料模型註冊表"
```

---

### Task 16: 測試分層、PostgreSQL CI、部署 runbook 與完整驗證

**Files:**
- Create: `pytest.ini`
- Create: `.github/workflows/quality-gates.yml`
- Create: `docs/runbooks/credential-rotation.md`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/integration/test_spc_migration_38_postgres.py`
- Modify: `backend/tests/integration/test_spc_time_model_concurrency_postgres.py`
- Modify: `backend/tests/test_services/test_calibration_migration.py`
- Modify: `backend/tests/test_services/test_spc_golden.py`
- Modify: `backend/tests/test_services/test_msa_golden.py`
- Modify: `backend/tests/test_services/test_msa_report.py`
- Modify: `backend/tests/test_services/test_spc_report_versioning.py`
- Create: `docs/testing.md`

- [ ] **Step 1: 先寫 marker 與 workflow 靜態測試**

以實際命令驗證 marker 與 workflow：

```python
def test_pytest_markers_are_registered(repo_root):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--markers"],
        cwd=repo_root, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    for marker in ("unit", "integration", "postgresql", "slow"):
        assert f"@pytest.mark.{marker}" in result.stdout
```

Workflow 不加原始碼文字測試；建立後執行 `actionlint .github/workflows/quality-gates.yml`，並以 GitHub Actions 的 PostgreSQL job 實際執行作為正式證據。

- [ ] **Step 2: 執行 RED 測試**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_repository_security.py -q`

Expected: FAIL；pytest.ini 與 workflow 尚不存在。

Run: `actionlint .github/workflows/quality-gates.yml`

Expected: FAIL；workflow 尚不存在。若本機沒有 `actionlint`，先用官方 release binary 的固定版本執行，不以 YAML 文字搜尋替代。

- [ ] **Step 3: 註冊 markers 並標記現有測試**

```ini
[pytest]
markers =
    unit: 不需 Flask app 或資料庫的快速單元測試
    integration: 需要 Flask app、檔案或資料庫的整合測試
    postgresql: 必須在 PostgreSQL 執行的 schema、鎖定與並發測試
    slow: 執行時間較長的報表、golden 或大量資料測試
```

兩個 `backend/tests/integration/*postgres.py` 與 `test_calibration_migration.py` 的 PostgreSQL cases 加 `postgresql`、`integration`；`test_spc_golden.py`、`test_msa_golden.py`、`test_msa_report.py`、`test_spc_report_versioning.py` 加 `slow`。本機快速命令：`python -m pytest backend/tests -m "not postgresql and not slow" -q`。正式後端閘門仍跑全部 SQLite 可跑測試；PostgreSQL job 單獨跑 `-m postgresql --run-postgres`。

- [ ] **Step 4: 建立 CI jobs**

- `backend-sqlite`：安裝 requirements，設定測試 SECRET_KEY，跑全部非 postgresql tests 與 `pip check`。
- `backend-postgresql`：service `postgres:16`，建立隔離 DB，套 migration 38、49、50、51，跑 `backend/tests/integration -m postgresql --run-postgres` 與 calibration migration/route contract。
- `frontend`：Node 22、`npm ci`、`npm test`、`npm run lint -- --max-warnings=0`、`npm run build`、`npm audit --omit=dev`。
- `repository-security`：執行 tracked secret scanner 與 `git diff --check`。

- [ ] **Step 5: 撰寫憑證與歷史清理 runbook**

文件固定順序：

1. 備份 DB 與目前環境變數來源。
2. 產生新 PostgreSQL 密碼與至少 32-byte `SECRET_KEY`。
3. 更新 secret manager/主機環境，停止應用、修改 DB 帳號、重建容器。
4. 驗證 login、`/api/verify-token`、代表性 authenticated GET；確認舊 JWT 401。
5. 決定是否用 `git filter-repo` 清歷史；若執行，先封鎖 push、備份 mirror、通知協作者、force-push 經核准分支，協作者重新 clone，不以 pull 合併舊歷史。
6. 記錄操作者、時間、變更單、驗證結果與 rollback 條件。

- [ ] **Step 6: 執行窄驗證並提交**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/test_repository_security.py -q`

Run: `actionlint .github/workflows/quality-gates.yml`

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests -m "not postgresql and not slow" -q`

Expected: PASS，且無 unknown marker warning。

```powershell
git add pytest.ini .github/workflows/quality-gates.yml docs/runbooks/credential-rotation.md docs/testing.md backend/tests/conftest.py backend/tests/integration/test_spc_migration_38_postgres.py backend/tests/integration/test_spc_time_model_concurrency_postgres.py backend/tests/test_services/test_calibration_migration.py backend/tests/test_services/test_spc_golden.py backend/tests/test_services/test_msa_golden.py backend/tests/test_services/test_msa_report.py backend/tests/test_services/test_spc_report_versioning.py backend/tests/test_repository_security.py
git diff --check
git commit -m "測試：建立分層閘門與憑證輪替手冊"
```

- [ ] **Step 7: 執行完整後端驗證**

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests -q`

Expected: 所有 SQLite 可執行測試 PASS；逐字記錄 passed/skipped 數量。

Run: `C:\QC_Database\venv\Scripts\python.exe -m pip check`

Expected: `No broken requirements found.`

- [ ] **Step 8: 執行 PostgreSQL migration/concurrency 驗證**

先確認隔離測試 DB URL，不得指向正式 `qa_database`。若 CI/local PostgreSQL 可用：

Run: `C:\QC_Database\venv\Scripts\python.exe -m pytest backend/tests/integration backend/tests/test_services/test_calibration_migration.py backend/tests/test_migration_50.py backend/tests/test_migration_51.py -m postgresql --run-postgres -q`

Expected: PASS，包含 migrations 38/49/50/51、SPC concurrency 與 calibration PostgreSQL contract。若環境不可用，回報「未執行」及缺少的具體服務，不改報為 PASS。

- [ ] **Step 9: 執行完整前端與供應鏈驗證**

Run: `npm test` (workdir `src_frontend`)

Run: `npm run lint -- --max-warnings=0` (workdir `src_frontend`)

Run: `npm run build` (workdir `src_frontend`)

Run: `npm audit --omit=dev` (workdir `src_frontend`)

Expected: 全部 exit 0，lint 0 warnings，audit 0 vulnerabilities。

- [ ] **Step 10: 執行 Docker 與 migration smoke**

Run: `$env:DB_PASSWORD='test-only-password'; Set-Item -Path Env:SECRET_KEY -Value 'test-only-secret-key-32-bytes-minimum'; docker compose build --no-cache app`

Expected: build exit 0，映像內不存在 `/app/.env`。

以隔離 volume 啟動後，執行 login、verify-token、NCMR create/list/delete rollback probe、Dashboard end-date probe；完成後用同一 Compose project name 停止並移除該隔離測試容器與 volume。不得連線正式 volume。

- [ ] **Step 11: 最終 repository 檢查**

Run: `C:\QC_Database\venv\Scripts\python.exe backend/scripts/scan_tracked_secrets.py`

Run: `rg -n "db\.session\.commit\(" backend/routes -g "*.py"`

Expected: 兩者皆無問題；第二個命令無輸出。

Run: `git diff --check`

Run: `git status --short --branch`

Expected: diff check exit 0；工作樹乾淨，分支為 `fix/codebase-review-all`。

---

## 最終驗收對照

- [ ] 停用帳號舊 JWT：401、零寫入。
- [ ] 角色降權或密碼變更舊 JWT：401。
- [ ] 只有 view 權限呼叫代表性 mutation：403、零寫入。
- [ ] `ncmr.edit_own`：只允許同 inspector 的 NCMR。
- [ ] 合法 NCMR 日期 JSON：201；錯誤日期：422；非物件 body：400。
- [ ] audit 寫入失敗：業務異動 rollback、500、零 audit row。
- [ ] Dashboard 結束日中午資料計入；start>end 與超長範圍 400。
- [ ] Vendor Performance GET 零寫入、無 N× query、無效月份 400；refresh 單 transaction。
- [ ] Quality Analytics 以 SQL 聚合，不載入完整 ORM collection。
- [ ] route 不含 `str(e)` 5xx 或 `raise e`；5xx 固定 envelope 並帶 correlation id。
- [ ] Git 追蹤樹與 Docker context 無已知秘密；Compose 缺秘密拒絕展開。
- [ ] ORM registry 仍為 74 個公開模型，metadata 與 listeners parity 通過。
- [ ] 後端完整 suite、前端完整 suite、lint、build、audit、pip check、diff check 通過。
- [ ] PostgreSQL 與 Docker smoke 有實際 PASS 證據，或明確列為未執行且不混入通過項。
