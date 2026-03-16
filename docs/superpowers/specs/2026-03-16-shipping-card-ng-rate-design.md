# 出貨檢驗卡片改為超差率顯示

**日期：** 2026-03-16
**狀態：** 已核准

---

## 背景

儀表板出貨檢驗 KPI 卡片底部目前顯示「環比變化率」（本期與上期筆數的增減百分比）。此數值反映的是檢驗量的波動，與品質好壞無直接關聯，對品管人員的參考價值有限。

改為顯示「超差率（NG 率）」可直接反映出貨品質狀況。

---

## 需求

| 項目 | 內容 |
|------|------|
| 顯示指標 | 超差率（%）+ NG 筆數 |
| 計算範圍 | 跟隨儀表板時間篩選（本月、本季等） |
| 警示門檻 | 超差率 > 5% → 紅色警示；≤ 5% → 綠色正常 |
| 顯示格式 | `⚠ 超差率 8.3%（13 筆）` |

---

## 不在範圍內

- 其他 KPI 卡片（巡邏、NCMR、CAPA、CAR、重工）維持現狀
- 趨勢圖不變
- `change_pct` 欄位保留在 API 回應中（不刪除）

---

## 技術設計

### 後端 — `backend/routes/admin.py`

在 `get_stats_for_period()` 函式的 `shipping` 區塊，新增 `ng_count` 和 `ng_rate`：

```python
ng_count = count_for_model(
    ShippingData, ShippingData.date, start_date, end_date,
    ShippingData.is_ng == True
)
current = count_for_model(ShippingData, ShippingData.date, start_date, end_date)

"shipping": {
    "current": current,
    "previous": count_for_model(ShippingData, ShippingData.date, compare_start, compare_end),
    "ng_count": ng_count,
    "ng_rate": round((ng_count / current * 100), 1) if current > 0 else 0.0,
    "pending": 0
}
```

### 前端型別 — `src_frontend/src/types/index.ts`

`DomainStat` 介面新增兩個可選欄位：

```ts
ng_count?: number;
ng_rate?: number;
```

### 前端元件 — `src_frontend/src/components/dashboard/KPICards.tsx`

出貨檢驗卡片的底部指標區塊：

- **移除**：`change_pct` 環比變化率顯示
- **新增**：`ng_rate`（百分比）與 `ng_count`（筆數）
- **顏色邏輯**：
  - `ng_rate > 5` → 紅色（`#ef4444`）+ 警示圖示 ⚠
  - `ng_rate <= 5` → 綠色（`#22c55e`）+ 正常圖示 ✓
  - `current === 0`（無資料）→ 顯示 `—`

---

## 變更檔案清單

| 檔案 | 變更類型 |
|------|----------|
| `backend/routes/admin.py` | 修改 — 新增 ng_count / ng_rate 計算 |
| `src_frontend/src/types/index.ts` | 修改 — DomainStat 新增欄位 |
| `src_frontend/src/components/dashboard/KPICards.tsx` | 修改 — 卡片底部顯示邏輯 |
