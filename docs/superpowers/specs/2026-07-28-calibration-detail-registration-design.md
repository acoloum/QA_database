# 量測設備與校正詳細數據登錄模組設計

日期：2026-07-28

狀態：設計已由使用者核准，待書面規格審閱

適用專案：`C:\QC_Database`

## 1. 背景

現有系統已具備通用量測設備主檔、校驗紀錄、補正點、設備狀態事件及 MSA 設備資格判定。後端設備 API 已獨立為 `/api/measurement-equipment`，但前端仍掛在 `/msa/equipment`，校驗表單也只能保存每個補正點的一筆名目值、器示值及補正值，不能保存完整的重複讀值、逐點允差、環境條件、標準器快照及自動判定證據。

校正是跨模組共用的量測資源治理能力，不應由 MSA 擁有。出貨、巡檢、機械性質、CQI-9 與 MSA 都可能使用同一設備及其校正資格，因此本設計將前端、權限、服務與工作流拆成獨立的「量測設備與校正」模組；MSA 只引用已核准且仍有效的校正版本。

## 2. 已核准的核心決策

1. 校正詳細數據登錄從 MSA 拆出，成為獨立模組。
2. 沿用既有通用設備及校驗主體資料，不建立第二套設備主檔。
3. 首版保存完整原始數據：每個校正點可有多次標準讀值及受校件器示值。
4. 正式器差、補正值、統計摘要及合格判定由後端單一權威計算。
5. 允收條件由受控校正模板決定；模板具草稿、送審、核准及不可變版本。
6. 模板依設備類型定義校正點、重複次數、允差、重複性限制及環境要求。
7. 使用獨立權限：`calibration.view`、`calibration.execute`、`calibration.manage`、`calibration.approve`。
8. 建立者、讀值輸入者或送審者不得核准自己的模板或校正紀錄，管理員也不例外。
9. 外校必須有證書附件才能送審；內校以系統原始數據為主要證據，附件可選填；免校必須填寫理由。
10. 內校必須選擇設備主檔中有效、已核准且未逾期的參考標準器，並保存其資格快照。
11. 舊設備與校驗紀錄完整保留；舊校驗紀錄標示為 `summary_legacy`，不得補造不存在的原始讀值。
12. 舊 `/msa/equipment` 導向新設備入口；既有 MSA 研究引用不改寫、不斷鏈。

## 3. 目標與非目標

### 3.1 目標

- 建立設備、校正模板、原始讀值、計算、附件、核准及歷史版本的完整證據軌。
- 支援量塊／標準件的證書值模式，以及標準器與受校件的成對讀值模式。
- 由模板自動產生「校正點 × 重複次數」數據矩陣。
- 支援逐格輸入、鍵盤導覽及從 Excel 貼上多格數據。
- 依每點允差與重複性規則自動判定個別讀值、校正點及整份校正結果。
- 在送審時重新驗證設備、模板、標準器、附件及數據完整性。
- 保持核准證據不可變；退回、更正及修訂以後繼版本表達。
- 讓 MSA 透過穩定的資格介面查詢設備是否具有有效校正證據。

### 3.2 非目標

- 首版不直接連線卡尺、CMM、硬度機或其他儀器。
- 首版不以 OCR 解析外校證書。
- 首版不建立任意公式或使用者腳本引擎。
- 首版不將 CQI-9 記錄器／熱電偶的專用校正資料強制轉換成通用矩陣；只透過既有來源連結納入統一資格判定。
- 首版不補造舊校驗紀錄的原始重複讀值。
- 首版不新增校正 PDF／Excel 報告產生器；證書附件及頁面證據先滿足登錄與稽核需求。

## 4. 模組與檔案邊界

### 4.1 後端

建議邊界：

