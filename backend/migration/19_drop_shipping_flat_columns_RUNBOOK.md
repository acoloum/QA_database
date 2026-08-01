# 階段 3 Runbook — 移除出貨檢驗扁平量測欄位

本檔記錄「出貨檢驗量測資料」從「扁平欄位 + 子表雙寫」收斂到「只用子表」的最後步驟。
**階段 1（讀取改子表）與階段 2（匯入寫子表）已完成並上線。** 目前仍保留扁平欄位的
「寫入」作為安全網。本階段在觀察期結束、確認無誤後執行。

## 背景

- 子表：`出貨巡檢量測明細`（`ShippingMeasurement`，Numeric 型別）— 目前唯一被讀取的來源
- 扁平欄位：`出貨檢驗數據` 上的 `外徑1-min`…`真圓度10` 等 120 欄（實際為 NUMERIC）
- 階段 1 已驗證：子表為扁平的**超集**、SPC 回歸 720/720 一致、is_ng 同公差比對 6095 筆 0 差異

## 前置確認（全部打勾才執行）

- [ ] 階段 1+2 已上線並觀察 1~2 週
- [ ] SPC 圖表（X-R、Cp/Cpk、PPM、分佈）顯示正常
- [ ] 超差（is_ng）判定正常
- [ ] Excel 匯入後資料於列表/SPC/編輯皆可見
- [ ] 已完整備份資料庫

## 執行步驟

### 1. 重新產生 SPC 回歸基準並比對（確認此刻仍一致）
```
.\venv\Scripts\python.exe -m backend.scripts.spc_regression save
.\venv\Scripts\python.exe -m backend.scripts.spc_regression compare   # 應全部一致
```

### 2. 移除程式中扁平欄位的「寫入」

**`backend/services/shipping_service.py` → `save_data`**
- 移除 `measurements` 分支裡對扁平欄位的 `setattr(...)`（保留建立子表明細的部分）
- 移除 `else` 舊格式回退整段（前端早已只送巢狀 `measurements`）
- 移除 `ITEM_FLAT_MAP` 中僅供扁平寫入用途的部分（子表建立改用 item 名稱即可）

**`backend/services/shipping_service.py` → `import_data`**
- 移除迴圈內對扁平欄位的 `setattr(...)`（保留建立子表明細與 `parse_num`）

> 移除後務必再跑一次步驟 1 的 `compare` 確認一致。

### 3. 移除 model 的扁平欄位定義

**`backend/models.py` → `ShippingData`**
- 刪除 `for i in range(1, 11):` 那段動態欄位定義（`od{i}_min` … `roundness{i}`，第 ~133–145 行）

### 4. 執行 DROP migration（**不可逆**）
```
Set-Item -Path Env:PGPASSWORD -Value'<密碼>'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -d qa_database -f backend/migration/19_drop_shipping_flat_columns.sql
```

### 5. 重啟後端、回歸與煙霧測試
```
.\venv\Scripts\python.exe -m backend.scripts.spc_regression save      # 以最終狀態重建基準
```
- 手動煙霧：新增一筆、編輯一筆、匯入一筆、看 SPC 圖、看超差標示

## 回滾

DROP 為不可逆。若需回滾，從步驟 0 的備份還原資料庫，並 `git revert` 對應 commit。
扁平欄位的歷史資料在 DROP 前都仍存在，DROP 前的任何階段都可安全回滾程式碼。

## 已完成（本次預備）

- 已建立 `19_drop_shipping_flat_columns.sql`（**尚未執行**）
- 已移除死碼：`ShippingService.create` / `update` / `_to_dict`、`ShippingData.get_measurement`
