# MSA 設備與準則基礎實作計畫

> **Required subskill:** 執行本計畫時必須使用 `superpowers:test-driven-development`；每個任務完成後依下列窄測試驗證，整份計畫結束前使用 `superpowers:verification-before-completion`。

**Goal:** 建立可稽核的通用量測設備主檔、受控設備清單匯入、校驗與狀態事件，以及版本化 MSA 判定準則，並提供可實際操作的前後端頁面。

**Architecture:** 後端維持 Blueprint → Service → SQLAlchemy 三層，設備與 MSA 準則分成兩個 Blueprint，但共用 MSA 錯誤契約、權限與稽核格式。前端以獨立 `/msa` 垂直切片承接型別、React Query hooks、頁面與元件。核准後的校驗與準則版本由 ORM 事件及 PostgreSQL trigger 雙層保護。

**Tech Stack:** Flask 3.1、SQLAlchemy 2、PostgreSQL 16、pytest、React 19、TypeScript 5.9、TanStack React Query 5、Vitest、Testing Library、Bootstrap 5。

**Global Constraints:**

- 依據已核准規格：[MSA 第四版完整模組設計](../specs/2026-07-27-msa-fourth-edition-module-design.md)。
- 執行前先確認 `backend/migration` 仍以 `43_create_mechanical_waived_items.sql` 為最新遷移；若已有新遷移，只調整本計畫的遷移編號與檔名，不改變資料模型。
- 權限固定為 `msa.view`、`msa.execute`、`msa.manage`、`msa.approve`；管理員不得繞過後續研究的自己核准限制。
- 使用者提供的 `C:\Users\bihro\Downloads\measurements (1).csv` 只作為初始匯入輸入，不提交到 Git。
- 所有程式碼備註、錯誤訊息與 commit 訊息使用繁體中文。
- 不修改或納入使用者現有的 `src_frontend/vite.config.ts` 變更。

---

## Task 1：先鎖定 MSA 權限註冊與導覽邊界

**Files:**

- Modify: `backend/seeds/seed_roles.py`
- Modify: `src_frontend/src/pages/admin/adminPermissions.ts`
- Modify: `src_frontend/src/pages/admin/adminPermissions.test.ts`
- Modify: `src_frontend/src/components/Sidebar.tsx`
- Modify: `src_frontend/src/components/Sidebar.test.tsx`
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/App.test.tsx`
- Create: `src_frontend/src/pages/msa/MsaWorkspacePage.tsx`
- Test: `backend/tests/test_services/test_msa_permissions.py`

### Step 1：先寫失敗的後端角色種子測試

```python
"""MSA 權限種子的回歸測試。"""

from backend.seeds.seed_roles import ROLES


def _permissions(role_code: str) -> dict:
    return next(role["permissions"] for role in ROLES if role["code"] == role_code)


def test_msa_permissions_follow_separation_of_duties():
    assert _permissions("inspector")["msa.execute"] is True
    assert _permissions("qa_supervisor")["msa.manage"] is True
    assert "msa.approve" not in _permissions("qa_supervisor")
    assert _permissions("qc_manager")["msa.approve"] is True
    assert _permissions("admin")["msa.approve"] is True
```

### Step 2：執行測試，確認因權限尚未加入而失敗

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_permissions.py -q
```

Expected: FAIL，指出 `msa.execute` 或 `msa.manage` 不存在。

### Step 3：加入角色預設權限

在 `ROLES` 的既有 permission dict 中加入：

```python
# inspector
'msa.view': True, 'msa.execute': True,

# qa_supervisor
'msa.view': True, 'msa.execute': True, 'msa.manage': True,

# qc_manager 與 admin
'msa.view': True, 'msa.execute': True, 'msa.manage': True, 'msa.approve': True,
```

### Step 4：先寫失敗的前端權限與導覽測試

在 `adminPermissions.test.ts` 加入：

```typescript
it('可設定 MSA 檢視、執行、管理與核准四層權限', () => {
  const msa = PERMISSION_GROUPS.find(group => group.label === '量測系統分析');

  expect(msa?.perms).toEqual([
    { key: 'msa.view', label: '檢視' },
    { key: 'msa.execute', label: '執行研究與輸入資料' },
    { key: 'msa.manage', label: '管理設備、準則與送審' },
    { key: 'msa.approve', label: '核准與作廢' },
  ]);
});
```

在 `Sidebar.test.tsx` 加入：

```typescript
describe('Sidebar 的 MSA 選單', () => {
  it('沒有 msa.view 時不顯示 MSA 工作台', () => {
    authMock.mockReturnValue({ user: { role: 'user' }, hasPermission: () => false });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.queryByRole('link', { name: /MSA 工作台/ })).not.toBeInTheDocument();
  });

  it('具有 msa.view 時顯示 MSA 工作台', () => {
    authMock.mockReturnValue({
      user: { role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
    });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.getByRole('link', { name: /MSA 工作台/ })).toHaveAttribute('href', '/msa');
  });
});
```

在 `App.test.tsx` mock `MsaWorkspacePage` 並驗證 `/msa`：

```typescript
vi.mock('./pages/msa/MsaWorkspacePage', () => ({
  default: () => <h2>MSA 工作台路由頁面</h2>,
}));

it('已驗證使用者造訪 /msa 時呈現 MSA 工作台', async () => {
  window.history.replaceState({}, '', '/msa');
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'MSA 工作台路由頁面' })).toBeInTheDocument();
});
```

### Step 5：執行前端窄測試，確認失敗

Run:

```powershell
cd src_frontend
npx vitest run src/pages/admin/adminPermissions.test.ts src/components/Sidebar.test.tsx src/App.test.tsx
```

Expected: FAIL，MSA 權限群組、選單及路由尚不存在。

### Step 6：加入最小權限註冊、路由與工作台殼層

