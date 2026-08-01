# 進階 SPC 分析實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以現有出貨與巡檢資料完成 p／np 屬性管制圖、巡檢 Pm／Pmk 機器績效、完整 A1／A2／B／C1-C4／D 診斷，以及 Box-Cox／Johnson 轉換，並全部納入不可變研究版本與進階 SPC 頁面。

**Architecture:** 擴充既有 `SpcStudy`／`SpcStudyVersion` 生命週期，以 `analysis_family` 區分 `variable`、`attribute`、`machine`。統計公式放在四個獨立 service module，`SpcStudyService` 只負責資料轉接、版本、權限、確認與稽核；前端以獨立 `/spc/advanced` 頁面組合四個工作區。

**Tech Stack:** Python 3、Flask、SQLAlchemy、SciPy、NumPy、PostgreSQL 16、React 19、TypeScript、TanStack React Query、Chart.js、Vitest。

## Global Constraints

- 所有使用者訊息、commit 訊息、程式碼註解與說明使用繁體中文。
- 方法版本與輸入契約版本固定升為 `2026.2`；既有 `2026.1` 版本不可重算或覆寫。
- 不新增 Python 或 npm 依賴；統計方法只使用目前已有的 NumPy／SciPy。
- 原始資料與既有研究版本不可修改；確認轉換或模型必須建立後繼版本。
- 屬性圖只使用可可靠判定的 `is_ng`；不把 NCMR 不合格數量當成缺陷數。
- 本次只實作 p／np，不實作 c／u；機器績效只接受巡檢資料，不實作 Excel 匯入與出貨機台來源。
- B／C／D 與轉換均為系統候選加人工理由確認；不得自動把 B／C／D 報告成 Cp／Cpk。
- 所有新行為遵循 TDD：先執行失敗測試，再寫最小實作，再跑相關回歸。

---

### Task 1: 研究族別、資料庫唯一鍵與共用契約

**Files:**
- Create: `backend/migration/38_add_spc_analysis_family.sql`
- Modify: `backend/models.py:295-451`
- Modify: `backend/services/spc_contracts.py:12-100`
- Modify: `backend/services/spc_adapters/common.py:11-119`
- Modify: `backend/services/spc_study_service.py:44-55,448-526,816-870`
- Modify: `backend/routes/spc_studies.py:81-176,204-220`
- Test: `backend/tests/test_services/test_spc_models.py`
- Test: `backend/tests/test_services/test_spc_study_service.py`

**Interfaces:**
- Produces: `AnalysisFamily = Literal["variable", "attribute", "machine"]`.
- Produces: `SpcStudyInput.analysis_family: str` with default `variable`.
- Produces: `SpcStudy.analysis_family` and `SpcLimitVersion.analysis_family`.
- Changes: `SpcStudyService.analyze(source, filters, actor_id, study_type="retrospective", analysis_family="variable", options=None)`.

- [ ] **Step 1: Write failing model and service tests**

```python
def test_spc_study_identity_includes_analysis_family(app, db_session):
    variable = SpcStudy(
        source="shipping", study_type="retrospective", analysis_family="variable",
        process_stream_key="same-stream", characteristic="不符合單位", filters={},
    )
    attribute = SpcStudy(
        source="shipping", study_type="retrospective", analysis_family="attribute",
        process_stream_key="same-stream", characteristic="不符合單位", filters={},
    )
    db_session.add_all([variable, attribute])
    db_session.commit()
    assert {item.analysis_family for item in SpcStudy.query.all()} == {"variable", "attribute"}


def test_analyze_rejects_unknown_analysis_family(app, db_session, spc_view_user):
    with pytest.raises(SpcValidationError) as error:
        SpcStudyService.analyze(
            "shipping", {}, spc_view_user.id, analysis_family="unknown"
        )
    assert error.value.code == "SPC_ANALYSIS_FAMILY_INVALID"
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_models.py backend\tests\test_services\test_spc_study_service.py -q
```

Expected: FAIL because `analysis_family` and the new argument do not exist.

- [ ] **Step 3: Add schema and contract fields**

```python
class SpcStudy(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            '資料來源', '研究類型', '分析族別', '製程流識別鍵', '品質特性',
            name='uq_spc_study_identity',
        ),
        db.Index(
            'idx_spc_study_stream_characteristic',
            '分析族別', '製程流識別鍵', '品質特性',
        ),
    )
    analysis_family = db.Column('分析族別', db.String(20), nullable=False, default='variable')


class SpcLimitVersion(db.Model):
    analysis_family = db.Column('分析族別', db.String(20), nullable=False, default='variable')
```

Update the active partial index columns to `分析族別, 製程流識別鍵, 品質特性`. Add `analysis_family` to `SpcStudyInput`, serialized study/version/limit payloads, study identity, active-limit lookup and limit creation. Validate against `{"variable", "attribute", "machine"}` and pass family-specific `options` without putting them into source filters. Set `SPC_METHOD_VERSION`, `SPC_INPUT_CONTRACT_VERSION` and preview schema version to `2026.2`; keep saved `2026.1` rows untouched.

- [ ] **Step 4: Add idempotent PostgreSQL migration**

