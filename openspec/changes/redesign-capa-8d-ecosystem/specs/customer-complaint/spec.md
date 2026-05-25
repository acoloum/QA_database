## ADDED Requirements

### Requirement: 客訴獨立模組記錄外部不良

客訴 SHALL 為獨立資料表 `customer_complaint`，與 NCMR 並列為 CAPA 源頭。記錄客戶端發現的不良事件，欄位包含客戶、客訴日、料號、不良描述、客戶聯絡人、嚴重度、附件。

#### Scenario: 建立客訴
- **WHEN** QA 在客訴頁面點擊「新增」並填寫必填欄位（客戶、客訴日、料號、不良描述）
- **THEN** 系統建立客訴紀錄，狀態預設為「待處理」

#### Scenario: 客訴可開立 CAPA
- **WHEN** QA 在客訴明細頁點擊「開立 CAPA」
- **THEN** 系統建立 CAPA 並以 `source_type='complaint'`、`source_id=客訴.id` 關聯

### Requirement: 應答時效追蹤

客訴 SHALL 提供應答期限欄位（初步回覆期限、最終回覆期限），系統 SHALL 計算剩餘天數並於 Dashboard 顯示即將逾期 / 已逾期的客訴清單。

#### Scenario: 設定應答期限
- **WHEN** QA 於客訴設定初步回覆期限為 7 天後
- **THEN** 系統儲存期限並開始倒數計算

#### Scenario: 逾期警示
- **WHEN** 客訴應答期限已過且狀態仍為「待處理」或「處理中」
- **THEN** Dashboard 顯示該客訴於「逾期客訴」區塊，並以紅色標示

### Requirement: 回覆內容與滿意度

客訴 SHALL 提供欄位記錄初步回覆內容、最終回覆內容、客戶滿意度（1–5 分）、滿意度備註。

#### Scenario: 登錄回覆內容
- **WHEN** QA 填寫初步回覆內容並按「送出回覆」
- **THEN** 系統儲存回覆內容與送出時間，狀態轉為「處理中」

#### Scenario: 結案需填滿意度
- **WHEN** QA 將客訴狀態改為「已結案」但未填滿意度
- **THEN** 系統阻擋並要求填寫滿意度

### Requirement: 重複客訴自動警示

客訴 SHALL 於建立時自動比對歷史紀錄（客戶 + 料號 + 不良類別），若 12 個月內有相同組合的客訴，系統 SHALL 警示「重複客訴」並列出歷史單號。

#### Scenario: 偵測到重複客訴
- **WHEN** QA 建立客訴且過去 12 個月內存在「相同客戶 + 相同料號 + 相同不良類別」紀錄
- **THEN** 系統於儲存後顯示警示對話框，列出歷史客訴單號與日期

### Requirement: 客戶與料號維度統計

系統 SHALL 提供客訴統計頁面，依客戶、料號、不良類別、月份維度匯總客訴次數與趨勢。

#### Scenario: 依客戶統計
- **WHEN** QA 於客訴統計頁選擇「依客戶」分組
- **THEN** 系統顯示各客戶於選定期間內的客訴件數與排名

#### Scenario: 依料號統計
- **WHEN** QA 於客訴統計頁選擇「依料號」分組
- **THEN** 系統顯示各料號客訴件數與重複率（重複客訴比例）

### Requirement: Warranty 與 Field Failure 追蹤

客訴 SHALL 提供分類欄位 `complaint_type ENUM('quality', 'warranty', 'field_failure')`，分別對應一般品質客訴、保固期內失效、現場使用失效。Warranty / Field Failure 類別 SHALL 額外記錄失效裝置序號、使用環境、失效時數。

#### Scenario: 建立 Warranty 客訴
- **WHEN** QA 建立客訴並選擇類別為 Warranty
- **THEN** 介面額外顯示「失效裝置序號、使用環境、失效時數」三個欄位

#### Scenario: Warranty 統計獨立呈現
- **WHEN** QA 於客訴統計頁查看 Warranty 類別
- **THEN** 系統獨立顯示 Warranty 件數、平均失效時數、料號分布
