# NCMR / CAR / CAPA 分頁與篩選功能設計

**日期：** 2026-04-08  
**範圍：** 不合格品管理（NCMR）、矯正措施（CAR）、異常矯正措施（CAPA）三個清單頁面

---

## 目標

三個歷史清單頁面目前一次載入全部資料，資料量大時效能差且無法快速定位。本次新增：
1. 後端分頁（server-side pagination）
2. 後端篩選（server-side filtering）
3. 前端篩選列（FilterBar）與分頁列（PaginationBar）
4. NCMR 清單「數量」欄改顯示不合格數量
5. NCMRModal 移除「產品數量」欄位

---

## 後端設計

### 統一回傳格式

三支 list API 改為回傳 pagination envelope：

```json
{
  "data": [...],
  "total": 250,
  "page": 1,
  "per_page": 20
}
```

### NCMR — `GET /api/ncmr`

新增 query params：

| 參數 | 型別 | 說明 |
|------|------|------|
| `page` | int (預設 1) | 頁碼 |
| `per_page` | int (預設 20) | 每頁筆數，最大 100 |
| `date_from` | string (YYYY-MM-DD) | 發現日期起 |
| `date_to` | string (YYYY-MM-DD) | 發現日期迄 |
| `source` | string | 來源（完全比對） |
| `vendor` | string | 廠商（ilike 模糊） |
| `material` | string | 材質（ilike 模糊） |
| `product_info` | string | 規格（ilike 模糊） |
| `status` | string | 狀態（完全比對） |

`NCMRService.get_ncmr_list()` 改為接受以上參數，使用 SQLAlchemy `.filter()` 組合條件，最後呼叫 `.paginate(page, per_page, error_out=False)`，回傳 `(items, total)`。

### CAR — `GET /api/cara`

新增 query params：

| 參數 | 說明 |
|------|------|
| `page` / `per_page` | 分頁 |
| `date_from` / `date_to` | 建立日期範圍 |
| `vendor` | 廠商（ilike） |
| `material` | 材質（ilike） |
| `product_info` | 規格（ilike） |
| `status` | 狀態 |

篩選條件透過 JOIN NCMR 表的 `vendor`、`material`、`product_info` 欄位實現。

### CAPA — `GET /api/capa`

與 CAR 相同的 query params，邏輯對稱。

---

## 前端設計

### 共用元件

#### `FilterBar`（`src/components/common/FilterBar.tsx`）

收合式篩選列，預設展開。Props：

```typescript
interface FilterBarProps {
  filters: Record<string, string>;
  onFilterChange: (key: string, value: string) => void;
  onReset: () => void;
  children: React.ReactNode; // 各頁自行傳入篩選欄位
}
```

#### `PaginationBar`（`src/components/common/PaginationBar.tsx`）

頁碼列。Props：

```typescript
interface PaginationBarProps {
  page: number;
  perPage: number;
  total: number;
  onPageChange: (page: number) => void;
}
```

顯示：「上一頁 | 1 2 3 … | 下一頁」及「共 N 筆，第 X / Y 頁」。頁碼按鈕最多顯示 5 個，超過以 `…` 省略。

### NCMR 頁篩選欄位

| 欄位 | 元件 | filter key |
|------|------|-----------|
| 日期（起） | `<input type="date">` | `date_from` |
| 日期（迄） | `<input type="date">` | `date_to` |
| 來源 | `<select>` (進料/巡檢/出貨檢/客訴/退貨) | `source` |
| 廠商 | `<input type="text">` | `vendor` |
| 材質 | `<input type="text">` | `material` |
| 規格 | `<input type="text">` | `product_info` |
| 狀態 | `<select>` (待處理/CAR處理中/矯正中/轉重工/已結案) | `status` |

### CAR / CAPA 頁篩選欄位

| 欄位 | 元件 | filter key |
|------|------|-----------|
| 日期（起） | `<input type="date">` | `date_from` |
| 日期（迄） | `<input type="date">` | `date_to` |
| 廠商 | `<input type="text">` | `vendor` |
| 材質 | `<input type="text">` | `material` |
| 規格 | `<input type="text">` | `product_info` |
| 狀態 | `<select>` | `status` |

### React Query 整合

- NCMR 已使用 React Query（`useNCMRList`），擴充 hook 接受 `params` 物件，query key 為 `['ncmr', 'list', params]`。
- CAR / CAPA 目前用手動 `useState + loadData`，**本次一併改為 React Query**，新增 `useCARAList(params)` 與 `useCAPAList(params)` hooks，放在 `src/hooks/useNCMR.ts`（與現有 NCMR hooks 同檔）。
- filter 或 page 變動時，React Query 自動重取；filter 任一欄位變動時 page 重置為 1。

---

## 其他修改

### NCMR 清單「數量」欄

- 欄位標題改為「不合格數量」
- 顯示值改為 `item.defect_qty`（對應 API 回傳的 `不合格數量`）

### NCMRModal 移除「產品數量」欄位

- `NCMRModal.tsx` 移除 `productQty` state 及對應的 `<Form.Control>`
- `handleSubmit` 的 payload 移除 `產品數量` 欄位
- schema `NCMRCreateSchema` 的 `產品數量` 欄位改為可選（已是 `load_default=None`，無需額外修改）

---

## 不在本次範圍

- 後端不改 export/print 邏輯
- 不修改 NCMR Modal 其他欄位
- 不加 URL query string 保存篩選狀態（頁面重整後篩選重置）

---

## 檔案異動清單

| 檔案 | 異動類型 |
|------|---------|
| `backend/services/ncmr_service.py` | 修改 `get_ncmr_list`、`get_cara_list`、`get_capa_list` 加篩選+分頁 |
| `backend/routes/ncmr.py` | 修改三支 GET routes 讀取 query params 並傳給 service |
| `src/hooks/useNCMR.ts` | 擴充 `useNCMRList`；新增 `useCARAList`、`useCAPAList` |
| `src/components/common/FilterBar.tsx` | 新增共用篩選列元件 |
| `src/components/common/PaginationBar.tsx` | 新增共用分頁列元件 |
| `src/pages/ncmr/NCMRPage.tsx` | 加入篩選列、分頁列；修改數量欄 |
| `src/pages/cara/CARAPage.tsx` | 加入篩選列、分頁列；改用 React Query |
| `src/pages/capa/CAPAPage.tsx` | 加入篩選列、分頁列；改用 React Query |
| `src/components/ncmr/NCMRModal.tsx` | 移除產品數量欄位 |
