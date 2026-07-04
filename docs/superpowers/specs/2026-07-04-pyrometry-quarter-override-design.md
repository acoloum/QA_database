# 爐溫測試「季別」手動覆寫欄位 設計文件

日期：2026-07-04

## 背景

爐溫測試（TUS/SAT）的「季別」（如 2026Q2、2026Q3）目前完全由「測試日期」
自動計算（`backend/services/pyrometry_calculations.py` 的 `quarter_of(d)`）。
但實務上會遇到「Q2 的例行測試延到 7 月初才做」這類情況——測試日期落在下一季，
但這筆測試在稽核/排程意義上應該歸屬於原本的季別。

後端其實已經支援手動覆寫：`create_test`/`update_test` 的邏輯是
`quarter=data.get("季別") or quarter_of(test_date)`——只要 payload 有帶
非空的「季別」，就會採用該值；沒帶（或空字串）才會自動依日期計算。
但目前「新增/編輯爐溫測試」表單完全沒有暴露這個欄位，使用者無法從畫面
覆寫，只能任由系統依日期自動判定。

## 目標

在爐溫測試表單加入一個可編輯的「季別」欄位：
- 選擇「測試日期」時，自動帶入依日期計算出的預設季別。
- 使用者可以手動把這個值改成別的季別（例如把自動算出的 2026Q3 改成 2026Q2）。
- 編輯既有紀錄時，欄位顯示資料庫已存的季別值。
- 送出存檔時把這個欄位值一起送給後端；後端沿用既有的「有填用填的、沒填自動算」
  邏輯，不需要修改後端程式碼。
- 若使用者不慎把欄位清空，後端會自動退回依測試日期計算，不會因此出錯或
  存入空值。

## 設計

### 1. 前端新增純函式：依日期計算季別標籤

新增於 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`：

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

用 `getUTCFullYear`/`getUTCMonth`（而非 local time 的 `getFullYear`/`getMonth`）
是因為 `<input type="date">` 給的日期字串（如 `"2026-07-03"`）被 `new Date(...)`
解析成 UTC 午夜——若改用 local-time 存取子，在負時區（例如美洲）會被往前推
一天，季度邊界日（每季第一天）可能因此被誤判成上一季，用 UTC 存取子可避免
這個時區陷阱。邏輯與後端 `quarter_of(d) -> f"{d.year}Q{(d.month-1)//3+1}"`
完全對應。

### 2. `PyrometryTestForm.tsx`：新增 state 與自動帶入邏輯

新增 `const [quarter, setQuarter] = useState('');`（與其他表單欄位 state
並列）。

新增一個處理測試日期變更的 handler，選日期時同步自動帶入計算出的季別：

```typescript
const handleTestDateChange = (value: string) => {
  setTestDate(value);
  setQuarter(computeQuarterLabel(value));
};
```

`<PyrometryBasicSection>` 呼叫處的 `onTestDateChange={setTestDate}` 改為
`onTestDateChange={handleTestDateChange}`，並新增 `quarter={quarter}`、
`onQuarterChange={setQuarter}` 兩個 prop（`onQuarterChange` 讓使用者可以
手動覆寫，直接呼叫 `setQuarter`，不需要額外包裝函式）。

編輯既有紀錄的 `useEffect`（載入 `editData` 後的 `queueMicrotask` 區塊）
新增 `setQuarter(state.quarter);`，緊鄰其他 `setXxx(state.xxx)` 呼叫。

### 3. `PyrometryBasicSection.tsx`：新增輸入欄位

`Props` 介面新增 `quarter: string;` 與 `onQuarterChange: (value: string) => void;`。

在「測試日期」欄位之後新增一欄（`Col md={2}`，維持與同排其他窄欄位一致的
寬度）：

```tsx
<Col md={2}>
  <Form.Label>季別</Form.Label>
  <Form.Control size="sm" value={quarter} onChange={e => onQuarterChange(e.target.value)} />
</Col>
```

不加必填星號（`*`）——因為即使留空，後端也會自動退回依日期計算，不是
真正必要欄位。

### 4. `pyrometryPayload.ts`：payload 帶入季別

`BuildPyrometryPayloadInput` 新增 `quarter: string;`；`PyrometryPayload`
新增 `季別: string;`；`buildPyrometryPayload` 的參數解構與回傳物件都加入
對應欄位（`季別: quarter`）。

`PyrometryTestForm.tsx` 呼叫 `buildPyrometryPayload({...})` 的地方補上
`quarter,`。

### 5. `pyrometryFormHydration.ts`：編輯模式回填

`MainData` 型別新增 `季別?: string | null;`；`PyrometryEditFormState` 新增
`quarter: string;`；`buildPyrometryEditFormState` 的回傳物件新增
`quarter: toText(main.季別),`（沿用既有的 `toText` 轉換，`null`/`undefined`
一律轉空字串）。

## 測試

- `computeQuarterLabel`：涵蓋各季第一個月/最後一個月的邊界日期（如
  1、3、4、6、7、9、10、12 月）、無效日期字串、跨年份。
- `PyrometryBasicSection.test.tsx`（既有測試檔）補一個測試：渲染時傳入
  `quarter` 值應正確顯示、輸入變更應觸發 `onQuarterChange`。
- `pyrometryPayload.ts`、`pyrometryFormHydration.ts` 的既有測試補上
  `quarter`/`季別` 相關斷言。

## 不在此次範圍

- 不修改後端（`quarter_of`/`create_test`/`update_test` 的覆寫邏輯已存在
  且足夠）。
- 不做「季別格式驗證」（例如強制格式必須是 `\d{4}Q[1-4]`）——維持自由
  文字，信任使用者輸入，這與清單頁既有的「季別」篩選欄位（自由文字，
  placeholder「如 2026Q2」）風格一致。
- 不回溯修改既有已存檔測試的季別值——這是純粹的表單輸入能力擴充，
  既有紀錄的季別維持原值不變（除非使用者之後主動編輯該筆紀錄）。
