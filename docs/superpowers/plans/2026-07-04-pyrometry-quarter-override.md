# 爐溫測試「季別」手動覆寫欄位 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在爐溫測試表單加入可編輯的「季別」欄位，選日期時自動帶入計算值，使用者可手動覆寫（例如延遲測試仍歸屬原季別）。

**Architecture:** 新增純函式 `computeQuarterLabel(dateStr)` 依日期計算季別標籤；`PyrometryTestForm.tsx` 新增 `quarter` state，選測試日期時自動帶入計算值，並可被使用者手動修改；`PyrometryBasicSection.tsx` 新增對應輸入欄位；`pyrometryPayload.ts`/`pyrometryFormHydration.ts` 分別負責把這個欄位送出/回填。後端既有的「有填用填的、沒填自動算」邏輯不需修改。

**Tech Stack:** React + TypeScript；Vitest + Testing Library（前端測試）。純前端改動，不涉及後端。

---

## File Structure

| 檔案 | 動作 | 責任 |
|------|------|------|
| `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts` | 修改 | 新增 `computeQuarterLabel` |
| `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts` | 修改 | `computeQuarterLabel` 測試 |
| `src_frontend/src/pages/pyrometry/PyrometryBasicSection.tsx` | 修改 | 新增「季別」輸入欄位 |
| `src_frontend/src/pages/pyrometry/PyrometryBasicSection.test.tsx` | 修改 | 補新 props 與新測試 |
| `src_frontend/src/pages/pyrometry/pyrometryPayload.ts` | 修改 | payload 帶入 `季別` |
| `src_frontend/src/pages/pyrometry/pyrometryPayload.test.ts` | 修改 | 補 `quarter`/`季別` 斷言 |
| `src_frontend/src/pages/pyrometry/pyrometryFormHydration.ts` | 修改 | 編輯模式回填季別 |
| `src_frontend/src/pages/pyrometry/pyrometryFormHydration.test.ts` | 修改 | 補季別回填測試 |
| `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx` | 修改 | 新增 `quarter` state、自動帶入、串接 payload |

---

## Task 1: `computeQuarterLabel` 純函式（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`
- Test: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts`

- [ ] **Step 1: 寫失敗測試**

先讀 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts` 檔案開頭的 import 區塊，把：

```typescript
import {
  addSatReadingToPoint,
  applyParsedPyrometryData,
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  computeRangeStats,
  detectSoakStartIndex,
  inheritReportFields,
  parseActiveZone,
  parseOptionalChannel,
  parseRangeIndex,
  removeSatReadingFromPoint,
  splitReportFields,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';
```

改為（新增 `computeQuarterLabel`）：

```typescript
import {
  addSatReadingToPoint,
  applyParsedPyrometryData,
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  computeQuarterLabel,
  computeRangeStats,
  detectSoakStartIndex,
  inheritReportFields,
  parseActiveZone,
  parseOptionalChannel,
  parseRangeIndex,
  removeSatReadingFromPoint,
  splitReportFields,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';
```

在 `describe('pyrometryFormUtils', () => { ... })` 區塊內、`describe('detectSoakStartIndex', ...)` 這個巢狀區塊**之後**、describe 結尾的 `});` **之前**，新增：

