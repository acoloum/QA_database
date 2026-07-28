# 量測設備與校正詳細數據登錄 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立獨立的量測設備與校正模組，支援受控模板、多次原始讀值、後端自動判定、標準器快照、附件門檻、職責分離及 MSA 資格引用。

**Architecture:** 沿用既有 `量測設備` 與 `設備校驗紀錄` 主體，以 Migration 49 增加模板、實際校正點、原始讀值及參考標準器快照。校正計算與工作流集中在獨立服務層，前端移至 `/measurement-equipment` 與 `/calibrations`，MSA 只透過資格介面讀取核准證據。

**Tech Stack:** Flask 3.1、SQLAlchemy、PostgreSQL 16／SQLite 測試、React 19、TypeScript、TanStack React Query、Vitest、Testing Library。

## Global Constraints

- 所有使用者介面、程式碼註解、文件及 commit 訊息使用繁體中文。
- 後端測試及正式指令使用 `C:\QC_Database\venv\Scripts\python.exe`。
- 路由保持薄層；校正規則、資格判定、計算及工作流一律在 service layer。
- 正式數值由後端以 `Decimal` 計算；前端不得重算或覆寫正式結果。
- 不可使用近似資料、假欄位或由舊補正點反推不存在的原始讀值。
- 每項正式程式碼前必須先建立會因功能缺失而失敗的測試，並實際確認 RED。
- 已送審或核准的模板、原始讀值、計算、快照及稽核證據不可原地修改或刪除。
- 所有 mutation 先拒絕停用帳號，並維持穩定的 `code/message/details` 錯誤 envelope。
- 所有狀態更新使用 `expected_version` 或列鎖，禁止舊頁面覆蓋新資料。
- 不得修改或提交工作區現有的 `src_frontend/vite.config.ts`、`.omo/`、`.opencode/package-lock.json`。
- Migration 實作時先確認編號 49 尚未占用；若已占用，僅調整檔名與部署編號，不改變本計畫資料契約。
- 首版不做儀器直連、OCR、任意公式引擎或新校正 PDF／Excel 報告產生器。

---

## File Structure

### Backend

- `backend/models.py`：ORM 模型、關聯、check constraints 與 ORM 不可變事件。
- `backend/migration/49_create_calibration_detail_registration.sql`：正式 PostgreSQL schema、舊資料標記、索引與 trigger。
- `backend/services/calibration_errors.py`：校正模組穩定錯誤類型。
- `backend/routes/calibration_adapters.py`：認證、獨立權限與錯誤 envelope。
- `backend/services/calibration_calculation.py`：純 `Decimal` 計算與判定，不存取資料庫。
- `backend/services/calibration_template_service.py`：模板及版本工作流。
- `backend/services/calibration_service.py`：校正草稿、讀值、資格、附件、送審及核准。
- `backend/services/calibration_eligibility.py`：設備目前校正資格與 MSA 相容介面。
- `backend/services/measurement_equipment_service.py`：通用設備主檔相容匯出。
- `backend/routes/calibration_templates.py`：模板 API。
- `backend/routes/calibrations.py`：校正紀錄 API。
- `backend/routes/measurement_equipment.py`：切換至 `calibration.*` 權限及設備服務。
- `backend/scripts/smoke_calibration.py`：正式服務 authenticated smoke 與非正式資料清理。

### Frontend

- `src_frontend/src/types/calibration.ts`：獨立校正契約。
- `src_frontend/src/hooks/useCalibrationTemplates.ts`：模板 query／mutation。
- `src_frontend/src/hooks/useCalibrations.ts`：校正 query／mutation、blob 下載及精確 cache invalidation。
- `src_frontend/src/components/CalibrationViewRoute.tsx`：獨立 `calibration.view` 路由防線。
- `src_frontend/src/pages/equipment/MeasurementEquipmentPage.tsx`：從 MSA 搬出的設備頁。
- `src_frontend/src/pages/calibration/CalibrationTemplateListPage.tsx`：模板清單。
- `src_frontend/src/pages/calibration/CalibrationTemplateEditorPage.tsx`：模板版本編輯與核准。
- `src_frontend/src/pages/calibration/CalibrationEntryWizardPage.tsx`：四步登錄精靈。
- `src_frontend/src/pages/calibration/CalibrationWorkQueuePage.tsx`：校正工作佇列。
- `src_frontend/src/pages/calibration/CalibrationDetailPage.tsx`：分層證據及工作流。
- `src_frontend/src/components/calibration/*`：矩陣、條件、摘要、檢閱及工作流元件。
- `src_frontend/src/App.tsx`：新路由及舊路由導向。
- `src_frontend/src/components/Sidebar.tsx`：獨立導覽入口。

---

### Task 1: 建立校正詳細資料模型與 Migration 49

**Files:**
- Create: `backend/migration/49_create_calibration_detail_registration.sql`
- Modify: `backend/models.py`
- Create: `backend/tests/test_services/test_calibration_models.py`
- Create: `backend/tests/test_services/test_calibration_migration.py`

**Interfaces:**
- Produces: `CalibrationTemplate`、`CalibrationTemplateVersion`、`CalibrationTemplatePoint`、`EquipmentCalibrationPoint`、`EquipmentCalibrationReading`、`CalibrationReferenceSnapshot`。
- Extends: `EquipmentCalibrationRecord` with `template_version_id`, `data_level`, expanded `status`, `row_version`, `template_snapshot`, `environment_conditions`, `calculation_summary`, `calculation_version`, `data_hash`, `reference_standard_equipment_id`, `submitted_by`, `submitted_at`, `rejection_reason`, `void_reason`, `successor_id`。
- Consumed by: Tasks 2–7 and 13。

- [ ] **Step 1: 寫入會失敗的 ORM 約束測試**

```python
from backend.models import (
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    EquipmentCalibrationPoint,
    EquipmentCalibrationReading,
)


def test_template_point_number_is_unique_within_version(db_session):
    template = CalibrationTemplate(
        template_code="CAL-CALIPER",
        name="游標卡尺",
        equipment_type="游標卡尺",
    )
    db_session.add(template)
    db_session.flush()
    version = CalibrationTemplateVersion(
        template_id=template.id,
        version_no=1,
        procedure_code="WI-CAL-001",
        procedure_name="游標卡尺內校",
        default_repetitions=3,
        environment_requirements={"temperature": {"required": True}},
        allow_limited_use=True,
        status="draft",
    )
    db_session.add(version)
    db_session.flush()
    for code in ("P01", "P01"):
        db_session.add(CalibrationTemplatePoint(
            template_version_id=version.id,
            point_order=1,
            point_code=code,
            measurement_mode="外徑",
            nominal_value="10",
            unit="mm",
            reference_input_mode="certified_value",
            required_repetitions=3,
            error_lower_limit="-0.02",
            error_upper_limit="0.02",
            evaluation_basis="all_readings",
            repeatability_rule="range",
            repeatability_limit="0.01",
            qualification_scope_code="OD-0-150",
            required=True,
        ))

    with pytest.raises(IntegrityError):
        db_session.commit()
```

另加入：

- `required_repetitions > 0`。
- 下限不得大於上限。
- `range/stddev` 必須有非負重複性上限。
- `summary_legacy` 舊紀錄可沒有模板版本。
- `detailed` 紀錄必須有模板版本及模板快照。
- 同一實際校正點的試驗序號唯一。
- `submitted/approved` 原始讀值不可更新或刪除。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_models.py -q
```

Expected: collection FAIL，因新模型尚不存在。

- [ ] **Step 3: 實作 ORM 模型與關聯**

在 `backend/models.py` 以現有中文資料表命名慣例加入：

```python
class CalibrationTemplate(db.Model):
    __tablename__ = "校正模板"

    id = db.Column("識別碼", db.Integer, primary_key=True)
    template_code = db.Column("模板代碼", db.String(80), nullable=False, unique=True)
    name = db.Column("名稱", db.String(160), nullable=False)
    equipment_type = db.Column("適用設備類型", db.String(80), nullable=False)
    description = db.Column("說明", db.Text)
    status = db.Column("狀態", db.String(20), nullable=False, default="active")
    current_approved_version_id = db.Column("目前核准版本ID", db.Integer)


