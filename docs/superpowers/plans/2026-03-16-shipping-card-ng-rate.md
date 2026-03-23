# 出貨檢驗卡片改為超差率顯示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將儀表板出貨檢驗 KPI 卡片底部的環比變化率，改為顯示本期超差率（%）與 NG 筆數，超差率 > 5% 顯示紅色警示。

**Architecture:** 後端在現有 `get_stats_for_period()` 的 shipping 區塊新增 `ng_count` 與 `ng_rate` 兩個欄位；前端在 `useDashboard.ts` 擴充型別，在 `KPICards.tsx` 的 shipping 項目加入 `getNgInfo` getter，並在渲染迴圈中條件渲染底部指標。

**Tech Stack:** Flask 3.1 (Python) · SQLAlchemy · React 19 (TypeScript) · TanStack React Query

---

## Chunk 1: 後端新增 ng_count / ng_rate

### Task 1: 後端新增 ng_count / ng_rate

**Files:**
- Modify: `backend/routes/admin.py` — `get_stats_for_period()` 函式的 shipping 區塊
- Test: 手動呼叫 API 驗證（專案無後端單元測試架構，以 curl 驗證）

---

- [ ] **Step 1: 閱讀現有程式碼確認位置**

  開啟 `backend/routes/admin.py`，找到 `get_stats_for_period()` 函式（約 line 10）。
  找到 `stats = {` 字典定義，確認 `"shipping"` 區塊的結構（lines 52–57）：

  ```python
  "shipping": {
      "current": count_for_model(ShippingData, ShippingData.date, start_date, end_date),
      "previous": count_for_model(ShippingData, ShippingData.date, compare_start, compare_end),
      "pending": 0
  },
  ```

- [ ] **Step 2: 在 `stats = {` 之前新增兩行預先計算**

  找到 `stats = {` 這行（約 line 52），在**其正上方**插入：

  ```python
  _shipping_current = count_for_model(ShippingData, ShippingData.date, start_date, end_date)
  _shipping_ng = count_for_model(
      ShippingData, ShippingData.date, start_date, end_date,
      ShippingData.is_ng == True
  )
  ```

  `stats = {` 本身及其他所有 key（patrol / ncmr / capa / rework / cara）**不動**。

- [ ] **Step 3: 只替換 `"shipping"` 子字典**

  在 `stats = {` 字典內，找到原本的 `"shipping"` 區塊：

  ```python
  "shipping": {
      "current": count_for_model(ShippingData, ShippingData.date, start_date, end_date),
      "previous": count_for_model(ShippingData, ShippingData.date, compare_start, compare_end),
      "pending": 0
  },
  ```

  替換為（使用剛才新增的兩個變數）：

  ```python
  "shipping": {
      "current": _shipping_current,
      "previous": count_for_model(ShippingData, ShippingData.date, compare_start, compare_end),
      "ng_count": _shipping_ng,
      "ng_rate": round((_shipping_ng / _shipping_current * 100), 1) if _shipping_current > 0 else None,
      "pending": 0
  },
  ```

  注意：`ng_rate` 在無資料時回傳 `None`（JSON null），不是 `0.0`。其餘 key 保持不變。

- [ ] **Step 4: 啟動 Flask dev server 驗證 API 回應**

  ```bash
  cd backend && python app.py
  ```

  另開終端執行：
  ```bash
  # 先取得 JWT token（替換實際密碼）
  curl -s -X POST http://localhost:5001/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"YOUR_PASSWORD"}' | python -m json.tool
  ```

  複製 token，再呼叫 stats endpoint：
  ```bash
  curl -s http://localhost:5001/api/dashboard/stats?period=this_month \
    -H "Authorization: Bearer YOUR_TOKEN" | python -m json.tool
  ```

  預期回應的 `shipping` 區塊應包含：
  ```json
  "shipping": {
    "current": 156,
    "previous": 58,
    "ng_count": 13,
    "ng_rate": 8.3,
    "pending": 0,
    "trend": "up",
    "change_pct": 169.0
  }
  ```

  確認：
  - `ng_count` 為整數
  - `ng_rate` 為一位小數浮點數（或 `null` 若本期無資料）
  - `change_pct` 與 `trend` 仍然存在且值合理