```text
backend/
├── routes/
│   ├── measurement_equipment.py
│   ├── calibration_templates.py
│   └── calibrations.py
├── services/
│   ├── measurement_equipment_service.py
│   ├── calibration_template_service.py
│   ├── calibration_service.py
│   ├── calibration_calculation.py
│   ├── calibration_eligibility.py
│   └── calibration_errors.py
├── tests/
│   ├── test_calibration_routes.py
│   └── test_services/
│       ├── test_calibration_models.py
│       ├── test_calibration_templates.py
│       ├── test_calibration_calculation.py
│       ├── test_calibration_workflow.py
│       ├── test_calibration_permissions.py
│       ├── test_calibration_attachments.py
│       ├── test_calibration_reference_standards.py
│       └── test_calibration_migration.py
└── migration/
    └── 49_create_calibration_detail_registration.sql
```

`backend/models.py` 仍是 ORM 模型單一來源。既有 `msa_equipment_service.py` 的設備主檔能力逐步搬到 `measurement_equipment_service.py`；原模組保留相容匯出，避免一次破壞現有 MSA 呼叫。MSA 只透過 `calibration_eligibility.py` 取得資格摘要與核准版本快照，不直接修改校正資料。

路由保持薄層，欄位正規化、資格驗證、計算、工作流、附件門檻與職責分離都放在服務層。

### 4.2 前端

```text
src_frontend/src/
├── pages/calibration/
│   ├── CalibrationWorkQueuePage.tsx
│   ├── CalibrationEntryWizardPage.tsx
│   ├── CalibrationDetailPage.tsx
│   ├── CalibrationTemplateListPage.tsx
│   └── CalibrationTemplateEditorPage.tsx
├── pages/equipment/
│   └── MeasurementEquipmentPage.tsx
├── components/calibration/
│   ├── CalibrationStepper.tsx
│   ├── CalibrationConditionForm.tsx
│   ├── CalibrationReadingMatrix.tsx
│   ├── CalibrationPointSummary.tsx
│   ├── CalibrationEvidenceReview.tsx
│   ├── CalibrationWorkflowBar.tsx
│   ├── CalibrationTemplatePointEditor.tsx
│   └── CalibrationTemplateVersionTimeline.tsx
├── hooks/
│   ├── useCalibrations.ts
│   └── useCalibrationTemplates.ts
└── types/
    └── calibration.ts
```

現有 `components/msa` 中純設備功能移至設備或校正領域；MSA 專用元件仍留在 `components/msa`。所有 API 繼續使用共用 Axios instance，伺服器狀態使用 TanStack React Query。

## 5. 導覽與路由

側邊欄新增一級模組「量測設備與校正」：

| 路由 | 用途 |
|---|---|
| `/measurement-equipment` | 設備主檔、校正風險與到期管理 |
| `/calibrations` | 校正工作佇列與歷史查詢 |
| `/measurement-equipment/:equipmentId/calibrations/new` | 依設備建立詳細校正紀錄 |
| `/calibrations/:calibrationId` | 校正詳細證據、工作流與稽核 |
| `/calibration/templates` | 校正模板與生效版本清單 |
| `/calibration/templates/:templateId` | 模板版本編輯、檢閱與核准 |

`/msa/equipment` 使用 React Router 導向 `/measurement-equipment`。MSA 建立研究時只顯示設備資格摘要及校正證據連結；使用者沒有 `calibration.view` 時可看到資格結果與阻擋原因，但不能開啟完整校正原始數據。

## 6. 資料模型

### 6.1 `CalibrationTemplate`

保存模板穩定身分：

- 模板代碼，唯一且不可重用。
- 模板名稱。
- 適用設備類型。
- 說明。
- 狀態：`active`、`inactive`。
- 目前核准版本 ID。
- 建立者、建立時間、更新者、更新時間。

模板被校正紀錄引用後不得硬刪除。

### 6.2 `CalibrationTemplateVersion`

保存受控版本：

- 模板 ID。
- 版本號；同一模板內唯一。
- 校正程序代碼與名稱。
- 程序說明。
- 預設重複次數。
- 環境要求 JSON；只允許服務層定義的欄位結構及數值範圍。
- 是否允許由合格量測範圍自動判為限制使用。
- 版本狀態：`draft`、`submitted`、`approved`、`rejected`、`superseded`。
- 修訂原因。
- 建立者、送審者、核准者及各時間。
- 核准／退回理由。
- 後繼版本 ID。