class CalibrationTemplateVersion(db.Model):
    __tablename__ = "校正模板版本"

    id = db.Column("識別碼", db.Integer, primary_key=True)
    template_id = db.Column(
        "模板ID", db.Integer, db.ForeignKey("校正模板.識別碼"), nullable=False
    )
    version_no = db.Column("版本號", db.Integer, nullable=False)
    procedure_code = db.Column("程序代碼", db.String(80), nullable=False)
    procedure_name = db.Column("程序名稱", db.String(160), nullable=False)
    procedure_description = db.Column("程序說明", db.Text)
    default_repetitions = db.Column("預設重複次數", db.Integer, nullable=False)
    environment_requirements = db.Column(
        "環境要求", JsonType, nullable=False, default=dict
    )
    allow_limited_use = db.Column(
        "允許限制使用", db.Boolean, nullable=False, default=False
    )
    status = db.Column("狀態", db.String(20), nullable=False, default="draft")
    row_version = db.Column("資料版本", db.Integer, nullable=False, default=1)
```

其他欄位依設計規格逐一建立，所有 relationship 指定清楚 `back_populates`，實際校正點使用 cascade 保存讀值，但不使用會繞過不可變防線的 delete-orphan。

- [ ] **Step 4: 實作 Migration 49**

Migration 必須：

```sql
BEGIN;

CREATE TABLE "校正模板" (...);
CREATE TABLE "校正模板版本" (...);
CREATE TABLE "校正模板校正點" (...);
CREATE TABLE "設備校正點" (...);
CREATE TABLE "設備校正原始讀值" (...);
CREATE TABLE "校正參考標準器快照" (...);

ALTER TABLE "設備校驗紀錄"
    ADD COLUMN "模板版本ID" INTEGER REFERENCES "校正模板版本"("識別碼"),
    ADD COLUMN "資料等級" VARCHAR(30) NOT NULL DEFAULT 'summary_legacy',
    ADD COLUMN "資料版本" INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN "模板快照" JSONB,
    ADD COLUMN "環境條件" JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN "計算摘要" JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN "計算版本" VARCHAR(40),
    ADD COLUMN "資料雜湊" VARCHAR(64),
    ADD COLUMN "參考標準設備ID" INTEGER REFERENCES "量測設備"("識別碼"),
    ADD COLUMN "送審者ID" INTEGER REFERENCES "使用者"("識別碼"),
    ADD COLUMN "送審時間" TIMESTAMPTZ,
    ADD COLUMN "退回理由" TEXT,
    ADD COLUMN "作廢理由" TEXT,
    ADD COLUMN "後繼紀錄ID" INTEGER REFERENCES "設備校驗紀錄"("識別碼");

UPDATE "設備校驗紀錄"
SET "資料等級" = 'summary_legacy',
    "狀態" = CASE
        WHEN "狀態" = 'approved' THEN 'approved'
        ELSE 'draft'
    END;

COMMIT;
```

補齊規格內所有 check constraint、unique constraint、索引及 PostgreSQL JSONB 型別。Migration 測試讀取 SQL，確認沒有 `DROP TABLE`、舊資料更新不生成詳細讀值，且所有新表與保護 trigger 名稱存在。

- [ ] **Step 5: 執行模型與 migration 測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_models.py backend\tests\test_services\test_calibration_migration.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
git add backend/models.py backend/migration/49_create_calibration_detail_registration.sql backend/tests/test_services/test_calibration_models.py backend/tests/test_services/test_calibration_migration.py
git commit -m "資料庫：建立校正詳細數據與模板模型"
```

---

### Task 2: 建立純 Decimal 校正計算引擎

**Files:**
- Create: `backend/services/calibration_calculation.py`
- Create: `backend/tests/test_services/test_calibration_calculation.py`

**Interfaces:**
- Produces:

```python
def calculate_point(
    rule: CalibrationPointRule,
    readings: Sequence[CalibrationReadingInput],
) -> CalibrationPointCalculation: ...

def calculate_calibration(
    points: Sequence[CalibrationPointCalculation],
    *,
    allow_limited_use: bool,
) -> CalibrationCalculation: ...
```

- `CalibrationPointRule` includes reference mode, limits, evaluation basis, repeatability rule, scope and uncertainty requirement.
- Consumed by: `CalibrationService.save_readings()` and `CalibrationService.validate()`。

- [ ] **Step 1: 寫入精確數值與判定失敗測試**

```python
def test_certified_value_calculates_decimal_evidence():
    result = calculate_point(
        rule(
            reference_input_mode="certified_value",
            reference_value=Decimal("10.000"),
            error_lower_limit=Decimal("-0.05"),
            error_upper_limit=Decimal("0.05"),
            evaluation_basis="all_readings",
            repeatability_rule="range",
            repeatability_limit=Decimal("0.05"),
        ),
        [
            reading("10.020"),
            reading("10.040"),
            reading("10.000"),
        ],
    )

    assert result.errors == (
        Decimal("0.020"), Decimal("0.040"), Decimal("0.000")
    )
    assert result.mean_error == Decimal("0.020")
    assert result.mean_correction == Decimal("-0.020")
    assert result.error_range == Decimal("0.040")
    assert result.sample_stddev == Decimal("0.020")
    assert result.result == "pass"
```

另測：

- `paired_reading` 每筆使用自身標準器讀值。
- `all_readings` 任一筆超差即 fail。
- `mean_error` 以平均器差判定。
- 單邊允差及包含端點。
- `range`、`stddev` 限制。
- 缺值為 pending。
- 不確定度必填。
- 至少一個資格範圍完全合格時自動 `limited_use`。
- NaN、Infinity、無限精度、超大指數回 `CALIBRATION_NUMERIC_FAILURE`。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_calculation.py -q
```

Expected: collection FAIL，因 `calibration_calculation` 尚不存在。

- [ ] **Step 3: 實作不可變輸入／輸出型別**

```python
@dataclass(frozen=True)
class CalibrationReadingInput:
    trial_no: int
    indicated_value: Decimal | None
    standard_reading: Decimal | None = None


@dataclass(frozen=True)
class CalibrationPointCalculation:
    point_code: str
    scope_code: str
    readings: tuple[CalibrationReadingCalculation, ...]
    mean_error: Decimal | None
    mean_correction: Decimal | None
    minimum_error: Decimal | None
    maximum_error: Decimal | None
    error_range: Decimal | None
    sample_stddev: Decimal | None
    result: Literal["pending", "pass", "fail"]
    blockers: tuple[str, ...]
```

所有數值入口先用 `Decimal(str(value))`，再檢查 `is_finite()`、調整後指數及最大有效位數。正式引擎版本固定為 `CALCULATION_VERSION = "CALIBRATION_1_0"`。

- [ ] **Step 4: 實作計算及整體判定**

使用：

```python
error = indicated_value - effective_reference
correction = -error
mean_error = sum(errors, Decimal("0")) / Decimal(len(errors))
error_range = max(errors) - min(errors)
sample_stddev = (
    sum((value - mean_error) ** 2 for value in errors)
    / Decimal(len(errors) - 1)
).sqrt()
```

`calculate_calibration()` 依 `scope_code` 分組，只有模板允許且至少一組全部通過、至少一組失敗時回 `limited_use`；沒有完整合格範圍時回 `fail`。

- [ ] **Step 5: 執行計算測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_calculation.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
git add backend/services/calibration_calculation.py backend/tests/test_services/test_calibration_calculation.py
git commit -m "功能：建立校正數值計算與自動判定引擎"
```

---

### Task 3: 建立獨立錯誤、權限與認證防線

**Files:**
- Create: `backend/services/calibration_errors.py`
- Create: `backend/routes/calibration_adapters.py`
- Modify: `backend/seeds/seed_roles.py`
- Create: `backend/tests/test_services/test_calibration_permissions.py`
- Modify: `backend/tests/test_msa_routes.py`

**Interfaces:**
- Produces: `CalibrationServiceError`、`CalibrationNotFound`、`CalibrationForbidden`、`CalibrationConflict`、`CalibrationValidationError`。
- Produces decorators: `calibration_auth_required`、`require_calibration_permission(permission)`、`handle_calibration_errors`。
- Role permissions exactly match the approved spec.