`adminPermissions.ts` 新增：

```typescript
{
  label: '量測系統分析',
  perms: [
    { key: 'msa.view', label: '檢視' },
    { key: 'msa.execute', label: '執行研究與輸入資料' },
    { key: 'msa.manage', label: '管理設備、準則與送審' },
    { key: 'msa.approve', label: '核准與作廢' },
  ],
},
```

`Sidebar.tsx` 的品質管理群組加入：

```typescript
{ title: 'MSA 工作台', path: '/msa', icon: 'fa-ruler-combined', permission: 'msa.view' },
```

`App.tsx` 加入 lazy import 與受保護路由：

```typescript
const MsaWorkspacePage = lazy(() => import('./pages/msa/MsaWorkspacePage'));
<Route path="/msa" element={<MsaWorkspacePage />} />
```

`MsaWorkspacePage.tsx` 先建立可辨識殼層：

```tsx
export default function MsaWorkspacePage() {
  return (
    <section aria-labelledby="msa-title">
      <h1 id="msa-title">MSA 工作台</h1>
      <p>管理量測設備、判定準則與量測系統研究。</p>
    </section>
  );
}
```

### Step 7：執行窄測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_permissions.py -q
cd src_frontend
npx vitest run src/pages/admin/adminPermissions.test.ts src/components/Sidebar.test.tsx src/App.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add backend/seeds/seed_roles.py backend/tests/test_services/test_msa_permissions.py src_frontend/src/pages/admin/adminPermissions.ts src_frontend/src/pages/admin/adminPermissions.test.ts src_frontend/src/components/Sidebar.tsx src_frontend/src/components/Sidebar.test.tsx src_frontend/src/App.tsx src_frontend/src/App.test.tsx src_frontend/src/pages/msa/MsaWorkspacePage.tsx
git commit -m "功能：建立 MSA 權限與入口"
```

---

## Task 2：建立設備、匯入與準則的資料庫不可變基礎

**Files:**

- Create: `backend/migration/44_create_msa_and_measurement_equipment.sql`
- Modify: `backend/models.py`
- Test: `backend/tests/test_services/test_msa_models.py`

### Step 1：先寫模型與不可變性失敗測試

測試至少涵蓋以下行為：

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import (
    MeasurementEquipment, EquipmentCalibrationRecord,
    MsaCriteriaProfile, MsaCriteriaVersion,
)


def test_equipment_number_is_unique(db_session):
    db_session.add(MeasurementEquipment(equipment_no="EQ-001", name="游標卡尺"))
    db_session.commit()
    db_session.add(MeasurementEquipment(equipment_no="EQ-001", name="重複設備"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_approved_calibration_cannot_be_changed(db_session):
    equipment = MeasurementEquipment(equipment_no="EQ-002", name="分厘卡")
    db_session.add(equipment)
    db_session.flush()
    record = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date(2026, 7, 1),
        result="pass",
        status="approved",
    )
    db_session.add(record)
    db_session.commit()
    record.certificate_no = "CERT-CHANGED"
    with pytest.raises(ValueError, match="核准後的校驗紀錄不可修改"):
        db_session.commit()


def test_approved_criteria_version_cannot_be_changed(db_session):
    profile = MsaCriteriaProfile(name="一般計量型")
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id,
        version_no=1,
        method_version="MSA4-1.0",
        effective_date=date(2026, 7, 27),
        thresholds={"grr_accept_max": 10, "grr_conditional_max": 30, "ndc_min": 5},
        status="approved",
    )
    db_session.add(version)
    db_session.commit()
    version.thresholds = {"grr_accept_max": 9}
    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可修改"):
        db_session.commit()
```

### Step 2：執行測試，確認模型尚不存在

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_models.py -q
```

Expected: collection FAIL，找不到新模型。

### Step 3：建立遷移

SQL 必須在單一交易內建立下列資料表與索引：

```sql
BEGIN;

CREATE TABLE "量測設備" (
    "識別碼" SERIAL PRIMARY KEY,
    "設備編號" VARCHAR(80) NOT NULL UNIQUE,
    "名稱" VARCHAR(160) NOT NULL,
    "設備類型" VARCHAR(80),
    "製造商" VARCHAR(120),
    "型號" VARCHAR(120),
    "序號" VARCHAR(160),
    "量程下限" NUMERIC,
    "量程上限" NUMERIC,
    "解析度" NUMERIC,
    "單位" VARCHAR(40),
    "部門" VARCHAR(120),
    "存放位置" VARCHAR(200),
    "保管人" VARCHAR(120),
    "狀態" VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    "校驗類別" VARCHAR(30),
    "校驗週期月數" INTEGER,
    "參考標準" BOOLEAN NOT NULL DEFAULT FALSE,
    "影響產品判定" BOOLEAN NOT NULL DEFAULT TRUE,
    "建立者ID" INTEGER REFERENCES users(id),
    "建立時間" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "更新者ID" INTEGER REFERENCES users(id),
    "更新時間" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_equipment_status CHECK (
        "狀態" IN ('pending_review', 'active', 'maintenance', 'inactive', 'scrapped')
    ),
    CONSTRAINT ck_equipment_calibration_type CHECK (
        "校驗類別" IS NULL OR "校驗類別" IN ('internal', 'external', 'exempt')
    )
);

CREATE INDEX idx_equipment_status_due
    ON "量測設備" ("狀態", "設備編號");
```

同一遷移繼續建立：

- `量測設備連結`
- `設備校驗紀錄`
- `設備校驗補正點`
- `設備狀態事件`
- `設備匯入批次`
- `設備匯入列`
- `MSA準則設定`
- `MSA準則版本`

關鍵限制：

```sql
CREATE UNIQUE INDEX uq_equipment_current_source_link
ON "量測設備連結" ("來源模組", "來源實體類型", "來源實體ID")
WHERE "目前正式連結" IS TRUE;

