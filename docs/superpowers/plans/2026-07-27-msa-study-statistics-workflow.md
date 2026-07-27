# MSA 研究、統計與核准核心實作計畫

> **Required subskill:** 執行本計畫時必須使用 `superpowers:test-driven-development`；每一種統計方法都先以手算／固定參考資料建立失敗測試，再寫正式引擎。整份計畫結束前使用 `superpowers:verification-before-completion`。

**Goal:** 建立完整的 MSA 研究生命週期，從研究建立、設備與準則快照、隨機盲測收集，到七類第四版方法的後端統計、不可變結果版本、職責分離核准及再研究要求。

**Architecture:** 研究資料分成可編輯的 `MsaStudy`、凍結後不可變的 `MsaPlanVersion`、append-only `MsaObservation`、不可變 `MsaResultVersion` 與 append-only `MsaWorkflowDecision`。方法選擇由 registry 以穩定 method code/version 路由到純函式統計引擎；service layer 負責交易、查詢、資格、hash、狀態及稽核，route 不放商業邏輯。

**Tech Stack:** Flask 3.1、SQLAlchemy 2、PostgreSQL 16、NumPy 2.4、SciPy 1.17、pytest。

**Global Constraints:**

- 前置依賴：[設備與準則基礎實作計畫](2026-07-27-msa-equipment-criteria-foundation.md) 必須完成。
- 依據已核准規格：[MSA 第四版完整模組設計](../specs/2026-07-27-msa-fourth-edition-module-design.md)。
- 正式研究變差固定採 `6σ`；`5.15σ` 只能存在明確 legacy method version，不能標示為第四版正式結果。
- 所有統計引擎都是純函式；不得自行查資料庫、使用目前時間或改寫輸入。
- 所有結果拒絕 NaN、Infinity、奇異模型、非平衡資料誤套平衡公式。
- 觀測只允許新增後繼紀錄；計畫凍結後、結果建立後、決策建立後不得 UPDATE/DELETE。
- 程式碼備註、錯誤訊息與 commit 訊息使用繁體中文。

---

## Task 1：建立研究、觀測、結果與工作流資料模型

**Files:**

- Create: `backend/migration/46_create_msa_studies.sql`
- Modify: `backend/models.py`
- Test: `backend/tests/test_services/test_msa_models.py`

### Step 1：先寫模型關聯與不可變性失敗測試

```python
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import (
    MsaStudy, MsaStudyEquipment, MsaPlanVersion, MsaPart,
    MsaAppraiser, MsaObservation, MsaResultVersion, MsaWorkflowDecision,
)


def test_study_requires_unique_number(db_session):
    db_session.add(MsaStudy(
        study_no="MSA-2026-0001", study_type="grr_xbar_r",
        measurement_purpose="product_control", characteristic="外徑",
        unit="mm", status="draft",
    ))
    db_session.commit()
    db_session.add(MsaStudy(
        study_no="MSA-2026-0001", study_type="bias",
        measurement_purpose="product_control", characteristic="外徑",
        unit="mm", status="draft",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_observation_correction_is_append_only(db_session, frozen_msa_plan):
    original = MsaObservation(
        plan_version_id=frozen_msa_plan.id,
        part_id=frozen_msa_plan.parts[0].id,
        appraiser_id=frozen_msa_plan.appraisers[0].id,
        trial_no=1,
        requested_order=1,
        actual_entry_order=1,
        numeric_value=Decimal("10.001"),
        source="page_single",
        entered_by_id=1,
        is_effective=True,
    )
    db_session.add(original)
    db_session.commit()
    original.numeric_value = Decimal("11")
    with pytest.raises(ValueError, match="MSA 觀測不可直接修改"):
        db_session.commit()


def test_only_one_effective_observation_per_task(db_session, frozen_msa_plan):
    common = {
        "plan_version_id": frozen_msa_plan.id,
        "part_id": frozen_msa_plan.parts[0].id,
        "appraiser_id": frozen_msa_plan.appraisers[0].id,
        "trial_no": 1,
        "source": "page_single",
        "entered_by_id": 1,
        "is_effective": True,
    }
    db_session.add(MsaObservation(
        **common,
        requested_order=1,
        actual_entry_order=1,
        numeric_value=Decimal("10.001"),
    ))
    db_session.commit()
    db_session.add(MsaObservation(
        **common,
        requested_order=1,
        actual_entry_order=2,
        numeric_value=Decimal("10.002"),
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

### Step 2：執行測試，確認模型尚不存在

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_models.py -q
```

Expected: collection FAIL。

### Step 3：建立遷移

單一交易建立：

- `MSA研究`
- `MSA研究設備`
- `MSA計畫版本`
- `MSA零件`
- `MSA評價人`
- `MSA觀測`
- `MSA觀測匯入批次`
- `MSA結果版本`
- `MSA工作流決策`
- `MSA再研究要求`
- `MSA軟體確效執行`

核心限制：

```sql
ALTER TABLE "MSA研究"
ADD CONSTRAINT ck_msa_study_status CHECK (
    "狀態" IN (
        'draft', 'ready', 'collecting', 'ready_for_analysis',
        'analyzed', 'submitted', 'approved', 'rejected',
        'voided', 'superseded'
    )
);

ALTER TABLE "MSA研究設備"
ADD CONSTRAINT uq_msa_study_equipment_role
UNIQUE ("研究ID", "設備ID", "角色", "量測模式");

CREATE UNIQUE INDEX uq_msa_effective_observation
ON "MSA觀測" ("計畫版本ID", "零件ID", "評價人ID", "試驗次數")
WHERE "是否有效" IS TRUE;

CREATE UNIQUE INDEX uq_msa_one_submitted_result
ON "MSA結果版本" ("研究ID")
WHERE "狀態" = 'submitted';

ALTER TABLE "MSA結果版本"
ADD CONSTRAINT uq_msa_result_revision UNIQUE ("研究ID", "結果版本號");
```

Append-only trigger：

```sql
CREATE OR REPLACE FUNCTION msa_block_immutable_change()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'MSA 不可變證據不得修改或刪除';
END;
$$ LANGUAGE plpgsql;
```

套用規則：

- 凍結後的 `MSA計畫版本`。
- `MSA零件`、`MSA評價人`（所屬計畫凍結後）。
- `MSA觀測` 只允許 correction transaction 將 `是否有效` 由 TRUE 改為 FALSE；其他 UPDATE 與全部 DELETE 阻擋。
- `MSA結果版本` 只允許 workflow service 改變 `狀態`；統計、圖表、hash、snapshot 與全部 DELETE 阻擋。
- 全部 `MSA工作流決策`。
- 全部 `MSA軟體確效執行`。

`MSA研究` 可變欄位限目前狀態、下次到期日、目前 plan/result ID、updated_at/updated_by；其餘正式識別資料在 plan freeze 後不得直接改寫。

### Step 4：建立 SQLAlchemy 模型與 ORM listener

`MsaObservation` 同時支援計量與計數，但以 CHECK 限定只能有一種：

```python
__table_args__ = (
    db.CheckConstraint(
        '("計量讀值" IS NOT NULL AND "計數分類" IS NULL) OR '
        '("計量讀值" IS NULL AND "計數分類" IS NOT NULL)',
        name="ck_msa_observation_one_value",
    ),
)
```

結果必須保存：

