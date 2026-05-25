## ADDED Requirements

### Requirement: CAPA 必須具備可追溯源頭

CAPA 單據 SHALL 必須關聯一個源頭（NCMR 或客訴），不可獨立開立。源頭資訊以 `source_type` 與 `source_id` 兩欄位記錄，皆為必填。

#### Scenario: 從 NCMR 開立 CAPA
- **WHEN** QA 在 NCMR 明細頁點擊「開立 CAPA」
- **THEN** 系統建立 CAPA 並自動填入 `source_type='ncmr'`、`source_id=NCMR.id`，於 CAPA 頁面顯示源頭資訊

#### Scenario: 從客訴開立 CAPA
- **WHEN** QA 在客訴明細頁點擊「開立 CAPA」
- **THEN** 系統建立 CAPA 並自動填入 `source_type='complaint'`、`source_id=客訴.id`

#### Scenario: 嘗試獨立開單
- **WHEN** API 收到無 `source_type` 或無 `source_id` 的 CAPA 建立請求
- **THEN** 系統回傳 400 錯誤，訊息為「CAPA 必須關聯 NCMR 或客訴」

### Requirement: D0 立案需記錄判斷準則與嚴重度

CAPA SHALL 在 D0 步驟記錄症狀描述、立案判斷準則（多選）、嚴重度（Critical / Major / Minor）、嚴格度（完整 8D / 簡化 5D）與選填的客戶要求結案日。

#### Scenario: 嚴重度預設聯動嚴格度
- **WHEN** QA 於 D0 選擇嚴重度為 Critical 或 Major
- **THEN** 系統將嚴格度欄位預設為「完整 8D」，但允許 QA 手動 override

#### Scenario: Minor 預設簡化 5D
- **WHEN** QA 於 D0 選擇嚴重度為 Minor
- **THEN** 系統將嚴格度欄位預設為「簡化 5D」，但允許 QA 手動 override

#### Scenario: 症狀描述繼承自 NCMR
- **WHEN** CAPA 由 NCMR 開立
- **THEN** D0 症狀描述欄位預先填入 NCMR 的「不良描述」內容，QA 可編輯

### Requirement: D1 小組成員須結構化記錄

CAPA D1 SHALL 以三個結構化欄位記錄小組成員：Champion（高階負責人）、Leader（8D 領隊）、Members（成員多選），皆引用 `inspector` / 使用者資料表。

#### Scenario: 完整 8D 必填 D1
- **WHEN** CAPA 嚴格度為「完整 8D」且 QA 欲推進至 D2 之後
- **THEN** 系統檢查 D1 的 Leader 欄位必填，否則阻擋並提示「請先指派 Leader」

#### Scenario: 簡化 5D 跳過 D1
- **WHEN** CAPA 嚴格度為「簡化 5D」
- **THEN** D1 步驟於介面隱藏，不參與進度計算

### Requirement: D2 問題描述以 5W2H 引導

CAPA D2 SHALL 提供結構化欄位：What、Where、When、Who、Why、How、How Many，每個欄位獨立儲存，並支援附件。

#### Scenario: 5W2H 欄位個別儲存
- **WHEN** QA 填寫 D2 的 7 個欄位後儲存
- **THEN** 系統將每欄位獨立儲存於資料表，列表頁顯示 What 欄位摘要

### Requirement: D4 真因分析提供 5Why 與魚骨圖兩種工具

CAPA D4 SHALL 允許 QA 選擇 5Why（單鏈 3–7 層動態）、魚骨圖（6M 固定分類）或兩者併用。工具結果以結構化 JSON 儲存，自動匯總至 `root_cause` 欄位（可手動編輯）。

#### Scenario: 5Why 動態增層
- **WHEN** QA 在 5Why 工具中已填 3 層並點擊「再追一層」
- **THEN** 系統新增第 4 層 Why / Answer 欄位，最多允許至第 7 層

#### Scenario: 5Why 最少 3 層
- **WHEN** QA 嘗試移除使 5Why 少於 3 層
- **THEN** 系統阻擋移除並提示「5Why 至少需 3 層」

#### Scenario: 魚骨圖 6M 分類
- **WHEN** QA 切換至魚骨圖工具
- **THEN** 介面顯示 6 個固定分類（人、機、料、法、量、環），各分類可新增多項子因

#### Scenario: 魚骨圖自動 SVG 渲染
- **WHEN** QA 在魚骨圖中輸入子因並儲存
- **THEN** 系統依輸入內容產生標準魚骨圖 SVG 顯示於介面