- [ ] **Step 5: 測試無資料期間（ng_rate 應為 null）**

  呼叫一個確定沒有出貨資料的時間區間：
  ```bash
  curl -s "http://localhost:5001/api/dashboard/stats?period=custom&start=2000-01-01&end=2000-01-31" \
    -H "Authorization: Bearer YOUR_TOKEN" | python -m json.tool
  ```

  預期 `"ng_rate": null`（不是 0 也不是 0.0）。

- [ ] **Step 6: Commit**

  ```bash
  git add backend/routes/admin.py
  git commit -m "feat(dashboard): add ng_count and ng_rate to shipping stats API"
  ```

---

## Chunk 2: 前端型別與元件

### Task 2: 擴充 TypeScript 型別

**Files:**
- Modify: `src_frontend/src/hooks/useDashboard.ts` — `DashboardStats` 介面的 `shipping` 欄位

---

- [ ] **Step 1: 修改 DashboardStats 介面**

  開啟 `src_frontend/src/hooks/useDashboard.ts`，找到 line 5 的 `shipping` 型別定義：

  ```ts
  shipping: { current: number; previous: number; pending: number; trend: string; change_pct: number };
  ```

  替換為：

  ```ts
  shipping: { current: number; previous: number; pending: number; trend: string; change_pct: number; ng_count?: number; ng_rate?: number | null };
  ```

- [ ] **Step 2: 確認 TypeScript 編譯無誤**

  ```bash
  cd src_frontend && npx tsc --noEmit
  ```

  預期：無錯誤輸出。

---

### Task 3: 修改 KPICards 元件

**Files:**
- Modify: `src_frontend/src/components/dashboard/KPICards.tsx`

---

- [ ] **Step 1: 修改 kpiItems 陣列中的 shipping 項目**

  開啟 `src_frontend/src/components/dashboard/KPICards.tsx`，找到 `kpiItems` 陣列的 `shipping` 項目（lines 14–24）：

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
      isAnomaly: (s: any) => (s?.shipping?.trend === 'up' && s?.shipping?.change_pct > 30)
  },
  ```

  替換為：

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
      isAnomaly: () => false,
      getNgInfo: (s: any) => ({
          rate: s?.shipping?.ng_rate ?? null,
          count: s?.shipping?.ng_count ?? 0,
      }),
  },
  ```

- [ ] **Step 2: 修改渲染迴圈的 kpi-trend 區塊**

  在渲染迴圈中找到（約 line 154–156）：

  ```tsx
  <div className="kpi-trend">
      {getTrendIcon(trend, change)}
  </div>
  ```

  替換為：

  ```tsx
  <div className="kpi-trend">
      {(item as any).getNgInfo ? (
          (() => {
              const { rate, count } = (item as any).getNgInfo(stats);
              if (rate === null) {
                  return <span style={{ color: '#94a3b8' }}>—</span>;
              }
              if (count === 0) {
                  return <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ 全數合格</span>;
              }
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

- [ ] **Step 3: 確認 TypeScript 編譯無誤**

  ```bash
  cd src_frontend && npx tsc --noEmit
  ```

  預期：無錯誤輸出。

- [ ] **Step 4: 啟動前端 dev server 目視驗證**

  確認後端仍在執行（`python app.py`），再啟動前端：

  ```bash
  cd src_frontend && npm run dev
  ```

  開啟 `http://localhost:5173`，登入後進入儀表板，確認：

  1. 出貨檢驗卡片底部顯示「超差率 X.X%（N 筆）」或「全數合格」
  2. 超差率 > 5% 時文字為**紅色** `#ef4444`
  3. 超差率 ≤ 5% 時文字為**綠色** `#22c55e`
  4. 卡片右上角不再出現 ⚠️ 徽章
  5. 其他五張卡片（巡邏、不合格品、重工、CAR、矯正措施）顯示正常，仍有環比趨勢箭頭

- [ ] **Step 5: 切換時間篩選確認動態更新**

  在儀表板切換「本週」、「本月」、「上個月」篩選，確認：
  - 超差率數值跟著改變
  - 切換到無資料的區間時，顯示「—」

- [ ] **Step 6: Production build 最終驗證**

  ```bash
  cd src_frontend && npm run build
  ```

  預期：無 TypeScript 編譯錯誤，無 Vite build 錯誤。

- [ ] **Step 7: Commit**

  ```bash
  git add src_frontend/src/hooks/useDashboard.ts \
          src_frontend/src/components/dashboard/KPICards.tsx
  git commit -m "feat(dashboard): replace shipping change_pct with ng_rate display"
  ```
