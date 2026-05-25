## ADDED Requirements

### Requirement: 任務為跨模組共用實體

任務 SHALL 為獨立資料表 `task`，含 `source_type` 與 `source_id` 多型外鍵，可關聯至 CAPA（初期）或未來其他模組（稽核、其他）。每筆任務 SHALL 含類別、標題、描述、負責人、應完成日、狀態、完成證明、附件。

#### Scenario: CAPA D7 建立任務
- **WHEN** QA 於 CAPA D7 勾選橫展類型並指派負責人與期限
- **THEN** 系統建立 `task` 紀錄，`source_type='capa'`、`source_id=CAPA.id`、`category=` 對應的類型代碼

#### Scenario: 任務類別限定列舉
- **WHEN** API 收到 task 建立請求且 `category` 不在 ('pfmea','control_plan','sop','training','cross_part','customer_notify','other') 範圍內
- **THEN** 系統回傳 400 錯誤

### Requirement: 任務狀態機

任務狀態 SHALL 為 `pending`（待辦）→ `in_progress`（進行中）→ `completed`（完成）或 `waived`（豁免）。狀態流轉 SHALL 遵守：pending 可至 in_progress / waived；in_progress 可至 completed / waived；completed / waived 為終態。

#### Scenario: 標記任務完成需附完成證明
- **WHEN** 負責人將任務狀態由 in_progress 改為 completed 且未填完成證明
- **THEN** 系統阻擋並要求填寫完成證明或上傳附件

#### Scenario: 豁免任務需備註理由
- **WHEN** 任何使用者將任務狀態改為 waived 且未填豁免理由
- **THEN** 系統阻擋並要求填寫豁免理由

### Requirement: 「我的待辦」首頁區塊

Dashboard SHALL 提供「我的待辦」區塊，列出 `assignee_id = current_user` 且狀態為 pending / in_progress 的任務，依應完成日由近至遠排序，逾期者以紅色標示。

#### Scenario: 顯示當前使用者任務
- **WHEN** 使用者開啟 Dashboard
- **THEN** 「我的待辦」區塊列出該使用者所有未完成任務，含關聯 CAPA / 模組標籤

#### Scenario: 逾期任務紅色標示
- **WHEN** 任務應完成日已過且狀態為 pending 或 in_progress
- **THEN** 「我的待辦」中該任務以紅色顯示，並標示「逾期 N 天」

### Requirement: 任務查詢與篩選

系統 SHALL 提供任務列表頁，支援依負責人、狀態、類別、來源類型、應完成日區間篩選。

#### Scenario: 篩選未完成任務
- **WHEN** QA 於任務列表選擇「狀態 = 進行中」
- **THEN** 系統僅顯示符合條件的任務

### Requirement: CAPA D7 與任務狀態雙向同步

當 CAPA D7 取消勾選某橫展類型時，系統 SHALL 依該類型對應任務的狀態決定處理方式：若為 pending → 刪除任務；若為 in_progress → 阻擋取消；若為 completed → 阻擋取消（請改用豁免）。

#### Scenario: 取消勾選刪除待辦任務
- **WHEN** QA 在 D7 取消勾選「更新 SOP」且該任務狀態為 pending
- **THEN** 系統刪除任務並記錄變更歷史

#### Scenario: 取消勾選阻擋進行中任務
- **WHEN** QA 在 D7 取消勾選「更新 SOP」且該任務狀態為 in_progress
- **THEN** 系統阻擋並提示「該任務正在進行，請先完成或豁免後再取消勾選」