```typescript
  describe('computeQuarterLabel', () => {
    it('computes Q1 for January (start of year)', () => {
      expect(computeQuarterLabel('2026-01-15')).toBe('2026Q1');
    });

    it('computes Q1 for March (end of Q1)', () => {
      expect(computeQuarterLabel('2026-03-31')).toBe('2026Q1');
    });

    it('computes Q2 for April (start of Q2)', () => {
      expect(computeQuarterLabel('2026-04-01')).toBe('2026Q2');
    });

    it('computes Q2 for June (end of Q2)', () => {
      expect(computeQuarterLabel('2026-06-30')).toBe('2026Q2');
    });

    it('computes Q3 for July (the late-test scenario)', () => {
      expect(computeQuarterLabel('2026-07-03')).toBe('2026Q3');
    });

    it('computes Q4 for October (start of Q4)', () => {
      expect(computeQuarterLabel('2026-10-01')).toBe('2026Q4');
    });

    it('computes Q4 for December (end of year)', () => {
      expect(computeQuarterLabel('2026-12-31')).toBe('2026Q4');
    });

    it('handles year rollover correctly', () => {
      expect(computeQuarterLabel('2027-01-01')).toBe('2027Q1');
    });

    it('returns empty string for invalid date strings', () => {
      expect(computeQuarterLabel('')).toBe('');
      expect(computeQuarterLabel('not-a-date')).toBe('');
    });
  });
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormUtils.test.ts`
Expected: FAIL（`computeQuarterLabel` 尚未從 `pyrometryFormUtils.ts` 匯出，import 會報錯）

- [ ] **Step 3: 實作 `computeQuarterLabel`**

