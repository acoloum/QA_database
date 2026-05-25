## ADDED Requirements

### Requirement: CARA 用於對供應商發出矯正要求

CARA SHALL 用於要求供應商執行矯正措施。觸發源頭限定為來料異常（NCMR 中來源為 IQC 者）。流程簡化為 D2 / D3 / D4 / D6 / D8，省略 D1（供應商自組團隊）與 D5（供應商寫永久對策回覆）。

#### Scenario: 從 IQC 來料 NCMR 開立 CARA
- **WHEN** QA 在來料異常 NCMR 明細頁點擊「開立 CARA」
- **THEN** 系統建立 CARA 並關聯至該 NCMR，預設供應商欄位帶入 NCMR 的廠商

#### Scenario: 非來料來源不可開 CARA
- **WHEN** QA 嘗試從非來料來源的 NCMR 開立 CARA
- **THEN** 系統阻擋並提示「CARA 僅適用於來料異常」

### Requirement: CARA 步驟限定簡化流程

CARA SHALL 僅含 D2 / D3 / D4 / D6 / D8 五個步驟。其他步驟（D0 / D1 / D5 / D7）於介面隱藏，不參與進度計算。

#### Scenario: 進度條僅顯示 5 步驟
- **WHEN** QA 開啟 CARA 明細頁
- **THEN** 進度條顯示 D2 / D3 / D4 / D6 / D8 五個步驟，依完成度計算百分比

### Requirement: CARA 記錄供應商回覆內容

CARA SHALL 提供欄位記錄供應商回覆的暫時對策（D3）、真因分析（D4）、永久對策驗證（D6）。QA 角色負責登錄供應商提供的內容。

#### Scenario: 供應商回覆內容由 QA 登錄
- **WHEN** QA 收到供應商 8D 回覆並於 CARA 頁填寫各 D 欄位
- **THEN** 系統儲存內容並標記填寫人為當前 QA 使用者

### Requirement: CARA 不產出 AIAG 報表

CARA SHALL 不提供 AIAG 8D 報表下載功能。CARA 為對外發出的要求單，非提交給客戶的完整 8D。

#### Scenario: CARA 頁面無 AIAG 報表按鈕
- **WHEN** QA 開啟任何 CARA 明細頁
- **THEN** 介面不顯示「下載 8D 報表」按鈕

### Requirement: 既有 CARA 資料相容性

既有 CARA 紀錄 SHALL 於資料遷移後可正常開啟、編輯與檢視。新增欄位以 NULLABLE 方式相容。

#### Scenario: 既有 CARA 開啟正常
- **WHEN** QA 開啟遷移前已存在的 CARA
- **THEN** 介面正常顯示既有 D2 / D3 / D4 / D6 / D7 / D8 內容