核准後內容不可修改或刪除。同一模板同一時間只有一個目前生效的核准版本。

### 6.3 `CalibrationTemplatePoint`

每列定義一個受控校正點：

- 模板版本 ID。
- 校正點順序及代碼。
- 量測模式。
- 名目值。
- 單位。
- 參考輸入模式：
  - `certified_value`：使用標準件或證書值。
  - `paired_reading`：每次同時輸入標準器讀值及受校件器示值。
- 必要重複次數。
- 器差下限及上限。
- 判定基礎：
  - `all_readings`：每筆器差都必須在允差內。
  - `mean_error`：平均器差必須在允差內。
- 重複性規則：
  - `none`。
  - `range`，搭配極差上限。
  - `stddev`，搭配標準差上限。
- 資格範圍代碼；用來把同一量測模式或量程的必要校正點分成一組。
- 資格範圍起點及終點；不適用時為空值。
- 是否要求登錄該點的擴充不確定度。
- 是否為必要校正點。
- 操作提示。

所有上限、下限、名目值及重複次數都經服務層有限數值驗證；禁止 NaN、Infinity、超大指數及無意義精度。

### 6.4 擴充 `EquipmentCalibrationRecord`

沿用既有 `設備校驗紀錄`，新增：

- 模板版本 ID。
- 完整模板快照 JSON。
- 資料等級：`detailed`、`summary_legacy`。
- 工作流狀態：
  - `draft`
  - `in_progress`
  - `ready_for_submission`
  - `submitted`
  - `rejected`
  - `approved`
  - `superseded`
  - `voided`
- 樂觀鎖定版本號。
- 校正程序代碼與名稱。
- 校正地點。
- 執行開始及完成時間。
- 環境條件 JSON。
- 整體計算摘要 JSON。
- 計算引擎版本。
- 資料雜湊。
- 送審者與送審時間。
- 退回理由、作廢理由及後繼紀錄 ID。

既有校驗類型、日期、機構、證書、追溯標準、不確定度說明、結果、限制條件、附件、建立與核准資料繼續保留。

### 6.5 `EquipmentCalibrationPoint`

模板實例化後產生實際校正點：

- 校正紀錄 ID。
- 來源模板校正點 ID。
- 校正點順序、代碼及量測模式。
- 名目值。
- 實際參考值；`certified_value` 模式必填，預設帶入模板名目值並由執行者確認。
- 單位。
- 參考輸入模式。
- 必要重複次數。
- 器差上下限。
- 判定及重複性規則快照。
- 平均器差、平均補正值、最小值、最大值、極差及樣本標準差。
- 擴充不確定度及涵蓋因子；模板要求時必填。
- 完整讀值數。
- 校正點結果：`pending`、`pass`、`fail`。

模板後續改版不得改寫已建立校正紀錄中的實際校正點。

### 6.6 `EquipmentCalibrationReading`

保存逐筆原始讀值及計算證據：

- 實際校正點 ID。
- 試驗序號。
- 標準器讀值；`paired_reading` 模式必填。
- 受校件器示值。
- 有效參考值。
- 器差。
- 補正值。
- 個別讀值結果：`pending`、`pass`、`fail`、`not_individually_evaluated`。
- 輸入者及輸入時間。
- 最後修訂者、時間及修訂原因。

草稿階段可修訂，但所有變更寫入共用稽核紀錄。送審後的原始讀值不可更新或刪除；退回後建立後繼校正草稿，不在已送審版本原地覆寫。

### 6.7 `CalibrationReferenceSnapshot`

內校保存參考標準器當時的資格：

- 校正紀錄 ID。
- 參考標準設備 ID。
- 設備編號、名稱、型號、序號、量程、解析度及單位快照。
- 被引用的核准校正紀錄 ID。
- 校正日期、到期日、結果、證書編號及資料雜湊快照。
- 建立快照時間。