- [ ] **Step 1: 寫入停用帳號及獨立權限測試**

```python
def test_inactive_user_is_rejected_before_calibration_manage_mutation(
    client, inactive_calibration_manager_token
):
    response = client.post(
        "/api/calibration-templates",
        headers={"Authorization": f"Bearer {inactive_calibration_manager_token}"},
        json={"template_code": "CAL-001", "name": "卡尺", "equipment_type": "卡尺"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "CALIBRATION_USER_INACTIVE"
    assert CalibrationTemplate.query.count() == 0
```

另測：

- `msa.manage` 沒有 `calibration.manage` 時回 403。
- service 自我核准的 `CALIBRATION_SELF_APPROVAL_FORBIDDEN` 不被 adapter 蓋成一般權限錯誤。
- admin 仍須通過停用帳號檢查。
- seed roles 對應 inspector、qa_supervisor、qc_manager、admin。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_permissions.py -q
```

Expected: FAIL，因獨立 adapter 與權限尚不存在。

- [ ] **Step 3: 實作錯誤類型與 adapter**

`calibration_errors.py`：

```python
class CalibrationServiceError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class CalibrationNotFound(CalibrationServiceError):
    status_code = 404


class CalibrationForbidden(CalibrationServiceError):
    status_code = 403


class CalibrationConflict(CalibrationServiceError):
    status_code = 409


class CalibrationValidationError(CalibrationServiceError):
    status_code = 422
```

`calibration_adapters.py` 依現有 MSA adapter 的 inactive JWT、服務層錯誤保留及穩定 envelope 邏輯建立，但錯誤碼全部改為 `CALIBRATION_*`。

- [ ] **Step 4: 更新角色 seed**

精確加入：

```python
# inspector
"calibration.view": True,
"calibration.execute": True,

# qa_supervisor
"calibration.view": True,
"calibration.execute": True,
"calibration.manage": True,

# qc_manager
"calibration.view": True,
"calibration.approve": True,

# admin
"calibration.view": True,
"calibration.execute": True,
"calibration.manage": True,
"calibration.approve": True,
```

- [ ] **Step 5: 執行權限及既有 MSA adapter 回歸測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_permissions.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
git add backend/services/calibration_errors.py backend/routes/calibration_adapters.py backend/seeds/seed_roles.py backend/tests/test_services/test_calibration_permissions.py backend/tests/test_msa_routes.py
git commit -m "安全：建立獨立校正權限與錯誤契約"
```

---

### Task 4: 實作受控校正模板服務與 API

**Files:**
- Create: `backend/services/calibration_template_service.py`
- Create: `backend/routes/calibration_templates.py`
- Modify: `backend/app.py`
- Create: `backend/tests/test_services/test_calibration_templates.py`
- Create: `backend/tests/test_calibration_routes.py`

**Interfaces:**
- Produces:

```python
class CalibrationTemplateService:
    @staticmethod
    def list(params) -> dict: ...
    @staticmethod
    def get(template_id: int) -> dict: ...
    @staticmethod
    def create(payload: dict, actor_id: int) -> dict: ...
    @staticmethod
    def create_version(template_id: int, payload: dict, actor_id: int) -> dict: ...
    @staticmethod
    def update_version(version_id: int, payload: dict, actor_id: int) -> dict: ...
    @staticmethod
    def submit_version(version_id: int, payload: dict, actor_id: int) -> dict: ...
    @staticmethod
    def approve_version(version_id: int, payload: dict, actor_id: int) -> dict: ...
    @staticmethod
    def reject_version(version_id: int, payload: dict, actor_id: int) -> dict: ...
```

- Consumed by: template routes and frontend Task 10。

- [ ] **Step 1: 寫入模板工作流測試**

```python
def test_approver_cannot_approve_own_template_version(db_session, manager):
    version = create_submitted_template_version(
        db_session,
        created_by=manager.id,
        submitted_by=manager.id,
    )

    with pytest.raises(CalibrationForbidden) as error:
        CalibrationTemplateService.approve_version(
            version.id,
            {
                "expected_version": version.row_version,
                "reason": "內容符合內校程序",
            },
            manager.id,
        )

    assert error.value.code == "CALIBRATION_SELF_APPROVAL_FORBIDDEN"
```

另測：

- 版本校正點代碼、順序及資格範圍完整性。
- `range/stddev` 限制欄位配對。
- 送審時至少一個必要校正點。
- 核准時列鎖與 `expected_version`。
- 新版核准後舊版 `superseded` 且模板只指向新版。
- 核准後 update/delete 被 ORM 及 PostgreSQL trigger 阻擋。
- 巨大 page/page_size 回 422，不造成 500。

- [ ] **Step 2: 執行服務測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_templates.py -q
```

Expected: collection FAIL，因 service 尚不存在。

- [ ] **Step 3: 實作模板正規化與狀態轉換**

建立白名單：

```python
VERSION_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"approved", "rejected"},
    "approved": {"superseded"},
    "rejected": set(),
    "superseded": set(),
}

REFERENCE_INPUT_MODES = {"certified_value", "paired_reading"}
EVALUATION_BASES = {"all_readings", "mean_error"}
REPEATABILITY_RULES = {"none", "range", "stddev"}
```

所有版本 mutation：

```python
version = db.session.execute(
    db.select(CalibrationTemplateVersion)
    .where(CalibrationTemplateVersion.id == version_id)
    .with_for_update()
).scalar_one_or_none()
```

核對 `row_version` 後才更新，成功更新時加一。核准與模板目前版本更新在同一交易。

- [ ] **Step 4: 實作模板 routes**

使用 `calibration_auth_required`、`require_calibration_permission()` 及 `handle_calibration_errors`，註冊：

```python
calibration_template_bp = Blueprint("calibration_templates", __name__)

@calibration_template_bp.get("/api/calibration-templates")
@require_calibration_permission("calibration.view")
...

@calibration_template_bp.post(
    "/api/calibration-template-versions/<int:version_id>/approve"
)
@require_calibration_permission("calibration.approve")
...
```

在 `backend/app.py` 註冊 blueprint。

- [ ] **Step 5: 寫入並執行 API 契約測試**

測試 `201/200/403/404/409/422`、穩定 envelope、JSON 非物件、停用 JWT 與零寫入。

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_templates.py backend\tests\test_calibration_routes.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
git add backend/services/calibration_template_service.py backend/routes/calibration_templates.py backend/app.py backend/tests/test_services/test_calibration_templates.py backend/tests/test_calibration_routes.py
git commit -m "功能：建立受控校正模板版本工作流"
```

---

### Task 5: 建立校正草稿、模板實例及參考標準器資格

**Files:**
- Create: `backend/services/calibration_service.py`
- Create: `backend/services/calibration_eligibility.py`
- Create: `backend/routes/calibrations.py`
- Modify: `backend/app.py`
- Create: `backend/tests/test_services/test_calibration_reference_standards.py`
- Create: `backend/tests/test_services/test_calibration_drafts.py`
- Modify: `backend/tests/test_calibration_routes.py`

**Interfaces:**
- Produces:

```python
class CalibrationEligibilityService:
    @staticmethod
    def assert_reference_standard_usable(
        equipment_id: int, *, on_date: date
    ) -> ReferenceEligibility: ...

    @staticmethod
    def equipment_qualification(
        equipment_id: int, *, on_date: date, measurement_mode: str | None = None
    ) -> EquipmentQualification: ...


class CalibrationService:
    @staticmethod
    def list(params, actor_id: int) -> dict: ...
    @staticmethod
    def get(calibration_id: int) -> dict: ...
    @staticmethod
    def create(payload: dict, actor_id: int) -> dict: ...
    @staticmethod
    def update(calibration_id: int, payload: dict, actor_id: int) -> dict: ...
```

- `create()` locks an approved template version, stores its snapshot, and creates `EquipmentCalibrationPoint` rows.

- [ ] **Step 1: 寫入內校標準器及草稿實例測試**

