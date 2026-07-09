# 出貨檢驗外徑分段量測(前/中/後)設計

**日期:** 2026-07-09
**狀態:** 已確認

## 背景與目標

出貨檢驗的外徑目前每組只有一對 Min/Max。依情況(客戶/製程需求),外徑需要量測前、中、後三段數據。巡檢模組已有「測量位置」(前段/中段/後段)的完整前例,本設計讓出貨檢驗以最小改動長出同一維度。

**需求確認:**
- 分段由檢驗員每筆紀錄手動切換(非依廠商/規格自動)。
- config 設計為通用(任何 minmax 項目都可宣告可分段),介面先只對外徑開放。
- 前/中/後三段共用同一組「外徑」公差。

## 1. 資料層

`ShippingMeasurement`(出貨巡檢量測明細,`backend/models.py`)新增欄位:

- `測量位置` `String(10)` **NOT NULL DEFAULT ''**。空字串代表「未分段」。刻意不用 NULL:PostgreSQL 唯一鍵不比較 NULL,會使重複防護失效。
- 唯一鍵 `uq_shipping_group_item` 改為 `(出貨檢驗_ID, 組別, 量測項目, 測量位置)`。
- 位置合法值:`''`、`前段`、`中段`、`後段`(與巡檢子檔用語一致)。
- migration:add column(default '')+ 重建唯一鍵,既有資料不需搬移。

## 2. API 傳輸格式

巢狀 `measurements[組別][鍵]` 的**鍵**採複合鍵設計:

- 未分段:`外徑`(與現行完全相同)
- 分段:`外徑@前段`、`外徑@中段`、`外徑@後段`

後端寫入時以 `partition('@')` 拆出項目與位置;項目需屬 VALID_ITEMS,位置僅允許 `前段/中段/後段`(空位置即未分段),不合法者略過。回傳時反向組合鍵(位置為空字串則鍵為項目名)。

**理由:** 舊紀錄 JSON 完全不變;DB `量測項目` 保持乾淨的「外徑」,SPC 查詢與 `compute_is_ng` 不受污染。

## 3. 前端設定層(通用化)

- `ShippingItemConfig` 新增選填欄位:`segmentable?: boolean`、`position?: string`。
- `BASE_SHIPPING_ITEMS`(`shippingInspectionItems.ts`)僅外徑標 `segmentable: true`。
- 新增純函式 `expandSegmentedItems(items, segmentedKeys: Set<string>)`:被啟用分段的項目展開為三列,例:
  `{ label: '外徑(前)', key: '外徑@前段', toleranceKey: '外徑', position: '前段', type: 'minmax' }`
- groups state、驗證、超差紅框、tabIndex 皆以 `item.key` 為鍵,展開後自動生效;公差查找走既有 `toleranceKey` fallback(`shippingMeasurementUtils.ts`),三段共用「外徑」公差,公差邏輯不動。

## 4. 表格 UI 與切換行為

- 外徑列項目標題格加小型「分段」switch(僅 `segmentable` 項目顯示)。
- **開啟分段:** 原單段已輸入的 Min/Max 自動搬到「前段」,展開為三列(前/中/後)。
- **關閉分段:** 若中段/後段有值,跳確認提示「將只保留前段數據」;確認後收合回單列,前段值成為單段值。
- **編輯舊紀錄:** 載入時偵測 measurements 含 `外徑@` 開頭的鍵即自動開啟分段模式;否則維持單列。

## 5. 違規偵測

- 表單內即時偵測:`toleranceKey` fallback 已涵蓋,不需大改。
- 列表頁 `shippingViolationUtils.ts`:比對時除原鍵外,同時比對 `${項目}@` 開頭的複合鍵,套用同一組公差。

## 6. 後端既有功能影響

| 功能 | 影響 |
|------|------|
| `compute_is_ng` | 不用改——DB `量測項目` 仍為「外徑」,三段自然納入判定 |
| SPC 統計(`item == '外徑'`) | 不用改——三段併入同一條外徑序列 |
| Excel 匯出(`shipping_export.py`) | 格式不變;分段紀錄的 `外徑{g}-最小/最大` 填三段整體極值(最小值取三段最小、最大值取三段最大) |
| Excel 匯入 | 維持單段格式,分段資料不支援匯入 |

## 7. 測試範圍

**前端:**
- `expandSegmentedItems` 展開邏輯
- payload 組建含複合鍵
- 編輯載入自動偵測分段模式
- 切換行為:開啟搬移前段、關閉確認並保留前段
- 列表違規複合鍵比對

**後端:**
- 複合鍵解析與位置驗證
- 分段資料寫入/回傳 round-trip
- 含分段資料的 `is_ng` 計算
- 匯出取三段極值

## 已拍板的決策

1. 開啟分段時單段值搬到前段;關閉時只保留前段(中/後段捨棄需使用者確認)。
2. 匯出時分段資料取三段極值填入既有欄位,不新增匯出欄位。
3. SPC 初期三段併同一序列,分段篩選留待未來需求(可照搬巡檢模式)。