同一內校可保存一個或多個模板要求的參考標準器；首版頁面預設一個主要標準器。送審時重新驗證目前資格，成功送審後以快照作為歷史權威。

### 6.8 附件

沿用共用 `附件` 表：

- 外校至少一個證書附件，允許 PDF、JPEG、PNG。
- 內校可附 PDF、JPEG、PNG、XLSX。
- 附件必須先屬於該設備或校正草稿，服務層才能綁定。
- 使用既有受認證下載 API，不產生裸檔案連結。
- 上傳及校正紀錄建立失敗時不得留下錯誤正式關聯。

## 7. 計算與判定

### 7.1 有效參考值

`certified_value`：

```text
有效參考值 = 實際校正點的參考值
```

`paired_reading`：

```text
有效參考值 = 同一次試驗的標準器讀值
```

### 7.2 逐筆計算

```text
器差 = 受校件器示值 − 有效參考值
補正值 = 有效參考值 − 受校件器示值
```

正式數值由後端使用 `Decimal` 計算並依輸入精度及單位規則序列化，不使用二進位浮點數作為資料庫正式證據。

### 7.3 校正點摘要

每個校正點保存：

- 讀值數。
- 平均器差。
- 平均補正值。
- 最小及最大器差。
- 器差極差。
- 樣本標準差；讀值少於兩筆時為不適用。

### 7.4 校正點判定

`all_readings`：

```text
所有必要讀值完整
AND 每筆器差皆位於器差下限與上限之間
AND 重複性規則通過
```

`mean_error`：

```text
所有必要讀值完整
AND 平均器差位於器差下限與上限之間
AND 重複性規則通過
```

上下限為包含端點。只有上限或只有下限時支援單邊判定。缺少必要允差、參考值或讀值時結果為 `pending`，不得送審。

### 7.5 整體判定

- 所有必要校正點完整且通過、模板有效、設備資格符合、內校標準器有效、外校附件齊全時，結果為 `pass`。
- 任一必要校正點失敗時，結果為 `fail`。
- `limited_use` 只能在模板明確允許時由後端產生。後端依資格範圍代碼分組；至少一組的所有必要校正點通過、且至少一組失敗時，結果為 `limited_use`。適用模式、量程及限制理由由通過與失敗的資格範圍快照產生並保存。沒有任何完整合格範圍時結果為 `fail`。
- 擴充不確定度及涵蓋因子作為校正證據保存並顯示；首版正式允收判定仍依模板器差上下限及重複性規則，不把不確定度靜默套入未核准的防護帶公式。
- 前端不得提交或覆寫正式結果；結果完全由後端計算。
- 計算出現非有限值、精度溢位或規則矛盾時回穩定錯誤，不保存通過結果。

## 8. 工作流

### 8.1 模板版本

```text
draft → submitted → approved
                  ↘ rejected
approved → superseded
```

- `calibration.manage` 建立及送審模板版本。
- `calibration.approve` 核准或退回。
- 建立者或送審者不得核准。
- 被退回或已核准版本的修訂建立後繼草稿。

### 8.2 校正紀錄

```text
draft → in_progress → ready_for_submission → submitted → approved
                                           ↘ rejected
approved → superseded
任一非正式狀態 → voided
```

- 建立草稿時鎖定設備及模板版本。
- 第一次保存有效讀值後進入 `in_progress`。
- `/validate` 通過後進入 `ready_for_submission`。
- 送審時重新驗證模板、設備、標準器、附件、原始讀值及結果。
- 送審後原始數據、模板與參考標準器證據不可變。
- 核准者不得是建立者、任一原始讀值輸入者或送審者。
- 退回保留原送審證據，修正建立後繼草稿。
- 核准後的更正建立後繼紀錄；新版核准後舊版標為 `superseded`。

## 9. 頁面設計

### 9.1 校正工作佇列

`/calibrations` 優先顯示：

- 我的草稿及執行中紀錄。
- 待送審。
- 待核准。
- 被退回。
- 即將到期。
- 校正失敗。
- 限制使用。

