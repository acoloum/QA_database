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
| 計算範圍 | 跟隨儀表板時間篩選（本月、本週等） |
| 警示門檻 | 超差率 > 5% → 紅色；≤ 5%（且有資料）→ 綠色；無資料 → 顯示 `—` |

顯示格式的三種狀態：

| 狀態 | 顯示 |
|------|------|
| 本期無檢驗筆數 | `—` |
| 全數合格（ng_count == 0） | `✓ 全數合格` |
| 有 NG（ng_count > 0，≤ 5%） | `✓ 超差率 2.1%（3 筆）` |
| 超差率 > 5% | `⚠ 超差率 8.3%（13 筆）` |

---

## 不在範圍內

- 其他 KPI 卡片（巡邏、NCMR、CAPA、CAR、重工）維持現狀
- 趨勢圖不變
- `change_pct` 和 `trend` 欄位保留在 API 回應中（不刪除）

---

## 技術設計

### 1. 後端 — `backend/routes/admin.py`

在 `get_stats_for_period()` 函式的 `shipping` 區塊，先計算 `_shipping_current` 和 `_shipping_ng`，再組成 dict。當期間內無資料時，`ng_rate` 回傳 JSON `null`（Python `None`）而非 `0.0`，以便前端區分「無資料」與「零超差」：

```python
_shipping_current = count_for_model(ShippingData, ShippingData.date, start_date, end_date)
_shipping_ng = count_for_model(
    ShippingData, ShippingData.date, start_date, end_date,
    ShippingData.is_ng == True
)

stats = {
    "shipping": {
        "current": _shipping_current,
        "previous": count_for_model(ShippingData, ShippingData.date, compare_start, compare_end),
        "ng_count": _shipping_ng,
        "ng_rate": round((_shipping_ng / _shipping_current * 100), 1) if _shipping_current > 0 else None,
        "pending": 0
    },
    # ... 其他 key 不變
}
```

`change_pct` / `trend` 的計算迴圈（line 98 起的 `for key in stats`）**不需修改**，它讀取 `stats[key]['current']` 和 `stats[key]['previous']`，這兩個欄位仍然存在。

> **NULL 處理：** `is_ng` 在資料庫中可為 `NULL`（舊資料或無公差設定的記錄）。`is_ng == True` 的 SQL 查詢自然排除 NULL，因此 NULL 記錄計入分母（`_shipping_current`）但不計入 `_shipping_ng`，等同視為合格，此為預期行為。

---

### 2. 前端型別 — `src_frontend/src/hooks/useDashboard.ts`

`DashboardStats` 介面的 `shipping` 行（line 5）新增兩個可選欄位：

```ts
// 修改前
shipping: { current: number; previous: number; pending: number; trend: string; change_pct: number };

// 修改後
shipping: { current: number; previous: number; pending: number; trend: string; change_pct: number; ng_count?: number; ng_rate?: number | null };
```

---

### 3. 前端元件 — `src_frontend/src/components/dashboard/KPICards.tsx`

#### 3a. `kpiItems` 陣列 — shipping 項目的變更

修改兩處，其餘屬性（`getPending`、`getValue`、`getTrend`、`getChange`、`path`）不變：

1. **`isAnomaly` 改為 `() => false`**：卡片底部的超差率文字已有顏色警示，頂部的 ⚠️ 徽章（`kpi-alert`）會重複，故停用。現有渲染迴圈中的 `{isAnomaly && <span ...>⚠️</span>}` 不需刪除，`false` 使其靜默即可。
2. **新增 `getNgInfo` getter**：讓渲染迴圈識別此卡片需特殊渲染底部。

```ts
{
    label: '出貨檢驗',
    key: 'shipping',
    icon: 'fa-gift',
    getValue: (s: any) => s?.shipping?.current || 0,
    getPending: (s: any) => s?.shipping?.pending || 0,
    getTrend: (s: any) => s?.shipping?.trend || 'stable',
    getChange: (s: any) => s?.shipping?.change_pct || 0,
    path: '/shipping',
    isAnomaly: () => false,   // 改為 false（由底部顏色代替警示）
    getNgInfo: (s: any) => ({
        rate: s?.shipping?.ng_rate ?? null,  // null = 無資料（backend 回傳 None）
        count: s?.shipping?.ng_count ?? 0,   // 缺席時預設 0，向下相容舊快取回應
    }),
},
```

其他五個 kpiItems 項目不做任何修改。

#### 3b. 渲染迴圈 — 替換 `kpi-trend` 的內容

在渲染迴圈（lines 120–162）中，`<div className="kpi-trend">` 目前固定渲染 `{getTrendIcon(trend, change)}`。改為條件渲染：

```tsx
<div className="kpi-trend">
    {(item as any).getNgInfo ? (
        (() => {
            const { rate, count } = (item as any).getNgInfo(stats);
            // 無資料（本期無檢驗筆數）
            if (rate === null) {
                return <span style={{ color: '#94a3b8' }}>—</span>;
            }
            // 全數合格
            if (count === 0) {
                return <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ 全數合格</span>;
            }
            // 有 NG
            const isHigh = rate > 5;
            return (
                <span style={{ color: isHigh ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                    {isHigh ? '⚠ ' : '✓ '}超差率 {rate}%（{count} 筆）
                </span>
            );
        })()
    ) : (
        getTrendIcon(trend, change)
    )}
</div>
```

> **`(item as any).getNgInfo` 的使用：** 以 duck-typing 方式讓 shipping 卡片特殊化，其餘卡片走原有邏輯。這是刻意的設計，避免為 `kpiItems` 建立完整的型別介面。顏色使用 inline style，不新增 CSS class，不修改樣式表。

---

## 變更檔案清單

| 檔案 | 變更類型 | 說明 |
|------|----------|------|
| `backend/routes/admin.py` | 修改 | `get_stats_for_period()` 的 shipping 區塊加入 `ng_count` / `ng_rate`（無資料時為 `None`） |
| `src_frontend/src/hooks/useDashboard.ts` | 修改 | `DashboardStats.shipping` 型別新增 `ng_count?` / `ng_rate?` |
| `src_frontend/src/components/dashboard/KPICards.tsx` | 修改 | shipping 項目加 `getNgInfo`；`isAnomaly` 改為 `() => false`；`kpi-trend` 改為條件渲染 |
