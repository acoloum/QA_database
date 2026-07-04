# TUS/SAT 圖表恆溫穩定期自動偵測起點 設計文件

日期：2026-07-04

## 背景與問題

上傳 TUS/SAT/爐體溫度記錄檔後，`applyParsedPyrometryData`
（`src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`）目前把「恆溫穩定期」
（rangeStart/rangeEnd）預設為**整段上傳資料**（`rangeStart=0`, `rangeEnd=lastIndex`）。

`TusChart.tsx` 的超限標色邏輯（`ptStateColor`/`ptIsOut`）只在 `inSoak(j)` 範圍內才判斷
「超上限／低於下限」。因為預設把整段資料（含爐溫爬升期）都當成穩定期，爬升期間
（溫度遠低於下限）的每一個資料點都會被誤判為「低於下限」而標記紅/藍色，在使用者
手動調整「開始/結束」之前，圖表會被爬升期大量的超限標記淹沒，難以判讀
（此問題與 2026-07-04 稍早修正的「畫布過矮」「正常點也畫圓點標記」等可讀性問題
是同一次使用者回報「上傳TUS溫度後，曲線圖看不清楚」的根本原因之一）。

## 目標

上傳後自動偵測一個合理的「恆溫穩定期起點」預設值，取代目前寫死的 `0`，讓使用者
不需要每次都手動拖動「開始」滑桿才能得到正確的超限判讀。**結束點維持不變**（仍是
資料最後一筆），本次只處理起點。

## 設計

### 核心演算法：`detectSoakStartIndex`

新增純函式於 `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`：

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

邏輯：從資料尾端往回掃描，找到「最後一個仍有任一通道超出公差區間
`[setpoint-tolerance, setpoint+tolerance]`」的索引 `i`，回傳 `i+1` 作為穩定期起點——
這保證從回傳值到資料結尾，所有通道都確實落在公差內，符合 CQI-9 對「恆溫穩定期」
的定義（所有量測點同時穩定在允收公差內）。

### 退化情況一律回退到 `0`（即現行行為：整段資料）

- `setpoint`/`tolerance` 非有限數字（使用者尚未填寫或格式無效）。
- 掃描全程都找不到任何超限點（`length===0` 或迴圈跑完未觸發，即一路都在公差內）：
  回傳 `0`（此時「回退」與「正確答案」剛好相同，因為整段資料本來就都合格）。
- 掃描到最後（`i=0`）仍是超限（代表資料自始至終都沒有真正穩定）：`start` 會等於
  `length`，超過 `length-2` 的門檻，回退到 `0`。
- 偵測到的穩定期不足 2 個點（`start > length-2`）：回退到 `0`。

### 套用範圍：TUS／SAT／爐體三種上傳路徑

`applyParsedPyrometryData` 目前對三種 `destination`（`'recorder'`/`'sat'`/`'furnace'`）
都把 `rangeStart`/`satRangeStart`/`furnaceRangeStart` 寫死為 `0`。三者都改為呼叫
`detectSoakStartIndex(chartData.數值, setpoint, tolerance)`。三種路徑共用同一份表單的
`setpoint`/`tolerance`（同一測試的設定溫度與允許公差），不需要額外狀態。

`rangeEnd`/`satRangeEnd`/`furnaceRangeEnd` **維持不變**，仍是 `lastIndex`。

### 函式簽章變更

`applyParsedPyrometryData` 新增兩個參數：

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
}) => { /* ... */ };
```

呼叫端 `PyrometryTestForm.tsx` 的 `handleFileUpload` 需把表單目前的 `setpoint`/
`tolerance`（字串 state）解析成數字後傳入：

```typescript
const handleFileUpload = async (file: File, dest: PyrometryUploadDestination) => {
  const r = await parseMutation.mutateAsync(file);
  if (!r.success) return;
  const result = applyParsedPyrometryData({
    destination: dest,
    parsedData: r.data,
    tusPoints,
    satPoints,
    setpoint: Number(setpoint),
    tolerance: Number(tolerance),
  });
  // ...其餘不變
};
```

`Number('')` 為 `0`（非 `NaN`），這會讓「設定溫度留空」被誤判為 `setpoint=0` 而非
「無效」。為避免這個陷阱，`handleFileUpload` 應比照表單其他地方的慣例，對空字串
明確轉成 `NaN`（例如 `setpoint.trim() === '' ? NaN : Number(setpoint)`），確保
`detectSoakStartIndex` 的 `Number.isFinite` 檢查能正確攔截「尚未填寫」的情況。

## 測試

### `detectSoakStartIndex`（新測試）

1. 正常爬升後穩定：回傳穩定期正確起點。
2. 全程都在公差內：回傳 `0`。
3. 全程都未穩定（結尾仍超限）：回傳 `0`。
4. 偵測到的穩定期不足 2 點：回傳 `0`。
5. `setpoint`/`tolerance` 為 `NaN`：回傳 `0`。
6. 多通道情境：某通道較晚才進入公差，起點應由「最晚穩定的通道」決定（取多通道
   中最大的穩定起點）。

### `applyParsedPyrometryData`（既有測試補充）

驗證三種 `destination`（`recorder`/`sat`/`furnace`）皆正確呼叫
`detectSoakStartIndex` 並帶出對應的 `rangeStart`/`satRangeStart`/
`furnaceRangeStart`；`rangeEnd`/`satRangeEnd`/`furnaceRangeEnd` 不受影響
（仍等於 `lastIndex`）。

## 不在此次範圍

- 自動偵測/裁切「結束點」（例如爐溫測試結束後的降溫段）——本次只處理起點。
- 後端（Python）同步這套偵測邏輯——這是純前端上傳後的即時預覽輔助，不影響
  已存檔資料的判定（判定邏輯仍以使用者最終確認、送出存檔的
  `穩定開始`/`穩定結束` 為準）。