CREATE UNIQUE INDEX uq_equipment_import_sha
ON "設備匯入批次" ("檔案SHA256");

ALTER TABLE "MSA準則版本"
ADD CONSTRAINT uq_msa_criteria_revision UNIQUE ("準則設定ID", "版本號");
```

建立共用不可變 trigger：

```sql
CREATE OR REPLACE FUNCTION msa_block_approved_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' OR OLD."狀態" = 'approved' THEN
        RAISE EXCEPTION '核准的 MSA 證據不可修改或刪除';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

將它套用在 `設備校驗紀錄` 與 `MSA準則版本` 的 UPDATE/DELETE。

### Step 4：建立 SQLAlchemy 模型與 ORM 保護

模型欄位須與 SQL 表一致；JSON 欄位使用 `db.JSON`，PostgreSQL 端由遷移建立為 `JSONB`。設備主模型至少含：

```python
class MeasurementEquipment(db.Model):
    __tablename__ = "量測設備"

    id = db.Column("識別碼", db.Integer, primary_key=True)
    equipment_no = db.Column("設備編號", db.String(80), nullable=False, unique=True)
    name = db.Column("名稱", db.String(160), nullable=False)
    equipment_type = db.Column("設備類型", db.String(80))
    manufacturer = db.Column("製造商", db.String(120))
    model = db.Column("型號", db.String(120))
    serial_no = db.Column("序號", db.String(160))
    range_min = db.Column("量程下限", db.Numeric)
    range_max = db.Column("量程上限", db.Numeric)
    resolution = db.Column("解析度", db.Numeric)
    unit = db.Column("單位", db.String(40))
    department = db.Column("部門", db.String(120))
    location = db.Column("存放位置", db.String(200))
    custodian = db.Column("保管人", db.String(120))
    status = db.Column("狀態", db.String(30), nullable=False, default="pending_review")
    calibration_type = db.Column("校驗類別", db.String(30))
    calibration_interval_months = db.Column("校驗週期月數", db.Integer)
    is_reference_standard = db.Column("參考標準", db.Boolean, nullable=False, default=False)
    affects_product_decision = db.Column("影響產品判定", db.Boolean, nullable=False, default=True)
```

ORM 保護使用同一 listener：

```python
def _block_approved_msa_evidence(mapper, connection, target):
    if target.status == "approved":
        label = (
            "校驗紀錄" if isinstance(target, EquipmentCalibrationRecord)
            else "MSA 準則版本"
        )
        raise ValueError(f"核准後的{label}不可修改")


for _msa_approved_model in (EquipmentCalibrationRecord, MsaCriteriaVersion):
    event.listen(_msa_approved_model, "before_update", _block_approved_msa_evidence)
    event.listen(_msa_approved_model, "before_delete", _block_approved_msa_evidence)
```

### Step 5：執行模型測試與 PostgreSQL 遷移 smoke

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_models.py -q
psql -U postgres -d qa_database -v ON_ERROR_STOP=1 -f backend/migration/44_create_msa_and_measurement_equipment.sql
```

Expected: pytest PASS；SQL 完整 COMMIT，無部分建立。

### Step 6：提交

```powershell
git add backend/migration/44_create_msa_and_measurement_equipment.sql backend/models.py backend/tests/test_services/test_msa_models.py
git commit -m "資料庫：建立 MSA 設備與準則模型"
```

---

## Task 3：建立穩定錯誤契約與設備資格判定

**Files:**

- Create: `backend/services/msa_errors.py`
- Create: `backend/services/msa_contracts.py`
- Create: `backend/services/msa_permissions.py`
- Create: `backend/services/msa_equipment_service.py`
- Test: `backend/tests/test_services/test_msa_equipment.py`

### Step 1：寫資格判定失敗測試

```python
from datetime import date, timedelta

import pytest

from backend.models import MeasurementEquipment, EquipmentCalibrationRecord
from backend.services.msa_equipment_service import MsaEquipmentService
from backend.services.msa_errors import MsaValidationError


def test_pending_equipment_cannot_be_used_for_official_study(db_session):
    equipment = MeasurementEquipment(
        equipment_no="EQ-PENDING", name="待確認量具", status="pending_review"
    )
    db_session.add(equipment)
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(equipment.id, on_date=date.today())

    assert error.value.code == "MSA_EQUIPMENT_PENDING_REVIEW"


def test_expired_calibration_is_rejected(db_session):
    equipment = MeasurementEquipment(
        equipment_no="EQ-EXPIRED", name="逾期量具", status="active",
        calibration_type="external",
    )
    db_session.add(equipment)
    db_session.flush()
    db_session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date.today() - timedelta(days=400),
        next_calibration_date=date.today() - timedelta(days=35),
        result="pass",
        status="approved",
    ))
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(equipment.id, on_date=date.today())

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_EXPIRED"
```

另寫 pass、limited_use、maintenance、scrapped、exempt 及「後一筆核准校驗覆蓋前一筆」測試。

### Step 2：執行測試，確認服務尚不存在

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_equipment.py -q
```

Expected: collection FAIL。

### Step 3：建立錯誤與回應契約

`msa_errors.py`：

```python
class MsaServiceError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class MsaNotFound(MsaServiceError):
    status_code = 404


class MsaForbidden(MsaServiceError):
    status_code = 403


class MsaConflict(MsaServiceError):
    status_code = 409


class MsaValidationError(MsaServiceError):
    status_code = 422
```

`msa_contracts.py`：

```python
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class EquipmentEligibility:
    equipment_id: int
    eligible: bool
    checked_on: date
    calibration_record_id: int | None
    blocking_codes: tuple[str, ...] = field(default_factory=tuple)
    limitation: str | None = None


@dataclass(frozen=True)
class EquipmentSnapshot:
    equipment_id: int
    equipment_no: str
    name: str
    status: str
    resolution: Decimal | None
    unit: str | None
    calibration: dict
```