```sql
BEGIN;
ALTER TABLE "SPC研究" ADD COLUMN IF NOT EXISTS "分析族別" VARCHAR(20);
UPDATE "SPC研究" SET "分析族別" = 'variable' WHERE "分析族別" IS NULL;
ALTER TABLE "SPC研究" ALTER COLUMN "分析族別" SET NOT NULL;

ALTER TABLE "SPC界限版本" ADD COLUMN IF NOT EXISTS "分析族別" VARCHAR(20);
UPDATE "SPC界限版本" SET "分析族別" = 'variable' WHERE "分析族別" IS NULL;
ALTER TABLE "SPC界限版本" ALTER COLUMN "分析族別" SET NOT NULL;

ALTER TABLE "SPC研究" DROP CONSTRAINT IF EXISTS uq_spc_study_identity;
ALTER TABLE "SPC研究" ADD CONSTRAINT uq_spc_study_identity
    UNIQUE ("資料來源", "研究類型", "分析族別", "製程流識別鍵", "品質特性");

DROP INDEX IF EXISTS uq_spc_one_active_limit;
CREATE UNIQUE INDEX uq_spc_one_active_limit
    ON "SPC界限版本" ("分析族別", "製程流識別鍵", "品質特性")
    WHERE "狀態" = 'active';
COMMIT;
```

Include preflight checks for unsupported existing family values and duplicate post-backfill identities before replacing constraints.

- [ ] **Step 5: Run focused regression and commit**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_models.py backend\tests\test_services\test_spc_study_service.py backend\tests\test_services\test_spc_2026_regressions.py -q
git diff --check
git add backend/models.py backend/migration/38_add_spc_analysis_family.sql backend/services/spc_contracts.py backend/services/spc_adapters/common.py backend/services/spc_study_service.py backend/routes/spc_studies.py backend/tests/test_services/test_spc_models.py backend/tests/test_services/test_spc_study_service.py
git commit -m "功能：建立 SPC 研究族別與唯一鍵"
```

Expected: focused tests pass; commit contains no product feature beyond the family foundation.

---

### Task 2: p／np 統計引擎與屬性來源轉接器

**Files:**
- Create: `backend/services/spc_attribute_engine.py`
- Create: `backend/services/spc_adapters/attribute.py`
- Create: `backend/tests/test_services/test_spc_attribute_engine.py`
- Create: `backend/tests/test_services/test_spc_attribute_adapter.py`
- Modify: `backend/services/spc_adapters/__init__.py`
- Modify: `backend/services/spc_adapters/common.py`

**Interfaces:**
- Produces: `AttributeSubgroup(key, timestamp, inspected, nonconforming, record_ids)`.
- Produces: `calculate_attribute_chart(subgroups, requested_chart, alpha=0.0027) -> dict`.
- Produces: `build_attribute_study_input(source, filters, interval) -> SpcStudyInput`.

- [ ] **Step 1: Write failing exact-binomial tests**

```python
def test_p_chart_uses_weighted_center_and_point_specific_exact_limits():
    groups = (
        AttributeSubgroup("2026-07-01", date(2026, 7, 1), 50, 2, (1,)),
        AttributeSubgroup("2026-07-02", date(2026, 7, 2), 100, 8, (2,)),
    )
    result = calculate_attribute_chart(groups, "p")
    assert result["chart_type"] == "p"
    assert result["center"] == pytest.approx(10 / 150)
    assert result["values"] == pytest.approx([0.04, 0.08])
    assert result["ucl"][0] != result["ucl"][1]
    assert all(0 <= value <= 1 for value in result["lcl"] + result["ucl"])


def test_np_rejects_variable_subgroup_size():
    with pytest.raises(SpcChartNotApplicable) as error:
        calculate_attribute_chart(
            (AttributeSubgroup("a", None, 50, 1, (1,)),
             AttributeSubgroup("b", None, 51, 1, (2,))),
            "np",
        )
    assert error.value.code == "NP_REQUIRES_FIXED_SUBGROUP_SIZE"


def test_zero_defect_baseline_is_not_turned_into_limits():
    with pytest.raises(SpcChartNotApplicable) as error:
        calculate_attribute_chart(
            (AttributeSubgroup("a", None, 50, 0, (1,)),), "p"
        )
    assert error.value.code == "ZERO_DEFECT_BASELINE"
```

- [ ] **Step 2: Run engine tests and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_attribute_engine.py -q
```

Expected: collection error because the new module is absent.

- [ ] **Step 3: Implement exact-binomial engine**

```python
@dataclass(frozen=True)
class AttributeSubgroup:
    key: str
    timestamp: date | datetime | str | None
    inspected: int
    nonconforming: int
    record_ids: tuple[int, ...] = ()

    def __post_init__(self):
        if self.inspected <= 0 or not 0 <= self.nonconforming <= self.inspected:
            raise ValueError("屬性子組數量不合法")


def _exact_limits(n: int, p_bar: float, alpha: float) -> tuple[int, int]:
    cdf = scipy_stats.binom.cdf(np.arange(n + 1), n, p_bar)
    lower_candidates = np.flatnonzero(cdf <= alpha / 2.0)
    upper_candidates = np.flatnonzero(cdf >= 1.0 - alpha / 2.0)
    lower = int(lower_candidates[-1]) if lower_candidates.size else 0
    upper = int(upper_candidates[0]) if upper_candidates.size else n
    return max(0, lower), min(n, upper)
```