```python
def test_internal_draft_instantiates_points_from_approved_template(
    db_session, executor, approved_template_version, valid_reference_standard
):
    result = CalibrationService.create(
        {
            "equipment_id": create_equipment(db_session, "EQ-UUT").id,
            "template_version_id": approved_template_version.id,
            "calibration_type": "internal",
            "calibration_date": "2026-07-28",
            "reference_standard_equipment_id": valid_reference_standard.id,
        },
        executor.id,
    )

    assert result["data_level"] == "detailed"
    assert result["status"] == "draft"
    assert [point["point_code"] for point in result["points"]] == ["P01", "P02"]
    assert all(len(point["readings"]) == 3 for point in result["points"])
```

另測：

- 模板未核准、設備類型不符、受校設備停用時拒絕。
- 參考標準器未標記、維修、校正失敗、逾期或缺少到期日時拒絕。
- 受校設備不能同時作為自己的標準器。
- 外校草稿可先沒有附件，但保留 `certificate_attachment_id=None`。
- 環境條件只接受模板宣告的鍵；必填溫度／濕度缺漏或超出模板範圍時回精確欄位錯誤。
- `expected_version` 衝突回 `CALIBRATION_VERSION_CONFLICT`。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_reference_standards.py backend\tests\test_services\test_calibration_drafts.py -q
```

Expected: collection FAIL，因新 service 尚不存在。

- [ ] **Step 3: 實作資格服務**

`assert_reference_standard_usable()` 必須同時驗證：

```python
equipment.is_reference_standard is True
equipment.status == "active"
latest_approved_calibration.result in {"pass", "limited_use"}
latest_approved_calibration.next_due_date is not None
latest_approved_calibration.next_due_date >= on_date
```

缺少任何一項回 `CALIBRATION_REFERENCE_INVALID`，`details` 含設備 ID、設備編號及阻擋原因。

草稿條件更新使用模板 snapshot 的 `environment_requirements` 驗證 JSON；未知鍵回 `CALIBRATION_FIELD_INVALID`，必要鍵缺少時保持草稿可保存，但 `/validate` 回 `CALIBRATION_DATA_INCOMPLETE` 及對應 `field`。

- [ ] **Step 4: 實作草稿建立與模板實例化**

建立實際校正點時完整複製模板規則：

```python
for template_point in template_version.points:
    point = EquipmentCalibrationPoint(
        calibration_record=record,
        template_point_id=template_point.id,
        point_order=template_point.point_order,
        point_code=template_point.point_code,
        measurement_mode=template_point.measurement_mode,
        nominal_value=template_point.nominal_value,
        reference_value=template_point.nominal_value,
        unit=template_point.unit,
        reference_input_mode=template_point.reference_input_mode,
        required_repetitions=template_point.required_repetitions,
        error_lower_limit=template_point.error_lower_limit,
        error_upper_limit=template_point.error_upper_limit,
        evaluation_basis=template_point.evaluation_basis,
        repeatability_rule=template_point.repeatability_rule,
        repeatability_limit=template_point.repeatability_limit,
        qualification_scope_code=template_point.qualification_scope_code,
        required=template_point.required,
    )
    point.readings = [
        EquipmentCalibrationReading(trial_no=trial_no)
        for trial_no in range(1, template_point.required_repetitions + 1)
    ]
```

模板 snapshot 使用排序後 JSON 及穩定 key 名稱。

- [ ] **Step 5: 實作 list/get/create/update routes**

註冊 `/api/calibrations` 及 `/api/calibrations/:id`，建立草稿使用 `calibration.execute`，一般管理欄位更新使用 `calibration.manage`，讀取使用 `calibration.view`。

- [ ] **Step 6: 執行草稿及 route 測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_reference_standards.py backend\tests\test_services\test_calibration_drafts.py backend\tests\test_calibration_routes.py -q
```

Expected: PASS。

- [ ] **Step 7: Commit**

```powershell
git add backend/services/calibration_service.py backend/services/calibration_eligibility.py backend/routes/calibrations.py backend/app.py backend/tests/test_services/test_calibration_reference_standards.py backend/tests/test_services/test_calibration_drafts.py backend/tests/test_calibration_routes.py
git commit -m "功能：建立校正草稿與參考標準器資格"
```

---

### Task 6: 儲存原始讀值並由後端重算正式證據

**Files:**
- Modify: `backend/services/calibration_service.py`
- Modify: `backend/routes/calibrations.py`
- Create: `backend/tests/test_services/test_calibration_readings.py`
- Modify: `backend/tests/test_calibration_routes.py`

**Interfaces:**
- Produces:

```python
CalibrationService.save_readings(
    calibration_id: int,
    payload: dict,
    actor_id: int,
) -> dict

CalibrationService.validate(
    calibration_id: int,
    payload: dict,
    actor_id: int,
) -> dict
```

- `PUT /api/calibrations/:id/readings` accepts the complete changed matrix and is transaction atomic.

- [ ] **Step 1: 寫入讀值原子性與重新計算測試**

```python
def test_save_readings_recalculates_and_persists_backend_evidence(
    db_session, detailed_draft, executor
):
    result = CalibrationService.save_readings(
        detailed_draft.id,
        {
            "expected_version": 1,
            "points": [{
                "point_id": detailed_draft.points[0].id,
                "reference_value": "10.000",
                "expanded_uncertainty": "0.003",
                "coverage_factor": "2",
                "readings": [
                    {"trial_no": 1, "indicated_value": "10.010"},
                    {"trial_no": 2, "indicated_value": "10.020"},
                    {"trial_no": 3, "indicated_value": "10.000"},
                ],
            }],
        },
        executor.id,
    )

    point = result["points"][0]
    assert point["mean_error"] == "0.010"
    assert point["mean_correction"] == "-0.010"
    assert point["result"] == "pass"
    assert result["result"] == "pass"
    assert result["status"] == "in_progress"
    assert result["row_version"] == 2
```

另測：

