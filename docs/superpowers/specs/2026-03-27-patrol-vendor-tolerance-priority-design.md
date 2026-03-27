# 設計規格：巡檢歷史清單優先套用廠商公差

**日期：** 2026-03-27
**狀態：** 已核准

---

## 問題描述

巡檢歷史清單（`get_history`）在計算押出公差 NG 時，呼叫 `ExtrusionToleranceService.check` 只傳入 `material` 和 `spec`，未傳入 `vendor_id`（即 `PatrolMain.customer_id`）。

導致即使廠商公差管理系統（`VendorToleranceMain`）有對應的廠商+材質+規格記錄，也永遠不會被套用，只能落入 Priority 5–8（無廠商記錄）或押出公差。

---

## 需求

當巡檢紀錄同時符合以下三個條件時，優先套用廠商公差管理系統的資料作為押出公差：

1. **相同廠商**：`PatrolMain.customer_id` == `VendorToleranceMain.vendor_id`
2. **相近規格**：廠商公差規格為 `a*b`，巡檢規格為 `a*b*c`，視為相同（前兩段相符）
3. **相近材質**：`6061` 與 `6061-F` 視為相近（單向包含匹配，現有邏輯）

---

## 現有優先順序（`check_tolerance` Priority Buckets）

| Priority | 條件 | 說明 |
|---|---|---|
| 1 | 廠商匹配 + 規格完全相同 | |
| 2 | 廠商匹配 + 規格前段匹配 | 如 `a*b*c` startswith `a*b*` |
| 3 | 廠商匹配 + 規格前兩段相同 | 如 `a*b*c` 與 `a*b` |
| 4 | 廠商匹配 + 無規格（通用） | |
| 5–8 | 無廠商記錄的對應 | |

`ExtrusionToleranceService.check` 已正確實作：先呼叫 `ToleranceService.check_tolerance`（廠商公差），若找到則優先返回；找不到才查 `ExtrusionToleranceMain`（押出公差）。

**問題根因：** `get_history` 呼叫端沒傳 `vendor_id`，造成 Priority 1–4 永遠無法命中。

---

## 解決方案（方案 A，最小改動）

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
- `get_spc`：不修改
- 前端所有元件：不修改

---

## 測試情境

| 情境 | 期望結果 |
|---|---|
| 廠商 A + 材質 6061 + 規格 62.5*2.3*450，廠商公差有 廠商 A + 6061 + 62.5*2.3 | 套用廠商公差（Priority 3） |
| 廠商 A + 材質 6061-F + 規格 62.5*2.3*450，廠商公差有 廠商 A + 6061-F + 62.5*2.3 | 套用廠商公差（Priority 3） |
| 廠商 A，但廠商公差無對應廠商記錄 | fallback 到押出公差（不變） |
| 無廠商（customer_id = None） | 行為與現在相同 |