可依設備編號、設備類型、校正方式、狀態、日期及執行人員篩選。風險狀態必須同時使用文字、圖示及顏色，並顯示阻擋原因。

### 9.2 詳細數據登錄精靈

#### 步驟一：設備與模板

- 顯示設備編號、名稱、序號、量程、解析度、單位及目前資格。
- 只列出已核准且適用該設備類型的模板版本。
- 選擇內校或外校。

#### 步驟二：校正條件

- 內校選擇有效參考標準器。
- 外校輸入機構、證書編號並上傳證書。
- 輸入日期、地點、執行人員、溫度、濕度及模板要求欄位。
- 缺少必要條件時精確顯示欄位錯誤。

#### 步驟三：原始數據

- 由模板建立「校正點 × 重複次數」矩陣。
- 支援 Tab、Shift+Tab、方向鍵及 Enter 導覽。
- 支援從 Excel 貼上矩形數據；欄列數不符時先預覽錯誤，不部分套用。
- 每次保存由後端回傳器差、補正值、摘要及暫時判定。
- 草稿可不完整；狀態及未完成數量保持可見。
- 行動裝置改為逐校正點卡片輸入，不縮小密集矩陣。

#### 步驟四：檢閱與送審

- 顯示整體結果及各校正點摘要。
- 顯示完整性、模板、標準器、附件及環境證據。
- 列出所有阻擋項目及定位連結。
- 無阻擋項目才能送審。

草稿保存在伺服器端。頁面有尚未完成的保存請求或本地未送出變更時，離開前提示使用者。

### 9.3 校正紀錄詳情

證據閱讀順序：

1. 整體判定、狀態及下一步。
2. 校正點摘要。
3. 完整原始讀值。
4. 標準器及模板快照。
5. 環境條件與附件。
6. 送審、核准、退回、作廢理由。
7. 版本及稽核歷程。

核准畫面要求核准者確認原始讀值、計算、標準器資格、附件及模板版本，並填寫非空白核准理由。

### 9.4 模板管理

- 模板清單顯示適用設備類型、目前版本、狀態及生效時間。
- 編輯器提供校正點及允差矩陣、重複次數、判定基礎、重複性規則、環境要求與操作提示。
- 送審前提供唯讀預覽。
- 版本時間軸顯示草稿、送審、核准、取代及退回證據。

## 10. API

### 10.1 設備

既有 API 保持相容：

```text
GET    /api/measurement-equipment
POST   /api/measurement-equipment
GET    /api/measurement-equipment/:id
PATCH  /api/measurement-equipment/:id
```

### 10.2 模板

```text
GET    /api/calibration-templates
POST   /api/calibration-templates
GET    /api/calibration-templates/:id
POST   /api/calibration-templates/:id/versions
PATCH  /api/calibration-template-versions/:id
POST   /api/calibration-template-versions/:id/submit
POST   /api/calibration-template-versions/:id/approve
POST   /api/calibration-template-versions/:id/reject
```

### 10.3 校正紀錄

```text
GET    /api/calibrations
POST   /api/calibrations
GET    /api/calibrations/:id
PATCH  /api/calibrations/:id
PUT    /api/calibrations/:id/readings
POST   /api/calibrations/:id/validate
POST   /api/calibrations/:id/submit
POST   /api/calibrations/:id/approve
POST   /api/calibrations/:id/reject
POST   /api/calibrations/:id/void
```

所有修改及狀態轉換請求接受 `expected_version`。讀值 API 以單一交易驗證並保存整次矩陣變更；任一儲存格無效時整批拒絕並回傳校正點代碼及試驗序號，不留下半套數據。

清單 API 使用有上限的分頁及白名單排序。附件上傳及下載沿用共用受認證 API。

## 11. 權限與角色

| 權限 | 能力 |
|---|---|
| `calibration.view` | 查看設備、模板、校正證據及附件 |
| `calibration.execute` | 建立校正草稿及輸入原始讀值 |
| `calibration.manage` | 管理設備、建立模板版本、驗證、送審及作廢 |
| `calibration.approve` | 核准或退回模板及校正紀錄 |

初始角色：