Return chart values, CL/UCL/LCL arrays, subgroup sizes, raw counts, sample-size warning, 25% size-variation warning and Pearson residuals. For np, reject any non-identical `n`.

- [ ] **Step 4: Write adapter RED tests and implement source eligibility**

Tests must create dated shipping and patrol records, then assert day/week/month grouping, `x_i/n_i`, record IDs, and exclusion of records whose conformance cannot be determined. Implement family-specific canonical filters and the characteristic `不符合單位`. The adapter must store excluded classification snapshots:

```python
{
    "record_id": record.id,
    "eligible": False,
    "reason_code": "ATTRIBUTE_CLASSIFICATION_UNKNOWN",
}
```

For patrol, reuse tolerance resolution to distinguish `tol_found=False` from a conforming record. For shipping, require saved inspection outcome plus recorded measurement specification evidence.

- [ ] **Step 5: Run focused tests and commit**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_attribute_engine.py backend\tests\test_services\test_spc_attribute_adapter.py -q
git diff --check
git add backend/services/spc_attribute_engine.py backend/services/spc_adapters/attribute.py backend/services/spc_adapters/__init__.py backend/services/spc_adapters/common.py backend/tests/test_services/test_spc_attribute_engine.py backend/tests/test_services/test_spc_attribute_adapter.py
git commit -m "功能：新增 p 與 np 屬性管制圖引擎"
```

---

### Task 3: 屬性研究版本、持續監控與版本報表

**Files:**
- Modify: `backend/services/spc_study_service.py`
- Modify: `backend/services/spc_stability.py`
- Modify: `backend/services/spc_report.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `backend/services/patrol_service.py:588-743`
- Test: `backend/tests/test_services/test_spc_study_service.py`
- Create: `backend/tests/test_services/test_spc_attribute_study.py`
- Modify: `backend/tests/test_services/test_spc_report_versioning.py`

**Interfaces:**
- Consumes: attribute adapter and chart result from Task 2.
- Produces: attribute versions through existing analyze/list/detail/history endpoints.
- Produces: ongoing p／np evaluation using frozen approved limits and approved rule set.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_attribute_analysis_persists_family_counts_and_exact_limits(
    app, db_session, spc_view_user
):
    version = SpcStudyService.analyze(
        "shipping", SHIPPING_FILTERS, spc_view_user.id,
        analysis_family="attribute",
        options={"interval": "day", "chart_type": "p"},
    )
    assert version.study.analysis_family == "attribute"
    assert version.chart_result["chart_type"] == "p"
    assert version.chart_result["counts"][0]["inspected"] > 0
    assert version.method_version == "2026.2"


def test_attribute_ongoing_uses_approved_limits_without_recentering(
    app, db_session, spc_view_user
):
    baseline = create_approved_attribute_baseline(db_session)
    ongoing = SpcStudyService.analyze(
        "shipping", CURRENT_FILTERS, spc_view_user.id,
        study_type="ongoing", analysis_family="attribute",
        options={"interval": "day", "chart_type": "p"},
    )
    assert ongoing.chart_result["cl"] == baseline.limits["cl"]
```

- [ ] **Step 2: Run lifecycle tests and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_attribute_study.py -q
```

Expected: FAIL because study orchestration handles only variable charts.

- [ ] **Step 3: Add family dispatch and attribute stability**

```python
CALCULATORS = {
    "variable": _calculate_variable_results,
    "attribute": _calculate_attribute_results,
    "machine": _calculate_machine_results,
}
```

For attribute stability, `beyond_limits` evaluates exact binomial limits. Run/trend rules consume Pearson residuals with center 0 and three-sigma zones. Persist `rules_used`, `residual_method="binomial_pearson"`, counts, exact alpha and interval. Approval must include `analysis_family` in limit lookup and creation.

- [ ] **Step 4: Generate reports only from immutable versions**

Extend `_stats_from_version()` and report sheets for p／np counts, exact limits, warnings, family and method. Replace patrol export's call to `PatrolService.get_spc()` plus `generate_report()` with creation or selection of a saved version followed by:

```python
spc_output = SpcReportService.generate_version_report(
    version.id, field_label, filters
)
```

Add tests asserting the workbook contains study version ID, data hash, method `2026.2`, subgroup inspected/nonconforming counts and approval metadata.

- [ ] **Step 5: Run regressions and commit**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_attribute_study.py backend\tests\test_services\test_spc_study_service.py backend\tests\test_services\test_spc_report_versioning.py -q
git diff --check
git add backend/services/spc_study_service.py backend/services/spc_stability.py backend/services/spc_report.py backend/routes/spc_studies.py backend/services/patrol_service.py backend/tests/test_services/test_spc_attribute_study.py backend/tests/test_services/test_spc_study_service.py backend/tests/test_services/test_spc_report_versioning.py
git commit -m "功能：整合屬性研究版本與可追溯報表"
```

---

### Task 4: 進階 SPC 頁面骨架與屬性工作區

**Files:**
- Create: `src_frontend/src/pages/spc/AdvancedSpcPage.tsx`
- Create: `src_frontend/src/pages/spc/AdvancedSpcPage.test.tsx`
- Create: `src_frontend/src/components/spc/attribute/AttributeStudyPanel.tsx`
- Create: `src_frontend/src/components/spc/attribute/AttributeStudyPanel.test.tsx`
- Create: `src_frontend/src/components/spc/attribute/AttributeControlChart.tsx`
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/components/Sidebar.tsx`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`
- Modify: `src_frontend/src/types/spc.ts`

**Interfaces:**
- Consumes: `analysis_family="attribute"` analyze API.
- Produces: route `/spc/advanced`, query-prefilled source filters, p／np chart UI.

- [ ] **Step 1: Write failing route and panel tests**

```tsx
it('從 query 載入出貨屬性研究條件', async () => {
  renderWithRouter(
    <AdvancedSpcPage />,
    '/spc/advanced?family=attribute&source=shipping&vendor=甲',
  );
  expect(screen.getByRole('heading', { name: '進階 SPC 分析' })).toBeInTheDocument();
  expect(screen.getByLabelText('資料來源')).toHaveValue('shipping');
  expect(screen.getByLabelText('廠商')).toHaveValue('甲');
});