### Step 4：實作設備資格與快照服務

`assert_officially_usable` 判定順序固定：

1. 不存在 → `MSA_EQUIPMENT_NOT_FOUND`
2. `pending_review` → `MSA_EQUIPMENT_PENDING_REVIEW`
3. `maintenance`、`inactive`、`scrapped` → `MSA_EQUIPMENT_STATUS_BLOCKED`
4. `exempt` → 可用，但快照必須保存 exempt 理由
5. 沒有核准校驗 → `MSA_EQUIPMENT_CALIBRATION_MISSING`
6. 最近核准校驗為 fail/pending → `MSA_EQUIPMENT_CALIBRATION_FAILED`
7. 下次校驗日早於研究日 → `MSA_EQUIPMENT_CALIBRATION_EXPIRED`
8. `limited_use` → 只有研究的模式與限制一致才可用

核心查詢：

```python
record = (
    EquipmentCalibrationRecord.query
    .filter_by(equipment_id=equipment_id, status="approved")
    .order_by(
        EquipmentCalibrationRecord.calibration_date.desc(),
        EquipmentCalibrationRecord.id.desc(),
    )
    .first()
)
```

### Step 5：執行窄測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_equipment.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_errors.py backend/services/msa_contracts.py backend/services/msa_permissions.py backend/services/msa_equipment_service.py backend/tests/test_services/test_msa_equipment.py
git commit -m "功能：建立 MSA 設備資格與錯誤契約"
```

---

## Task 4：完成設備 CRUD、校驗、狀態事件與附件權限

**Files:**

- Create: `backend/routes/measurement_equipment.py`
- Modify: `backend/services/msa_equipment_service.py`
- Modify: `backend/services/attachment_service.py`
- Modify: `backend/routes/attachment.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_msa_routes.py`
- Create: `backend/tests/test_services/test_attachment_service.py`

### Step 1：先寫 API 權限與狀態測試

至少建立下列測試矩陣：

```python
def test_equipment_list_requires_msa_view(client, msa_user_headers):
    response = client.get("/api/measurement-equipment", headers=msa_user_headers("no_msa"))
    assert response.status_code == 403


def test_equipment_create_requires_msa_manage(client, msa_user_headers):
    response = client.post(
        "/api/measurement-equipment",
        json={"equipment_no": "EQ-API-1", "name": "高度規"},
        headers=msa_user_headers("msa_execute"),
    )
    assert response.status_code == 403


def test_equipment_list_is_paginated(client, msa_user_headers):
    response = client.get(
        "/api/measurement-equipment?page=1&page_size=25&sort=equipment_no",
        headers=msa_user_headers("msa_view"),
    )
    assert response.status_code == 200
    assert set(response.get_json()["data"]) == {"items", "page", "page_size", "total"}
```

另測：

- `page_size > 100` 被拒絕。
- 非白名單 `sort` 被拒絕。
- PATCH 不得變更設備編號。
- 已被研究引用的設備不得刪除；本 API 不提供 DELETE。
- `msa.manage` 可建立 draft 校驗紀錄，`msa.approve` 才能核准。
- 校驗 payload 的 correction points 在同一交易建立。
- 建立狀態事件的權限。
- CQI-9 來源連結的部分唯一限制與正式連結切換。

### Step 2：執行測試，確認路由尚不存在

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_msa_routes.py -q
```

Expected: FAIL，404。

### Step 3：建立 Blueprint 與一致錯誤處理

```python
measurement_equipment_bp = Blueprint("measurement_equipment", __name__)


def _handle_msa_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MsaServiceError as error:
            return jsonify({
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                }
            }), error.status_code
    return wrapped
```

路由與權限：

```python
@measurement_equipment_bp.get("/api/measurement-equipment")
@auth_required
@require_permission("msa.view")
@_handle_msa_errors
def list_equipment(current_user):
    return jsonify({"data": MsaEquipmentService.list(request.args)})


@measurement_equipment_bp.post("/api/measurement-equipment")
@auth_required
@require_permission("msa.manage")
@_handle_msa_errors
def create_equipment(current_user):
    return jsonify({"data": MsaEquipmentService.create(request.get_json(), current_user.id)}), 201
```

其餘路由依規格 12.1 節完成，並補上資料模型所需的受控動作：

```text
POST /api/measurement-equipment/calibrations/:calibrationId/approve
POST /api/measurement-equipment/:id/links
POST /api/measurement-equipment/:id/links/:linkId/retire
```

校驗核准與正式連結切換使用列鎖及 expected status/id；以 `log_audit` 保存設備建立、主檔修改、校驗新增／核准、來源連結與狀態事件。

### Step 4：擴充附件實體與權限映射

`attachment_service.py`：

```python
VALID_ENTITY_TYPES = {
    'capa', 'task', 'complaint', 'pyrometry',
    'measurement_equipment', 'equipment_calibration',
}
```

`attachment.py`：

```python
_ENTITY_PERMISSION_PREFIX = {
    # 保留既有映射
    'measurement_equipment': 'msa',
    'equipment_calibration': 'msa',
}
```

由於附件服務使用 `view/edit` 後綴，而 MSA 使用四層權限，調整 `_has_entity_permission`：

```python
if entity_type in {'measurement_equipment', 'equipment_calibration'}:
    required = 'msa.view' if action == 'view' else 'msa.manage'
    return role.has_permission(required)
```

新增測試確認 `msa.view` 可下載但不可上傳，`msa.manage` 可上傳／刪除。

### Step 5：註冊 Blueprint 並執行窄測試

`backend/app.py`：