- paired readings。
- 任一未知 point ID、重複 trial、缺少必要讀值、非法數字時整批零寫入。
- `expected_version` 衝突。
- submitted/approved/rejected 版本不得保存讀值。
- input user ID 與時間被保存。
- payload 大小及 point/readings 數量上限。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_readings.py -q
```

Expected: FAIL，因 `save_readings()` 尚不存在。

- [ ] **Step 3: 實作批次正規化與純引擎轉接**

每次請求：

1. 列鎖校正紀錄。
2. 驗證 `expected_version` 及可編輯狀態。
3. 先在記憶體正規化全部 points/readings。
4. 呼叫 `calculate_point()`／`calculate_calibration()`。
5. 全部成功後才更新 ORM rows、摘要、結果、計算版本及 row version。
6. 以排序後的模板、環境、標準器選擇、原始讀值及計算摘要建立 SHA-256。

資料雜湊：

```python
canonical = json.dumps(
    payload,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
data_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: 實作 `/readings` 及 `/validate` routes**

`/readings` 使用 `calibration.execute`；`/validate` 使用 `calibration.manage`。錯誤 `details` 必須帶 `step="readings"`、`point_code`、`trial_no` 或 `field`。

- [ ] **Step 5: 執行讀值與 API 測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_calculation.py backend\tests\test_services\test_calibration_readings.py backend\tests\test_calibration_routes.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
git add backend/services/calibration_service.py backend/routes/calibrations.py backend/tests/test_services/test_calibration_readings.py backend/tests/test_calibration_routes.py
git commit -m "功能：保存校正原始讀值並產生正式計算證據"
```

---

### Task 7: 完成送審、附件、標準器快照與核准工作流

**Files:**
- Modify: `backend/services/calibration_service.py`
- Modify: `backend/services/attachment_service.py`
- Modify: `backend/routes/calibrations.py`
- Modify: `backend/migration/49_create_calibration_detail_registration.sql`
- Modify: `backend/models.py`
- Create: `backend/tests/test_services/test_calibration_workflow.py`
- Create: `backend/tests/test_services/test_calibration_attachments.py`
- Modify: `backend/tests/test_calibration_routes.py`

**Interfaces:**
- Produces:

```python
CalibrationService.submit(calibration_id, payload, actor_id) -> dict
CalibrationService.approve(calibration_id, payload, actor_id) -> dict
CalibrationService.reject(calibration_id, payload, actor_id) -> dict
CalibrationService.void(calibration_id, payload, actor_id) -> dict
```

- Attachment service accepts `entity_type="equipment_calibration"` and validates MIME by calibration type.

- [ ] **Step 1: 寫入送審與職責分離測試**

```python
def test_external_calibration_cannot_submit_without_certificate(
    db_session, ready_external_calibration, manager
):
    with pytest.raises(CalibrationValidationError) as error:
        CalibrationService.submit(
            ready_external_calibration.id,
            {
                "expected_version": ready_external_calibration.row_version,
                "reason": "送交外校證書審查",
            },
            manager.id,
        )

    assert error.value.code == "CALIBRATION_CERTIFICATE_REQUIRED"
    assert ready_external_calibration.status == "ready_for_submission"
```

另測：

- 外校附件屬於其他設備／校正草稿時拒絕。
- 內校送審時重新驗證標準器並保存 snapshot。
- 標準器在草稿期間逾期時零寫入。
- 建立者、任何讀值輸入者或送審者不可核准。
- 核准競爭恰好一個成功。
- 退回保存 submitted 證據並建立 successor draft。
- 核准後 update/delete 被 ORM 與 PostgreSQL trigger 阻擋。
- void reason 必填。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_workflow.py backend\tests\test_services\test_calibration_attachments.py -q
```

Expected: FAIL，因工作流方法尚不存在。

- [ ] **Step 3: 實作送審交易**

同一交易內：

```python
record = _lock_record(calibration_id)
_require_version(record, payload["expected_version"])
_assert_ready_for_submission(record)
_assert_attachment_policy(record)
snapshot = _build_reference_snapshot(record)
_recalculate_and_compare_saved_evidence(record)
record.status = "submitted"
record.submitted_by = actor_id
record.submitted_at = utc_now()
record.row_version += 1
db.session.add(snapshot)
db.session.commit()
```

`_recalculate_and_compare_saved_evidence()` 必須使用資料庫原始讀值重算，與保存摘要及 hash 不符時回 `CALIBRATION_DATA_CHANGED`。

- [ ] **Step 4: 實作核准、退回、作廢及不可變防線**

核准前：

```python
participants = {
    record.created_by,
    record.submitted_by,
    *(reading.entered_by for point in record.points for reading in point.readings),
}
if actor_id in participants:
    raise CalibrationForbidden(
        "CALIBRATION_SELF_APPROVAL_FORBIDDEN",
        "建立、輸入或送審人員不得核准自己的校正紀錄",
    )
```

Migration trigger 對 `submitted`、`approved` 的模板快照、原始讀值、計算摘要、hash 及標準器快照 UPDATE/DELETE 一律 `RAISE EXCEPTION`；只允許明確的工作流欄位轉換。

- [ ] **Step 5: 擴充附件服務**

允許 entity types：

```python
CALIBRATION_ATTACHMENT_TYPES = {
    "external": {
        "application/pdf",
        "image/jpeg",
        "image/png",
    },
    "internal": {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
}
```

保留現有檔名清理、大小限制、路徑安全與補償刪除。

- [ ] **Step 6: 執行工作流、PostgreSQL trigger 及 API 測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_calibration_workflow.py backend\tests\test_services\test_calibration_attachments.py backend\tests\test_calibration_routes.py -q
```

另在可用的 PostgreSQL 測試資料庫執行 migration integration tests，Expected: PASS。

- [ ] **Step 7: Commit**

```powershell
git add backend/services/calibration_service.py backend/services/attachment_service.py backend/routes/calibrations.py backend/migration/49_create_calibration_detail_registration.sql backend/models.py backend/tests/test_services/test_calibration_workflow.py backend/tests/test_services/test_calibration_attachments.py backend/tests/test_calibration_routes.py
git commit -m "功能：完成校正送審核准與不可變證據工作流"
```

---

### Task 8: 建立前端校正契約、hooks 與路由權限

**Files:**
- Create: `src_frontend/src/types/calibration.ts`
- Create: `src_frontend/src/hooks/useCalibrationTemplates.ts`
- Create: `src_frontend/src/hooks/useCalibrationTemplates.test.tsx`
- Create: `src_frontend/src/hooks/useCalibrations.ts`
- Create: `src_frontend/src/hooks/useCalibrations.test.tsx`
- Create: `src_frontend/src/components/CalibrationViewRoute.tsx`
- Create: `src_frontend/src/components/CalibrationViewRoute.test.tsx`

**Interfaces:**
- Produces `calibrationKeys`, template hooks, calibration hooks and protected route.
- `CalibrationViewRoute` renders `<Outlet />` when authenticated and authorized, so it can protect the complete calibration route subtree.
- All mutations preserve backend `ApiError.status/code/details/field/message`.
- Consumed by Tasks 9–12。

- [ ] **Step 1: 寫入 query key、payload 與權限 RED 測試**

```tsx
it('批次儲存讀值時保留 expected_version 並只失效受影響校正快取', async () => {
  vi.mocked(api.put).mockResolvedValue({
    data: { data: { id: 41, row_version: 3, result: 'pass' } },
  });
  const queryClient = new QueryClient();
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
  const { result } = renderHook(() => useSaveCalibrationReadings(), {
    wrapper: createWrapper(queryClient),
  });

  await act(async () => {
    await result.current.mutateAsync({
      calibrationId: 41,
      expected_version: 2,
      points: [],
    });
  });

  expect(api.put).toHaveBeenCalledWith('/calibrations/41/readings', {
    expected_version: 2,
    points: [],
  });
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ['calibration', 'records', 'detail', 41],
  });
});
```

另測：

- template list/detail keys 不互相污染。
- list predicate invalidation 不波及其他 detail。
- 沒有 `calibration.view` 時 route 導向首頁。
- admin 仍由既有 `hasPermission` 通過。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
Set-Location src_frontend
npx vitest run src/hooks/useCalibrationTemplates.test.tsx src/hooks/useCalibrations.test.tsx src/components/CalibrationViewRoute.test.tsx
```

Expected: collection FAIL，因檔案尚不存在。

- [ ] **Step 3: 建立精確 TypeScript 契約**

`types/calibration.ts` 必須定義：

```ts
export type CalibrationWorkflowStatus =
  | 'draft'
  | 'in_progress'
  | 'ready_for_submission'
  | 'submitted'
  | 'rejected'
  | 'approved'
  | 'superseded'
  | 'voided';

export interface SaveCalibrationReadingsInput {
  calibrationId: number;
  expected_version: number;
  points: Array<{
    point_id: number;
    reference_value?: string | null;
    expanded_uncertainty?: string | null;
    coverage_factor?: string | null;
    readings: Array<{
      trial_no: number;
      standard_reading?: string | null;
      indicated_value?: string | null;
    }>;
  }>;
}
```

所有正式 Decimal 以字串型別傳輸，避免 JS float 改變證據。

- [ ] **Step 4: 實作 hooks 與路由防線**

使用：

```ts
export const calibrationKeys = {
  all: ['calibration'] as const,
  templateLists: () => ['calibration', 'templates', 'list'] as const,
  template: (id: number) => ['calibration', 'templates', 'detail', id] as const,
  recordLists: () => ['calibration', 'records', 'list'] as const,
  record: (id: number) => ['calibration', 'records', 'detail', id] as const,
};
```

`CalibrationViewRoute` 與現有 `MsaViewRoute` 行為一致，但檢查 `calibration.view`。

```tsx
export default function CalibrationViewRoute() {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();
  if (isLoading) return <div role="status">載入中…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return hasPermission('calibration.view')
    ? <Outlet />
    : <Navigate to="/" replace />;
}
```

- [ ] **Step 5: 執行 hooks 與 route 測試**

Run:

```powershell
npx vitest run src/hooks/useCalibrationTemplates.test.tsx src/hooks/useCalibrations.test.tsx src/components/CalibrationViewRoute.test.tsx
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
Set-Location ..
git add src_frontend/src/types/calibration.ts src_frontend/src/hooks/useCalibrationTemplates.ts src_frontend/src/hooks/useCalibrationTemplates.test.tsx src_frontend/src/hooks/useCalibrations.ts src_frontend/src/hooks/useCalibrations.test.tsx src_frontend/src/components/CalibrationViewRoute.tsx src_frontend/src/components/CalibrationViewRoute.test.tsx
git commit -m "前端：建立校正資料契約與獨立權限防線"
```

---

### Task 9: 搬遷設備頁與建立獨立導覽

