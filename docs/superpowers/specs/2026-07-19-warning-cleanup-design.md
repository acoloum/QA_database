# SQLAlchemy 與前端 Fast Refresh 警告清理設計

**日期：** 2026-07-19

**狀態：** 已確認

**範圍：** 後端測試中 4 項 SQLAlchemy LegacyAPIWarning，以及前端 ESLint 的 1 項 Fast Refresh warning

## 1. 背景

目前功能測試與 build 均通過，但驗證輸出仍有下列警告：

1. `ExtrusionToleranceService.get_detail()` 使用 SQLAlchemy 1.x 的 `Query.get()`。
2. `ToleranceService.get_tolerance_detail()` 使用 SQLAlchemy 1.x 的 `Query.get()`。
3. `test_shipping_position_roundtrip.py` 兩次使用 `ShippingMeasurement.query.get()`。
4. `TusChart.tsx` 同時匯出 React 元件、色彩常數與一般函式，觸發 `react-refresh/only-export-components`。

本次目標是消除警告來源，不以 pytest warning filter、ESLint disable 或全域規則放寬隱藏問題。

## 2. 後端設計

兩個服務保留目前的主鍵查詢與 eager loading 行為，改用 SQLAlchemy 2.x session API：

```python
db.session.get(
    Model,
    primary_key,
    options=[joinedload(...)],
)
```

此方式維持「依主鍵取單筆」語意，並保留關聯預載；找不到資料時仍沿用現有 `ValueError`。

測試中的兩次查詢改用 fixture 提供的 `db_session.get(ShippingMeasurement, m_id)`，避免測試本身產生 deprecated API warning。

不更動資料模型、交易範圍、API 回應或 migration。

## 3. 前端設計

新增 `src_frontend/src/components/pyrometry/tusChartColors.ts`，只負責：

- TUS 曲線色盤；
- `EXCLUDED_COLOR`；
- `channelLineColor(index, excluded)`。

`TusChart.tsx` 只匯出 React 元件，並從新模組匯入 `channelLineColor`。既有單元測試改為直接測試 `tusChartColors.ts`，不再為測試一般函式而從元件模組匯入。

色碼、索引取餘數方式及排除通道顏色完全不變，因此圖表外觀與資料行為不變。

## 4. 測試策略

採測試先行：

- 後端先以 `LegacyAPIWarning` 視為 error 執行三個警告來源測試，確認舊程式會失敗；修改後相同命令必須通過且無警告。
- 前端先執行 ESLint，確認 `TusChart.tsx` warning 可重現；抽離後 ESLint 必須為 `0 errors / 0 warnings`。
- `TusChart` 色彩測試必須維持通過，證明抽離沒有改變色碼行為。

完成前執行：

- 後端全量 pytest，要求通過且沒有 warning summary；
- 前端全量 Vitest；
- `npm run lint`，要求零 warning；
- `npm run build`；
- `npm audit`；
- `git diff --check`。

## 5. 驗收標準

- 後端全量測試不再出現 `LegacyAPIWarning`。
- 前端 ESLint 顯示 `0 errors / 0 warnings`。
- TUS 圖表色盤、排除通道顏色及畫面行為不變。
- 公差明細查詢仍會預載既有關聯，找不到資料時錯誤契約不變。
- 無 warning suppression、ESLint disable、資料庫 migration 或非必要功能變更。