```python
from .routes.measurement_equipment import measurement_equipment_bp
app.register_blueprint(measurement_equipment_bp)
```

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_msa_routes.py backend\tests\test_services\test_attachment_service.py -q
```

Expected: PASS。

### Step 6：提交

```powershell
git add backend/routes/measurement_equipment.py backend/services/msa_equipment_service.py backend/services/attachment_service.py backend/routes/attachment.py backend/app.py backend/tests/test_msa_routes.py backend/tests/test_services/test_attachment_service.py
git commit -m "功能：完成量測設備與校驗 API"
```

---

## Task 5：以預覽／確認兩階段完成設備 CSV 受控匯入

**Files:**

- Create: `backend/services/msa_import_service.py`
- Modify: `backend/routes/measurement_equipment.py`
- Test: `backend/tests/test_services/test_msa_import.py`
- Test fixture: `backend/tests/fixtures/msa_equipment_import.csv`

### Step 1：建立最小去識別測試 fixture

fixture 只保留測試所需的六列，不複製正式 108 筆資料，內容必須涵蓋：

- 使用中且有效。
- 使用中但校驗逾期。
- 維修。
- 報廢。
- 備註含 `S/N:`。
- 提醒欄含 `<span>` HTML。
- 校驗類別為「遊校」。

### Step 2：先寫解析、清理與冪等失敗測試

```python
def test_preview_normalizes_without_creating_equipment(app, db_session, fixture_path):
    batch = MsaImportService.preview(fixture_path, "equipment.csv", actor_id=1)

    assert batch.status == "previewed"
    assert MeasurementEquipment.query.count() == 0
    rows = EquipmentImportRow.query.filter_by(batch_id=batch.id).order_by(
        EquipmentImportRow.source_row_no
    ).all()
    assert rows[0].normalized_json["status"] == "active"
    assert "<span" not in rows[0].normalized_json["reminder_text"]


def test_preview_extracts_serial_from_notes_without_hiding_source():
    normalized = normalize_equipment_row({
        "設備編號": "EQ-9",
        "備註": "送校，S/N: ABC123",
        "序號": "",
    }, source_row_no=2)
    assert normalized.data["serial_no"] == "ABC123"
    assert normalized.data["legacy_notes"] == "送校，S/N: ABC123"


def test_ambiguous_calibration_type_requires_confirmation():
    normalized = normalize_equipment_row({"校驗類別": "遊校"}, source_row_no=4)
    assert "MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE" in normalized.issue_codes


def test_confirm_is_idempotent_for_same_sha(db_session, preview_batch):
    first = MsaImportService.confirm(preview_batch.id, actor_id=1, resolutions={})
    second = MsaImportService.confirm(preview_batch.id, actor_id=1, resolutions={})
    assert second.id == first.id
    assert MeasurementEquipment.query.count() == first.success_count
```

### Step 3：執行測試，確認失敗

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_import.py -q
```

Expected: collection FAIL。

### Step 4：實作有界解析與正規化

常數固定：

```python
PARSER_VERSION = "msa-equipment-csv-1"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 50
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp950")

STATUS_MAP = {
    "使用中": "active",
    "維修": "maintenance",
    "停用": "inactive",
    "報廢": "scrapped",
}

CALIBRATION_TYPE_MAP = {
    "內校": "internal",
    "外校": "external",
    "免校": "exempt",
}
```

清理 HTML 只輸出純文字；原始 JSON 永遠保留。序號只接受明確前綴：

```python
SERIAL_PATTERN = re.compile(
    r"(?:S/N|SN|序號)\s*[:：#]?\s*([A-Za-z0-9._/-]+)",
    re.IGNORECASE,
)
```

日期以來源值解析，不直接信任來源「逾期」旗標；確認日重新計算：

```python
is_expired = bool(
    next_calibration_date and next_calibration_date < confirmation_date
)
```

### Step 5：實作預覽與確認交易

預覽：

1. 串流讀檔並計算 SHA-256。
2. 驗證副檔名、大小、列數、欄數。
3. 同 SHA 已存在時回傳原 batch，不建立重複列。
4. 保存原始 JSON、正規化 JSON、問題碼。
5. 不建立設備。

確認：

```python
with db.session.begin_nested():
    batch = (
        EquipmentImportBatch.query
        .filter_by(id=batch_id)
        .with_for_update()
        .one()
    )
    if batch.status == "confirmed":
        return batch
    # 只有 resolved 或 clean 列可寫入正式設備
    # pending_review 列仍可建立，但不得執行正式研究
    batch.status = "confirmed"
```

對 2026-07-27 的正式來源檔，預期預覽統計須能重現：

- 108 列。
- 97 使用中、9 報廢、2 維修。
- 68 筆由備註辨識出序號候選。
- 32 筆 HTML 已轉純文字但原值仍存在 raw JSON。
- 1 筆「遊校」留待人工映射。
- 31 筆使用中設備在確認日為校驗逾期。

### Step 6：接上 API

```python
@measurement_equipment_bp.post("/api/measurement-equipment/imports/preview")
@auth_required
@require_permission("msa.manage")
@_handle_msa_errors
def preview_import(current_user):
    file = request.files.get("file")
    batch = MsaImportService.preview(file, current_user.id)
    return jsonify({"data": serialize_import_batch(batch, include_rows=True)}), 201


@measurement_equipment_bp.post("/api/measurement-equipment/imports/<int:batch_id>/confirm")
@auth_required
@require_permission("msa.manage")
@_handle_msa_errors
def confirm_import(current_user, batch_id):
    payload = request.get_json() or {}
    batch = MsaImportService.confirm(
        batch_id,
        current_user.id,
        resolutions=payload.get("resolutions", {}),
    )
    return jsonify({"data": serialize_import_batch(batch, include_rows=True)})
```