**Files:**
- Move: `src_frontend/src/pages/msa/MeasurementEquipmentPage.tsx` → `src_frontend/src/pages/equipment/MeasurementEquipmentPage.tsx`
- Move: `src_frontend/src/pages/msa/MeasurementEquipmentPage.test.tsx` → `src_frontend/src/pages/equipment/MeasurementEquipmentPage.test.tsx`
- Move: `src_frontend/src/pages/msa/msaEquipment.css` → `src_frontend/src/pages/equipment/measurementEquipment.css`
- Modify: `src_frontend/src/components/msa/EquipmentDetailDrawer.tsx`
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/App.test.tsx`
- Modify: `src_frontend/src/components/Sidebar.tsx`
- Modify: `src_frontend/src/components/Sidebar.test.tsx`
- Modify: `src_frontend/src/pages/msa/MsaWorkspacePage.tsx`

**Interfaces:**
- Produces `/measurement-equipment` and `/msa/equipment` redirect.
- Equipment read/manage controls use `calibration.view/manage`。
- Legacy calibration display remains read-only and labelled `舊版摘要資料`。

- [ ] **Step 1: 寫入新導覽及舊路由導向測試**

```tsx
it('舊 MSA 設備入口導向獨立設備模組', async () => {
  renderAppAt('/msa/equipment', {
    permissions: { 'calibration.view': true },
  });

  expect(await screen.findByRole('heading', { name: '設備清單' })).toBeInTheDocument();
  expect(window.location.pathname).toBe('/measurement-equipment');
});
```

另測：

- 側邊欄有「量測設備」與「校正管理」獨立項目。
- 只有 MSA 權限時不顯示校正管理入口。
- 設備管理控制改用 `calibration.manage`。
- 舊摘要紀錄顯示明確標籤且不顯示虛構原始讀值。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
Set-Location src_frontend
npx vitest run src/App.test.tsx src/components/Sidebar.test.tsx src/pages/msa/MeasurementEquipmentPage.test.tsx
```

Expected: FAIL，因新路由及權限尚未建立。

- [ ] **Step 3: 搬移頁面並更新權限**

更新 import、CSS、測試路徑及：

```tsx
const canManage = hasPermission('calibration.manage');
```

將舊抽屜中的「建立校驗草稿」表單移除，改為：

```tsx
<Link
  className="msa-button msa-button--primary"
  to={`/measurement-equipment/${equipment.id}/calibrations/new`}
>
  建立詳細校正
</Link>
```

既有校驗摘要及附件下載保留。

- [ ] **Step 4: 註冊路由與側邊欄**

`App.tsx`：

```tsx
<Route element={<CalibrationViewRoute />}>
  <Route element={<MainLayout />}>
    <Route path="/measurement-equipment" element={<MeasurementEquipmentPage />} />
  </Route>
</Route>
<Route path="/msa/equipment" element={<Navigate to="/measurement-equipment" replace />} />
```

側邊欄新增 `permission: 'calibration.view'` 的「量測設備」及「校正管理」。

- [ ] **Step 5: 執行設備及導覽測試**

Run:

```powershell
npx vitest run src/App.test.tsx src/components/Sidebar.test.tsx src/pages/equipment/MeasurementEquipmentPage.test.tsx
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
Set-Location ..
git add src_frontend/src/pages/equipment src_frontend/src/components/msa/EquipmentDetailDrawer.tsx src_frontend/src/App.tsx src_frontend/src/App.test.tsx src_frontend/src/components/Sidebar.tsx src_frontend/src/components/Sidebar.test.tsx src_frontend/src/pages/msa/MsaWorkspacePage.tsx
git commit -m "前端：將量測設備與校正入口移出 MSA"
```

---

### Task 10: 建立校正模板清單與受控版本編輯器

**Files:**
- Create: `src_frontend/src/pages/calibration/CalibrationTemplateListPage.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationTemplateListPage.test.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationTemplateEditorPage.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationTemplateEditorPage.test.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationTemplatePointEditor.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationTemplateVersionTimeline.tsx`
- Create: `src_frontend/src/pages/calibration/calibration.css`
- Modify: `src_frontend/src/App.tsx`

**Interfaces:**
- Produces template list, point grid, preview, submit, approve, reject and successor version UI.
- Uses Task 8 hooks only; no direct `api` calls in pages.

- [ ] **Step 1: 寫入模板編輯及核准 UI RED 測試**

```tsx
it('建立校正點時要求完整允差與重複性規則', async () => {
  const user = userEvent.setup();
  render(<CalibrationTemplateEditorPage />);

  await user.click(await screen.findByRole('button', { name: '新增校正點' }));
  await user.type(screen.getByLabelText('校正點代碼'), 'P01');
  await user.selectOptions(screen.getByLabelText('重複性規則'), 'range');
  await user.click(screen.getByRole('button', { name: '儲存草稿' }));

  expect(screen.getByRole('alert')).toHaveTextContent('極差上限為必填');
  expect(updateVersionMock).not.toHaveBeenCalled();
});
```

另測：

