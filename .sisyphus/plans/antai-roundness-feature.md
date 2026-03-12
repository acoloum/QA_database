# 工作計劃：安泰廠商真圓度檢驗項目自動顯示功能

## 計劃概述

| 項目 | 內容 |
|------|------|
| **功能名稱** | 安泰廠商真圓度檢驗項目自動顯示 |
| **目標頁面** | 出貨檢驗新增/編輯頁面 (ShippingModal) |
| **功能描述** | 當選擇廠商為「安泰」時，自動在檢驗項目表格中顯示「真圓度」欄位 |

---

## 範圍邊界

### 包含 (IN)
- [x] 新增資料庫欄位 (真圓度1-5)
- [x] 修改後端 ShippingData 模型
- [x] 修改前端 ShippingModal 檢驗項目渲染邏輯
- [x] 處理表單資料讀寫

### 不包含 (OUT)
- [ ] 修改其他模組（如巡檢）
- [ ] 修改公差管理頁面（目前由使用者手動設定）
- [ ] 自動化測試（手動驗證）

---

## 關鍵決策記錄

| 決策 | 選項 | 選擇理由 |
|------|------|----------|
| 實作方式 | 方案 A：硬編碼安泰 | 使用者指定需求範圍明確，未來如有其他廠商需求可再擴充 |
| 廠商名稱 | 「安泰」 | 使用者確認資料庫中廠商名稱為「安泰」 |
| 資料庫變更 | 新增欄位 | 需支援 5 組測量資料，與其他項目一致 |

---

## 任務清單

### 階段 1: 資料庫層

#### 任務 1.1: 建立資料庫遷移腳本
- **檔案**: `migration/06_add_roundness_columns.sql`
- **說明**: 在 `出貨檢驗數據` 資料表新增真圓度欄位
- **SQL 內容**:
  ```sql
  ALTER TABLE 出貨檢驗數據 
  ADD COLUMN IF NOT EXISTS 真圓度1 VARCHAR,
  ADD COLUMN IF NOT EXISTS 真圓度2 VARCHAR,
  ADD COLUMN IF NOT EXISTS 真圓度3 VARCHAR,
  ADD COLUMN IF NOT EXISTS 真圓度4 VARCHAR,
  ADD COLUMN IF NOT EXISTS 真圓度5 VARCHAR;
  ```
- **QA 場景**:
  - [x] 執行 SQL 後，用工具確認欄位已建立
  - [x] 嘗試新增一筆含真圓度資料的出貨檢驗

#### 任務 1.2: 更新後端模型
- **檔案**: `backend/models.py`
- **修改位置**: `ShippingData` 類別 (約第 60-86 行)
- **說明**: 在現有欄位定義後，新增真圓度欄位
- **修改內容**:
  ```python
  # 在現有 for i in range(1, 6) 迴圈內的真直度後新增：
  locals()[f'roundness{i}'] = db.Column(f'真圓度{i}', db.String)
  ```
- **QA 場景**:
  - [x] 啟動後端，確認模型載入無錯誤
  - [x] 確認 API 可以正確讀寫真圓度欄位

---

### 階段 2: 前端層

#### 任務 2.1: 修改前端類型定義 (如需要)
- **檔案**: `src_frontend/src/types/index.ts`
- **說明**: 檢查並確認 ShippingInspection 類型包含真圓度欄位
- **QA 場景**:
  - [x] TypeScript 編譯無錯誤

#### 任務 2.2: 修改 ShippingModal ITEMS 邏輯
- **檔案**: `src_frontend/src/components/shipping/ShippingModal.tsx`
- **修改位置**: 
  1. 第 21-25 行 `ItemConfig` 介面 - 保持不變
  2. 第 27-35 行 `ITEMS` 陣列 - 保持基本項目
  3. 新增 `getAnTaiItems()` 函數 - 取得安泰專屬項目
  4. 第 372 行渲染處 - 使用動態取得項目函數