#### Scenario: 兩工具併用時根本原因合併
- **WHEN** QA 選擇「兩者併用」且兩工具皆有結論
- **THEN** 系統將 5Why 最後一層與魚骨圖標記為「採用」的項目合併匯入 `root_cause`，允許手動編輯

### Requirement: D6 驗證 gate

CAPA D6 SHALL 含「verified」布林欄位，必須勾選為 true 後始能推進至 D7。

#### Scenario: 未驗證阻擋進入 D7
- **WHEN** QA 在 D6 `verified=false` 時嘗試填寫 D7
- **THEN** 系統阻擋並提示「請先確認 D6 驗證通過」

### Requirement: D7 預防再發必須產生橫展任務

CAPA D7 SHALL 提供橫展類型勾選（更新 PFMEA、更新控制計畫、更新 SOP、教育訓練、橫展其他料號、通知客戶、其他）。每勾選一項，系統 SHALL 於 `task` 資料表自動建立對應任務並關聯至本 CAPA。

#### Scenario: 勾選橫展類型即建任務
- **WHEN** QA 在 D7 勾選「更新 PFMEA」並指派負責人與期限
- **THEN** 系統於 `task` 表建立一筆 `source_type='capa'`、`category='pfmea'` 的任務

#### Scenario: 取消勾選刪除未完成任務
- **WHEN** QA 取消勾選某橫展類型且對應任務狀態為「待辦」
- **THEN** 系統刪除該任務並記錄於變更歷史

#### Scenario: 取消勾選阻擋已完成任務
- **WHEN** QA 取消勾選某橫展類型但對應任務狀態為「完成」
- **THEN** 系統阻擋取消並提示「該任務已完成，請改用豁免」

### Requirement: D8 結案 gate

CAPA D8 SHALL 於結案時檢查所有關聯任務狀態。若有任何任務狀態為「待辦」或「進行中」，系統 SHALL 拒絕結案。

#### Scenario: 全部任務完成可結案
- **WHEN** QA 點擊「結案」且所有關聯任務狀態為「完成」或「豁免」
- **THEN** 系統將 CAPA 狀態改為「已結案」，填入結案日期

#### Scenario: 任務未完成擋結案
- **WHEN** QA 點擊「結案」且存在任務狀態為「待辦」或「進行中」
- **THEN** 系統回傳 400 錯誤，訊息列出未完成任務清單

#### Scenario: 任務豁免需備註
- **WHEN** QA 對任務按「豁免」且未填理由
- **THEN** 系統拒絕並要求填寫豁免理由

### Requirement: AIAG 8D 報表產出

CAPA SHALL 於 D8 結案後支援產出 AIAG 標準 8D 報表，格式為 PDF 與 Excel（安泰版範本）。報表內容 SHALL 包含 D0–D8 全部欄位與依步驟分類的附件清單。

#### Scenario: 結案後產出 PDF
- **WHEN** QA 在已結案 CAPA 頁面點擊「下載 8D 報表 (PDF)」
- **THEN** 系統產出 PDF 並下載，內容對應 AIAG 8D 表格欄位、含安泰抬頭

#### Scenario: 結案後產出 Excel
- **WHEN** QA 在已結案 CAPA 頁面點擊「下載 8D 報表 (Excel)」
- **THEN** 系統以安泰範本 `aiag_8d_antai.xlsx` 填入資料並下載

#### Scenario: 未結案不可下載
- **WHEN** QA 在進行中 CAPA 頁面嘗試下載 8D 報表
- **THEN** 系統阻擋並提示「請先結案再產出報表」

### Requirement: CAPA 進度視覺化

CAPA 列表頁與明細頁 SHALL 顯示進度條，標示 D0–D8 各步驟完成狀態，並計算完成百分比。

#### Scenario: 進度條依步驟完成度更新
- **WHEN** QA 完成某 D 步驟必填欄位並儲存
- **THEN** 系統將該 D 步驟標記為「完成」並更新進度條與百分比

### Requirement: 既有 CAPA 資料相容性

既有 CAPA 紀錄 SHALL 在資料遷移後可正常開啟、編輯與檢視。新欄位以 NULLABLE 方式新增，遷移腳本 SHALL 將既有「負責人」資料填入新 `leader_id` 欄位，並將 `rigor` 預設為「完整 8D」。

#### Scenario: 既有資料開啟顯示「舊版」標記
- **WHEN** QA 開啟遷移前已存在的 CAPA
- **THEN** 介面顯示「此單為舊版資料，D0 待補填」提示

#### Scenario: 既有資料的負責人對應 Leader
- **WHEN** 系統執行資料遷移腳本
- **THEN** 既有 CAPA 的 `負責人員姓名` 欄位內容對應到新 `leader_id` 欄位（透過 inspector 表查詢）
