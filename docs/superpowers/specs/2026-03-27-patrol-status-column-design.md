# 現場巡檢歷史清單狀態欄位 — 設計規格

**日期：** 2026-03-27
**功能：** 在現場巡檢歷史清單新增「狀態」欄位，顯示合格或超差

---

## 背景

出貨檢驗（ShippingPage）的歷史清單已有「狀態」欄位，可即時顯示每筆記錄是否超差。使用者希望現場巡檢（PatrolPage）的歷史清單也有相同功能。

---

## 現況分析

### 出貨檢驗的狀態判斷方式（參考基準）
- 前端批次呼叫 `/api/tolerance/check?material=&spec=&vendor_id=`（廠商公差主檔）
- 前端比對量測值與公差，計算合格/超差
- `ShippingData` 資料表有 `is_ng` 欄位，儲存時即計算

### 現場巡檢與出貨檢驗的差異
| 項目 | 出貨檢驗 | 現場巡檢 |
|------|---------|---------|
| 公差系統 | 廠商公差（`/api/tolerance/check`） | 押出公差（`/api/extrusion-tolerance/check`） |
| NG 儲存 | DB 有 `is_ng` 欄位（存檔時計算） | DB 無 `is_ng`，Modal 中即時計算 |
| 歷史 API 回傳明細 | 是（量測值含在記錄中） | 否（只有 id、日期、機台、人員、材質、規格） |

### 押出公差結構
- 以 `(材質, 規格)` 查詢，優先等級：完全匹配 > 前兩段匹配 > 通用（無規格）
- 每個 `項目`（外徑/內徑/厚度/同心度）含 `公差下限`/`公差上限`，**不分量測位置**
- 同心度計算：`厚度 max_val − min_val`，比對同心度公差

### PatrolDetail 結構
```
group      → 組別（整數）
item       → 測量項目（外徑/內徑/厚度）
position   → 測量位置（前段/中段/後段）
min_val    → 最小量測值
max_val    → 最大量測值
```

---

## 選用方案

**方案 A：後端計算 `is_ng`，在 `get_history` 回傳**

後端在歷史清單 API 中，直接計算每筆記錄是否 NG，並將結果回傳給前端。前端只需顯示 badge，無需自行呼叫公差 API。

**選用理由：** 前端零額外 API 呼叫；批次處理唯一的 `(材質, 規格)` 組合，效能佳；邏輯集中在後端，易維護。

---

## 詳細設計

### 後端：`backend/services/patrol_service.py`

**修改方法：** `PatrolService.get_history()`

**步驟：**

1. 在**現有的 tuple 查詢**（`db.session.query(PatrolMain, Machine.name, ...)`）加入 `.options(selectinload(PatrolMain.details))`，以 eager load 明細，避免 N+1 查詢。注意不要改用 `PatrolMain.query`，否則會遺漏已有的 outerjoin 結構。

2. 收集本頁所有唯一的 `(material, spec)` 組合，批次呼叫 `ExtrusionToleranceService.check()`，建立快取 `dict`：
   ```python
   tol_cache: Dict[Tuple[str, str], Optional[Dict]] = {}
   # value: 公差 dict（以 項目名稱 為 key），或 None（查無資料）
   # 例：{'外徑': {'公差下限': 0.5, '公差上限': 1.5}, '同心度': {...}}
   ```
   若同一 `項目` 在押出公差主檔有多筆（理論上不應發生），取第一筆（`check()` 內部已按優先等級選取唯一主檔）。

3. 對每筆記錄，執行 NG 判斷：
   - 從 `tol_cache` 取得對應公差；查無資料則 `tol_found = False`，`is_ng = False`
   - 遍歷該記錄的所有 `PatrolDetail`（已 eager loaded），進行以下判斷：
     - **一般項目**（外徑/內徑）：比對 `min_val`、`max_val` 是否超出對應 `項目` 的 `公差下限`/`公差上限`
     - **厚度項目**：
       - 同上，比對 `min_val`、`max_val` 與厚度公差
       - 另外計算同心度：對**同一 PatrolDetail 記錄**（即同一 group + position 的厚度行），`同心度 = max_val − min_val`，與同心度公差比對（對齊 PatrolModal `isConcentricityNG` 邏輯）
   - 比對時不區分量測位置（position），押出公差以 `項目` 為 key，統一適用所有位置
   - 任一值超差即設 `is_ng = True`，short-circuit 停止比對

4. 在回傳的每筆資料中加入 `is_ng` 與 `tol_found`：
   ```python
   data.append({
       'id': patrol.id,
       'date': date_str,
       ...
       'is_ng': is_ng,     # bool，查無公差時為 False
       'tol_found': tol_found,  # bool
   })
   ```

**不需要修改 API route，不需要 DB migration。**

---

### 前端：`src_frontend/src/types/index.ts`

在 `PatrolInspection` interface 新增：
```typescript
is_ng?: boolean;
tol_found?: boolean;
```

---

### 前端：`src_frontend/src/pages/patrol/PatrolPage.tsx`

1. **表格標題列**：在「規格」欄後、「操作」欄前，插入：
   ```tsx
   <th className="text-center">狀態</th>
   ```

2. **表格資料列**：在對應位置插入 badge 顯示邏輯：
   ```tsx
   <td className="text-center">
       {!item.tol_found ? (
           <span className="badge bg-secondary">-</span>
       ) : item.is_ng ? (
           <span className="badge bg-danger">⚠️ 超差</span>
       ) : (
           <span className="badge bg-success">✓ 合格</span>
       )}
   </td>
   ```

3. **`colSpan` 更新**：表格 loading / 無資料 row 的 `colSpan` 從 8 改為 9。

---

## 影響範圍

| 檔案 | 修改類型 |
|------|---------|
| `backend/services/patrol_service.py` | 功能擴充（`get_history` 加入 NG 計算） |
| `src_frontend/src/types/index.ts` | 型別擴充 |
| `src_frontend/src/pages/patrol/PatrolPage.tsx` | UI 擴充（新增欄位） |

不影響其他模組、不需要 DB migration、不破壞既有 API 相容性。

---

## 邊界條件

- 若該記錄無材質資料 → `tol_found = False`，顯示 `-`
- 若押出公差主檔查無對應規格 → `tol_found = False`，顯示 `-`
- 若所有明細均無量測值（`None`）→ `is_ng = False`，顯示「✓ 合格」（與 Modal NG 判斷一致）
- 同心度公差缺失 → 跳過同心度判斷

---

## 測試重點

- 有公差資料且所有值合格 → 顯示「✓ 合格」
- 有公差資料且任一值超出公差 → 顯示「⚠️ 超差」
- 同心度（max 厚度 − min 厚度）超差 → 顯示「⚠️ 超差」
- 無公差資料（查無對應材質/規格）→ 顯示「-」
- 多筆記錄同一 (材質, 規格) 組合，公差僅查詢一次（快取驗證）
