# SQLAlchemy 與前端 Fast Refresh 警告清理實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除後端全量測試中的 4 項 SQLAlchemy LegacyAPIWarning，以及前端 ESLint 的 1 項 Fast Refresh warning，且不改變功能行為。

**Architecture:** 後端將舊式 `Query.get()` 換成 SQLAlchemy 2.x `Session.get()`，並透過 `options` 保留 eager loading。前端將非 React 的 TUS 色彩常數與函式移出元件模組，使 `TusChart.tsx` 只匯出 React 元件。

**Tech Stack:** Flask 3.1、SQLAlchemy 2.x、pytest、React 19、TypeScript、ESLint、Vitest、Vite

## Global Constraints

- 所有程式碼備註、說明與 commit 訊息使用繁體中文。
- 不使用 pytest warning filter、warning suppression、ESLint disable 或規則放寬隱藏警告。
- 不改變 API、資料模型、migration、交易範圍、TUS 色碼或圖表行為。
- `tmp/` 不得納入任何 commit。
- 後端全量 pytest 必須通過且沒有 warning summary。
- 前端 ESLint 必須為 `0 errors / 0 warnings`。

---

### Task 1: 遷移 SQLAlchemy 主鍵查詢 API

**Files:**
- Modify: `backend/services/extrusion_tolerance_service.py`
- Modify: `backend/services/tolerance_service.py`
- Modify: `backend/tests/test_services/test_shipping_position_roundtrip.py`

**Interfaces:**
- Produces: `ExtrusionToleranceService.get_detail()` 維持原回應與 `details` 預載。
- Produces: `ToleranceService.get_tolerance_detail()` 維持原回應與 `vendor`、`details` 預載。
- Produces: 測試重新讀取量測資料時使用 fixture session。

- [ ] **Step 1: 以 LegacyAPIWarning 視為錯誤重現失敗**

```powershell
venv\Scripts\python.exe -m pytest `
  backend\tests\test_services\test_extrusion_tolerance.py::test_extrusion_tolerance_detail_roundtrips_characteristic_class `
  backend\tests\test_services\test_tolerance.py::test_tolerance_detail_roundtrips_characteristic_class `
  backend\tests\test_services\test_shipping_position_roundtrip.py::test_set_measurement_exclusion_and_stats_skip `
  -W error::sqlalchemy.exc.LegacyAPIWarning -q
```

Expected: FAIL，三個測試共觸發 4 次 `LegacyAPIWarning`；失敗堆疊分別指向兩個 service `.get()` 與測試中的兩次 `.query.get()`。

- [ ] **Step 2: 將擠壓公差查詢改為 Session.get**

以以下程式取代 `ExtrusionToleranceMain.query.options(...).get(tolerance_id)`：

```python
t = db.session.get(
    ExtrusionToleranceMain,
    tolerance_id,
    options=[joinedload(ExtrusionToleranceMain.details)],
)
```

保留原本 `if not t` 與後續序列化內容。

- [ ] **Step 3: 將一般公差查詢改為 Session.get**

以以下程式取代 `VendorToleranceMain.query.options(...).get(tolerance_id)`：

```python
t = db.session.get(
    VendorToleranceMain,
    tolerance_id,
    options=[
        joinedload(VendorToleranceMain.vendor),
        joinedload(VendorToleranceMain.details),
    ],
)
```

保留原本找不到資料的 `ValueError` 與回應欄位。

- [ ] **Step 4: 將測試資料重新讀取改為 fixture session**

將兩次：

```python
ShippingMeasurement.query.get(m_id)
```

分別改為：

```python
db_session.get(ShippingMeasurement, m_id)
```

- [ ] **Step 5: 重新執行 warning-as-error 窄測試**

```powershell
venv\Scripts\python.exe -m pytest `
  backend\tests\test_services\test_extrusion_tolerance.py::test_extrusion_tolerance_detail_roundtrips_characteristic_class `
  backend\tests\test_services\test_tolerance.py::test_tolerance_detail_roundtrips_characteristic_class `
  backend\tests\test_services\test_shipping_position_roundtrip.py::test_set_measurement_exclusion_and_stats_skip `
  -W error::sqlalchemy.exc.LegacyAPIWarning -q
```

Expected: `3 passed`，沒有 warning summary。

