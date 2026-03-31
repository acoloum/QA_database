# 設計規格：巡檢歷史清單優先套用廠商公差

**日期：** 2026-03-27
**狀態：** 已核准

---

## 問題描述

巡檢歷史清單（`get_history`）在計算押出公差 NG 時，呼叫 `ExtrusionToleranceService.check` 只傳入 `material` 和 `spec`，未傳入 `vendor_id`（即 `PatrolMain.customer_id`）。

導致即使廠商公差管理系統（`VendorToleranceMain`）有對應的廠商+材質+規格記錄，也無法命中 Priority 1–4（廠商匹配），只能落入 Priority 5–8（無廠商綁定的通用記錄）或押出公差（`ExtrusionToleranceMain`）。

---

## 需求

當巡檢紀錄同時符合以下三個條件時，優先套用廠商公差管理系統的資料作為押出公差：

1. **相同廠商**：`PatrolMain.customer_id` == `VendorToleranceMain.vendor_id`
2. **相近規格**：廠商公差規格為 `a*b`，巡檢規格為 `a*b*c`，視為相同（前兩段相符）
3. **相近材質**：`6061` 與 `6061-F` 視為相近（單向包含匹配，現有邏輯）

---

## 現有優先順序（`check_tolerance` Priority Buckets）

| Priority | 條件 |
|---|---|
| 1 | 廠商匹配 + 規格完全相同 |
| 2 | 廠商匹配 + 規格前段包含匹配（如 `a*b*c` startswith `a*b*`） |
| 3 | 廠商匹配 + 規格前兩段相同（如 `a*b*c` 與 `a*b`） |
| 4 | 廠商匹配 + 無規格（通用） |
| 5–8 | 對應 Priority 1–4，但無廠商綁定的記錄 |

`ExtrusionToleranceService.check` 已正確實作：先呼叫 `ToleranceService.check_tolerance`（廠商公差），若找到則優先返回；找不到才查 `ExtrusionToleranceMain`（押出公差）。

**問題根因：** `get_history` 呼叫端沒傳 `vendor_id`，`check_tolerance` 內的 `vendor_match` 永遠為 `False`，造成 Priority 1–4 永遠無法命中。

---

## 解決方案（最小改動）

**修改檔案：** `backend/services/patrol_service.py`，`get_history` 方法

### 變更一：unique_combos 的 key 加入 `customer_id`

```python
# 舊
unique_combos = {
    (patrol_item.material or '', patrol_item.spec or '')
    for patrol_item, *_ in pagination.items
    if patrol_item.material
}

# 新
unique_combos = {
    (patrol_item.material or '', patrol_item.spec or '', patrol_item.customer_id)
    for patrol_item, *_ in pagination.items
    if patrol_item.material
}
```

### 變更二：呼叫 `check` 時傳入 `vendor_id`

```python
# 舊
for mat, sp in unique_combos:
    result = ExtrusionToleranceService.check({'material': mat, 'spec': sp})
    if result.get('found'):
        tol_cache[(mat, sp)] = {t['項目']: t for t in result.get('tolerances', [])}
    else:
        tol_cache[(mat, sp)] = None

# 新
for mat, sp, vid in unique_combos:
    result = ExtrusionToleranceService.check({'material': mat, 'spec': sp, 'vendor_id': vid})
    if result.get('found'):
        tol_cache[(mat, sp, vid)] = {t['項目']: t for t in result.get('tolerances', [])}
    else:
        tol_cache[(mat, sp, vid)] = None
```

### 變更三：cache lookup 用三元 key

```python
# 舊
tol_map = tol_cache.get((mat, sp)) if mat else None

# 新
tol_map = tol_cache.get((mat, sp, patrol.customer_id)) if mat else None
```

---

## 不受影響的範圍

- `ExtrusionToleranceService.check`：不修改
- `ToleranceService.check_tolerance`：不修改
- 前端所有元件：不修改

### `get_spc` 為何不修改

`get_spc` 是跨多筆紀錄的 SPC 統計聚合，查詢條件為使用者輸入的材質/規格篩選器，沒有單一對應的廠商 ID，無法對應到特定廠商公差。本次範圍僅限歷史清單（`get_history`）的每筆 NG 計算。

### 效能說明

cache key 由二元改為三元後，相同 `(material, spec)` 但不同廠商的巡檢紀錄各自觸發一次 `check` 呼叫。單頁最多 20 筆，唯一廠商數量有限，實際影響極小。

---

## 邊界案例

| 情境 | 行為 |
|---|---|
| `customer_id = None` | `vid = None`，傳入 `vendor_id=None`，`check_tolerance` 中 `vendor_match=False`，與現在相同（走 Priority 5–8 或押出公差） |
| `customer_id` 存在但廠商公差表無此廠商記錄 | `check_tolerance` 找不到 Priority 1–4，fallback 到 Priority 5–8（通用廠商公差）或押出公差 |
| `customer_id` 指向已刪除的廠商（FK 孤兒） | `vendor_match` 永遠 `False`（無記錄可比對），靜默 fallback 到 Priority 5–8；屬預期行為 |
| 同頁多筆不同廠商 | 三元 key 確保每個廠商各自查詢、各自快取，不互相污染 |

---

## 測試情境

| 情境 | 期望結果 |
|---|---|
| 廠商 A + 材質 6061 + 規格 62.5\*2.3\*450，廠商公差有 廠商 A + 6061 + 62.5\*2.3 | 套用廠商公差（Priority 3） |
| 廠商 A + 材質 6061-F + 規格 62.5\*2.3\*450，廠商公差有 廠商 A + 6061-F + 62.5\*2.3 | 套用廠商公差（Priority 3） |
| 廠商 A + 廠商 B 同頁，各有各自廠商公差 | 各自套用對應廠商公差，快取不互相污染 |
| 廠商 A，但廠商公差無廠商 A 記錄 | fallback 到 Priority 5–8 或押出公差 |
| 無廠商（customer_id = None） | 行為與現在相同 |
| `customer_id` 指向已刪除廠商 | 靜默 fallback，行為與無廠商相同 |