- **修改細節**:
  ```typescript
  // 基本項目（所有廠商）
  const BASE_ITEMS: ItemConfig[] = [
      { label: "外徑", key: "外徑", type: "minmax" },
      { label: "內徑", key: "內徑", type: "minmax" },
      { label: "厚度", key: "厚度", type: "minmax" },
      { label: "同心度", key: "同心度", type: "single" },
      { label: "長度", key: "長度", type: "single" },
      { label: "硬度", key: "硬度", type: "single" },
      { label: "真直度", key: "真直度", type: "single" }
  ];

  // 安泰專屬項目
  const ANTAI_ITEMS: ItemConfig[] = [
      { label: "真圓度", key: "真圓度", type: "single" }
  ];

  // 取得當前顯示的項目（根據廠商）
  const getDisplayItems = (vendorName: string): ItemConfig[] => {
      if (vendorName === '安泰') {
          return [...BASE_ITEMS, ...ANTAI_ITEMS];
      }
      return BASE_ITEMS;
  };
  ```

- **QA 場景**:
  - [x] 選擇「安泰」廠商時，真圓度欄位顯示
  - [x] 選擇其他廠商時，真圓度欄位不顯示
  - [x] 切換廠商時，項目正確變化

#### 任務 2.3: 更新表單測量資料處理
- **檔案**: `src_frontend/src/components/shipping/ShippingModal.tsx`
- **修改位置**: 
  1. 第 118-129 行 `useEffect` (編輯時載入資料)
  2. 第 246-254 行 `handleSubmit` (提交資料)

- **說明**: 
  - 編輯時需正確讀取真圓度資料
  - 提交時需包含真圓度資料

- **QA 場景**:
  - [x] 編輯現有安泰檢驗資料時，真圓度資料正確顯示
  - [x] 儲存安泰檢驗資料時，真圓度正確寫入資料庫

---

### 階段 3: 公差檢查 (可選優化)

#### 任務 3.1: 公差檢查相容性
- **說明**: 如果安泰有設定真圓度的公差標準，系統應能正確驗證
- **現狀**: 公差 API 會回傳該廠商的公差項目，前端會據此驗證
- **QA 場景**:
  - [x] 安泰設定真圓度公差後，輸入值超出範圍會顯示警示

---

## 驗收標準

| 功能 | 驗收條件 |
|------|----------|
| 資料庫欄位 | 出貨檢驗數據表有真圓度1-5 欄位 |
| 後端模型 | 後端啟動正常，API 可讀寫資料 |
| 前端顯示 | 選擇安泰時顯示真圓度欄位 |
| 前端顯示 | 選擇其他廠商時不顯示真圓度欄位 |
| 資料儲存 | 安泰的檢驗資料包含真圓度 |
| 資料讀取 | 編輯時正確顯示真圓度資料 |

---

## 檔案變更清單

| 檔案 | 變更類型 | 說明 |
|------|----------|------|
| `migration/06_add_roundness_columns.sql` | 新增 | 資料庫遷移腳本 |
| `backend/models.py` | 修改 | 新增 roundness 欄位 |
| `src_frontend/src/components/shipping/ShippingModal.tsx` | 修改 | 動態渲染真圓度項目 |
| `src_frontend/src/types/index.ts` | 修改 (如有需要) | 類型定義 |

---

## 預估工作量

- 資料庫遷移: 10 分鐘
- 後端模型更新: 10 分鐘  
- 前端邏輯修改: 30 分鐘
- 測試驗證: 20 分鐘

**總計**: 約 70 分鐘

---

## 風險與緩解

| 風險 | 影響 | 緩解措施 |
|------|------|----------|
| 欄位命名衝突 | 低 | 使用「真圓度」與現有命名不衝突 |
| 資料庫權限 | 中 | 需確認有 ALTER TABLE 權限 |
| 快取問題 | 低 | 前端表單重置後會重新渲染 |

---

## 備註

- 此功能採用硬編碼方式，未來如有其他廠商特殊項目需求，可重構為配置導向
- 真圓度為「單一數值」類型（single），與同心度、真直度相同
- 公差設定需由使用者在「廠商公差管理」頁面手動設定
