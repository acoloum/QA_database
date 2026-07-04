# 爐溫測試量測點排除（不列入計算）設計

日期：2026-07-04
範圍：TUS + SAT

## 背景與目的

爐溫測試（CQI-9）進行時，若某支熱電偶／某個頻道整體測溫異常（感測失效），該頻道
的所有值需要從測試中「捨棄，不列入計算」。目前系統無此機制：`evaluate_tus` /
`evaluate_sat` 會把傳入的每一個量測點都納入均勻度與判定計算，前端明細表也沒有排除
選項或刪列功能。

本設計新增「逐頻道（逐量測點）排除」能力：被排除的頻道不列入計算與判定，但資料仍
保留、於報表與曲線上以可辨識方式呈現，並要求填寫排除原因以利稽核。

## 行為需求（已與使用者確認）

1. 被排除的頻道在**報表中仍顯示，並標註「已排除」**（含原因）。
2. 被排除的頻道在**曲線圖畫成灰色**（取消超限紅/藍標記）。
3. **排除原因強制填寫**（前後端雙重把關）。
4. **不做**「有效點數低於下限就擋存檔」的驗證（暫不納入 CQI-9 最少熱電偶數檢查）。

## 方法選擇

採「在量測點列本身加旗標」：於 `TusPoint` / `SatPoint` 各加 `已排除`、`排除原因`
兩欄。改動集中、與現有資料結構貼合，排除狀態隨該點移動。（另評估過「另建排除記錄
表」與「點位狀態 enum」，皆為過度設計，不採用。）

## 設計細節

### 1. 資料模型

Migration `backend/migration/31_add_point_exclusion.sql`：

- `TUS量測點明細`：新增 `已排除 BOOLEAN NOT NULL DEFAULT false`、`排除原因 TEXT NULL`
- `SAT量測點明細`：同上兩欄

`backend/models.py`：於 `TusPoint`、`SatPoint` 對應加欄位
（`excluded` 對映 `已排除`、`exclude_reason` 對映 `排除原因`）。

### 2. 判定邏輯（`backend/services/pyrometry_calculations.py`）

- `evaluate_tus`：`已排除=True` 的點 **不計入** `all_max`/`all_min`（均勻度極差、
  最大正/負偏差）與 `overall_pass`；該點回傳 `最大偏差=None`、`是否合格=None`、
  `已排除=True`，仍保留於 `points`（供持久化與顯示）。
- `evaluate_sat`：`已排除=True` 的控溫區同樣不計入 `overall_pass`，其讀值偏差不參與
  判定；回傳時標記 `已排除=True`。

### 3. 服務層（`backend/services/pyrometry_service.py`）

- `create_test` / `update_test`：讀取 payload 的 `已排除`、`排除原因` 寫入點；
  序列化 detail（`_serialize_*`）時帶出這兩個欄位。
- 驗證（`validate_test_payload` 或存檔前）：任一點 `已排除=true` 而 `排除原因` 為空
  → 丟 `PyrometryValidationError("排除的量測點必須填寫排除原因")`。

### 4. 報表（`backend/services/pyrometry_report.py`）

- `build_tus_sheet` / `build_sat_sheet`：已排除列仍輸出，整列套灰底
  （新增 `_EXCLUDED_FILL`），判定欄顯示「已排除：<原因>」；該列不進入 `worst`
  彙總（彙總取自已扣除的判定結果，天然一致）。
- 原始數據曲線（`build_raw_sheet` 及圖表）：被排除的頻道線條畫成灰色。

### 5. 曲線元件（`src_frontend/src/components/pyrometry/TusChart.tsx`）

- 灰色化主要適用 **TUS 原始溫度曲線**（SAT 為控制/測試讀值比對，無時間序列曲線，
  其排除僅反映於明細表與報表）。
- `TusChart` 新增 `excludedChannels?: string[]`（點位名集合）prop：命中頻道線條改灰色
  （如 `#adb5bd`）、`ptStateColor`/`ptIsOut` 對該頻道一律回傳灰色 / false、圖例灰階。

### 6. 前端表單

- `src_frontend/src/types/index.ts`：`TusPoint`、`SatPoint` 型別加
  `已排除?: boolean`、`排除原因?: string`。
- `TusSection.tsx` / `SatSection.tsx`：明細表加「排除」勾選欄與「排除原因」輸入
  （未勾選時原因欄停用；勾選後必填）。勾選的點位名彙整後傳給對應曲線圖做灰色化。
- `PyrometryTestForm.tsx`：存檔前擋「已排除但未填原因」；透過既有 `onUpdateTus` /
  SAT 對應 handler 更新旗標與原因。

### 資料流

使用者於明細表勾選 TUS-3「排除」並填原因 → 存檔 payload 帶 `已排除/排除原因` →
服務層驗證原因非空後寫入 → `evaluate_tus` 跳過 TUS-3 之均勻度/判定 → 報表輸出 TUS-3
灰底列並標「已排除：原因」、原始曲線 TUS-3 線條灰色。

## 測試

- 後端（`test_pyrometry.py` / `test_pyrometry_calculations.py`）：
  - 排除某 TUS 點 → 不影響均勻度極差／最大正負偏差／整體判定；該點 `最大偏差=None`。
  - 排除某 SAT 控溫區 → 不影響整體判定。
  - `已排除=true` 且原因為空 → `PyrometryValidationError`。
- 前端（`TusSection.test.tsx` / `SatSection.test.tsx` / 表單測試）：
  - 勾選「排除」啟用原因欄；未填原因無法存檔。
  - 已排除點位名正確傳入曲線圖。

## 不在此次範圍

- CQI-9 最少有效熱電偶數／有效點數下限驗證。
- 既有已存檔測試的回溯排除（本功能對新建/編輯生效）。
