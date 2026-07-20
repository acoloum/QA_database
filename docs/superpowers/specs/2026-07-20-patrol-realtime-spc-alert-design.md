# 巡檢即時量測示警設計

日期：2026-07-20

## 背景與目標

現行「巡檢」（製程巡檢）流程是離散批次作業：巡檢員在 `PatrolModal` 一次填完整份記錄
（多個 group × 量測項目 × 前中後段的 min/max），送出後才存成一筆 `PatrolMain` +
多筆 `PatrolDetail`。是否超差（`is_ng`）在存檔時依規格公差比對。

目標：在巡檢員逐筆輸入量測值的當下，就能依 SPC 管制界限即時判讀製程是否出現
異常徵兆（AIAG-VDA SPC 手冊 §9.2.2 穩定性準則／§9.2.3 OCAP），並提示可能的擠壓
模具調整方向，讓調整發生在「還沒產出大量不良品」之前，而不是等一批巡檢記錄
存檔、事後才發現異常。

## 現有相關基礎設施（設計前提）

- `backend/services/spc_stability.py`：西方電氣/Nelson 穩定性準則判定，**唯一權威**
  來源。預設精簡規則集 `DEFAULT_STABILITY_RULES = ["beyond_limits",
  "run_9_same_side", "trend_6"]`（§9.2.2.1：避免多規則疊加推高誤警率）。
- `SpcLimitVersion`（`backend/models.py`）：§9.4 確效流程核准後生效的管制界限版本，
  以 `process_stream_key`（由 `canonical_process_stream()` 對篩選條件做正規化雜湊
  得出）+ `characteristic`（量測項目）唯一定位一條「製程流」的生效界限。
- `POST /api/spc/studies/analyze`（`study_type=ongoing`）：`SpcStudyService.analyze()`
  既有端點，讀取生效中的 `SpcLimitVersion`、比對已存檔資料、違規時自動呼叫
  `SpcOcapService.sync_events()` 建立正式 `SpcEvent`（去重）。**本設計不修改此
  端點**，存檔後直接沿用。
- `SpcOcapOffcanvas.tsx`：既有 OCAP 調查/處置面板，吃 `eventId` 顯示 6M調查、重新
  量測、製程調整、產品處置、責任人、有效性確認。**本設計不新增欄位**，只是把
  觸發時機提前到輸入當下。
- `src_frontend/src/utils/spcAnalysis.ts`：既有前端規則判定鏡像，程式碼註解已
  明講定位為「展示與測試工具」，不得覆蓋後端正式判定結果——正好符合本設計
  「前端僅做即時提示，後端存檔後才是正式判定」的分層。
- **重要限制**：`build_patrol_study_input()`／`analyze()`／`preview()` 都是從資料庫
  查已存檔的 `PatrolDetail` 建立分析輸入，無法對「表單中尚未送出」的值做正式
  判定。這是本設計採兩層架構的根本原因。

## 架構總覽

```
輸入量測值（即時模式開啟）
  └─ 前端：抓取/快取該 item+position 的生效界限 + 近期歷史值
       └─ spcAnalysis.ts 本地判定（僅 3 條預設規則，與後端一致）
            └─ 違規 → 欄位標紅 + 規則標籤 + 模具調整提示（純前端，不寫入 DB）

按下「儲存」
  └─ 照舊存 PatrolMain / PatrolDetail（不變動）
       └─ 若本次任何欄位曾標紅 → 對每個 item+position 呼叫既有
          POST /api/spc/studies/analyze（study_type=ongoing）
               └─ 既有邏輯自動建立正式 SpcEvent
                    └─ 前端 toast「觸發 N 項異常，查看建議」
                         └─ 點擊開啟既有 SpcOcapOffcanvas
```

## 後端變更

### 新增：`GET /api/patrol/live-limits`（唯讀，`spc.view` 權限）

參數：`machine_id, material, spec, item, position`

行為：
1. 用 `canonical_process_stream("patrol", filters)` 算出 `process_stream_key`
   （沿用既有正規化邏輯，filters 需與 `build_patrol_study_input` 的篩選鍵對齊，
   但**不含日期區間**——製程流身分需與查詢時間窗無關）。
2. 查詢 `SpcLimitVersion.query.filter_by(analysis_family="variable",
   process_stream_key=..., characteristic=item, status="active")`。
3. 找不到 → 回傳 `{"found": false}`。
4. 找到 → 回傳：
   ```json
   {
     "found": true,
     "x_cl": ..., "x_ucl": ..., "x_lcl": ...,
     "r_cl": ..., "r_ucl": ..., "r_lcl": ...,
     "avg_n": ...,
     "recent_values": [最近 14 筆已存檔個別值，依日期/main_id/group 排序]
   }
   ```
   `recent_values` 沿用 `build_patrol_study_input` 同款查詢邏輯（`PatrolDetail`
   join `PatrolMain`，依 `item`/`position`/`machine_id`/`material`/`spec` 過濾，
   取末 14 筆）。**編輯既有記錄時，前端需傳入 `exclude_main_id` 排除自己**，
   避免歷史序列包含編輯前的舊值。

不新增資料表，不寫入任何資料——單純唯讀查詢組裝。

### 不變動