- 核准版本唯讀。
- 新版從核准版本複製並要求修訂理由。
- 沒有 `calibration.manage` 隱藏編輯／送審。
- 沒有 `calibration.approve` 隱藏核准／退回。
- 核准理由必填及自我核准後端錯誤顯示。
- point grid 的 label、caption、鍵盤焦點。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
Set-Location src_frontend
npx vitest run src/pages/calibration/CalibrationTemplateListPage.test.tsx src/pages/calibration/CalibrationTemplateEditorPage.test.tsx
```

Expected: collection FAIL。

- [ ] **Step 3: 實作模板表單模型與 point editor**

本地草稿型別：

```ts
interface TemplatePointDraft {
  point_code: string;
  point_order: number;
  measurement_mode: string;
  nominal_value: string;
  unit: string;
  reference_input_mode: 'certified_value' | 'paired_reading';
  required_repetitions: string;
  error_lower_limit: string;
  error_upper_limit: string;
  evaluation_basis: 'all_readings' | 'mean_error';
  repeatability_rule: 'none' | 'range' | 'stddev';
  repeatability_limit: string;
  qualification_scope_code: string;
  uncertainty_required: boolean;
  required: boolean;
}
```

送出前由純函式驗證並轉成 API payload；空字串不得轉成 `0`。

- [ ] **Step 4: 實作清單、版本時間軸及工作流按鈕**

頁面狀態與按鈕完全由 server state 及權限決定。`409/422` 使用 `ApiError.details` 定位欄位或顯示版本衝突。

- [ ] **Step 5: 註冊模板路由並執行測試**

Run:

```powershell
npx vitest run src/pages/calibration/CalibrationTemplateListPage.test.tsx src/pages/calibration/CalibrationTemplateEditorPage.test.tsx src/App.test.tsx
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
Set-Location ..
git add src_frontend/src/pages/calibration src_frontend/src/components/calibration/CalibrationTemplatePointEditor.tsx src_frontend/src/components/calibration/CalibrationTemplateVersionTimeline.tsx src_frontend/src/App.tsx
git commit -m "前端：建立受控校正模板管理頁面"
```

---

### Task 11: 建立四步校正詳細數據登錄精靈

**Files:**
- Create: `src_frontend/src/pages/calibration/CalibrationEntryWizardPage.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationEntryWizardPage.test.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationStepper.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationConditionForm.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationReadingMatrix.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationReadingMatrix.test.tsx`
- Create: `src_frontend/src/components/calibration/calibrationMatrixPaste.ts`
- Create: `src_frontend/src/components/calibration/calibrationMatrixPaste.test.ts`
- Create: `src_frontend/src/components/calibration/CalibrationEvidenceReview.tsx`
- Modify: `src_frontend/src/App.tsx`

**Interfaces:**
- `CalibrationReadingMatrix` emits string payloads only.
- `parseCalibrationMatrixPaste(text, rows, columns)` is pure and rejects dimension mismatch atomically.
- Wizard persists each step through Task 8 hooks.

- [ ] **Step 1: 寫入矩陣貼上與鍵盤 RED 測試**

```tsx
it('Excel 貼上維度不符時不部分覆寫既有讀值', async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();
  render(
    <CalibrationReadingMatrix
      points={[pointWithThreeTrials]}
      values={{ 'P01:1': '10.001', 'P01:2': '10.002', 'P01:3': '10.003' }}
      onChange={onChange}
    />,
  );

  const firstCell = screen.getByLabelText('P01 試驗 1 受校件器示值');
  await user.click(firstCell);
  fireEvent.paste(firstCell, {
    clipboardData: { getData: () => '11.1\t11.2\n12.1\t12.2' },
  });

  expect(screen.getByRole('alert')).toHaveTextContent('貼上資料為 2 列 2 欄');
  expect(onChange).not.toHaveBeenCalled();
});
```

另測：

- Tab、Shift+Tab、方向鍵、Enter。
- paired mode 顯示標準器及受校件兩欄。
- certified mode 只顯示參考值及受校件讀值。
- Decimal 字串不先轉 number。
- 行動版逐點卡片仍具完整 label。

- [ ] **Step 2: 寫入四步精靈 RED 測試**

測試：

- 設備與模板選擇。
- 內校必須選標準器。
- 外校必須填機構及證書資訊。
- 外校使用既有 `useUploadAttachment()` 上傳 `entity_type="equipment_calibration"`、`entity_id=calibrationId`、`purpose="cert"`，成功後把附件 ID 寫回草稿。
- 環境必填欄位由模板產生。
- 儲存後顯示後端計算，不在前端自行運算。
- blockers 可連回對應步驟及校正點。
- 未保存變更離開提示。

- [ ] **Step 3: 執行測試並確認 RED**

Run:

```powershell
Set-Location src_frontend
npx vitest run src/components/calibration/CalibrationReadingMatrix.test.tsx src/components/calibration/calibrationMatrixPaste.test.ts src/pages/calibration/CalibrationEntryWizardPage.test.tsx
```

Expected: collection FAIL。

- [ ] **Step 4: 實作純貼上解析器與矩陣**

```ts
export const parseCalibrationMatrixPaste = (
  text: string,
  expectedRows: number,
  expectedColumns: number,
): string[][] => {
  const matrix = text
    .replace(/\r\n/g, '\n')
    .split('\n')
    .filter((row, index, rows) => !(index === rows.length - 1 && row === ''))
    .map((row) => row.split('\t').map((cell) => cell.trim()));

  if (
    matrix.length !== expectedRows
    || matrix.some((row) => row.length !== expectedColumns)
  ) {
    throw new CalibrationMatrixPasteError(matrix.length, matrix[0]?.length ?? 0);
  }
  return matrix;
};
```

矩陣用實際 `<table>`、caption、th scope，錯誤訊息以 `aria-describedby` 連到格子。

- [ ] **Step 5: 實作精靈及 server draft 流程**

步驟：

1. `POST /calibrations` 建立草稿。
2. `PATCH /calibrations/:id` 保存條件。
3. 外校證書透過共用附件 API 上傳並將附件 ID 綁定草稿。
4. `PUT /calibrations/:id/readings` 保存完整矩陣。
5. `POST /calibrations/:id/validate` 取得 blockers。
6. 送審只由檢閱步驟觸發。

正式結果只顯示 mutation 回傳的 `result/calculation_summary`。

- [ ] **Step 6: 註冊路由並執行測試**

Run:

```powershell
npx vitest run src/components/calibration/CalibrationReadingMatrix.test.tsx src/components/calibration/calibrationMatrixPaste.test.ts src/pages/calibration/CalibrationEntryWizardPage.test.tsx src/App.test.tsx
```

Expected: PASS。

- [ ] **Step 7: Commit**

```powershell
Set-Location ..
git add src_frontend/src/pages/calibration/CalibrationEntryWizardPage.tsx src_frontend/src/pages/calibration/CalibrationEntryWizardPage.test.tsx src_frontend/src/components/calibration src_frontend/src/App.tsx
git commit -m "前端：建立校正詳細原始數據登錄精靈"
```

---

### Task 12: 建立校正工作佇列、詳情與核准頁

**Files:**
- Create: `src_frontend/src/pages/calibration/CalibrationWorkQueuePage.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationWorkQueuePage.test.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationDetailPage.tsx`
- Create: `src_frontend/src/pages/calibration/CalibrationDetailPage.test.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationPointSummary.tsx`
- Create: `src_frontend/src/components/calibration/CalibrationWorkflowBar.tsx`
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/components/Sidebar.tsx`

**Interfaces:**
- Work queue consumes paginated list with risk sort.
- Detail page renders saved evidence layers and workflow actions.
- Approval requires five explicit confirmations and a non-blank reason.

- [ ] **Step 1: 寫入工作佇列排序與詳情證據 RED 測試**

```tsx
it('核准前必須確認五層證據並填寫理由', async () => {
  const user = userEvent.setup();
  render(<CalibrationDetailPage />);

  await screen.findByRole('heading', { name: '校正紀錄 CAL-2026-0041' });
  await user.type(screen.getByLabelText('核准理由'), '計算與追溯證據均已核對');

  expect(screen.getByRole('button', { name: '核准校正' })).toBeDisabled();

  for (const label of [
    '已核對原始讀值',
    '已核對計算結果',
    '已核對標準器資格',
    '已核對證書附件',
    '已核對模板版本',
  ]) {
    await user.click(screen.getByLabelText(label));
  }

  expect(screen.getByRole('button', { name: '核准校正' })).toBeEnabled();
});
```

另測：

- 工作佇列高風險優先。
- 篩選參數直接交給後端。
- 詳情依判定、摘要、讀值、快照、附件、簽核、版本順序呈現。
- legacy 紀錄只有摘要層並標示限制。
- `409/422/403` 保留中文訊息及 details。
- 核准、退回、作廢按鈕依權限與狀態顯示。
- 行動版讀值改為逐點卡片。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
Set-Location src_frontend
npx vitest run src/pages/calibration/CalibrationWorkQueuePage.test.tsx src/pages/calibration/CalibrationDetailPage.test.tsx
```

Expected: collection FAIL。

- [ ] **Step 3: 實作風險佇列與分層證據**

工作佇列風險順序：

```ts
const WORK_QUEUE_ORDER = [
  'submitted',
  'rejected',
  'fail',
  'limited_use',
  'ready_for_submission',
  'in_progress',
  'draft',
] as const;
```

後端回傳 sort 是正式順序，前端不只排序當前頁；上述陣列只用於標籤及測試資料生成。

- [ ] **Step 4: 實作核准／退回／作廢操作**

核准 payload：

```ts
{
  expected_version: calibration.row_version,
  reason: approvalReason.trim(),
  confirmations: {
    raw_readings: true,
    calculations: true,
    reference_standard: true,
    attachments: true,
    template_version: true,
  },
}
```

前端確認項目只改善使用體驗；後端仍獨立執行所有資格及職責分離驗證。

- [ ] **Step 5: 註冊路由並執行測試**

Run:

```powershell
npx vitest run src/pages/calibration/CalibrationWorkQueuePage.test.tsx src/pages/calibration/CalibrationDetailPage.test.tsx src/App.test.tsx src/components/Sidebar.test.tsx
```

Expected: PASS。

- [ ] **Step 6: Commit**

```powershell
Set-Location ..
git add src_frontend/src/pages/calibration/CalibrationWorkQueuePage.tsx src_frontend/src/pages/calibration/CalibrationWorkQueuePage.test.tsx src_frontend/src/pages/calibration/CalibrationDetailPage.tsx src_frontend/src/pages/calibration/CalibrationDetailPage.test.tsx src_frontend/src/components/calibration/CalibrationPointSummary.tsx src_frontend/src/components/calibration/CalibrationWorkflowBar.tsx src_frontend/src/App.tsx src_frontend/src/components/Sidebar.tsx
git commit -m "前端：建立校正工作佇列與分層證據核准頁"
```

---

### Task 13: 切換設備權限並保持 MSA／舊資料相容

**Files:**
- Create: `backend/services/measurement_equipment_service.py`
- Modify: `backend/services/msa_equipment_service.py`
- Modify: `backend/services/calibration_eligibility.py`
- Modify: `backend/routes/measurement_equipment.py`
- Modify: `backend/tests/test_services/test_msa_equipment.py`
- Create: `backend/tests/test_services/test_calibration_legacy_compatibility.py`
- Modify: `src_frontend/src/pages/msa/MsaStudyWizardPage.test.tsx`
- Modify: `src_frontend/src/pages/msa/MsaStudyWizardPage.tsx`

**Interfaces:**
- `MeasurementEquipmentService` owns list/get/create/update/status/import-related equipment operations.
- `MsaEquipmentService.assert_officially_usable()` delegates current qualification to `CalibrationEligibilityService` and keeps existing MSA error codes.
- Legacy summary records remain readable but cannot claim detailed evidence.

- [ ] **Step 1: 寫入 MSA qualification 相容 RED 測試**

```python
def test_msa_uses_new_approved_detailed_calibration_qualification(
    db_session, approved_detailed_calibration
):
    qualification = MsaEquipmentService.assert_officially_usable(
        approved_detailed_calibration.equipment_id,
        on_date=date(2026, 7, 28),
    )

    assert qualification.calibration_record_id == approved_detailed_calibration.id
    assert qualification.data_level == "detailed"
    assert qualification.data_hash == approved_detailed_calibration.data_hash