### Step 7：驗證 fixture 與正式來源預覽

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_import.py backend\tests\test_msa_routes.py -q
venv\Scripts\python.exe -m backend.scripts.preview_msa_equipment_import "C:\Users\bihro\Downloads\measurements (1).csv" --as-of 2026-07-27
```

若要保留 CLI，建立 `backend/scripts/preview_msa_equipment_import.py` 並納入提交；CLI 必須唯讀，只列統計，不執行確認。

Expected: 測試 PASS；正式來源統計與上述 108/97/9/2/68/32/1/31 相符。

### Step 8：提交

```powershell
git add backend/services/msa_import_service.py backend/routes/measurement_equipment.py backend/tests/test_services/test_msa_import.py backend/tests/fixtures/msa_equipment_import.csv backend/scripts/preview_msa_equipment_import.py
git commit -m "功能：完成設備清單受控匯入"
```

---

## Task 6：完成版本化 MSA 判定準則與核准流程

**Files:**

- Create: `backend/services/msa_criteria_service.py`
- Create: `backend/routes/msa.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_services/test_msa_criteria.py`
- Modify: `backend/tests/test_msa_routes.py`

### Step 1：先寫版本、預設值與核准失敗測試

```python
def test_default_fourth_edition_thresholds_are_explicit():
    thresholds = MsaCriteriaService.default_thresholds()
    assert thresholds["grr_accept_max"] == 10
    assert thresholds["grr_conditional_max"] == 30
    assert thresholds["ndc_min"] == 5
    assert thresholds["alpha"] == 0.05


def test_approving_new_version_supersedes_current_version(db_session, approver):
    profile = create_profile_with_approved_version(db_session, approver.id)
    second = MsaCriteriaService.create_version(
        profile.id,
        {"thresholds": {"grr_accept_max": 8, "grr_conditional_max": 20, "ndc_min": 5}},
        actor_id=approver.id,
    )
    approved = MsaCriteriaService.approve_version(
        second.id, actor_id=approver.id, expected_status="draft"
    )
    db_session.refresh(profile)
    assert profile.current_version_id == approved.id
```

另測：

- 門檻順序必須 `0 <= accept < conditional <= 100`。
- `ndc_min >= 2`。
- alpha 在 `(0, 1)`。
- 同一版本重複核准回 409。
- 沒有 `msa.approve` 回 403。
- 核准版本保存完整 thresholds、stability_rules、conditional_actions 與 basis。

### Step 2：執行測試，確認服務尚不存在

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_criteria.py -q
```

Expected: collection FAIL。

### Step 3：實作服務

預設準則：

```python
DEFAULT_THRESHOLDS = {
    "grr_accept_max": 10.0,
    "grr_conditional_max": 30.0,
    "ndc_min": 5,
    "alpha": 0.05,
    "kappa_min": 0.75,
    "effectiveness_min": 90.0,
    "false_accept_max": 5.0,
    "false_reject_max": 5.0,
}

DEFAULT_STABILITY_RULES = {
    "rule_set": "WECO",
    "enabled_rules": [1, 2, 3, 4],
}
```

核准使用列鎖與版本檢查：

```python
version = (
    MsaCriteriaVersion.query
    .filter_by(id=version_id)
    .with_for_update()
    .one_or_none()
)
if version is None:
    raise MsaNotFound("MSA_CRITERIA_VERSION_NOT_FOUND", "找不到判定準則版本")
if version.status != expected_status:
    raise MsaConflict("MSA_VERSION_CONFLICT", "判定準則版本已被其他人更新")
```

核准後：

- 新 version 改為 `approved` 並寫 approver/time。
- profile.current_version_id 指向新版本。
- 舊核准版本維持不可變的 `approved` 證據；由 `profile.current_version_id` 判斷目前版，UI 將其他 approved 版本顯示為歷史版。
- `log_audit` 保存 profile、version、門檻快照。

### Step 4：完成 MSA Blueprint 的準則路由

```python
msa_bp = Blueprint("msa", __name__)


@msa_bp.get("/api/msa/criteria")
@auth_required
@require_permission("msa.view")
@_handle_msa_errors
def list_criteria(current_user):
    return jsonify({"data": MsaCriteriaService.list(request.args)})


@msa_bp.post("/api/msa/criteria/versions/<int:version_id>/approve")
@auth_required
@require_permission("msa.approve")
@_handle_msa_errors
def approve_criteria_version(current_user, version_id):
    payload = request.get_json() or {}
    result = MsaCriteriaService.approve_version(
        version_id,
        current_user.id,
        expected_status=payload.get("expected_status"),
    )
    return jsonify({"data": serialize_criteria_version(result)})
```

註冊：

```python
from .routes.msa import msa_bp
app.register_blueprint(msa_bp)
```

### Step 5：執行窄測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_criteria.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_criteria_service.py backend/routes/msa.py backend/app.py backend/tests/test_services/test_msa_criteria.py backend/tests/test_msa_routes.py
git commit -m "功能：建立版本化 MSA 判定準則"
```

---

## Task 7：建立設備、匯入與準則前端資料層

**Files:**

- Create: `src_frontend/src/types/msa.ts`
- Create: `src_frontend/src/hooks/useMsaEquipment.ts`
- Create: `src_frontend/src/hooks/useMsaImports.ts`
- Create: `src_frontend/src/hooks/useMsaCriteria.ts`
- Test: `src_frontend/src/hooks/useMsaEquipment.test.tsx`
- Test: `src_frontend/src/hooks/useMsaImports.test.tsx`
- Test: `src_frontend/src/hooks/useMsaCriteria.test.tsx`

### Step 1：先寫 hooks 失敗測試

測試沿用既有 QueryClient wrapper：

```typescript
it('以有界分頁與白名單排序取得設備', async () => {
  vi.mocked(api.get).mockResolvedValueOnce({
    data: { data: { items: [], page: 1, page_size: 25, total: 0 } },
  });

  const { result } = renderHook(
    () => useMsaEquipment({ page: 1, page_size: 25, sort: 'equipment_no' }),
    { wrapper },
  );

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(api.get).toHaveBeenCalledWith('/measurement-equipment', {
    params: { page: 1, page_size: 25, sort: 'equipment_no' },
  });
});
```

匯入測試必須確認 `FormData`、confirm resolutions；準則測試確認核准後 invalidates `['msa', 'criteria']`。

### Step 2：執行測試，確認檔案尚不存在

Run:

```powershell
cd src_frontend
npx vitest run src/hooks/useMsaEquipment.test.tsx src/hooks/useMsaImports.test.tsx src/hooks/useMsaCriteria.test.tsx
```

Expected: collection FAIL。

### Step 3：建立型別

`types/msa.ts` 至少定義：

```typescript
export type EquipmentStatus =
  | 'pending_review' | 'active' | 'maintenance' | 'inactive' | 'scrapped';