- `inspector`：`calibration.view`、`calibration.execute`
- `qa_supervisor`：`calibration.view`、`calibration.execute`、`calibration.manage`
- `qc_manager`：`calibration.view`、`calibration.approve`
- `admin`：全部校正權限

MSA 權限不自動授予校正修改權。`msa.view` 可從 MSA 介面取得設備資格摘要；開啟完整校正證據仍需要 `calibration.view`。

所有 mutation 在任何管理員捷徑前先驗證 JWT 使用者仍為啟用狀態。權限不足、自我核准或資格不符必須零寫入。

## 12. 錯誤處理與並發

代表性穩定錯誤碼：

| HTTP | 錯誤碼 | 用途 |
|---|---|---|
| 400 | `CALIBRATION_FIELD_INVALID` | 欄位或讀值格式錯誤 |
| 403 | `CALIBRATION_PERMISSION_DENIED` | 權限不足 |
| 403 | `CALIBRATION_SELF_APPROVAL_FORBIDDEN` | 違反職責分離 |
| 404 | `CALIBRATION_NOT_FOUND` | 校正紀錄不存在 |
| 409 | `CALIBRATION_VERSION_CONFLICT` | 樂觀鎖定版本衝突 |
| 409 | `CALIBRATION_STATUS_CONFLICT` | 工作流狀態不允許操作 |
| 422 | `CALIBRATION_TEMPLATE_NOT_APPROVED` | 模板未核准或已失效 |
| 422 | `CALIBRATION_REFERENCE_INVALID` | 參考標準器資格不符 |
| 422 | `CALIBRATION_CERTIFICATE_REQUIRED` | 外校缺少證書附件 |
| 422 | `CALIBRATION_DATA_INCOMPLETE` | 必要原始數據不完整 |
| 422 | `CALIBRATION_NUMERIC_FAILURE` | 計算無法產生有限證據 |

錯誤 `details` 必須能定位：

- 精靈步驟。
- 欄位名稱。
- 校正點代碼。
- 試驗序號。
- 目前及預期版本。

同一草稿的更新採版本號條件更新。同一送審版本的並發核准使用列鎖或條件更新，恰好一個請求可成功。

## 13. Migration 49 與舊資料相容

Migration 49 採非破壞式策略：

1. 建立校正模板、模板版本、模板校正點、實際校正點、原始讀值及參考標準器快照表。
2. 擴充 `設備校驗紀錄` 的模板、資料等級、工作流、版本、計算及稽核欄位。
3. 將既有校驗紀錄標示為 `summary_legacy`。
4. 既有已核准紀錄映射為新的 `approved` 工作流狀態；草稿維持 `draft`。
5. 既有 `設備校驗補正點` 原樣保留，詳情頁以「舊版摘要補正點」呈現。
6. 不由名目值及器示值反推任何重複讀值、標準差或模板版本。
7. MSA 與 CQI-9 的既有設備連結及外鍵保持不變。
8. 建立 PostgreSQL constraint／trigger，保護已送審或核准的模板版本、原始讀值、計算摘要、資料雜湊及標準器快照。

執行 migration 前必須確認正式資料庫最新 migration 編號仍可使用 49；若編號已占用，使用下一個可用編號，但資料結構及行為不變。

## 14. 驗證策略

### 14.1 TDD

每個新行為先建立因功能缺失而失敗的窄測試，確認失敗原因正確後才實作最小功能。模型、計算、工作流、權限、附件、前端矩陣及路由皆遵守此流程。

### 14.2 後端測試

