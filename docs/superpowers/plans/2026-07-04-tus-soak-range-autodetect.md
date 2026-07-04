# TUS/SAT 圖表恆溫穩定期自動偵測起點 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上傳 TUS/SAT/爐體溫度記錄檔後，自動偵測一個合理的「恆溫穩定期」起點（取代目前寫死的 `0`），避免爬升期被誤判超限而讓圖表看不清楚。

**Architecture:** 新增純函式 `detectSoakStartIndex`（從資料尾端往回掃描，找到最後一個仍超出公差的索引，取其後一格），在 `applyParsedPyrometryData` 對 TUS/SAT/爐體三種上傳目的地統一呼叫，取代原本寫死的 `rangeStart: 0`。結束點維持不變。呼叫端 `PyrometryTestForm.tsx` 的 `handleFileUpload` 多帶入表單目前的 `setpoint`/`tolerance`（空字串需明確轉 `NaN`，避免 `Number('')===0` 造成誤判）。

**Tech Stack:** React + TypeScript；Vitest（前端測試）。純前端改動，不涉及後端。

---

## File Structure

| 檔案 | 動作 | 責任 |
|------|------|------|
| `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts` | 修改 | 新增 `detectSoakStartIndex`；`applyParsedPyrometryData` 改用其偵測結果 |
| `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts` | 修改 | 新增 `detectSoakStartIndex` 單元測試；更新/新增 `applyParsedPyrometryData` 測試 |
| `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx` | 修改 | `handleFileUpload` 呼叫 `applyParsedPyrometryData` 時多帶入 `setpoint`/`tolerance`（空字串轉 `NaN`） |

---

## Task 1: `detectSoakStartIndex` 純函式（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`
- Test: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts`

- [ ] **Step 1: 寫失敗測試**

在 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts` 檔案開頭 import 區塊，把：

```typescript
import {
  addSatReadingToPoint,
  applyParsedPyrometryData,
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  computeRangeStats,
  inheritReportFields,
  parseActiveZone,
  parseOptionalChannel,
  parseRangeIndex,
  removeSatReadingFromPoint,
  splitReportFields,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';
```

改為（新增 `detectSoakStartIndex`）：

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

在 `describe('pyrometryFormUtils', () => { ... })` 區塊內、最後一個 `it(...)`（`'applies parsed furnace data to SAT control readings'`）**之後**、`});`（describe 結尾）**之前**，新增：

```typescript
  describe('detectSoakStartIndex', () => {
    it('finds the soak start index once all channels enter the tolerance band and stay there', () => {
      expect(detectSoakStartIndex({ CH1: [100, 150, 178, 182, 181, 180] }, 180, 5)).toBe(2);
    });

    it('returns 0 when every value is already within tolerance', () => {
      expect(detectSoakStartIndex({ CH1: [180, 181, 179, 180] }, 180, 5)).toBe(0);
    });

    it('returns 0 when the data never stabilizes (still out of range at the end)', () => {
      expect(detectSoakStartIndex({ CH1: [100, 110, 120, 130] }, 180, 5)).toBe(0);
    });

    it('returns 0 when fewer than 2 stable points remain at the tail', () => {
      expect(detectSoakStartIndex({ CH1: [100, 150, 170, 181] }, 180, 5)).toBe(0);
    });

    it('returns 0 when setpoint or tolerance is not a finite number', () => {
      expect(detectSoakStartIndex({ CH1: [180, 181] }, NaN, 5)).toBe(0);
      expect(detectSoakStartIndex({ CH1: [180, 181] }, 180, NaN)).toBe(0);
    });

    it('returns 0 when there are no channels', () => {
      expect(detectSoakStartIndex({}, 180, 5)).toBe(0);
    });

    it('uses the channel that stabilizes latest across multiple channels', () => {
      expect(detectSoakStartIndex({
        CH1: [175, 181, 180, 181],
        CH2: [100, 150, 178, 181],
      }, 180, 5)).toBe(2);
    });
  });
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormUtils.test.ts`
Expected: FAIL（`detectSoakStartIndex` 尚未從 `pyrometryFormUtils.ts` 匯出，import 會報錯）

- [ ] **Step 3: 實作 `detectSoakStartIndex`**