export interface MeasurementEquipment {
  id: number;
  equipment_no: string;
  name: string;
  equipment_type: string | null;
  model: string | null;
  serial_no: string | null;
  resolution: string | null;
  unit: string | null;
  status: EquipmentStatus;
  calibration_status: 'valid' | 'due_soon' | 'expired' | 'failed' | 'missing' | 'exempt';
  next_calibration_date: string | null;
}

export interface EquipmentImportIssue {
  code: string;
  message: string;
  field?: string;
}

export interface MsaCriteriaVersion {
  id: number;
  version_no: number;
  status: 'draft' | 'approved';
  is_current: boolean;
  thresholds: Record<string, number>;
  stability_rules: Record<string, unknown>;
}
```

### Step 4：建立 React Query hooks

查詢鍵固定：

```typescript
export const msaKeys = {
  all: ['msa'] as const,
  equipment: (params: EquipmentListParams) => ['msa', 'equipment', params] as const,
  importBatch: (id: number) => ['msa', 'equipment-import', id] as const,
  criteria: () => ['msa', 'criteria'] as const,
};
```

所有 mutation 成功後只 invalidate 對應 MSA key，不清空全站 cache。

### Step 5：執行 hooks 測試並提交

Run:

```powershell
cd src_frontend
npx vitest run src/hooks/useMsaEquipment.test.tsx src/hooks/useMsaImports.test.tsx src/hooks/useMsaCriteria.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/types/msa.ts src_frontend/src/hooks/useMsaEquipment.ts src_frontend/src/hooks/useMsaImports.ts src_frontend/src/hooks/useMsaCriteria.ts src_frontend/src/hooks/useMsaEquipment.test.tsx src_frontend/src/hooks/useMsaImports.test.tsx src_frontend/src/hooks/useMsaCriteria.test.tsx
git commit -m "功能：建立 MSA 基礎前端資料層"
```

---

## Task 8：完成設備與受控匯入頁面

**Files:**

- Create: `src_frontend/src/pages/msa/MeasurementEquipmentPage.tsx`
- Create: `src_frontend/src/pages/msa/MsaImportHistoryPage.tsx`
- Create: `src_frontend/src/components/msa/EquipmentStatusBadge.tsx`
- Create: `src_frontend/src/components/msa/EquipmentDetailDrawer.tsx`
- Create: `src_frontend/src/components/msa/EquipmentCalibrationForm.tsx`
- Create: `src_frontend/src/components/msa/EquipmentImportReview.tsx`
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/pages/msa/MsaWorkspacePage.tsx`
- Test: `src_frontend/src/pages/msa/MeasurementEquipmentPage.test.tsx`
- Test: `src_frontend/src/components/msa/EquipmentImportReview.test.tsx`

### Step 1：先寫使用者行為失敗測試

```typescript
it('先預覽差異，未確認前不建立正式設備', async () => {
  const user = userEvent.setup();
  render(<MeasurementEquipmentPage />);

  await user.upload(screen.getByLabelText('設備清單檔案'), csvFile);
  await user.click(screen.getByRole('button', { name: '預覽匯入' }));

  expect(await screen.findByText('待人工確認 1 筆')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
});


it('不以 HTML 呈現來源提醒文字', () => {
  render(<EquipmentImportReview batch={batchWithHtmlReminder} />);
  expect(screen.getByText('校驗即將到期')).toBeInTheDocument();
  expect(document.querySelector('span.danger')).toBeNull();
});
```

另測：

- 狀態與校驗狀態篩選。
- 沒有 `msa.manage` 時不顯示新增、匯入、狀態變更按鈕。
- 解決「遊校」映射後才能確認。
- 逾期設備顯示阻擋原因。
- 設備明細顯示校驗、補正點、狀態事件與 CQI-9 來源連結。
- draft 校驗由 `msa.approve` 使用者核准後才成為正式資格證據。
- 小螢幕表格有可讀的卡片替代。

### Step 2：執行測試，確認頁面尚不存在

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MeasurementEquipmentPage.test.tsx src/components/msa/EquipmentImportReview.test.tsx
```

Expected: collection FAIL。

### Step 3：實作設備頁

頁面結構：

```tsx
<main className="msa-page" aria-labelledby="equipment-title">
  <header className="msa-page__header">
    <div>
      <p className="msa-eyebrow">量測資源治理</p>
      <h1 id="equipment-title">設備清單</h1>
    </div>
    {hasPermission('msa.manage') && <EquipmentActions />}
  </header>
  <EquipmentRiskSummary />
  <EquipmentFilters />