```python
class MsaResultVersion(db.Model):
    __tablename__ = "MSA結果版本"

    id = db.Column("識別碼", db.Integer, primary_key=True)
    study_id = db.Column("研究ID", db.Integer, db.ForeignKey("MSA研究.識別碼"), nullable=False)
    plan_version_id = db.Column("計畫版本ID", db.Integer, db.ForeignKey("MSA計畫版本.識別碼"), nullable=False)
    result_version_no = db.Column("結果版本號", db.Integer, nullable=False)
    method_code = db.Column("方法代碼", db.String(80), nullable=False)
    method_version = db.Column("方法版本", db.String(40), nullable=False)
    code_version = db.Column("程式版本", db.String(80), nullable=False)
    data_hash = db.Column("資料雜湊", db.String(64), nullable=False)
    raw_data_summary = db.Column("原始資料摘要", db.JSON, nullable=False)
    applicability_result = db.Column("適用性結果", db.JSON, nullable=False)
    statistics = db.Column("統計結果", db.JSON, nullable=False)
    chart_data = db.Column("圖表資料", db.JSON, nullable=False)
    criteria_snapshot = db.Column("準則快照", db.JSON, nullable=False)
    conclusion = db.Column("結論", db.JSON, nullable=False)
    warnings = db.Column("警告", db.JSON, nullable=False, default=list)
    blockers = db.Column("阻擋條件", db.JSON, nullable=False, default=list)
    status = db.Column("狀態", db.String(30), nullable=False, default="analyzed")
```

### Step 5：執行模型測試與 PostgreSQL smoke

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_models.py -q
psql -U postgres -d qa_database -v ON_ERROR_STOP=1 -f backend/migration/46_create_msa_studies.sql
```

Expected: PASS；SQL COMMIT。

### Step 6：提交

```powershell
git add backend/migration/46_create_msa_studies.sql backend/models.py backend/tests/test_services/test_msa_models.py
git commit -m "資料庫：建立 MSA 研究與不可變證據模型"
```

---

## Task 2：建立研究服務、編號與基礎 API

**Files:**

- Create: `backend/services/msa_study_service.py`
- Modify: `backend/routes/msa.py`
- Test: `backend/tests/test_services/test_msa_workflow.py`
- Modify: `backend/tests/test_msa_routes.py`

### Step 1：先寫建立、更新與分頁失敗測試

```python
def test_create_study_generates_transaction_safe_number(db_session, msa_manager):
    study = MsaStudyService.create({
        "study_type": "grr_xbar_r",
        "measurement_purpose": "product_control",
        "characteristic": "外徑",
        "unit": "mm",
        "lsl": 9.5,
        "usl": 10.5,
        "responsible_user_id": msa_manager.id,
        "primary_executor_id": msa_manager.id,
    }, actor_id=msa_manager.id)

    assert study.study_no.startswith("MSA-2026-")
    assert study.status == "draft"


def test_non_draft_identity_fields_cannot_be_patched(db_session, ready_msa_study, msa_manager):
    with pytest.raises(MsaConflict) as error:
        MsaStudyService.update(
            ready_msa_study.id,
            {"characteristic": "厚度"},
            actor_id=msa_manager.id,
            expected_updated_at=ready_msa_study.updated_at.isoformat(),
        )
    assert error.value.code == "MSA_VERSION_CONFLICT"
```

另測：

- LSL < USL。
- product_control 必須有規格或明確無公差原因。
- page_size 上限 100、sort 白名單。
- expected_updated_at 防止舊畫面覆蓋。
- `msa.view` 只能 GET；`msa.execute` 可建立研究；`msa.manage` 可管理他人研究。

### Step 2：實作研究編號與 CRUD

不得使用 `count()+1`。PostgreSQL 建立 sequence，SQLite 測試以 retry unique collision：

```python
def _next_study_no(now: datetime) -> str:
    year = now.year
    next_value = db.session.execute(
        db.text("SELECT nextval('msa_study_number_seq')")
    ).scalar_one()
    return f"MSA-{year}-{next_value:04d}"
```

本版研究編號採全域遞增 sequence，不逐年歸零；年份只表示建立年度。若未來要逐年歸零，必須另提遷移與並發測試，不在 service 內改用 `count()+1`。

### Step 3：接上路由

```python
@msa_bp.get("/api/msa/studies")
@auth_required
@require_permission("msa.view")
@_handle_msa_errors
def list_msa_studies(current_user):
    return jsonify({"data": MsaStudyService.list(request.args, current_user.id)})


@msa_bp.post("/api/msa/studies")
@auth_required
@require_permission("msa.execute")
@_handle_msa_errors
def create_msa_study(current_user):
    study = MsaStudyService.create(request.get_json() or {}, current_user.id)
    return jsonify({"data": serialize_msa_study(study)}), 201
```

完成 GET detail、PATCH、history。

### Step 4：執行窄測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_workflow.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_study_service.py backend/routes/msa.py backend/tests/test_services/test_msa_workflow.py backend/tests/test_msa_routes.py
git commit -m "功能：建立 MSA 研究基礎服務"
```

---

## Task 3：建立方法契約、版本 registry 與數值安全層

**Files:**

- Modify: `backend/services/msa_contracts.py`
- Create: `backend/services/msa_numeric.py`
- Create: `backend/services/msa_method_registry.py`
- Test: `backend/tests/test_services/test_msa_numeric.py`

### Step 1：先寫有限值、hash 與 registry 失敗測試

```python
import math

import pytest

from backend.services.msa_numeric import canonical_hash, require_finite_tree
from backend.services.msa_method_registry import MsaMethodRegistry


def test_hash_is_stable_across_dictionary_order():
    assert canonical_hash({"b": 2, "a": [1, 3]}) == canonical_hash({"a": [1, 3], "b": 2})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_rejected(value):
    with pytest.raises(MsaNumericError) as error:
        require_finite_tree({"result": value})
    assert error.value.code == "MSA_NUMERIC_FAILURE"


def test_registry_exposes_only_controlled_versions():
    descriptor = MsaMethodRegistry.get("MSA4_GRR_ANOVA_1_0")
    assert descriptor.study_variation_multiplier == 6.0
    assert descriptor.alpha == 0.05
```

### Step 2：建立共同輸入與輸出契約

```python
@dataclass(frozen=True)
class MsaMethodContext:
    method_code: str
    method_version: str
    alpha: float
    study_variation_multiplier: float
    tolerance: float | None
    process_sigma: float | None
    criteria: dict


@dataclass(frozen=True)
class MsaAnalysisOutput:
    applicability: dict
    statistics: dict
    chart_data: dict
    warnings: tuple[dict, ...]
```

### Step 3：建立 canonical hash 與數值檢查

```python
def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
```

`require_finite_tree` 遞迴檢查 dict/list/tuple/NumPy scalar；遇到非有限值拋出 `MSA_NUMERIC_FAILURE` 並提供 JSON path。

### Step 4：註冊受控方法