在 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`，找到 `export const applyParsedPyrometryData = ({` 這一行（檔案第 156 行附近），在它**之前**插入：

```typescript
export const detectSoakStartIndex = (
  數值: Record<string, number[]>,
  setpoint: number,
  tolerance: number,
): number => {
  const channels = Object.values(數值);
  if (!channels.length) return 0;
  const length = channels[0].length;
  if (length === 0 || !Number.isFinite(setpoint) || !Number.isFinite(tolerance)) return 0;
  const upper = setpoint + tolerance;
  const lower = setpoint - tolerance;
  for (let i = length - 1; i >= 0; i--) {
    const anyOut = channels.some(vals => {
      const v = vals[i];
      return v == null || v < lower || v > upper;
    });
    if (anyOut) {
      const start = i + 1;
      return start <= length - 2 ? start : 0;
    }
  }
  return 0;
};

```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormUtils.test.ts`
Expected: PASS（含新增的 7 個 `detectSoakStartIndex` 測試；既有測試此時應仍全部通過，因為還沒改動 `applyParsedPyrometryData` 的呼叫端）

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts
git commit -m "$(cat <<'EOF'
新增 detectSoakStartIndex 偵測恆溫穩定期起點

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 把 `detectSoakStartIndex` 接進 `applyParsedPyrometryData`（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`
- Test: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts`

- [ ] **Step 1: 更新兩個既有的 `applyParsedPyrometryData` 測試，補上新的必填參數**

找到：

```typescript
  it('applies parsed recorder data and returns the range plus updated TUS points', () => {
    const result = applyParsedPyrometryData({
      destination: 'recorder',
      parsedData: {
        時間: ['09:00', '09:10'],
        數值: { CH1: [180, 181] },
      },
      tusPoints: [{ 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }],
      satPoints: [],
    });
```

改為（加入 `setpoint: NaN, tolerance: NaN`，代表「使用者尚未填寫」，驗證回退到現行行為）：

```typescript
  it('applies parsed recorder data and returns the range plus updated TUS points', () => {
    const result = applyParsedPyrometryData({
      destination: 'recorder',
      parsedData: {
        時間: ['09:00', '09:10'],
        數值: { CH1: [180, 181] },
      },
      tusPoints: [{ 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }],
      satPoints: [],
      setpoint: NaN,
      tolerance: NaN,
    });
```

（該測試其餘的 `expect(...)` 斷言全部不變。）

找到：

```typescript
  it('applies parsed furnace data to SAT control readings', () => {
    const result = applyParsedPyrometryData({
      destination: 'furnace',
      parsedData: {
        時間: ['09:00'],
        數值: { F1: [180.123] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [{ 控制儀表讀值: '', 校正測試讀值: '181' }],
      }],
    });
```

改為（加入 `setpoint: NaN, tolerance: NaN`）：

```typescript
  it('applies parsed furnace data to SAT control readings', () => {
    const result = applyParsedPyrometryData({
      destination: 'furnace',
      parsedData: {
        時間: ['09:00'],
        數值: { F1: [180.123] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [{ 控制儀表讀值: '', 校正測試讀值: '181' }],
      }],
      setpoint: NaN,
      tolerance: NaN,
    });
```

（該測試其餘的 `expect(...)` 斷言全部不變。）

在這兩個測試**之後**（仍在 `describe('pyrometryFormUtils', ...)` 區塊內，`describe('detectSoakStartIndex', ...)` 這個巢狀區塊**之前**）新增三個測試，驗證 TUS/SAT/爐體三條路徑都真的接上了自動偵測：

```typescript
  it('auto-detects TUS soak start from setpoint/tolerance and trims stats accordingly', () => {
    const result = applyParsedPyrometryData({
      destination: 'recorder',
      parsedData: {
        時間: ['09:00', '09:10', '09:20', '09:30'],
        數值: { CH1: [100, 150, 178, 182] },
      },
      tusPoints: [{ 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }],
      satPoints: [],
      setpoint: 180,
      tolerance: 5,
    });

    expect(result.rangeStart).toBe(2);
    expect(result.rangeEnd).toBe(3);
    expect(result.tusPoints?.[0]).toMatchObject({ 最高溫: '182', 最低溫: '178' });
  });

  it('auto-detects SAT soak start from setpoint/tolerance', () => {
    const result = applyParsedPyrometryData({
      destination: 'sat',
      parsedData: {
        時間: ['09:00', '09:10', '09:20', '09:30'],
        數值: { CH13: [100, 150, 178, 182] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [
          { 控制儀表讀值: '180', 校正測試讀值: '' },
          { 控制儀表讀值: '180', 校正測試讀值: '' },
        ],
      }],
      setpoint: 180,
      tolerance: 5,
    });

    expect(result.satRangeStart).toBe(2);
    expect(result.satRangeEnd).toBe(3);
    expect(result.satPoints?.[0].readings).toEqual([
      { 控制儀表讀值: '180', 校正測試讀值: '178' },
      { 控制儀表讀值: '180', 校正測試讀值: '182' },
    ]);
  });

  it('auto-detects furnace body soak start from setpoint/tolerance', () => {
    const result = applyParsedPyrometryData({
      destination: 'furnace',
      parsedData: {
        時間: ['09:00', '09:10', '09:20', '09:30'],
        數值: { F1: [100, 150, 178, 182] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [
          { 控制儀表讀值: '', 校正測試讀值: '181' },
          { 控制儀表讀值: '', 校正測試讀值: '182' },
        ],
      }],
      setpoint: 180,
      tolerance: 5,
    });

    expect(result.furnaceRangeStart).toBe(2);
    expect(result.furnaceRangeEnd).toBe(3);
    expect(result.satPoints?.[0].readings).toEqual([
      { 控制儀表讀值: '178', 校正測試讀值: '181' },
      { 控制儀表讀值: '182', 校正測試讀值: '182' },
    ]);
  });
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormUtils.test.ts`
Expected: FAIL——TypeScript 編譯錯誤（`applyParsedPyrometryData` 目前的參數型別沒有 `setpoint`/`tolerance`，也沒有 `destination: 'sat'`/`'furnace'` 對應的必填欄位缺漏之外的問題；主要是新增的三個測試會因為函式尚未改為使用 `soakStart` 而斷言失敗，例如 `rangeStart` 目前仍會是 `0` 而非預期的 `2`）

- [ ] **Step 3: 修改 `applyParsedPyrometryData` 實作**

在 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`，找到完整的 `applyParsedPyrometryData` 函式：

```typescript
export const applyParsedPyrometryData = ({
  destination,
  parsedData,
  tusPoints,
  satPoints,
}: {
  destination: PyrometryUploadDestination;
  parsedData: ChartData;
  tusPoints: TusPoint[];
  satPoints: SatPoint[];
}) => {
  const chartData = { 時間: parsedData.時間, 數值: parsedData.數值 };
  const lastIndex = Math.max(chartData.時間.length - 1, 0);

  if (destination === 'recorder') {
    return {
      chartData,
      rangeStart: 0,
      rangeEnd: lastIndex,
      tusPoints: applyChartRangeToTusPoints(tusPoints, chartData, 0, lastIndex),
    };
  }

  if (destination === 'sat') {
    return {
      satChartData: chartData,
      satRangeStart: 0,
      satRangeEnd: lastIndex,
      satPoints: applyChartRangeToSatReadings(satPoints, chartData, 0, lastIndex, '校正測試讀值'),
    };
  }

  return {
    furnaceChartData: chartData,
    furnaceRangeStart: 0,
    furnaceRangeEnd: lastIndex,
    satPoints: applyChartRangeToSatReadings(satPoints, chartData, 0, lastIndex, '控制儀表讀值'),
  };
};
```

整段改為：

```typescript
export const applyParsedPyrometryData = ({
  destination,
  parsedData,
  tusPoints,
  satPoints,
  setpoint,
  tolerance,
}: {
  destination: PyrometryUploadDestination;
  parsedData: ChartData;
  tusPoints: TusPoint[];
  satPoints: SatPoint[];
  setpoint: number;
  tolerance: number;
}) => {
  const chartData = { 時間: parsedData.時間, 數值: parsedData.數值 };
  const lastIndex = Math.max(chartData.時間.length - 1, 0);
  const soakStart = detectSoakStartIndex(chartData.數值, setpoint, tolerance);

  if (destination === 'recorder') {
    return {
      chartData,
      rangeStart: soakStart,
      rangeEnd: lastIndex,
      tusPoints: applyChartRangeToTusPoints(tusPoints, chartData, soakStart, lastIndex),
    };
  }

  if (destination === 'sat') {
    return {
      satChartData: chartData,
      satRangeStart: soakStart,
      satRangeEnd: lastIndex,
      satPoints: applyChartRangeToSatReadings(satPoints, chartData, soakStart, lastIndex, '校正測試讀值'),
    };
  }

  return {
    furnaceChartData: chartData,
    furnaceRangeStart: soakStart,
    furnaceRangeEnd: lastIndex,
    satPoints: applyChartRangeToSatReadings(satPoints, chartData, soakStart, lastIndex, '控制儀表讀值'),
  };
};
```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/pyrometryFormUtils.test.ts`
Expected: PASS（全部測試，含 Task 1 的 7 個 + Task 2 更新/新增的 5 個）

- [ ] **Step 5: 型別檢查**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 出現錯誤——`PyrometryTestForm.tsx` 呼叫 `applyParsedPyrometryData` 時缺少新增的必填 `setpoint`/`tolerance` 參數。**這是預期中的狀態**，Task 3 會修正；先確認錯誤訊息只指向 `PyrometryTestForm.tsx` 這一處呼叫，沒有其他新增的型別錯誤。

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts src_frontend/src/pages/pyrometry/pyrometryFormUtils.test.ts
git commit -m "$(cat <<'EOF'
applyParsedPyrometryData 改用自動偵測的恆溫穩定期起點

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 呼叫端傳入 `setpoint`/`tolerance`（含空字串防呆）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`

- [ ] **Step 1: 修改 `handleFileUpload`**

在 `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`，找到：

```typescript
  const handleFileUpload = async (file: File, dest: PyrometryUploadDestination) => {
    const r = await parseMutation.mutateAsync(file);
    if (!r.success) return;
    const result = applyParsedPyrometryData({
      destination: dest,
      parsedData: r.data,
      tusPoints,
      satPoints,
    });
```

改為（新增一個小 helper 把空字串轉成 `NaN`，避免 `Number('')` 得到 `0` 而誤判為「設定溫度=0」）：

```typescript
  const handleFileUpload = async (file: File, dest: PyrometryUploadDestination) => {
    const r = await parseMutation.mutateAsync(file);
    if (!r.success) return;
    const toNumberOrNaN = (value: string) => (value.trim() === '' ? NaN : Number(value));
    const result = applyParsedPyrometryData({
      destination: dest,
      parsedData: r.data,
      tusPoints,
      satPoints,
      setpoint: toNumberOrNaN(setpoint),
      tolerance: toNumberOrNaN(tolerance),
    });
```

（`setpoint`/`tolerance` 是同一個元件裡既有的 state，直接沿用，不需要額外宣告。）

- [ ] **Step 2: 型別檢查確認乾淨**

Run: `cd src_frontend && npx tsc -b --force`
Expected: 完全無輸出/無錯誤

- [ ] **Step 3: 執行完整前端測試套件**

Run: `cd src_frontend && npx vitest run`
Expected: 全部通過（含 Task 1/2 新增與修改的測試）

- [ ] **Step 4: Lint 檢查**

Run: `cd src_frontend && npm run lint`
Expected: 0 個 error（既有的 `TusChart.tsx` `react-refresh/only-export-components` warning 是已知可接受的既有狀態，不需處理）

- [ ] **Step 5: Production build 驗證**

Run: `cd src_frontend && npm run build`
Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx
git commit -m "$(cat <<'EOF'
上傳時帶入設定溫度與允許公差以偵測恆溫穩定期起點

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## 備註 / 不在範圍

- 不自動偵測/裁切「結束點」（例如降溫段）——本次只處理起點，結束點永遠是資料最後一筆。
- 不動後端——這是純前端上傳後的即時預覽輔助，不影響已存檔資料的判定邏輯。
- 若想手動驗證效果：啟動前後端、登入、開啟「爐溫測試紀錄」→「+新增」→ 選爐子、填入設定溫度與允許公差 → 上傳含有明顯爬升期的 CSV，確認「開始」下拉選單預設值不再是資料第一筆，而是接近進入公差區間的那一筆。