- `spc_stability.py`、`SpcStudyService.analyze()`、`SpcOcapService`、
  `SpcOcapOffcanvas.tsx` 皆維持現狀，本設計完全重用。

## 前端變更

### `PatrolModal.tsx` / `PatrolMeasurementTable.tsx`

- 新增「即時模式」開關（`Form.Check` 或 `Button` toggle），預設關閉，狀態存在
  modal 內（不持久化，每次開啟表單重置）。
- 開啟後，`live-limits` 查詢結果以 `` `${item}|${position}` `` 為 key 快取在
  modal state；切換機台/材質/規格時清空快取。
- 量測輸入格（`min`/`max`）在 `onBlur` 觸發判讀（不逐字元觸發）：
  1. 若快取沒有該 `item+position` 的界限，先呼叫 `/api/patrol/live-limits`
     （編輯模式帶上 `exclude_main_id`）。
  2. `found=false` → 不做管制圖判讀，維持現有 `ToleranceBadgeList` 公差比對；
     額外顯示一條不打斷輸入的灰色提示：「此項目尚無生效管制界限，僅顯示規格
     公差比對」。
  3. `found=true` → 組序列：`recent_values` + 本次表單同 group/item/position
     已填值 + 剛輸入值，呼叫 `spcAnalysis.ts`（擴充為與後端
     `DEFAULT_STABILITY_RULES` 完全一致的三條規則：`beyond_limits`,
     `run_9_same_side`, `trend_6`）。
  4. 有違規 → 該格紅框（與現有超規格的紅色視覺區分，例如用不同底色，避免與
     `is_ng` 的既有紅色語彙混淆），格下顯示規則標籤 + 依圖別（X 位置圖／R
     變異圖）對應的擠壓製程調整提示文字（見下方對照表）。
- 關閉即時模式只清除畫面上的標紅與提示，不阻擋、不影響已輸入數值與儲存流程
  （純輔助提示，非強制關卡）。

### 提示文字對照（依規則與圖別）

| 規則 | 圖別 | 提示方向 |
|---|---|---|
| `beyond_limits` | X（位置） | 單點急劇偏移，先重量一次確認非量測失誤；屬實則檢查機頭壓力/料溫瞬間波動 |
| `run_9_same_side` | X（位置） | 製程中心已偏移，非單純波動，建議依 5M（人機料法環）排查後調整模具定位 |
| `trend_6` | X（位置） | 持續漂移，典型成因是模具磨耗或螺桿轉速緩慢飄移，建議檢查/微調模具間隙與牽引速度 |
| 任一規則 | R（變異） | 量測值波動變大，較可能是設備穩定度或原料問題，非模具位置問題 |

### 存檔後正式判定

- `handleSubmit` 存檔成功後，若即時模式開啟且本次有任一欄位曾標紅，對每個
  「曾標紅的 item+position」呼叫既有 `POST /api/spc/studies/analyze`
  （`source: "patrol", study_type: "ongoing"`，filters 為該 item+position 對應的
  完整篩選條件）。
- 回應中若有新違規（沿用既有 `stability_result.violations`／既有事件建立機制），
  存檔成功 toast 下追加一行「本次觸發 N 項製程異常，查看建議」，點擊用既有的
  事件/OCAP 抓取 hook 開啟 `SpcOcapOffcanvas`。

## 邊界情況

- **規則集對齊**：前端即時判讀只啟用與後端 `DEFAULT_STABILITY_RULES` 完全一致
  的三條規則，不擅自加碼，避免前端比後端敏感、造成「前端一直紅但存檔後都沒
  事」的落差感。
- **編輯既有記錄**：`recent_values` 查詢排除目前編輯中的 `main_id`。
- **效能**：界限查詢以 `item+position` 快取在 modal state 內，同一份表單內
  每個項目只查一次；判讀只在欄位失焦時觸發，不逐字元觸發。
- **無生效界限**：不強制判讀，僅顯示既有規格公差比對 + 灰色提示引導使用者
  至 SPC 研究頁面建立/核准界限（核准流程本身不在本次範圍）。
- **即時模式關閉/切換**：不影響已輸入數值與儲存，純提示層。

## 測試計畫

- 後端：`live-limits` 端點單元測試（有生效界限／無生效界限／權限不足／
  `exclude_main_id` 排除生效／機台或項目不存在）。
- 前端：`spcAnalysis.ts` 規則判定結果需有測試驗證與 `spc_stability.py` 三條
  預設規則在相同輸入下判定一致。
- 瀏覽器手動驗證：開啟即時模式 → 輸入連續偏高量測值 → 確認標紅與提示文字
  出現 → 儲存 → 確認 toast 出現「查看建議」→ 點開 OCAP 面板可見剛建立的事件。

## 明確排除範圍（YAGNI）

- 不新增資料表、不新增持久化的「即時警示紀錄」實體——即時提示純粹是前端
  advisory 層，正式紀錄仍走既有 `SpcEvent`/`SpcOcap`。
- 不支援量測儀器/感測器自動連線輸入（維持人工逐筆輸入，符合本次確認的
  「逐筆量測、量完立刻送出並判讀」範圍）。
- 不實作 SPC 界限核准流程本身（沿用既有 SPC 研究/確效頁面）。
- 不修改 `spc_stability.py`、`SpcStudyService.analyze()`、`SpcOcapOffcanvas.tsx`。