```python
@dataclass(frozen=True)
class MethodDescriptor:
    code: str
    version: str
    engine: Callable[[list[dict], MsaMethodContext], MsaAnalysisOutput]
    alpha: float
    study_variation_multiplier: float
    minimum_design: dict[str, int]
    supports_unbalanced: bool
    interaction_policy: str


METHODS = {
    "MSA4_GRR_RANGE_1_0": MethodDescriptor(
        "MSA4_GRR_RANGE_1_0", "1.0", analyze_range, 0.05, 6.0,
        {"parts": 5, "appraisers": 2, "trials": 1}, False, "not_applicable",
    ),
    "MSA4_GRR_XBAR_R_1_0": MethodDescriptor(
        "MSA4_GRR_XBAR_R_1_0", "1.0", analyze_xbar_r, 0.05, 6.0,
        {"parts": 2, "appraisers": 2, "trials": 2}, False, "not_applicable",
    ),
    "MSA4_GRR_ANOVA_1_0": MethodDescriptor(
        "MSA4_GRR_ANOVA_1_0", "1.0", analyze_crossed_anova, 0.05, 6.0,
        {"parts": 2, "appraisers": 2, "trials": 2}, False, "reduce_when_p_ge_alpha",
    ),
    "MSA4_BIAS_1_0": MethodDescriptor(
        "MSA4_BIAS_1_0", "1.0", analyze_bias, 0.05, 6.0,
        {"parts": 1, "appraisers": 1, "trials": 10}, False, "not_applicable",
    ),
    "MSA4_LINEARITY_1_0": MethodDescriptor(
        "MSA4_LINEARITY_1_0", "1.0", analyze_linearity, 0.05, 6.0,
        {"parts": 5, "appraisers": 1, "trials": 2}, False, "not_applicable",
    ),
    "MSA4_STABILITY_1_0": MethodDescriptor(
        "MSA4_STABILITY_1_0", "1.0", analyze_stability, 0.05, 6.0,
        {"subgroups": 20, "appraisers": 1, "trials": 1}, False, "not_applicable",
    ),
    "MSA4_ATTRIBUTE_1_0": MethodDescriptor(
        "MSA4_ATTRIBUTE_1_0", "1.0", analyze_attribute, 0.05, 6.0,
        {"parts": 20, "appraisers": 2, "trials": 2}, False, "not_applicable",
    ),
    "MSA4_NONREPEATABLE_1_0": MethodDescriptor(
        "MSA4_NONREPEATABLE_1_0", "1.0", analyze_nonrepeatable, 0.05, 6.0,
        {"parts": 10, "appraisers": 2, "trials": 1}, False, "design_specific",
    ),
}
```