在 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`，找到 `export const detectSoakStartIndex = (` 這個函式定義的**結尾**（`return 0;\n};` 之後），在 `export const applyParsedPyrometryData = ({` 這一行**之前**插入：

```typescript
export const computeQuarterLabel = (dateStr: string): string => {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '';
  const year = d.getUTCFullYear();
  const month = d.getUTCMonth() + 1;
  const q = Math.floor((month - 1) / 3) + 1;
  return `${year}Q${q}`;
};

```

（用 `getUTCFullYear`/`getUTCMonth` 而非 local time 的 `getFullYear`/`getMonth`，因為 `<input type="date">` 給的日期字串會被 `new Date(...)` 解析成 UTC 午夜，若改用 local-time 存取子，在負時區會被往前推一天，季度邊界日可能被誤判成上一季。）

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormUtils.test.ts`
Expected: PASS（含新增的 9 個 `computeQuarterLabel` 測試）

- [ ] **Step 5: 型別檢查**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 無錯誤

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts
git commit -m "$(cat <<'EOF'
新增 computeQuarterLabel 依日期計算季別標籤

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `PyrometryBasicSection.tsx` 新增季別輸入欄位（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/PyrometryBasicSection.tsx`
- Test: `src_frontend/src/pages/pyrometry/PyrometryBasicSection.test.tsx`

- [ ] **Step 1: 寫失敗測試**

在 `src_frontend/src/pages/pyrometry/PyrometryBasicSection.test.tsx`，找到現有的 `render(<PyrometryBasicSection ... />)` 呼叫，補上兩個新 prop（`quarter`、`onQuarterChange`）。把：

```tsx
    render(
      <PyrometryBasicSection
        furnaces={[{ 識別碼: 1, 爐號: 'F-1', 名稱: '時效爐', 製程類型: '', TUS點數: 12, SAT點數: 2, TUS頻率_月: 3, SAT頻率_月: 3, TUS允許公差: '10', SAT允許誤差: '5', 有效加熱區尺寸: '', 儀器型式: '', CQI9等級: '', 啟用狀態: true, 備註: '' }]}
        inspectors={[{ id: 9, name: '檢驗員A' }]}
        furnaceId=""
        testType="TUS"
        testDate="2026-06-27"
        setpoint="180"
        tolerance="10"
        testerId=""
        testInstrument=""
        stdInstrument=""
        calDueDate=""
        note=""
        onFurnaceChange={onFurnaceChange}
        onTestTypeChange={onTestTypeChange}
        onTestDateChange={vi.fn()}
        onSetpointChange={vi.fn()}
        onToleranceChange={vi.fn()}
        onTesterIdChange={vi.fn()}
        onTestInstrumentChange={vi.fn()}
        onStdInstrumentChange={vi.fn()}
        onCalDueDateChange={vi.fn()}
        onNoteChange={vi.fn()}
      />,
    );
```

改為：

```tsx
    render(
      <PyrometryBasicSection
        furnaces={[{ 識別碼: 1, 爐號: 'F-1', 名稱: '時效爐', 製程類型: '', TUS點數: 12, SAT點數: 2, TUS頻率_月: 3, SAT頻率_月: 3, TUS允許公差: '10', SAT允許誤差: '5', 有效加熱區尺寸: '', 儀器型式: '', CQI9等級: '', 啟用狀態: true, 備註: '' }]}
        inspectors={[{ id: 9, name: '檢驗員A' }]}
        furnaceId=""
        testType="TUS"
        testDate="2026-06-27"
        quarter="2026Q2"
        setpoint="180"
        tolerance="10"
        testerId=""
        testInstrument=""
        stdInstrument=""
        calDueDate=""
        note=""
        onFurnaceChange={onFurnaceChange}
        onTestTypeChange={onTestTypeChange}
        onTestDateChange={vi.fn()}
        onQuarterChange={vi.fn()}
        onSetpointChange={vi.fn()}
        onToleranceChange={vi.fn()}
        onTesterIdChange={vi.fn()}
        onTestInstrumentChange={vi.fn()}
        onStdInstrumentChange={vi.fn()}
        onCalDueDateChange={vi.fn()}
        onNoteChange={vi.fn()}
      />,
    );
```

在同一個 `it(...)` 測試的最後（`expect(onTestTypeChange).toHaveBeenCalledWith('SAT');` 之後），新增：

```tsx
    expect(screen.getByDisplayValue('2026Q2')).toBeInTheDocument();
```

在這個 `it(...)` 之後、`describe` 結尾的 `});` 之前，新增一個新測試：

```tsx
  it('notifies quarter changes when user edits the field', () => {
    const onQuarterChange = vi.fn();

    render(
      <PyrometryBasicSection
        furnaces={[]}
        inspectors={[]}
        furnaceId=""
        testType="TUS"
        testDate="2026-07-03"
        quarter="2026Q3"
        setpoint=""
        tolerance=""
        testerId=""
        testInstrument=""
        stdInstrument=""
        calDueDate=""
        note=""
        onFurnaceChange={vi.fn()}
        onTestTypeChange={vi.fn()}
        onTestDateChange={vi.fn()}
        onQuarterChange={onQuarterChange}
        onSetpointChange={vi.fn()}
        onToleranceChange={vi.fn()}
        onTesterIdChange={vi.fn()}
        onTestInstrumentChange={vi.fn()}
        onStdInstrumentChange={vi.fn()}
        onCalDueDateChange={vi.fn()}
        onNoteChange={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByDisplayValue('2026Q3'), { target: { value: '2026Q2' } });

    expect(onQuarterChange).toHaveBeenCalledWith('2026Q2');
  });
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/PyrometryBasicSection.test.tsx`
Expected: FAIL（`quarter`/`onQuarterChange` 目前不是 `Props` 的一部分，TypeScript 會報錯；畫面上也沒有顯示 '2026Q2' 的欄位）

- [ ] **Step 3: 修改 `PyrometryBasicSection.tsx`**

在 `Props` 介面裡，`testDate: string;` 這一行**之後**加入：

```typescript
  quarter: string;
```

在 `onTestDateChange: (value: string) => void;` 這一行**之後**加入：

```typescript
  onQuarterChange: (value: string) => void;
```

元件解構參數裡，`testDate,` 這一行**之後**加入 `quarter,`；`onTestDateChange,` 這一行**之後**加入 `onQuarterChange,`。

在 JSX 裡找到「測試日期」那個 `<Col md={2}>` 區塊：

```tsx
    <Col md={2}>
      <Form.Label>測試日期 *</Form.Label>
      <Form.Control size="sm" type="date" value={testDate} onChange={e => onTestDateChange(e.target.value)} />
    </Col>
```

在它**之後**新增一欄：

```tsx
    <Col md={2}>
      <Form.Label>季別</Form.Label>
      <Form.Control size="sm" value={quarter} onChange={e => onQuarterChange(e.target.value)} />
    </Col>
```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/PyrometryBasicSection.test.tsx`
Expected: PASS（含既有測試與新增測試，共 2 個）

- [ ] **Step 5: 型別檢查**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 出現錯誤——`PyrometryTestForm.tsx` 呼叫 `<PyrometryBasicSection>` 時缺少新增的必填 `quarter`/`onQuarterChange` prop。**這是預期中的狀態**，Task 5 會修正；請確認錯誤只指向這一處呼叫。

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/pyrometry/PyrometryBasicSection.tsx src_frontend/src/pages/pyrometry/PyrometryBasicSection.test.tsx
git commit -m "$(cat <<'EOF'
PyrometryBasicSection 新增季別輸入欄位

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `pyrometryPayload.ts` 帶入季別（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/pyrometryPayload.ts`
- Test: `src_frontend/src/pages/pyrometry/pyrometryPayload.test.ts`

- [ ] **Step 1: 更新既有測試，補上新的必填欄位**

在 `src_frontend/src/pages/pyrometry/pyrometryPayload.test.ts` 的第一個測試（`'builds a TUS payload with recorder curve data and report rows'`），找到 `buildPyrometryPayload({` 呼叫裡的：

```typescript
      testDate: '2026-06-19',
      setpoint: '180',
```

改為：

```typescript
      testDate: '2026-06-19',
      quarter: '2026Q2',
      setpoint: '180',
```

同一個測試的 `expect(payload).toEqual({...})` 斷言裡，找到：

```typescript
      測試日期: '2026-06-19',
      設定溫度: '180',
```

改為：

```typescript
      測試日期: '2026-06-19',
      季別: '2026Q2',
      設定溫度: '180',
```

第二個測試（`'builds a SAT payload with SAT and furnace curve data'`），找到 `buildPyrometryPayload({` 呼叫裡的：

```typescript
      testDate: '2026-06-19',
      setpoint: '180',
```

改為：

```typescript
      testDate: '2026-06-19',
      quarter: '2026Q3',
      setpoint: '180',
```

在該測試的 `expect(payload.測試人員).toBeNull();` 這行**之後**新增一行斷言：

```typescript
    expect(payload.季別).toBe('2026Q3');
```

第三個測試（`'rejects empty or invalid furnace ids before sending payload'`）裡的 `build` 函式，找到：

```typescript
      testDate: '2026-06-19',
      setpoint: '180',
```

改為：

```typescript
      testDate: '2026-06-19',
      quarter: '2026Q1',
      setpoint: '180',
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryPayload.test.ts`
Expected: FAIL——TypeScript 編譯錯誤（`buildPyrometryPayload` 目前不接受 `quarter` 這個屬性），以及第一個測試的 `toEqual` 斷言會因為缺少 `季別` 欄位而失敗

- [ ] **Step 3: 修改 `pyrometryPayload.ts`**

`BuildPyrometryPayloadInput` 介面裡，`testDate: string;` 這一行**之後**加入：

```typescript
  quarter: string;
```

`PyrometryPayload` 介面裡，`測試日期: string;` 這一行**之後**加入：

```typescript
  季別: string;
```

`buildPyrometryPayload` 的解構參數裡，`testDate,` 這一行**之後**加入 `quarter,`。

回傳物件裡，`測試日期: testDate,` 這一行**之後**加入：

```typescript
    季別: quarter,
```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryPayload.test.ts`
Expected: PASS（全部 3 個測試）

- [ ] **Step 5: 型別檢查**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 出現錯誤——`PyrometryTestForm.tsx` 呼叫 `buildPyrometryPayload({...})` 時缺少新增的必填 `quarter` 屬性（連同 Task 2 遺留的 `PyrometryBasicSection` 缺 prop 錯誤，這兩個都是預期中留給 Task 5 處理的狀態）。

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/pyrometry/pyrometryPayload.ts src_frontend/src/pages/pyrometry/pyrometryPayload.test.ts
git commit -m "$(cat <<'EOF'
buildPyrometryPayload 帶入季別欄位

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `pyrometryFormHydration.ts` 編輯模式回填季別（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/pyrometryFormHydration.ts`
- Test: `src_frontend/src/pages/pyrometry/pyrometryFormHydration.test.ts`

- [ ] **Step 1: 更新既有測試補上季別，並新增斷言**

在 `src_frontend/src/pages/pyrometry/pyrometryFormHydration.test.ts` 的第一個測試，找到 `main: {` 物件裡的：

```typescript
        測試日期: '2026-06-20',
        設定溫度: '180',
```

改為：

```typescript
        測試日期: '2026-06-20',
        季別: '2026Q2',
        設定溫度: '180',
```

在 `expect(state).toMatchObject({` 斷言裡，找到：

```typescript
      testDate: '2026-06-20',
      setpoint: '180',
```

改為：

```typescript
      testDate: '2026-06-20',
      quarter: '2026Q2',
      setpoint: '180',
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormHydration.test.ts`
Expected: FAIL（`state.quarter` 目前是 `undefined`，跟斷言的 `'2026Q2'` 不符）

- [ ] **Step 3: 修改 `pyrometryFormHydration.ts`**

`MainData` 型別裡，`測試日期?: string | null;` 這一行**之後**加入：

```typescript
  季別?: string | null;
```

`PyrometryEditFormState` 型別裡，`testDate: string;` 這一行**之後**加入：

```typescript
  quarter: string;
```

`buildPyrometryEditFormState` 函式裡的 `state` 物件字面量，找到：

```typescript
    testDate: toText(main.測試日期),
    setpoint: toText(main.設定溫度),
```

改為：

```typescript
    testDate: toText(main.測試日期),
    quarter: toText(main.季別),
    setpoint: toText(main.設定溫度),
```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormHydration.test.ts`
Expected: PASS（含既有測試與更新後的斷言，共 2 個測試）

- [ ] **Step 5: 型別檢查**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 錯誤數量與 Task 3 結束時相同（`PyrometryTestForm.tsx` 尚未接上 `quarter` state，這是 Task 5 的範圍），沒有新增其他錯誤。

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/pyrometry/pyrometryFormHydration.ts src_frontend/src/pages/pyrometry/pyrometryFormHydration.test.ts
git commit -m "$(cat <<'EOF'
buildPyrometryEditFormState 回填季別

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `PyrometryTestForm.tsx` 串接季別 state（收尾）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`

- [ ] **Step 1: 新增 `quarter` state**

找到：

```typescript
  const [testDate, setTestDate] = useState('');
```

在它**之後**加入：

```typescript
  const [quarter, setQuarter] = useState('');
```

- [ ] **Step 2: 新增測試日期變更 handler，自動帶入計算值**

在檔案開頭的 import 區塊，找到從 `./pyrometryFormUtils` 匯入的區塊：

```typescript
import {
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  addSatReadingToPoint,
  applyParsedPyrometryData,
  emptyItemRow,
  emptySatPoint,
  emptyTusPoint,
  inheritReportFields,
  removeSatReadingFromPoint,
  type ChartData,
  type ItemRow,
  type PyrometryUploadDestination,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';
```

改為（新增 `computeQuarterLabel`）：

```typescript
import {
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  addSatReadingToPoint,
  applyParsedPyrometryData,
  computeQuarterLabel,
  emptyItemRow,
  emptySatPoint,
  emptyTusPoint,
  inheritReportFields,
  removeSatReadingFromPoint,
  type ChartData,
  type ItemRow,
  type PyrometryUploadDestination,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';
```

找到 `applyFurnaceDefaults` 函式定義（在 `useState` 宣告區塊之後），在它**之前**加入一個新的 handler：

```typescript
  const handleTestDateChange = (value: string) => {
    setTestDate(value);
    setQuarter(computeQuarterLabel(value));
  };

```

- [ ] **Step 3: 編輯模式回填**

找到編輯資料的 `useEffect` 裡的 `queueMicrotask` 區塊：

```typescript
      setTestDate(state.testDate);
      setSetpoint(state.setpoint);
```

改為：

```typescript
      setTestDate(state.testDate);
      setQuarter(state.quarter);
      setSetpoint(state.setpoint);
```

- [ ] **Step 4: `<PyrometryBasicSection>` 呼叫處接上新 prop**

找到：

```tsx
            testDate={testDate}
            setpoint={setpoint}
            tolerance={tolerance}
            testerId={testerId}
            testInstrument={testInstrument}
            stdInstrument={stdInstrument}
            calDueDate={calDueDate}
            note={note}
            onFurnaceChange={value => { setFurnaceId(value); applyFurnaceDefaults(value, testType); }}
            onTestTypeChange={value => { setTestType(value); applyFurnaceDefaults(furnaceId, value); }}
            onTestDateChange={setTestDate}
            onSetpointChange={setSetpoint}
```

改為：

```tsx
            testDate={testDate}
            quarter={quarter}
            setpoint={setpoint}
            tolerance={tolerance}
            testerId={testerId}
            testInstrument={testInstrument}
            stdInstrument={stdInstrument}
            calDueDate={calDueDate}
            note={note}
            onFurnaceChange={value => { setFurnaceId(value); applyFurnaceDefaults(value, testType); }}
            onTestTypeChange={value => { setTestType(value); applyFurnaceDefaults(furnaceId, value); }}
            onTestDateChange={handleTestDateChange}
            onQuarterChange={setQuarter}
            onSetpointChange={setSetpoint}
```

- [ ] **Step 5: `buildPyrometryPayload` 呼叫處帶入 `quarter`**

找到：

```typescript
      const payload = buildPyrometryPayload({
        furnaceId,
        testType,
        testDate,
        setpoint,
```

改為：

```typescript
      const payload = buildPyrometryPayload({
        furnaceId,
        testType,
        testDate,
        quarter,
        setpoint,
```

- [ ] **Step 6: 型別檢查確認乾淨**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 完全無輸出/無錯誤（Task 2/3/4 遺留的缺參數錯誤這次應該被徹底解決）

- [ ] **Step 7: 執行完整前端測試套件**

Run: `cd src_frontend && npx vitest run`
Expected: 全部通過

- [ ] **Step 8: Lint 檢查**

Run: `cd src_frontend && npm run lint`
Expected: 0 個 error（既有的 `TusChart.tsx` `react-refresh/only-export-components` warning 是已知可接受的既有狀態，不需要處理）

- [ ] **Step 9: Production build 驗證**

Run: `cd src_frontend && npm run build`
Expected: 成功

- [ ] **Step 10: Commit**

```bash
git add src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx
git commit -m "$(cat <<'EOF'
表單接上季別 state，選日期自動帶入並可手動覆寫

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 瀏覽器手動驗證

**Files:** 無（操作）

- [ ] **Step 1: 啟動前後端，實際操作驗證**

啟動開發伺服器（前端 `npm run dev`、後端啟動 Flask，皆在 venv 環境），登入系統，開啟「爐溫測試紀錄」→「+新增」：
1. 選擇日期 2026-07-03，確認「季別」欄位自動帶入 `2026Q3`。
2. 手動把「季別」改成 `2026Q2`，確認欄位可正常編輯。
3. 填完必要欄位並儲存，於清單頁確認該筆紀錄的「季別」欄顯示 `2026Q2`（而非依日期自動算出的 `2026Q3`）。
4. 重新開啟該筆紀錄進行編輯，確認「季別」欄位正確回填 `2026Q2`。

- [ ] **Step 2: 若有微調，收尾 commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
季別欄位端到端驗證微調

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

（若手動驗證沒有發現問題、無需微調，跳過此步驟即可，不需要空 commit。）

---

## 備註 / 不在範圍

- 不修改後端——`quarter_of`/`create_test`/`update_test` 的覆寫邏輯已存在且足夠。
- 不做「季別格式驗證」——維持自由文字，與清單頁既有的「季別」篩選欄位風格一致。
- 不回溯修改既有已存檔測試的季別值。