```

另測：

- 舊 approved/pass 且未逾期紀錄仍可維持歷史相容。
- 新 detailed submitted/rejected/voided 不算核准資格。
- 最新核准 fail 蓋過舊 pass。
- limited use 需 exact measurement mode。
- next due date 缺少仍不得被序列化為 valid。
- measurement equipment endpoints 使用 `calibration.*` 權限。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_equipment.py backend\tests\test_services\test_calibration_legacy_compatibility.py -q
```

Expected: FAIL，因 MSA 尚未委派新資格服務。

- [ ] **Step 3: 抽出設備主檔服務並保留相容匯出**

`msa_equipment_service.py` 保留：

```python
from .measurement_equipment_service import MeasurementEquipmentService

class MsaEquipmentService(MeasurementEquipmentService):
    @staticmethod
    def assert_officially_usable(equipment_id, *, on_date, measurement_mode=None):
        try:
            return CalibrationEligibilityService.equipment_qualification(
                equipment_id,
                on_date=on_date,
                measurement_mode=measurement_mode,
            )
        except CalibrationServiceError as error:
            raise map_calibration_error_to_msa(error) from error
```

映射維持既有 `MSA_EQUIPMENT_*` code，避免研究精靈及既有 API 契約破壞。

- [ ] **Step 4: 切換 equipment routes 權限**

- list/get/import list：`calibration.view`。
- create/update/import confirm/status/link：`calibration.manage`。
- 舊簡易 calibration create/approve endpoints 保留一個相容版本週期，但固定回 `410 CALIBRATION_LEGACY_ENDPOINT_RETIRED`，不得再建立摘要型新紀錄；前端不再呼叫這兩個 endpoint。

- [ ] **Step 5: 更新 MSA 前端證據連結**

MSA 仍顯示校正狀態與阻擋原因；具有 `calibration.view` 時連到 `/calibrations/:id`，否則只顯示資格摘要。

- [ ] **Step 6: 執行相容與前端測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_equipment.py backend\tests\test_services\test_calibration_legacy_compatibility.py backend\tests\test_msa_routes.py -q

Set-Location src_frontend
npx vitest run src/pages/msa/MsaStudyWizardPage.test.tsx src/pages/equipment/MeasurementEquipmentPage.test.tsx
```

Expected: PASS。

- [ ] **Step 7: Commit**

```powershell
Set-Location ..
git add backend/services/measurement_equipment_service.py backend/services/msa_equipment_service.py backend/services/calibration_eligibility.py backend/routes/measurement_equipment.py backend/tests/test_services/test_msa_equipment.py backend/tests/test_services/test_calibration_legacy_compatibility.py src_frontend/src/pages/msa/MsaStudyWizardPage.tsx src_frontend/src/pages/msa/MsaStudyWizardPage.test.tsx
git commit -m "重構：統一設備校正資格並保持 MSA 歷史相容"
```

---

### Task 14: 完整驗證、正式 Migration 與 authenticated smoke

**Files:**
- Create: `backend/scripts/smoke_calibration.py`
- Create: `backend/tests/test_scripts/test_smoke_calibration_contract.py`

**Interfaces:**
- `smoke_calibration.py` accepts `--base-url`, manager/executor/approver credentials and `--keep-data`.
- Script verifies separate actors, template workflow, calculations, attachment gate, immutability and MSA qualification.

- [ ] **Step 1: 寫入 smoke client 契約 RED 測試**

```python
def test_smoke_requires_distinct_executor_and_approver():
    parser = build_parser()

    args = parser.parse_args([
        "--base-url", "http://localhost",
        "--executor-user", "qa",
        "--executor-password", "secret",
        "--approver-user", "qa",
        "--approver-password", "secret",
    ])

    with pytest.raises(SystemExit, match="執行者與核准者必須不同"):
        validate_args(args)
```

另測 endpoint 順序、`expected_version` 傳遞、fail point 不能手動改 pass、外校附件門檻及 cleanup 僅移除非正式測試資料。

- [ ] **Step 2: 執行測試並確認 RED**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_scripts\test_smoke_calibration_contract.py -q
```

Expected: collection FAIL。

- [ ] **Step 3: 實作 smoke 腳本**

腳本依序：

1. 登入 executor、manager、approver。
2. 建立測試設備與有效標準器。
3. 建立及送審模板。
4. 由另一名使用者核准模板。
5. 建立內校詳細草稿。
6. 輸入三次讀值並核對後端精確結果。
7. 送審及核准。
8. 驗證核准後修改回 409/422。
9. 建立超差紀錄，確認結果 fail。
10. 建立外校草稿，確認缺附件被阻擋。
11. 驗證 MSA 設備資格引用核准校正 ID 及 hash。
12. 清理可刪除的草稿；核准測試證據使用專用 smoke 前綴並依不可變政策保留或透過正式 void workflow 處理。

- [ ] **Step 4: 執行全部後端驗證**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: PASS；任何 skip 必須是已知且有理由，不能把校正測試 skip 當成功。

- [ ] **Step 5: 執行全部前端驗證**

Run:

```powershell
Set-Location src_frontend
npm test
npm run lint
npm run build
npm audit
```

Expected:

- tests PASS。
- lint 無 error。
- build PASS。
- audit 結果完整記錄；若有漏洞，不在未評估前宣稱完成。

- [ ] **Step 6: 執行靜態與差異檢查**

Run:

```powershell
Set-Location ..
git diff --check
git status --short
```

確認未納入使用者原有的 `vite.config.ts`、`.omo/`、`.opencode/package-lock.json`。

- [ ] **Step 7: 套用 Migration 49 並重啟實際服務**

先確認資料庫備份、migration 編號及 SQL 目標，再依專案 raw SQL migration 慣例執行：

```powershell
psql -v ON_ERROR_STOP=1 `
  -h $env:DB_HOST `
  -p $env:DB_PORT `
  -U $env:DB_USER `
  -d $env:DB_NAME `
  -f backend\migration\49_create_calibration_detail_registration.sql
```

完成後依 port listener 及 parent chain 定位實際後端程序，重啟載入新 ORM；不得按程序名稱廣泛終止 Node/Python。

- [ ] **Step 8: 執行 authenticated API 與頁面 smoke**

Run:

```powershell
venv\Scripts\python.exe backend\scripts\smoke_calibration.py --base-url http://localhost
```

另以瀏覽器完成：

- 模板建立、送審、核准。
- 四步內校登錄。
- Excel 多格貼上。
- 超差顯示。
- 外校附件阻擋。
- 核准後唯讀。
- MSA 資格連結。
- 桌面與窄螢幕。

只有實際服務已啟動且完成上述流程時，才能稱為 live UI smoke。

- [ ] **Step 9: Commit 最終驗證腳本與必要修正**

```powershell
git add backend/scripts/smoke_calibration.py backend/tests/test_scripts/test_smoke_calibration_contract.py
git commit -m "驗證：新增校正模組正式服務 smoke"
```

- [ ] **Step 10: 依完成分支技能進行交付**

確認所有驗證證據後，使用 `superpowers:verification-before-completion`，再使用 `superpowers:finishing-a-development-branch` 決定合併、推送或保留分支。未經使用者要求不自動 push。