<EquipmentTable />
</main>
```

狀態不得只靠顏色；badge 同時顯示圖示與文字。高風險排序為：

1. 校驗失敗。
2. 校驗逾期。
3. 待確認。
4. 維修。
5. 30 日內到期。

點選設備開啟 `EquipmentDetailDrawer`，分頁顯示：

- 主檔與量測能力。
- 校驗版本、證書附件及補正點。
- 狀態事件。
- Recorder／Thermocouple 等專用來源連結。
- 引用本設備的 MSA 研究。

### Step 4：實作受控匯入檢閱

三階段 stepper：

1. 上傳與解析。
2. 差異與問題處理。
3. 確認與稽核結果。

問題表每列顯示：

- 原始列號。
- 設備編號。
- 原始值。
- 正規化值。
- 問題碼與中文說明。
- 明確處置選項。

不得提供「全部忽略」。所有 blocking issue 必須逐列解決或拒絕。

### Step 5：加入子路由與工作台連結

`App.tsx`：

```tsx
<Route path="/msa/equipment" element={<MeasurementEquipmentPage />} />
<Route path="/msa/imports" element={<MsaImportHistoryPage />} />
```

工作台加入可存取卡片：

```tsx
<Link to="/msa/equipment">設備清單</Link>
<Link to="/msa/imports">設備匯入紀錄</Link>
```

### Step 6：執行測試並提交

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MeasurementEquipmentPage.test.tsx src/components/msa/EquipmentImportReview.test.tsx src/App.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/pages/msa/MeasurementEquipmentPage.tsx src_frontend/src/pages/msa/MsaImportHistoryPage.tsx src_frontend/src/components/msa/EquipmentStatusBadge.tsx src_frontend/src/components/msa/EquipmentDetailDrawer.tsx src_frontend/src/components/msa/EquipmentCalibrationForm.tsx src_frontend/src/components/msa/EquipmentImportReview.tsx src_frontend/src/App.tsx src_frontend/src/pages/msa/MsaWorkspacePage.tsx src_frontend/src/pages/msa/MeasurementEquipmentPage.test.tsx src_frontend/src/components/msa/EquipmentImportReview.test.tsx
git commit -m "功能：完成量測設備與匯入頁面"
```

---

## Task 9：完成準則管理頁與基礎整合驗證

**Files:**

- Create: `src_frontend/src/pages/msa/MsaCriteriaPage.tsx`
- Create: `src_frontend/src/components/msa/CriteriaVersionTimeline.tsx`
- Modify: `src_frontend/src/pages/msa/MsaWorkspacePage.tsx`
- Modify: `src_frontend/src/App.tsx`
- Test: `src_frontend/src/pages/msa/MsaCriteriaPage.test.tsx`

### Step 1：先寫版本歷程與權限失敗測試

```typescript
it('清楚顯示目前版本、前版與方法依據', async () => {
  render(<MsaCriteriaPage />);
  expect(await screen.findByText('一般計量型')).toBeInTheDocument();
  expect(screen.getByText('目前版本 v2')).toBeInTheDocument();
  expect(screen.getByText('MSA 第四版')).toBeInTheDocument();
});


it('核准時送出畫面看到的 expected_status', async () => {
  const user = userEvent.setup();
  render(<MsaCriteriaPage />);
  await user.click(await screen.findByRole('button', { name: '核准 v2' }));
  await user.type(screen.getByLabelText('核准理由'), '符合公司與顧客要求');
  await user.click(screen.getByRole('button', { name: '確認核准' }));
  expect(approveMock).toHaveBeenCalledWith({
    versionId: 2,
    expected_status: 'draft',
    reason: '符合公司與顧客要求',
  });
});
```

### Step 2：執行測試，確認頁面尚不存在

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MsaCriteriaPage.test.tsx
```

Expected: collection FAIL。

### Step 3：實作準則頁

頁面必須：

- 以人類可讀名稱顯示 GRR、ndc、Kappa、有效性、誤收與誤拒門檻。
- 明確區分 draft、目前 approved 與歷史 approved。
- 顯示適用顧客、產品族、品質特性、研究類型與生效日。
- 只有 `msa.manage` 可建立版本；只有 `msa.approve` 可核准。
- 核准動作要求理由與 expected status。
- 不提供編輯已核准版本的入口。

路由：

```tsx
<Route path="/msa/criteria" element={<MsaCriteriaPage />} />
```

### Step 4：執行前後端基礎整合驗證

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_permissions.py backend\tests\test_services\test_msa_models.py backend\tests\test_services\test_msa_equipment.py backend\tests\test_services\test_msa_import.py backend\tests\test_services\test_msa_criteria.py backend\tests\test_msa_routes.py -q
cd src_frontend
npx vitest run src/hooks/useMsaEquipment.test.tsx src/hooks/useMsaImports.test.tsx src/hooks/useMsaCriteria.test.tsx src/pages/msa/MeasurementEquipmentPage.test.tsx src/components/msa/EquipmentImportReview.test.tsx src/pages/msa/MsaCriteriaPage.test.tsx src/components/Sidebar.test.tsx src/App.test.tsx
npm run lint
npm run build
```

Expected: 全部 PASS；lint 無錯誤；build 完成。

### Step 5：提交

```powershell
git add src_frontend/src/pages/msa/MsaCriteriaPage.tsx src_frontend/src/components/msa/CriteriaVersionTimeline.tsx src_frontend/src/pages/msa/MsaWorkspacePage.tsx src_frontend/src/App.tsx src_frontend/src/pages/msa/MsaCriteriaPage.test.tsx
git commit -m "功能：完成 MSA 準則管理頁"
```

---

## 本計畫完成條件

- 四層 MSA 權限可在角色管理頁配置並由後端強制執行。
- 設備、校驗、狀態事件、匯入批次與準則版本均有資料庫限制及稽核軌跡。
- CSV 預覽不寫正式設備，確認流程可重現 108 筆來源檔的盤點統計。
- `pending_review`、維修、報廢、校驗失敗、校驗逾期設備不可通過正式研究資格檢查。
- 已核准校驗與準則版本不可更新／刪除。
- 設備、匯入、準則頁有權限、錯誤、空狀態、loading 與響應式測試。
- 所有窄測試、lint、build 通過。