it('np 子組不固定時顯示原因而不畫誤導圖表', () => {
  render(<AttributeStudyPanel result={npNotApplicableResult} />);
  expect(screen.getByText(/np 圖需要固定子組大小/)).toBeInTheDocument();
  expect(screen.queryByTestId('attribute-chart')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend tests and verify RED**

```powershell
cd src_frontend
npm test -- --run src/pages/spc/AdvancedSpcPage.test.tsx src/components/spc/attribute/AttributeStudyPanel.test.tsx
```

Expected: FAIL because page and components are absent.

- [ ] **Step 3: Add types, hook payload and page shell**

```typescript
export type SpcAnalysisFamily = 'variable' | 'attribute' | 'machine';
export type SpcChartType = 'xbar_s' | 'xbar_r' | 'i_mr' | 'p' | 'np';

export interface SpcAttributeCount {
  key: string;
  inspected: number;
  nonconforming: number;
  proportion: number;
}
```

Add `analysis_family` and `options` to `AnalyzeSpcStudyInput`. The page must expose source, interval and chart type, preserve query values, and render applicability reasons before charts.

- [ ] **Step 4: Render point-specific charts and navigation**

Use the existing Chart.js option helpers but pass array CL/UCL/LCL. Display inspected/nonconforming values in tooltips. Add sidebar item `進階 SPC` and lazy route. The page must show `方法版本 2026.2`, warning badges and saved version workflow.

- [ ] **Step 5: Run focused frontend checks and commit**

```powershell
cd src_frontend
npm test -- --run src/pages/spc/AdvancedSpcPage.test.tsx src/components/spc/attribute/AttributeStudyPanel.test.tsx src/utils/spcChartModel.test.ts
npm run lint
cd ..
git diff --check
git add src_frontend/src/pages/spc src_frontend/src/components/spc/attribute src_frontend/src/App.tsx src_frontend/src/components/Sidebar.tsx src_frontend/src/hooks/useSpcStudies.ts src_frontend/src/types/spc.ts
git commit -m "功能：新增進階 SPC 與屬性圖頁面"
```

---

### Task 5: 巡檢機器績效 Pm／Pmk 引擎與研究資格

**Files:**
- Create: `backend/services/spc_machine_performance.py`
- Create: `backend/tests/test_services/test_spc_machine_performance.py`
- Create: `backend/tests/test_services/test_spc_machine_study.py`
- Modify: `backend/services/spc_adapters/patrol.py`
- Modify: `backend/services/spc_study_service.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `backend/services/spc_report.py`

**Interfaces:**
- Produces: `calculate_machine_performance(values, specification, distribution, characteristic_class) -> dict`.
- Consumes: `options={"conditions_confirmed": bool, "condition_reason": str}`.
- Produces: `capability_result` with `index_family="machine"`, `pm`, `pmk`, `pmu`, `pml`, targets and eligibility.
- Produces: `SpcStudyService.approve_research(version_id, actor_id, reason)` and `POST /api/spc/study-versions/<id>/approve-research`.

- [ ] **Step 1: Write failing Pm/Pmk tests**

```python
def test_machine_normal_g_method_matches_six_sigma():
    values = NORMAL_MACHINE_VALUES_50
    dist = assess_distribution(values, field="外徑")
    result = calculate_machine_performance(
        values, {"LSL": 9.0, "USL": 11.0}, dist, "主要"
    )
    expected_pm = 2.0 / (6.0 * np.std(values, ddof=1))
    assert result["pm"] == pytest.approx(expected_pm, rel=0.02)
    assert result["preliminary"] is False
    assert result["targets"]["pm"] == 2.0
    assert result["targets"]["pmk"] == 1.67


def test_machine_study_under_50_is_preliminary_and_not_approvable():
    result = calculate_machine_performance(
        NORMAL_MACHINE_VALUES_50[:49], SPEC, DIST, "其他"
    )
    assert result["preliminary"] is True
    assert result["reason_code"] == "MACHINE_SAMPLE_INSUFFICIENT"
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_machine_performance.py -q
```

Expected: import failure because engine is absent.

- [ ] **Step 3: Implement G-method indices and fixed-stream evidence**

```python
def calculate_machine_performance(values, specification, distribution, characteristic_class):
    q_lo, q_mid, q_hi = dist_quantiles(distribution)
    span = q_hi - q_lo
    pm = (usl - lsl) / span if usl is not None and lsl is not None else None
    pmu = (usl - q_mid) / (q_hi - q_mid) if usl is not None else None
    pml = (q_mid - lsl) / (q_mid - q_lo) if lsl is not None else None
    pmk = min(value for value in (pmu, pml) if value is not None)
```

Reject non-patrol sources, missing exact machine/material/spec/item/position, inconsistent specs and unconfirmed conditions. Save unique operators, date span, record IDs and `source_semantics="patrol_min_max_observations"`. Do not average min/max pairs.

- [ ] **Step 4: Integrate versions, approval gate and report**

Family dispatch stores machine results in `capability_result`; `_assert_research_approvable` requires at least 50 values, confirmed conditions, accepted distribution and specification. Add `approve_research()` for machine and confirmed B/C/D research: it changes submitted version/study status to `approved`, writes AuditLog, and never creates `SpcLimitVersion`. Keep `approve_and_activate()` exclusive to production baselines that actually create limits. Report includes conditions, source semantics, N, quantiles, Pm/Pmk, targets and limitation statements.

- [ ] **Step 5: Run focused tests and commit**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_machine_performance.py backend\tests\test_services\test_spc_machine_study.py backend\tests\test_services\test_spc_report_versioning.py -q
git diff --check
git add backend/services/spc_machine_performance.py backend/services/spc_adapters/patrol.py backend/services/spc_study_service.py backend/routes/spc_studies.py backend/services/spc_report.py backend/tests/test_services/test_spc_machine_performance.py backend/tests/test_services/test_spc_machine_study.py backend/tests/test_services/test_spc_report_versioning.py
git commit -m "功能：新增巡檢機器績效研究"
```

---

### Task 6: 機器績效前端工作區

**Files:**
- Create: `src_frontend/src/components/spc/machine/MachinePerformancePanel.tsx`
- Create: `src_frontend/src/components/spc/machine/MachinePerformancePanel.test.tsx`
- Create: `src_frontend/src/components/spc/machine/MachineConditionForm.tsx`
- Modify: `src_frontend/src/pages/spc/AdvancedSpcPage.tsx`
- Modify: `src_frontend/src/types/spc.ts`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`

**Interfaces:**
- Consumes: machine analyze payload and machine capability result from Task 5.
- Produces: fixed-stream form, eligibility evidence, Pm/Pmk cards and condition confirmation.

- [ ] **Step 1: Write failing machine UI tests**

```tsx
it('未選單一機台與位置時禁止建立機器研究', () => {
  render(<MachineConditionForm value={incompleteFilters} onChange={vi.fn()} />);
  expect(screen.getByRole('button', { name: '分析機器績效' })).toBeDisabled();
  expect(screen.getByText(/必須鎖定單一機台/)).toBeInTheDocument();
});

it('顯示初步 Pm Pmk 且不宣告正式達標', () => {
  render(<MachinePerformancePanel result={preliminaryResult} />);
  expect(screen.getByText('初步結果')).toBeInTheDocument();
  expect(screen.queryByText('正式達標')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
cd src_frontend
npm test -- --run src/components/spc/machine/MachinePerformancePanel.test.tsx
```

Expected: FAIL because machine UI files are absent.

- [ ] **Step 3: Implement fixed-condition form and result cards**

Add types for `MachinePerformanceResult` and `MachineStudyEvidence`. Require machine, material, spec, item, position, controlled-condition checkbox and non-empty reason before analyze. Render sample N, date range, operators, source semantics, quantiles, Pm/Pmk targets, preliminary status and reason code.

```typescript
export interface MachinePerformanceResult {
  available: boolean;
  preliminary: boolean;
  pm: number | null;
  pmk: number | null;
  pmu: number | null;
  pml: number | null;
  valid_count: number;
  reason_code: string | null;
  evidence: MachineStudyEvidence;
}
```

- [ ] **Step 4: Add page tab and workflow integration**

The page passes `analysis_family="machine"` and condition options, then uses the existing version workflow. Extend version status types and workflow labels with `approved`. Machine research calls `approve-research`, hides control-limit activation wording and labels the action `核准研究結果`.

- [ ] **Step 5: Run and commit**

```powershell
cd src_frontend
npm test -- --run src/components/spc/machine/MachinePerformancePanel.test.tsx src/pages/spc/AdvancedSpcPage.test.tsx
npm run lint
cd ..
git diff --check
git add src_frontend/src/components/spc/machine src_frontend/src/pages/spc/AdvancedSpcPage.tsx src_frontend/src/types/spc.ts src_frontend/src/hooks/useSpcStudies.ts
git commit -m "功能：新增機器績效分析工作區"
```

---

### Task 7: 完整 B／C／D 時間模型診斷與人工改判

**Files:**
- Create: `backend/services/spc_time_diagnostics.py`
- Create: `backend/tests/test_services/test_spc_time_diagnostics.py`
- Modify: `backend/services/spc_time_model.py`
- Modify: `backend/services/spc_study_service.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `backend/tests/test_services/test_spc_golden.py`
- Modify: `backend/tests/test_services/test_spc_study_service.py`

**Interfaces:**
- Produces: `diagnose_time_model(chart_set, subgroups, distribution, alpha=0.05) -> dict`.
- Produces evidence keys: `trend`, `change_points`, `variance_change`, `instantaneous_distribution`, `aggregate_modality`, `multiple_testing`.
- Extends confirmation models to A1/A2/B/C1/C2/C3/C4/D with override reason.

- [ ] **Step 1: Add failing golden datasets for every model**

```python
@pytest.mark.parametrize((dataset, expected), [
    (A1_DATA, "A1"), (A2_DATA, "A2"), (B_VARIANCE_SHIFT, "B"),
    (C1_RANDOM_LOCATION_NORMAL, "C1"), (C2_RANDOM_LOCATION_SKEW, "C2"),
    (C3_MONOTONIC_WEAR, "C3"), (C4_BATCH_STEPS, "C4"),
    (D_LOCATION_AND_VARIANCE, "D"),
])
def test_time_diagnostic_golden_models(dataset, expected):
    result = diagnose_time_model(**dataset)
    assert result["candidate"] == expected
    assert result["diagnostic_version"] == "2026.2"
    assert result["evidence"]
```

Add a test asserting fewer than 25 subgroups returns `TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT` and cannot be confirmed.

- [ ] **Step 2: Run diagnostic tests and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_time_diagnostics.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement deterministic diagnostics**

```python
def diagnose_time_model(chart_set, subgroups, distribution, alpha=0.05):
    means = np.asarray(chart_set.location.values, dtype=float)
    trend = _kendall_theil_sen(means, alpha)
    changes = _recursive_welch_changes(means, min_segment=5, alpha=alpha)
    variance_change = _holm_levene_windows(subgroups, alpha=alpha)
    values = np.concatenate([np.asarray(group.values, dtype=float) for group in subgroups])
    modality = _kde_modality(values)
    candidate = _classify(trend, changes, variance_change, distribution, modality)
    return {
        "candidate": candidate,
        "confirmed": False,
        "diagnostic_version": "2026.2",
        "evidence": {
            "trend": trend,
            "change_points": changes,
            "variance_change": variance_change,
            "aggregate_modality": modality,
        },
    }
```

All p-value families must include Holm-adjusted values. Classification priority is D, B, C3, C4, C1/C2, A1/A2. Store exact indexes and thresholds; never depend on randomized optimization.

- [ ] **Step 4: Extend confirmation and immutable successor workflow**

Change permission for confirming/overriding diagnostics to `spc.approve`. Candidate confirmation and override both require a reason. Save:

```python
confirmed_time_model = {
    **diagnostic,
    "model": requested_model,
    "system_candidate": diagnostic["candidate"],
    "overridden": requested_model != diagnostic["candidate"],
    "confirmed": True,
    "confirmed_by": actor_id,
    "confirmed_at": utc_now().isoformat(),
    "confirmation_reason": reason,
}
```

Create a successor version and preserve samples. `_assert_approvable` continues to allow production capability/limit activation only for confirmed A1/A2; confirmed B/C/D uses `approve_research`, may reach `approved`, and cannot activate variable limits or Cp/Cpk.

- [ ] **Step 5: Run tests and commit**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_time_diagnostics.py backend\tests\test_services\test_spc_time_model.py backend\tests\test_services\test_spc_golden.py backend\tests\test_services\test_spc_study_service.py -q
git diff --check
git add backend/services/spc_time_diagnostics.py backend/services/spc_time_model.py backend/services/spc_study_service.py backend/routes/spc_studies.py backend/tests/test_services/test_spc_time_diagnostics.py backend/tests/test_services/test_spc_golden.py backend/tests/test_services/test_spc_study_service.py
git commit -m "功能：完成 B C D 時間模型診斷"
```

---

### Task 8: Box-Cox／Johnson 候選、反轉換與確認流程

**Files:**
- Create: `backend/services/spc_transformations.py`
- Create: `backend/tests/test_services/test_spc_transformations.py`
- Modify: `backend/services/spc_distribution.py`
- Modify: `backend/services/spc_study_service.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `backend/services/spc_analysis_service.py`
- Modify: `backend/tests/test_services/test_spc_distribution.py`

**Interfaces:**
- Produces: `evaluate_transformations(values, alpha=0.05) -> dict`.
- Produces: `transform_values(values, decision)`, `inverse_values(values, decision)`.
- Adds: `POST /api/spc/study-versions/<id>/transformation` with `{model, reason}`.

- [ ] **Step 1: Write failing transformation tests**

```python
@pytest.mark.parametrize("dataset,expected_model", [
    (BOXCOX_DATA, "boxcox"),
    (JOHNSON_SU_DATA, "johnson_su"),
    (JOHNSON_SB_DATA, "johnson_sb"),
    (JOHNSON_SL_DATA, "johnson_sl"),
])
def test_transformation_candidate_and_roundtrip(dataset, expected_model):
    result = evaluate_transformations(dataset)
    candidate = next(
        item for item in result["candidates"] if item["model"] == expected_model
    )
    assert candidate["accepted"] is True
    restored = inverse_values(transform_values(dataset, candidate), candidate)
    assert restored == pytest.approx(dataset, rel=1e-9, abs=1e-9)


def test_boxcox_rejects_nonpositive_values():
    result = evaluate_transformations([-1.0, 0.0, 1.0] * 10)
    boxcox = next(item for item in result["candidates"] if item["model"] == "boxcox")
    assert boxcox["reason_code"] == "BOXCOX_POSITIVE_VALUES_REQUIRED"
```

- [ ] **Step 2: Run and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_transformations.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement deterministic candidate evaluation**

Use `scipy.stats.boxcox_normmax`, `boxcox`, `johnsonsu`, `johnsonsb` and lognormal for SL. Johnson transform is `norm.ppf(fitted.cdf(x))`; inverse is `fitted.ppf(norm.cdf(z))`. Clip probabilities only to machine epsilon and store the clipping value. Candidate acceptance requires AD p >= 0.05, finite tail quantiles, strict monotonicity and round-trip relative error <= 1e-9. Rank by p descending then AD statistic ascending.

- [ ] **Step 4: Integrate distribution assessment and immutable confirmation**

Original accepted distribution suppresses automatic recommendation. Otherwise attach `transformation_candidates` to `distribution_result`. Confirmation requires `spc.approve`, accepted candidate and reason, then creates a successor version. Recalculate charts/stability/capability using transformed scale while keeping original samples and returning risk/quantiles to original scale. Preserve `original_model`; time-model A1/A2 identity remains based on original data.

- [ ] **Step 5: Run tests and commit**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_transformations.py backend\tests\test_services\test_spc_distribution.py backend\tests\test_services\test_spc_analysis_service.py backend\tests\test_services\test_spc_study_service.py -q
git diff --check
git add backend/services/spc_transformations.py backend/services/spc_distribution.py backend/services/spc_study_service.py backend/routes/spc_studies.py backend/services/spc_analysis_service.py backend/tests/test_services/test_spc_transformations.py backend/tests/test_services/test_spc_distribution.py
git commit -m "功能：新增 Box-Cox 與 Johnson 轉換"
```

---

### Task 9: 診斷與分布轉換前端、出貨／巡檢深層連結

**Files:**
- Create: `src_frontend/src/components/spc/diagnostics/TimeDiagnosticPanel.tsx`
- Create: `src_frontend/src/components/spc/diagnostics/TimeDiagnosticPanel.test.tsx`
- Create: `src_frontend/src/components/spc/distribution/TransformationPanel.tsx`
- Create: `src_frontend/src/components/spc/distribution/TransformationPanel.test.tsx`
- Modify: `src_frontend/src/pages/spc/AdvancedSpcPage.tsx`
- Modify: `src_frontend/src/components/shipping/ShippingCharts.tsx`
- Modify: `src_frontend/src/components/shipping/ShippingCharts.test.tsx`
- Modify: `src_frontend/src/components/patrol/PatrolCharts.tsx`
- Modify: `src_frontend/src/components/patrol/PatrolCharts.test.tsx`
- Modify: `src_frontend/src/components/spc/SpcBaselineApprovalModal.tsx`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`
- Modify: `src_frontend/src/types/spc.ts`

**Interfaces:**
- Consumes: diagnostic evidence, transformation candidates and confirmation APIs.
- Produces: reason-required confirmation/override forms and prefilled deep links.

- [ ] **Step 1: Write failing UI behavior tests**

```tsx
it('改判時間模型時保留系統候選並要求理由', async () => {
  render(<TimeDiagnosticPanel version={c3Version} />);
  await user.selectOptions(screen.getByLabelText('確認模型'), 'C4');
  expect(screen.getByText('系統候選：C3')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '確認模型' })).toBeDisabled();
  await user.type(screen.getByLabelText('確認理由'), '已核對批次切換紀錄');
  expect(screen.getByRole('button', { name: '確認模型' })).toBeEnabled();
});

it('只允許確認已通過的轉換候選', () => {
  render(<TransformationPanel version={transformationVersion} />);
  expect(screen.getByRole('radio', { name: /Johnson SU/ })).toBeEnabled();
  expect(screen.getByRole('radio', { name: /Box-Cox/ })).toBeDisabled();
});
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
cd src_frontend
npm test -- --run src/components/spc/diagnostics/TimeDiagnosticPanel.test.tsx src/components/spc/distribution/TransformationPanel.test.tsx
```

Expected: missing component failures.

- [ ] **Step 3: Implement evidence and confirmation panels**

Add types for trend, change points, variance evidence, modality, model override and transformation candidate. Render system candidate separately from confirmed model. Require reason for every confirmation. Show original scale, transformed scale, parameters, AD p-value, round-trip status and reason codes.

```typescript
export type SpcTimeModelCode = 'A1' | 'A2' | 'B' | 'C1' | 'C2' | 'C3' | 'C4' | 'D';

export interface SpcTransformationCandidate {
  model: 'boxcox' | 'johnson_su' | 'johnson_sb' | 'johnson_sl';
  accepted: boolean;
  params: number[];
  p_value: number | null;
  ad_stat: number | null;
  roundtrip_error: number | null;
  reason_code: string | null;
}
```

- [ ] **Step 4: Add deep links and hook mutations**

Shipping link includes `family=variable&source=shipping&vendor&material&spec&field&start_date&end_date`. Patrol link includes machine/operator/customer/material/spec/item/position/date parameters. Add `useConfirmSpcTransformation` and extend `ConfirmSpcTimeModelInput` to all eight models.

- [ ] **Step 5: Run frontend suite and commit**

```powershell
cd src_frontend
npm test -- --run src/components/spc/diagnostics/TimeDiagnosticPanel.test.tsx src/components/spc/distribution/TransformationPanel.test.tsx src/components/shipping/ShippingCharts.test.tsx src/components/patrol/PatrolCharts.test.tsx src/pages/spc/AdvancedSpcPage.test.tsx
npm run lint
cd ..
git diff --check
git add src_frontend/src/components/spc/diagnostics src_frontend/src/components/spc/distribution src_frontend/src/pages/spc/AdvancedSpcPage.tsx src_frontend/src/components/shipping/ShippingCharts.tsx src_frontend/src/components/shipping/ShippingCharts.test.tsx src_frontend/src/components/patrol/PatrolCharts.tsx src_frontend/src/components/patrol/PatrolCharts.test.tsx src_frontend/src/components/spc/SpcBaselineApprovalModal.tsx src_frontend/src/hooks/useSpcStudies.ts src_frontend/src/types/spc.ts
git commit -m "功能：新增時間診斷與分布轉換介面"
```

---

### Task 10: 確效紀錄、migration、文件與完整驗證

**Files:**
- Modify: `backend/scripts/spc_regression.py`
- Create: `backend/scripts/spc_advanced_regression.py`
- Modify: `backend/services/spc_report.py`
- Modify: `backend/models.py:542-560`
- Modify: `docs/spc_validation.md`
- Create: `docs/migrations/38-spc-analysis-family-runbook.md`
- Test: `backend/tests/test_services/test_spc_golden.py`
- Test: `backend/tests/test_services/test_spc_report_versioning.py`
- Test: `backend/tests/test_services/test_spc_models.py`

**Interfaces:**
- Produces: deterministic `spc-advanced-golden-2026.2` validation payload.
- Produces: persisted `SpcValidationRun` with expected, actual, tolerances and PASS/FAIL.
- Produces: migration dry-run and rollback/runbook evidence.

- [ ] **Step 1: Write failing validation persistence test**

```python
def test_advanced_regression_persists_validation_run(app, db_session, admin_user):
    result = run_advanced_regression(executed_by=admin_user.id, persist=True)
    saved = SpcValidationRun.query.order_by(SpcValidationRun.id.desc()).first()
    assert result["result"] == "PASS"
    assert saved.dataset_version == "spc-advanced-golden-2026.2"
    assert saved.method_version == "2026.2"
    assert saved.result == "PASS"
    assert saved.actual["attribute"]["chart_type"] == "p"
    assert saved.actual["machine"]["pmk"] is not None
    assert saved.actual["time_models"]["D"] == "D"
```

- [ ] **Step 2: Run and verify RED**

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_models.py::test_advanced_regression_persists_validation_run -q
```

Expected: FAIL because advanced regression runner is absent.

- [ ] **Step 3: Implement advanced golden runner and validation persistence**

The runner must execute fixed p/np, Pm/Pmk, eight time-model and four transformation datasets; compare actual values to versioned expected JSON with explicit tolerances; reject NaN/Infinity; optionally persist `SpcValidationRun`. CLI output must end with:

```text
[PASS] SPC 2026.2 進階分析確效通過；屬性圖、機器績效、時間模型與分布轉換皆符合固定基準。
```

- [ ] **Step 4: Prepare and execute PostgreSQL migration safely**

Document exact commands in the runbook. Determine installed PostgreSQL bin path, then run without printing the password:

```powershell
Set-Item -Path Env:PGPASSWORD -Value '<由本機 .env 讀取，不寫入文件或輸出>'
psql -v ON_ERROR_STOP=1 -U postgres -d qa_database -f tmp/migration/38_dry_run.sql
psql -v ON_ERROR_STOP=1 -U postgres -d qa_database -f backend/migration/38_add_spc_analysis_family.sql
psql -U postgres -d qa_database -c '\d+ "SPC研究"'
psql -U postgres -d qa_database -c '\d+ "SPC界限版本"'
```

Before the formal migration, verify a current daily backup file exists without printing credentials. Create `tmp/migration/38_dry_run.sql` from the committed migration with final `COMMIT` replaced by `ROLLBACK` using an approved mechanical formatting command, verify its absolute path is under `C:\QC_Database\tmp\migration`, run it, then delete `tmp` after evidence is captured.

- [ ] **Step 5: Run full backend verification**

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q
venv\Scripts\python.exe backend\scripts\spc_regression.py
venv\Scripts\python.exe backend\scripts\spc_advanced_regression.py --persist
```

Expected: all backend tests pass, both regression scripts print PASS, and one validation record is saved.

- [ ] **Step 6: Run full frontend and repository verification**

```powershell
cd src_frontend
npm test
npm run lint
npm run build
npm audit
cd ..
git diff --check
git status --short
```

Expected: tests, lint, build and audit exit 0; only intended implementation/documentation changes remain.

- [ ] **Step 7: Review requirement coverage and commit final integration**

Check the design sections line-by-line: p/np eligibility and exact limits, machine N/conditions, all eight time models, four transformations, immutable successor versions, permissions, deep links, version reports, validation record and migration evidence. Then commit:

```powershell
git add backend/scripts/spc_regression.py backend/scripts/spc_advanced_regression.py backend/services/spc_report.py backend/models.py docs/spc_validation.md docs/migrations/38-spc-analysis-family-runbook.md backend/tests/test_services/test_spc_golden.py backend/tests/test_services/test_spc_report_versioning.py backend/tests/test_services/test_spc_models.py
git commit -m "驗證：完成 SPC 2026.2 進階分析確效"
```

Do not push unless the user explicitly requests it.