### Step 5：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_numeric.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_contracts.py backend/services/msa_numeric.py backend/services/msa_method_registry.py backend/tests/test_services/test_msa_numeric.py
git commit -m "功能：建立 MSA 方法版本與數值安全層"
```

---

## Task 4：建立研究設計、設備快照、盲碼與凍結流程

**Files:**

- Create: `backend/services/msa_design_service.py`
- Modify: `backend/services/msa_study_service.py`
- Modify: `backend/routes/msa.py`
- Test: `backend/tests/test_services/test_msa_workflow.py`

### Step 1：先寫設計完整性與凍結失敗測試

```python
def test_grr_plan_requires_primary_gauge_parts_appraisers_and_trials(
    db_session, draft_msa_study, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.create_plan(
            draft_msa_study.id,
            {
                "method_code": "MSA4_GRR_XBAR_R_1_0",
                "part_count": 3,
                "appraiser_count": 1,
                "trial_count": 1,
                "equipment": [],
            },
            actor_id=msa_manager.id,
        )
    assert error.value.code == "MSA_DESIGN_INCOMPLETE"


def test_freeze_saves_calibration_criteria_and_random_order_snapshots(
    db_session, complete_draft_plan, msa_manager,
):
    frozen = MsaDesignService.freeze(
        complete_draft_plan.id,
        actor_id=msa_manager.id,
        expected_plan_hash=complete_draft_plan.plan_hash,
    )
    assert frozen.frozen_at is not None
    assert frozen.equipment_snapshot
    assert frozen.criteria_snapshot["version_id"]
    assert len(frozen.randomized_order) == (
        frozen.part_count * frozen.appraiser_count * frozen.trial_count
    )
```

另測：

- 至少一件 `primary_gauge`。
- bias/linearity 需要 reference standard 或可追溯 reference source。
- 設備資格不合格時 freeze 回 422 且不留下半成品。
- 解析度相對公差／製程變差不足時产生明確 blocker/warning。
- 相同 random seed 產生相同順序。
- 盲碼不得暴露真實零件 ID 或參考值。
- 已凍結 plan 再 freeze 回 `MSA_PLAN_ALREADY_FROZEN`。

### Step 2：實作設計矩陣與隨機順序

```python
tasks = [
    {
        "part_id": part.id,
        "appraiser_id": appraiser.id,
        "trial_no": trial_no,
    }
    for trial_no in range(1, trial_count + 1)
    for appraiser in appraisers
    for part in parts
]
random.Random(random_seed).shuffle(tasks)
randomized_order = [
    {**task, "requested_order": index}
    for index, task in enumerate(tasks, start=1)
]
```

不同 appraiser 的畫面可依其 task filter 顯示；正式 snapshot 保存全矩陣。

### Step 3：計畫雜湊與凍結交易

hash 輸入固定為：

```python
hash_input = {
    "method_code": plan.method_code,
    "method_version": descriptor.version,
    "design_type": plan.design_type,
    "parts": serialized_parts,
    "appraisers": serialized_appraisers,
    "randomized_order": randomized_order,
    "equipment_snapshot": equipment_snapshot,
    "criteria_snapshot": criteria_snapshot,
    "sampling_notes": plan.sampling_notes,
    "environment_notes": plan.environment_notes,
}
```

凍結在一個交易中：

1. lock study 與 plan。
2. 重新檢查設備資格。
3. 保存 snapshot/hash/frozen_by/frozen_at。
4. study `draft → ready`。
5. 寫 workflow decision 與 audit log。

### Step 4：接上 plans/freeze/tasks 路由

依規格完成：

- `POST /api/msa/studies/:id/plans`
- `POST /api/msa/plans/:planId/freeze`
- `GET /api/msa/plans/:planId/tasks`

tasks 回應對評價人隱藏：

- 真實零件識別。
- 參考值。
- 其他評價人的讀值。
- 自己先前 trial 的讀值。

### Step 5：執行窄測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_workflow.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_design_service.py backend/services/msa_study_service.py backend/routes/msa.py backend/tests/test_services/test_msa_workflow.py backend/tests/test_msa_routes.py
git commit -m "功能：完成 MSA 研究設計與凍結"
```

---

## Task 5：建立 append-only 觀測、逐筆收集與 Excel 預覽確認

**Files:**

- Create: `backend/services/msa_observation_service.py`
- Create: `backend/services/msa_observation_import_service.py`
- Modify: `backend/routes/msa.py`
- Test: `backend/tests/test_services/test_msa_observations.py`
- Test fixture: `backend/tests/fixtures/msa_observations.xlsx`

### Step 1：先寫收集、修正、順序與匯入失敗測試

```python
def test_appraiser_can_only_enter_assigned_blind_task(db_session, collecting_plan, appraiser_user):
    task = collecting_plan.randomized_order[0]
    observation = MsaObservationService.record(
        collecting_plan.id,
        {
            "task_order": task["requested_order"],
            "numeric_value": "10.004",
            "measured_at": "2026-07-27T09:30:00+08:00",
        },
        actor_id=appraiser_user.id,
    )
    assert observation.source == "page_single"
    assert observation.actual_entry_order == 1


def test_correction_supersedes_without_updating_original(
    db_session, existing_observation, msa_manager,
):
    corrected = MsaObservationService.correct(
        existing_observation.id,
        {"numeric_value": "10.002", "reason": "原紀錄小數點輸入錯誤"},
        actor_id=msa_manager.id,
    )
    db_session.refresh(existing_observation)
    assert existing_observation.is_effective is False
    assert corrected.supersedes_id == existing_observation.id
    assert corrected.is_effective is True


def test_import_preview_reports_excel_cell_for_invalid_value(
    db_session, collecting_plan, msa_manager,
):
    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "msa_observations.xlsx"
    )
    batch = MsaObservationImportService.preview(
        collecting_plan.id,
        fixture,
        msa_manager.id,
    )
    issue = batch.issues[0]
    assert issue["cell"] == "D7"
    assert issue["code"] == "MSA_OBSERVATION_INVALID"
```

### Step 2：實作逐筆與矩陣輸入

- `msa.execute` 只可輸入自己被指派的盲測 task。
- `msa.manage` 可用矩陣補資料，但每筆仍保存真實 actor、source=`page_matrix`。
- 數值使用 Decimal 解析，禁止 locale 模糊格式。
- 計數類別必須屬於 plan.freeze 時保存的 category set。
- 實際順序由資料庫內同 plan 的 next counter 原子取得。

### Step 3：實作修正

在單一交易：

1. lock 目前有效 observation。
2. 驗證 expected observation id。
3. 原紀錄 `is_effective=False`；這是 append-only 規則的唯一允許狀態欄位，由 ORM/trigger whitelist 明確限定。
4. 建立 successor，含 `supersedes_id` 與 correction reason。
5. 若已有 analyzed result，study 回到 `ready_for_analysis`，舊 result 標記 superseded 只能透過新 workflow decision 表達，不 UPDATE 舊 evidence payload。

### Step 4：實作 Excel 預覽／確認

- 只接受 `.xlsx`，最大 5 MB、10,000 列、200 欄。
- `openpyxl.load_workbook(upload_path, read_only=True, data_only=True)`。
- 不接受公式儲存格作為正式讀值。
- 先比對 plan id、plan hash、盲碼、評價人、trial。
- 每個問題回傳 sheet/cell/code/message。
- confirm 使用 batch hash 冪等，所有有效列同一交易寫入。

### Step 5：接上 API 並測試

完成：

- `POST /api/msa/plans/:planId/observations`
- `POST /api/msa/observations/:id/corrections`
- `POST /api/msa/plans/:planId/imports/preview`
- `POST /api/msa/plans/:planId/imports/:batchId/confirm`
- `POST /api/msa/plans/:planId/validate`

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_observations.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

### Step 6：提交

```powershell
git add backend/services/msa_observation_service.py backend/services/msa_observation_import_service.py backend/routes/msa.py backend/tests/test_services/test_msa_observations.py backend/tests/fixtures/msa_observations.xlsx
git commit -m "功能：完成 MSA 盲測資料收集"
```

---

## Task 6：實作極差法與平均值－極差法 GRR

**Files:**

- Create: `backend/services/msa_variable_grr.py`
- Test: `backend/tests/test_services/test_msa_variable_grr.py`
- Test fixture: `backend/tests/fixtures/msa_grr_reference.json`

### Step 1：以固定資料建立失敗測試

fixture 必須保存原始矩陣與獨立計算的期望值，不只保存最終判定：

```python
def test_xbar_r_matches_reference_components(grr_reference):
    output = analyze_xbar_r(grr_reference["observations"], grr_reference["context"])
    stats = output.statistics

    assert stats["ev"] == pytest.approx(grr_reference["expected"]["ev"], rel=1e-6)
    assert stats["av"] == pytest.approx(grr_reference["expected"]["av"], rel=1e-6)
    assert stats["grr"] == pytest.approx(grr_reference["expected"]["grr"], rel=1e-6)
    assert stats["pv"] == pytest.approx(grr_reference["expected"]["pv"], rel=1e-6)
    assert stats["tv"] == pytest.approx(grr_reference["expected"]["tv"], rel=1e-6)
    assert stats["ndc"] == grr_reference["expected"]["ndc"]


def test_xbar_r_rejects_unbalanced_design():
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_xbar_r(unbalanced_observations, context)
    assert error.value.code == "MSA_METHOD_NOT_APPLICABLE"
```

另測零極差、只有一名評價人、缺失 cell、無公差時 `%Tolerance = unavailable`。

### Step 2：實作受控 d2 常數

不要用近似常數散落在函式內：

```python
D2 = {
    2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326,
    6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078,
}
```

若設計超出受控表範圍，回 `MSA_METHOD_NOT_APPLICABLE`，不可外插。

### Step 3：實作 Xbar-R 公式

對平衡 crossed design：

```python
ev_sigma = r_bar / D2[trial_count]
appraiser_range = max(appraiser_means) - min(appraiser_means)
av_raw_variance = (
    (appraiser_range / D2[appraiser_count]) ** 2
    - (ev_sigma ** 2) / (part_count * trial_count)
)
av_variance = max(av_raw_variance, 0.0)
av_sigma = math.sqrt(av_variance)
grr_sigma = math.sqrt(ev_sigma ** 2 + av_sigma ** 2)
pv_sigma = part_mean_range / D2[part_count]
tv_sigma = math.sqrt(grr_sigma ** 2 + pv_sigma ** 2)
ndc = math.floor(1.41 * pv_sigma / grr_sigma) if grr_sigma > 0 else None
```

輸出同時保存 `av_raw_variance`、`av_adjusted_variance` 與 adjustment reason。

百分比：

```python
study_variation = 6.0 * sigma
percent_study_variation = 100.0 * sigma / tv_sigma
percent_tolerance = 100.0 * study_variation / tolerance if tolerance else None
percent_process = (
    100.0 * sigma / process_sigma if process_sigma and process_sigma > 0 else None
)
```

圖表輸出包含每個 part/appraiser mean/range、Xbar/R center/UCL/LCL 與超限點。

### Step 4：實作極差法

極差法只回：

- overall GRR sigma/study variation。
- %Tolerance（若有）。
- 取樣數、常數與適用性限制。
- `detail_components_available=False`。

不得虛構 EV/AV/PV。

### Step 5：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_variable_grr.py -q
```

Expected: PASS，reference 誤差在容許範圍內。

Commit:

```powershell
git add backend/services/msa_variable_grr.py backend/tests/test_services/test_msa_variable_grr.py backend/tests/fixtures/msa_grr_reference.json
git commit -m "功能：實作極差法與平均值極差法 GRR"
```

---

## Task 7：實作交叉型 ANOVA GRR

**Files:**

- Modify: `backend/services/msa_variable_grr.py`
- Test: `backend/tests/test_services/test_msa_variable_grr.py`
- Test fixture: `backend/tests/fixtures/msa_anova_reference.json`

### Step 1：先寫完整 ANOVA table 與變差分量失敗測試

```python
def test_crossed_anova_preserves_full_and_reduced_model_evidence(anova_reference):
    output = analyze_crossed_anova(
        anova_reference["observations"], anova_reference["context"]
    )
    full = output.statistics["anova"]["full_model"]
    assert [row["source"] for row in full["table"]] == [
        "part", "appraiser", "part_appraiser", "repeatability"
    ]
    assert full["table"][0]["ss"] == pytest.approx(
        anova_reference["expected"]["part_ss"], rel=1e-6
    )
    assert "raw_variance_components" in full
    assert "adjusted_variance_components" in full
    assert output.statistics["anova"]["selected_model"] in {"full", "reduced"}
```

另測：

- 非平衡資料明確拒絕。
- error DF=0 拒絕。
- interaction p < alpha 使用 full。
- interaction p >= alpha 依 descriptor 使用 reduced，但保存 full evidence。
- 負 component 保存 raw 後依受控規則歸零。
- SciPy 計算結果為 non-finite 時回 `MSA_NUMERIC_FAILURE`。

### Step 2：實作完整 crossed ANOVA

平衡設計 `p` parts、`o` appraisers、`r` trials：

```python
ss_part = o * r * sum((part_mean - grand_mean) ** 2 for part_mean in part_means)
ss_appraiser = p * r * sum(
    (appraiser_mean - grand_mean) ** 2 for appraiser_mean in appraiser_means
)
ss_interaction = r * sum(
    (
        cell_mean[(part, appraiser)]
        - part_means[part]
        - appraiser_means[appraiser]
        + grand_mean
    ) ** 2
    for part in parts
    for appraiser in appraisers
)
ss_repeatability = sum(
    (value - cell_mean[(part, appraiser)]) ** 2
    for part, appraiser, value in observations
)
```

DF：

```python
df_part = p - 1
df_appraiser = o - 1
df_interaction = (p - 1) * (o - 1)
df_repeatability = p * o * (r - 1)
```

full model component：

```python
var_repeatability = ms_repeatability
var_interaction_raw = (ms_interaction - ms_repeatability) / r
var_appraiser_raw = (ms_appraiser - ms_interaction) / (p * r)
var_part_raw = (ms_part - ms_interaction) / (o * r)
```

F 與 p：

```python
f_part = ms_part / ms_interaction
p_part = scipy.stats.f.sf(f_part, df_part, df_interaction)
f_appraiser = ms_appraiser / ms_interaction
p_appraiser = scipy.stats.f.sf(f_appraiser, df_appraiser, df_interaction)
f_interaction = ms_interaction / ms_repeatability
p_interaction = scipy.stats.f.sf(
    f_interaction, df_interaction, df_repeatability
)
```

reduced model 必須把 interaction SS/DF pool 進 repeatability，再重新計算 part/appraiser denominator 與 component。

### Step 3：計算 GRR、PV、TV、百分比與 ndc

full：

```python
grr_variance = (
    var_repeatability
    + adjusted["appraiser"]
    + adjusted["part_appraiser"]
)
pv_variance = adjusted["part"]
```

所有 sigma、6σ、%StudyVar、%Tolerance、%ProcessVar 與 ndc 走 Task 6 的共用 helper。

### Step 4：執行 reference 測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_variable_grr.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_variable_grr.py backend/tests/test_services/test_msa_variable_grr.py backend/tests/fixtures/msa_anova_reference.json
git commit -m "功能：實作交叉型 ANOVA GRR"
```

---

## Task 8：實作偏倚與線性

**Files:**

- Create: `backend/services/msa_bias_linearity.py`
- Test: `backend/tests/test_services/test_msa_bias_linearity.py`
- Test fixture: `backend/tests/fixtures/msa_bias_linearity_reference.json`

### Step 1：先寫偏倚參考測試

```python
def test_bias_matches_t_test_reference(reference):
    output = analyze_bias(reference["bias"]["readings"], reference["bias"]["context"])
    stats = output.statistics
    assert stats["mean"] == pytest.approx(reference["bias"]["expected"]["mean"])
    assert stats["bias"] == pytest.approx(reference["bias"]["expected"]["bias"])
    assert stats["t_value"] == pytest.approx(reference["bias"]["expected"]["t_value"])
    assert stats["p_value"] == pytest.approx(reference["bias"]["expected"]["p_value"])
    assert stats["confidence_interval"] == pytest.approx(
        reference["bias"]["expected"]["confidence_interval"]
    )
```

另測 n < 2、標準差為 0、沒有可信 reference evidence、CI 包含／不包含 0、超過校驗允許誤差。

### Step 2：實作偏倚

```python
mean_value = float(np.mean(readings))
bias = mean_value - reference_value
repeatability_sd = float(np.std(readings, ddof=1))
standard_error = repeatability_sd / math.sqrt(len(readings))
t_value = bias / standard_error if standard_error > 0 else None
p_value = (
    2 * scipy.stats.t.sf(abs(t_value), df=len(readings) - 1)
    if t_value is not None else None
)
t_critical = scipy.stats.t.ppf(
    1 - context.alpha / 2, df=len(readings) - 1
)
confidence_interval = (
    bias - t_critical * standard_error,
    bias + t_critical * standard_error,
)
```

零標準差且 bias=0 可以回「沒有觀察到偏倚但無法估計 t 檢定」；零標準差且 bias≠0 必須判定明顯偏倚並保存不可估計原因。

### Step 3：先寫線性參考測試

```python
def test_linearity_reports_regression_bands_and_residuals(reference):
    output = analyze_linearity(
        reference["linearity"]["groups"], reference["linearity"]["context"]
    )
    regression = output.statistics["regression"]
    assert regression["slope"] == pytest.approx(
        reference["linearity"]["expected"]["slope"], rel=1e-6
    )
    assert regression["intercept"] == pytest.approx(
        reference["linearity"]["expected"]["intercept"], rel=1e-6
    )
    assert "confidence_band" in output.chart_data
    assert "prediction_band" in output.chart_data
    assert "residuals" in output.chart_data
```

另測 reference level 少於 5、量程覆蓋不足、單看 R² 不可合格、constant x/奇異模型。

### Step 4：實作線性 OLS 與 band

每筆偏倚 `y_i = measured_i - reference_i`，模型 `y = b0 + b1*x`：

```python
result = scipy.stats.linregress(x_values, bias_values)
slope = result.slope
intercept = result.intercept
slope_p_value = result.pvalue
r_squared = result.rvalue ** 2
predicted = intercept + slope * x_grid
```

依殘差 MSE、`Sxx` 計算 mean confidence band 與 individual prediction band；同時輸出：

- 個別偏倚。
- 各 reference level 平均偏倚與 CI。
- zero line。
- slope/intercept 的 estimate、SE、t、p、CI。
- residual vs fitted 與適用性警告。

結論必須同時檢查 slope、各量程 CI 是否穿越 0、校驗容許誤差與殘差；不得使用 R² 單獨判斷。

### Step 5：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_bias_linearity.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_bias_linearity.py backend/tests/test_services/test_msa_bias_linearity.py backend/tests/fixtures/msa_bias_linearity_reference.json
git commit -m "功能：實作 MSA 偏倚與線性分析"
```

---

## Task 9：實作穩定性

**Files:**

- Create: `backend/services/msa_stability.py`
- Test: `backend/tests/test_services/test_msa_stability.py`
- Test fixture: `backend/tests/fixtures/msa_stability_reference.json`

### Step 1：先寫 Xbar-R、Xbar-S 與 I-MR 失敗測試

```python
@pytest.mark.parametrize(
    ("subgroup_size", "expected_chart"),
    [(4, "xbar_r"), (12, "xbar_s"), (1, "i_mr")],
)
def test_stability_selects_controlled_chart(subgroup_size, expected_chart):
    output = analyze_stability(make_stability_series(subgroup_size), context)
    assert output.statistics["chart_type"] == expected_chart


def test_stability_has_no_fake_single_index():
    output = analyze_stability(stable_series, context)
    assert "stability_index" not in output.statistics
    assert output.statistics["stable"] is True
    assert output.statistics["rule_violations"] == []
```

另測時間未排序、間隔遺失、基準件不可追溯、WECO 1–4 規則、phase baseline 不足。

### Step 2：實作 chart 選型與限制

- n=1 → I-MR。
- 2≤n≤10 → Xbar-R。
- n>10 → Xbar-S。
- subgroup size 不一致時，不得套固定常數；回不適用或使用受控 variable-n 方法版本。

重用 SPC 計算純函式時，只能重用數學 helper；不得建立 `SpcStudy` 或把 MSA 穩定性包裝成 SPC 管制界限。

### Step 3：輸出時間證據

```python
statistics = {
    "chart_type": chart_type,
    "baseline_period": {"from": dates[0], "to": dates[-1], "count": len(dates)},
    "stable": len(violations) == 0,
    "rule_violations": violations,
    "missing_intervals": missing_intervals,
}
```

圖表資料保存每期 raw readings、mean/range/sd、CL/UCL/LCL、違規規則與 equipment/status event markers。

### Step 4：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_stability.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_stability.py backend/tests/test_services/test_msa_stability.py backend/tests/fixtures/msa_stability_reference.json
git commit -m "功能：實作 MSA 穩定性分析"
```

---

## Task 10：實作計數型一致性、Kappa 與錯誤率

**Files:**

- Create: `backend/services/msa_attribute.py`
- Test: `backend/tests/test_services/test_msa_attribute.py`
- Test fixture: `backend/tests/fixtures/msa_attribute_reference.json`

### Step 1：先寫二分類與多分類失敗測試

```python
def test_attribute_binary_matches_reference(reference):
    output = analyze_attribute(reference["observations"], reference["context"])
    stats = output.statistics
    assert stats["within_appraiser"]["A"]["agreement"] == pytest.approx(
        reference["expected"]["within_a_agreement"]
    )
    assert stats["against_reference"]["overall"]["kappa"] == pytest.approx(
        reference["expected"]["overall_kappa"], rel=1e-6
    )
    assert stats["effectiveness"] == pytest.approx(reference["expected"]["effectiveness"])
    assert stats["false_accept_rate"] == pytest.approx(reference["expected"]["false_accept"])
    assert stats["false_reject_rate"] == pytest.approx(reference["expected"]["false_reject"])


def test_missing_reference_reports_agreement_not_accuracy():
    output = analyze_attribute(observations_without_reference, context)
    assert output.statistics["accuracy_available"] is False
    assert "effectiveness" not in output.statistics
```

另測：

- 某類別完全未出現造成 Kappa denominator 0。
- 多分類 confusion matrix。
- Kappa CI。
- 邊界灰色區分層結果。
- reference truth 不可信時阻擋「正確辨識」結論。

### Step 2：實作 confusion matrix 與 Cohen/Fleiss Kappa

兩評價序列：

```python
p_o = observed_agreement / total
p_e = sum(
    (row_total[label] / total) * (column_total[label] / total)
    for label in labels
)
kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else None
```

多評價人採明確版本化 Fleiss Kappa；不得把 pairwise average 偽稱為 overall Kappa。CI 以方法 descriptor 指定的 asymptotic 或 bootstrap 方法，保存 seed/replicates。

### Step 3：實作錯誤率

二分類：

```python
false_accept_rate = false_accept / reference_reject_count
false_reject_rate = false_reject / reference_accept_count
effectiveness = correct_decisions / total_decisions
```

分母為 0 時輸出 unavailable 與原因，不回 0。

輸出：

- 每位評價人內一致性。
- 評價人間一致性。
- 相對參考標準一致性與 CI。
- 二／多分類 confusion matrix。
- 灰色區與非灰色區分層。

### Step 4：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_attribute.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_attribute.py backend/tests/test_services/test_msa_attribute.py backend/tests/fixtures/msa_attribute_reference.json
git commit -m "功能：實作 MSA 計數型分析"
```

---

## Task 11：實作不可重複／破壞性研究

**Files:**

- Create: `backend/services/msa_nonrepeatable.py`
- Test: `backend/tests/test_services/test_msa_nonrepeatable.py`
- Test fixture: `backend/tests/fixtures/msa_nonrepeatable_reference.json`

### Step 1：先寫適用性 gate 失敗測試

```python
@pytest.mark.parametrize(
    "missing_confirmation",
    ["sample_homogeneity", "shelf_life", "process_stability", "pairing_assumption"],
)
def test_nonrepeatable_requires_physical_assumptions(missing_confirmation):
    confirmations = {
        "sample_homogeneity": True,
        "shelf_life": True,
        "process_stability": True,
        "pairing_assumption": True,
    }
    confirmations[missing_confirmation] = False
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_nonrepeatable(observations, {**context, "confirmations": confirmations})
    assert error.value.code == "MSA_METHOD_NOT_APPLICABLE"
```

另測四種 design type：

- `split_sample`
- `consecutive_paired`
- `homogeneous_lot`
- `multiple_stations`

### Step 2：建立明確 design dispatcher

```python
ANALYZERS = {
    "split_sample": analyze_split_sample,
    "consecutive_paired": analyze_consecutive_pairs,
    "homogeneous_lot": analyze_homogeneous_lot,
    "multiple_stations": analyze_multiple_stations,
}
```

每種 analyzer 必須：

- 驗證配對／巢狀結構。
- 保存假設與證據。
- 明確輸出可辨識與不可辨識的變差來源。
- 不呼叫 crossed GRR 作為 fallback。

### Step 3：實作配對差與巢狀分量

分割／連續配對至少輸出：

```python
differences = np.asarray(second_values) - np.asarray(first_values)
mean_difference = float(np.mean(differences))
sd_difference = float(np.std(differences, ddof=1))
paired_repeatability_sigma = sd_difference / math.sqrt(2)
```

多試驗台／同質批次採巢狀 ANOVA 時保存完整 DF/SS/MS/原始與調整後 components；非平衡設計若尚無受控 mixed model method version，回不適用。

### Step 4：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_nonrepeatable.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_nonrepeatable.py backend/tests/test_services/test_msa_nonrepeatable.py backend/tests/fixtures/msa_nonrepeatable_reference.json
git commit -m "功能：實作 MSA 不可重複研究"
```

---

## Task 12：整合方法 registry、完整性驗證、分析與結果判定

**Files:**

- Modify: `backend/services/msa_method_registry.py`
- Modify: `backend/services/msa_study_service.py`
- Create: `backend/services/msa_evaluation.py`
- Modify: `backend/routes/msa.py`
- Test: `backend/tests/test_services/test_msa_workflow.py`
- Modify: `backend/tests/test_msa_routes.py`

### Step 1：先寫分析交易與判定失敗測試

```python
def test_analyze_persists_exact_input_hash_and_result_snapshot(
    db_session, complete_grr_plan, msa_manager,
):
    result = MsaStudyService.analyze(
        complete_grr_plan.id,
        actor_id=msa_manager.id,
        expected_plan_hash=complete_grr_plan.plan_hash,
    )
    assert len(result.data_hash) == 64
    assert result.method_code == "MSA4_GRR_XBAR_R_1_0"
    assert result.criteria_snapshot["version_id"]
    assert result.status == "analyzed"


def test_analyze_rolls_back_when_engine_returns_nan(
    db_session, complete_grr_plan, msa_manager, monkeypatch,
):
    monkeypatch.setattr(engine, "analyze", lambda *_: {"statistics": {"grr": float("nan")}})
    with pytest.raises(MsaValidationError) as error:
        MsaStudyService.analyze(complete_grr_plan.id, msa_manager.id, complete_grr_plan.plan_hash)
    assert error.value.code == "MSA_NUMERIC_FAILURE"
    assert MsaResultVersion.query.count() == 0
```

另測：

- 缺測／重複有效觀測阻擋。
- 非平衡設計阻擋或路由到正確受控方法。
- plan hash 改變回 `MSA_DATA_CHANGED`。
- 相同資料可建立新 result version，但舊版不變。
- `%GRR <10` accept、10–30 conditional、>30 reject。
- ndc 不足會降級或 reject，依準則 snapshot。
- conditional 必須有處置期限與措施才能送審。

### Step 2：實作輸入組裝與 hash

hash 必須包含：

```python
analysis_input = {
    "study": frozen_study_snapshot,
    "plan": frozen_plan_snapshot,
    "effective_observations": serialized_effective_observations,
    "method": descriptor.as_dict(),
    "criteria": plan.criteria_snapshot,
}
data_hash = canonical_hash(analysis_input)
```

不得只 hash 讀值；順序、單位、參考值、設備、校驗、準則與方法版本都要納入。

結果的 `raw_data_summary` 必須保存同一份可 JSON 序列化輸入，不只保存計數摘要：

```python
raw_data_summary = {
    "study_snapshot": frozen_study_snapshot,
    "plan_snapshot": frozen_plan_snapshot,
    "observations": serialized_effective_observations,
    "method": descriptor.as_dict(),
    "criteria": plan.criteria_snapshot,
}
```

報告與歷史畫面只讀這份 snapshot；後續來源主檔或觀測狀態改變不影響舊結果版本。

### Step 3：實作三層判定

```python
conclusion = {
    "statistical_result": statistical_result,
    "system_disposition": disposition,
    "engineering_judgment": None,
}
```

GRR：

```python
if percent_grr < accept_max and ndc >= ndc_min:
    disposition = "acceptable"
elif percent_grr <= conditional_max:
    disposition = "conditionally_acceptable"
else:
    disposition = "unacceptable"
```

百分比口徑優先序須由 plan 明確選擇 `%Study Variation`、`%Tolerance` 或 `%Process Variation`，結果保存所用口徑；不得自動挑最有利數字。

人工工程判斷只能新增 decision payload，不改統計結果。

### Step 4：實作單一分析交易

1. lock study/plan。
2. 驗證狀態與 expected hash。
3. 讀有效觀測並驗證完整性。
4. 呼叫 registry engine。
5. `require_finite_tree`。
6. 套用 frozen criteria。
7. 建立 result version。
8. study `ready_for_analysis → analyzed`。
9. 建 decision/audit。
10. commit。

### Step 5：接上 validate/analyze API

```python
@msa_bp.post("/api/msa/plans/<int:plan_id>/analyze")
@auth_required
@require_permission("msa.execute")
@_handle_msa_errors
def analyze_msa_plan(current_user, plan_id):
    payload = request.get_json() or {}
    result = MsaStudyService.analyze(
        plan_id,
        current_user.id,
        expected_plan_hash=payload.get("expected_plan_hash"),
    )
    return jsonify({"data": serialize_msa_result(result)}), 201
```

### Step 6：執行跨方法工作流測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_workflow.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_method_registry.py backend/services/msa_study_service.py backend/services/msa_evaluation.py backend/routes/msa.py backend/tests/test_services/test_msa_workflow.py backend/tests/test_msa_routes.py
git commit -m "功能：整合 MSA 分析與版本化判定"
```

---

## Task 13：完成送審、職責分離核准、退回與作廢

**Files:**

- Modify: `backend/services/msa_study_service.py`
- Modify: `backend/services/msa_permissions.py`
- Modify: `backend/routes/msa.py`
- Modify: `backend/tests/test_services/test_msa_workflow.py`
- Modify: `backend/tests/test_msa_routes.py`

### Step 1：先寫狀態轉移與自己核准失敗測試

```python
@pytest.mark.parametrize("relationship", ["creator", "primary_executor", "data_entry"])
def test_self_approval_is_forbidden_even_for_admin(
    db_session, submitted_result, admin_user, relationship,
):
    arrange_relationship(submitted_result, admin_user, relationship)
    with pytest.raises(MsaForbidden) as error:
        MsaStudyService.approve_result(
            submitted_result.id,
            actor_id=admin_user.id,
            reason="核准",
            expected_status="submitted",
        )
    assert error.value.code == "MSA_SELF_APPROVAL_FORBIDDEN"


def test_concurrent_approval_uses_expected_status(
    db_session, approved_result, msa_approver,
):
    with pytest.raises(MsaConflict) as error:
        MsaStudyService.approve_result(
            approved_result.id,
            msa_approver.id,
            reason="重複核准",
            expected_status="submitted",
        )
    assert error.value.code == "MSA_VERSION_CONFLICT"
```

另測：

- analyzed → submitted 需要 `msa.manage`。
- conditional result 缺理由／措施／期限不能送審。
- submitted → approved/rejected。
- rejected 修正後須重分析，不能把同 result 改回 analyzed。
- approved 才能 void，且需 `msa.approve` 與理由。
- 同一研究只有一個 submitted。
- 每次動作都有 workflow decision 與 audit log。

### Step 2：建立明確狀態轉移表

```python
ALLOWED_TRANSITIONS = {
    "submit": {("analyzed", "submitted")},
    "approve": {("submitted", "approved")},
    "reject": {("submitted", "rejected")},
    "void": {("approved", "voided")},
}
```

任何不在表內的轉移回 `MSA_VERSION_CONFLICT`。

### Step 3：實作職責分離

```python
def assert_can_approve(result: MsaResultVersion, actor_id: int) -> None:
    study = result.study
    disallowed_actor_ids = {
        study.created_by_id,
        study.primary_executor_id,
        result.created_by_id,
        *(
            row.entered_by_id
            for row in result.plan_version.observations
            if row.is_effective
        ),
    }
    if actor_id in disallowed_actor_ids:
        raise MsaForbidden(
            "MSA_SELF_APPROVAL_FORBIDDEN",
            "建立、執行或輸入本研究資料的人員不得核准本研究",
        )
```

這個檢查不因 role=admin 略過。

### Step 4：以列鎖完成轉移

```python
result = (
    MsaResultVersion.query
    .filter_by(id=result_id)
    .with_for_update()
    .one_or_none()
)
if result.status != expected_status:
    raise MsaConflict("MSA_VERSION_CONFLICT", "結果版本狀態已變更")
```

保存 decision：

```python
MsaWorkflowDecision(
    study_id=result.study_id,
    result_version_id=result.id,
    action=action,
    from_status=old_status,
    to_status=new_status,
    reason=reason,
    actor_id=actor_id,
    separation_check={
        "passed": True,
        "checked_actor_id": actor_id,
        "disallowed_roles_checked": ["creator", "primary_executor", "data_entry"],
    },
)
```

### Step 5：接上四個 API

- `POST /api/msa/results/:versionId/submit`
- `POST /api/msa/results/:versionId/approve`
- `POST /api/msa/results/:versionId/reject`
- `POST /api/msa/results/:versionId/void`

所有 payload 必須有 `expected_status`、`reason`；conditional submit 另有 `actions` 與 `due_date`。

### Step 6：執行窄測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_workflow.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_study_service.py backend/services/msa_permissions.py backend/routes/msa.py backend/tests/test_services/test_msa_workflow.py backend/tests/test_msa_routes.py
git commit -m "功能：完成 MSA 職責分離核准流程"
```

---

## Task 14：建立週期與事件型再研究要求

**Files:**

- Create: `backend/services/msa_restudy_service.py`
- Modify: `backend/services/msa_equipment_service.py`
- Modify: `backend/services/msa_study_service.py`
- Modify: `backend/routes/msa.py`
- Test: `backend/tests/test_services/test_msa_restudy.py`

### Step 1：先寫冪等觸發失敗測試

```python
def test_equipment_maintenance_creates_restudy_for_approved_studies(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    MsaEquipmentService.add_status_event(
        linked_primary_gauge.id,
        {"event_type": "maintenance", "reason": "更換測頭"},
        actor_id=msa_manager.id,
    )
    requests = MsaRestudyRequest.query.filter_by(
        source_study_id=approved_study.id,
        trigger_type="equipment_maintenance",
    ).all()
    assert len(requests) == 1


def test_same_source_event_does_not_duplicate_restudy(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    event = MsaEquipmentService.add_status_event(
        linked_primary_gauge.id,
        {"event_type": "maintenance", "reason": "更換測頭"},
        actor_id=msa_manager.id,
    )
    first = MsaRestudyService.from_equipment_event(event.id)
    second = MsaRestudyService.from_equipment_event(event.id)
    assert second.id == first.id
```

另測校驗失敗、逾期、補正重大改變、方法／夾具／軟體／操作者／產品規格改變、conditional action 到期與固定週期。

### Step 2：實作 trigger registry

```python
TRIGGER_TYPES = {
    "equipment_maintenance",
    "equipment_major_adjustment",
    "calibration_failed",
    "calibration_expired",
    "correction_changed",
    "measurement_method_changed",
    "fixture_changed",
    "software_changed",
    "appraiser_population_changed",
    "product_or_spec_changed",
    "conditional_action_due",
    "periodic_due",
}
```

每個 request 保存 source entity/type/id、trigger payload、due date、status、linked new study id。

### Step 3：實作新研究建立與取代

- 只複製研究 metadata 與設計建議。
- 不複製任何舊觀測。
- 新研究先為 draft，引用 `previous_approved_study_id`。
- 新研究核准後才將前研究的 current relationship 標記為 superseded；舊 result 本體仍不可變。

### Step 4：加入工作台 API

```text
GET  /api/msa/restudy-requests
POST /api/msa/restudy-requests/:id/start
```

固定週期掃描 service 可由現有排程機制呼叫；若專案尚無排程器，先提供 idempotent CLI：

```powershell
venv\Scripts\python.exe -m backend.scripts.create_due_msa_restudies --as-of 2026-07-27
```

### Step 5：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_restudy.py backend\tests\test_services\test_msa_workflow.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_restudy_service.py backend/services/msa_equipment_service.py backend/services/msa_study_service.py backend/routes/msa.py backend/scripts/create_due_msa_restudies.py backend/tests/test_services/test_msa_restudy.py
git commit -m "功能：建立 MSA 再研究觸發與追蹤"
```

---

## Task 15：建立統計 golden validation runner

**Files:**

- Create: `backend/services/msa_validation.py`
- Create: `backend/scripts/run_msa_validation.py`
- Create: `backend/tests/fixtures/msa_golden_cases.json`
- Create: `backend/tests/test_services/test_msa_golden.py`

### Step 1：先寫 PASS／FAIL 都會持久化的失敗測試

```python
def test_validation_runner_persists_pass_and_fail(db_session, monkeypatch):
    passed = MsaValidationService.run_case("grr_xbar_r_reference", actor_id=1)
    assert passed.result == "PASS"
    assert passed.method_versions
    assert passed.code_version
    assert passed.tolerances

    monkeypatch.setattr(MsaValidationService, "_compare", lambda *_: ["grr 超出容許誤差"])
    failed = MsaValidationService.run_case("grr_xbar_r_reference", actor_id=1)
    assert failed.result == "FAIL"
    assert failed.differences == ["grr 超出容許誤差"]
```

另測 validation run 不可更新／刪除、缺 code version 直接 FAIL、fixture hash 不同明確記錄。

### Step 2：驗證 Task 1 已建立 validation run 表

`MSA軟體確效執行` 必須已包含：

- case id。
- fixture SHA-256。
- method codes/versions。
- code version。
- executed by/time。
- tolerances。
- observed/expected/differences。
- result `PASS|FAIL`。

確認已有 `PASS|FAIL` CHECK 與 immutable trigger；若缺少，回到 Task 1 修正尚未套用的 migration 46 及模型後，重新執行 Task 1 驗證，不在已套用環境事後改寫 migration。

### Step 3：建立 golden cases

至少涵蓋：

- Range。
- Xbar-R。
- ANOVA full interaction。
- ANOVA reduced interaction。
- Bias。
- Linearity。
- Stability Xbar-R 與 I-MR。
- Attribute binary/multiclass。
- Nonrepeatable paired。
- 各一個 not-applicable case。
- NaN/Infinity failure case。

fixture 的 expected 必須來自獨立手算、公開例題或另一個經確認工具；不可用同一正式函式先算再回填。

### Step 4：實作精確比較

```python
def compare_number(path: str, observed: float, expected: float, tolerance: dict) -> str | None:
    absolute = abs(observed - expected)
    allowed = max(
        tolerance["absolute"],
        tolerance["relative"] * abs(expected),
    )
    if absolute > allowed:
        return f"{path}: observed={observed}, expected={expected}, allowed={allowed}"
    return None
```

每個差異保存完整 JSON path，不能只回整體 FAIL。

### Step 5：執行 runner 與測試

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_golden.py -q
venv\Scripts\python.exe -m backend.scripts.run_msa_validation --all
```

Expected: pytest PASS；runner 全部 PASS 並保存實際 code/method/fixture hash。

### Step 6：提交

```powershell
git add backend/services/msa_validation.py backend/scripts/run_msa_validation.py backend/tests/fixtures/msa_golden_cases.json backend/tests/test_services/test_msa_golden.py
git commit -m "驗證：建立 MSA 統計黃金資料確效"
```

---

## Task 16：完成後端核心總驗證

**Files:**

- Modify only if tests reveal a defect; do not combine unrelated cleanup.

### Step 1：執行所有 MSA 窄測試

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_models.py backend\tests\test_services\test_msa_equipment.py backend\tests\test_services\test_msa_import.py backend\tests\test_services\test_msa_criteria.py backend\tests\test_services\test_msa_numeric.py backend\tests\test_services\test_msa_workflow.py backend\tests\test_services\test_msa_observations.py backend\tests\test_services\test_msa_variable_grr.py backend\tests\test_services\test_msa_bias_linearity.py backend\tests\test_services\test_msa_stability.py backend\tests\test_services\test_msa_attribute.py backend\tests\test_services\test_msa_nonrepeatable.py backend\tests\test_services\test_msa_restudy.py backend\tests\test_services\test_msa_golden.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

### Step 2：執行完整後端回歸

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q
git diff --check
```

Expected: 全部 PASS；無 whitespace error。

### Step 3：若修正了整合缺陷，單獨提交

先以 `git diff --name-only` 確認變更，再逐一 `git add` 本任務實際修正的 MSA 檔案；不得使用 `git add .`。有修正時提交 `修正：完成 MSA 核心整合驗證`，沒有修正時不建立空 commit。

---

## 本計畫完成條件

- 研究、plan、part、appraiser、observation、result、decision 與 restudy 均有正規化模型、索引、限制及稽核。
- plan freeze 保存設備／校驗／準則／隨機順序快照與 hash。
- 盲測收集不暴露參考值或前次讀值；修正只新增 successor。
- Range、Xbar-R、crossed ANOVA、bias、linearity、stability、attribute、nonrepeatable 均由受控方法版本計算。
- 每個引擎拒絕非適用設計、NaN、Infinity、奇異模型與不受控 fallback。
- 系統判定與工程判斷分離，統計數值不可被人工覆寫。
- 建立／執行／輸入者即使是 admin 也不可自己核准。
- fixed/event-based restudy 具冪等要求與完整來源證據。
- golden validation 保存 PASS 與 FAIL、精確差異、方法／程式／fixture 版本。
- MSA 窄測試與完整後端回歸全部通過。