- 模板版本核准後不可修改或刪除。
- 校正點的上下限、重複次數、判定及重複性規則驗證。
- `certified_value` 及 `paired_reading` 的有效參考值。
- 使用 `Decimal` 的器差、補正值、平均值、極差及樣本標準差。
- 雙邊、單邊、包含端點、每筆及平均器差判定。
- 極差及標準差重複性限制。
- 資格範圍分組及自動限制使用判定。
- 模板要求的擴充不確定度與涵蓋因子完整性。
- 缺值、NaN、Infinity、極端尺度、精度溢位及矛盾規則。
- 外校附件及免校理由門檻。
- 內校參考標準器狀態、到期日及核准版本資格。
- 草稿矩陣保存的交易原子性。
- 送審後原始讀值及計算證據不可變。
- 自我核准、inactive JWT、權限不足及所有零寫入防線。
- 並發核准只有一個成功。
- 舊 `summary_legacy` 紀錄可讀且不產生虛構統計。
- MSA 只接受有效、已核准的校正證據。
- PostgreSQL trigger 與 SQLite 單元測試之外的正式資料庫整合測試。

### 14.3 前端測試

- 新路由及舊 `/msa/equipment` 導向。
- 四步精靈的欄位及步驟驗證。
- 模板自動產生讀值矩陣。
- Tab、Shift+Tab、方向鍵、Enter 及焦點狀態。
- Excel 多格貼上成功與整批拒絕。
- 行動版逐校正點輸入。
- 權限控制及完整路由保護。
- 模板版本送審、核准、退回及後繼版本。
- 外校附件阻擋。
- `409`、`422`、校正點及試驗序號錯誤定位。
- 核准確認項目及非空白理由。
- 狀態不只使用顏色，表格有 caption、欄列標題及鍵盤可用性。

### 14.4 完整驗證

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q

Set-Location src_frontend
npm test
npm run lint
npm run build
npm audit

Set-Location ..
git diff --check
```

Migration 套用後必須重啟實際後端服務，再以不同權限帳號完成 authenticated smoke：

1. 建立模板及版本。
2. 由另一名核准者核准模板。
3. 建立有效參考標準器及其核准校正證據。
4. 建立內校詳細紀錄。
5. 輸入多次原始讀值並驗證自動計算。
6. 驗證超差會產生失敗且不能手動改成通過。
7. 送審並由非執行者核准。
8. 驗證核准後不可修改。
9. 從 MSA 建立研究流程確認設備資格可被引用。
10. 建立外校草稿，確認缺少證書時被阻擋、上傳後可送審。
11. 清理 smoke 建立的非正式測試資料；正式核准證據依測試隔離策略處理，不直接硬刪除。

## 15. 驗收條件

1. 校正模組有獨立導覽、路由、權限及服務邊界。
2. 受控模板可定義校正點、重複次數、允差、判定基礎、重複性及環境要求。
3. 模板核准後不可修改，修訂建立後繼版本。
4. 詳細登錄頁可保存每點多次原始讀值。
5. 後端正確計算器差、補正值、平均值、極差、標準差及逐層判定。
6. 模板可要求不確定度證據，並能依合格資格範圍自動產生限制使用結果。
7. 前端不能提交或覆寫正式校正結果。
8. 外校沒有證書附件時不得送審。
9. 內校只能使用有效參考標準器，並保存資格快照。
10. 建立者、讀值輸入者或送審者不能核准自己的紀錄。
11. 核准證據不可原地修改或刪除。
12. 舊校驗紀錄可追溯顯示，且明確標示為摘要資料。
13. 舊 MSA 設備入口正確導向新模組，既有研究引用不斷鏈。
14. MSA 只能引用有效且已核准的校正證據。
15. 後端、前端、資料庫約束、build、lint、audit、diff check 及正式服務 smoke 全部取得可驗證結果後，才能宣告完成。

## 16. 建議實作順序

1. Migration、ORM 模型、不可變約束及舊資料標記。
2. 純計算引擎與完整數值測試。
3. 模板版本服務、API、權限及核准工作流。
4. 校正紀錄、標準器快照、附件門檻及工作流 API。
5. 設備頁搬遷、獨立導覽及舊路由導向。
6. 模板管理頁。
7. 四步詳細數據登錄精靈及矩陣互動。
8. 校正詳情、核准與稽核頁。
9. MSA 資格介面相容調整。
10. 完整回歸、PostgreSQL 約束、服務重啟及 authenticated smoke。

每個階段都必須保持可測、可回滾且不破壞既有設備與 MSA 引用。