- [ ] **Step 6: 提交後端警告修正**

```powershell
git add backend/services/extrusion_tolerance_service.py backend/services/tolerance_service.py backend/tests/test_services/test_shipping_position_roundtrip.py
git commit -m "修正：移除 SQLAlchemy 舊式主鍵查詢警告"
```

### Task 2: 抽離 TUS 圖表色彩模組

**Files:**
- Create: `src_frontend/src/components/pyrometry/tusChartColors.ts`
- Modify: `src_frontend/src/components/pyrometry/TusChart.tsx`
- Modify: `src_frontend/src/components/pyrometry/TusChart.test.tsx`

**Interfaces:**
- Produces: `EXCLUDED_COLOR: string`。
- Produces: `channelLineColor(index: number, excluded: boolean): string`。
- Consumes: `TusChart.tsx` 與色彩測試共同匯入上述介面。

- [ ] **Step 1: 重現 Fast Refresh lint warning**

Run: `npm run lint`

Workdir: `src_frontend`

Expected: exit code 0，但輸出 `TusChart.tsx:38:14 react-refresh/only-export-components`，共 `0 errors / 1 warning`。

- [ ] **Step 2: 建立純色彩模組**

建立 `tusChartColors.ts`：

```typescript
const COLORS = [
  '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
  '#dcbeff', '#9a6324',
];

export const EXCLUDED_COLOR = '#adb5bd';

export const channelLineColor = (index: number, excluded: boolean): string =>
  excluded ? EXCLUDED_COLOR : COLORS[index % COLORS.length];
```

- [ ] **Step 3: 讓 TusChart 只匯出 React 元件**

在 `TusChart.tsx` 增加：

```typescript
import { channelLineColor } from './tusChartColors';
```

刪除檔案內的 `COLORS`、`EXCLUDED_COLOR` 與 `channelLineColor` 宣告，保留所有呼叫點不變。

- [ ] **Step 4: 更新色彩測試匯入來源**

將：

```typescript
import { channelLineColor, EXCLUDED_COLOR } from './TusChart';
```

改為：

```typescript
import { channelLineColor, EXCLUDED_COLOR } from './tusChartColors';
```

測試斷言內容維持不變。

- [ ] **Step 5: 執行 TUS 色彩測試**

Run: `npm test -- --run src/components/pyrometry/TusChart.test.tsx`

Workdir: `src_frontend`

Expected: `2 passed`。

- [ ] **Step 6: 執行 ESLint 並確認零警告**

Run: `npm run lint`

Workdir: `src_frontend`

Expected: exit code 0，沒有問題摘要，`0 errors / 0 warnings`。

- [ ] **Step 7: 提交前端警告修正**

```powershell
git add src_frontend/src/components/pyrometry/tusChartColors.ts src_frontend/src/components/pyrometry/TusChart.tsx src_frontend/src/components/pyrometry/TusChart.test.tsx
git commit -m "重構：抽離 TUS 圖表色彩工具"
```

### Task 3: 全量無警告驗證

**Files:**
- Verify only; no new files expected.

**Interfaces:**
- Consumes: Tasks 1–2 的所有修正。
- Produces: 可合併與推送的完整驗證證據。

- [ ] **Step 1: 執行後端全量測試並將 LegacyAPIWarning 視為錯誤**

Run: `venv\Scripts\python.exe -m pytest backend\tests -W error::sqlalchemy.exc.LegacyAPIWarning -q`

Expected: 所有測試通過，沒有 warning summary。

- [ ] **Step 2: 執行前端全量測試**

Run: `npm test`

Workdir: `src_frontend`

Expected: 所有 Vitest 測試通過。

- [ ] **Step 3: 執行前端 ESLint**

Run: `npm run lint`

Workdir: `src_frontend`

Expected: exit code 0，無 warning。

- [ ] **Step 4: 執行 production build**

Run: `npm run build`

Workdir: `src_frontend`

Expected: TypeScript 與 Vite build 成功。

- [ ] **Step 5: 執行依賴與 Git 檢查**

Run: `npm audit`

Workdir: `src_frontend`

Expected: `found 0 vulnerabilities`。

Run: `git diff --check`

Expected: 沒有輸出。

Run: `git status --short`

Expected: 只允許主工作樹既有未追蹤的 `tmp/`；隔離工作區應完全乾淨。
