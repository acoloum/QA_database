# MSA 第四版完整模組設計

日期：2026-07-27

狀態：已完成需求與設計核准，待使用者審閱書面規格

適用專案：`C:\QC_Database`

## 1. 背景

現有系統具備出貨檢驗、巡檢、機械性質、進階 SPC、CQI-9 校正資料及共用稽核能力，但沒有正式的量測系統分析（MSA）模組。現有 `SpcStudy.msa_status` 只是一個狀態欄位，不能保存研究設計、原始讀值、設備與校正快照、統計計算、核准證據或再研究歷程。

本設計依使用者提供的《MSA手册(第四版)中文版.pdf》規劃，主要依據包括：

- PDF 第 2 頁：基本計量型、基本計數型、不可重複與複雜量測系統的方法選擇。
- PDF 第 55–60 頁：研究準備、樣本代表性、隨機化、解析度及結果接受原則。
- PDF 第 60 頁：一般寬度誤差指引為低於 10%、10%–30%、高於 30%，且 ndc 應大於或等於 5；最終準則仍須考慮用途、風險與顧客要求。
- PDF 第 62–70 頁：穩定性、偏倚與線性研究。
- PDF 第 70–93 頁：極差法、平均值與極差法及 ANOVA GRR。
- PDF 第 94–107 頁：計數型假設試驗、Kappa、有效性與錯誤風險。
- PDF 第 109 頁以後：不可重複、破壞性與複雜量測系統。

本模組的目的不是產生一張 GRR 計算表，而是建立從研究策劃、盲測執行、統計證據、工程判斷、核准到再研究的受控工作流。

## 2. 已核准的核心決策

1. 建立獨立 MSA 垂直模組，不將 MSA 資料塞入現有 SPC 研究模型。
2. 建立跨模組可重用的通用量測設備主檔。
3. 首版涵蓋手冊核心方法：
   - 計量型 GRR：極差法、平均值與極差法、交叉型 ANOVA。
   - 偏倚。
   - 線性。
   - 穩定性。
   - 計數型 Kappa、有效性、錯誤接受與錯誤拒收。
   - 不可重複／破壞性研究設計。
4. 支援頁面逐筆輸入、受控矩陣輸入與 Excel 範本匯入，並預留未來儀器串接欄位。
5. 採獨立權限：`msa.view`、`msa.execute`、`msa.manage`、`msa.approve`。
6. 建立者、資料輸入者或主要執行者不得核准自己的研究。
7. 使用者提供的 `measurements (1).csv` 作為設備主檔初始資料來源，採受控清理後匯入。
8. 報廢、維修、校正逾期或資料待確認設備不得開始正式研究。
9. 判定準則採不可變受控版本，支援顧客、產品與特性風險差異。
10. 正式輸出同時提供 PDF 與 Excel。
11. 再研究採固定週期與事件觸發雙軌。
12. 首頁採「風險導向工作台」，結果頁採「分層證據」。

## 3. 目標與非目標

### 3.1 目標

- 保存完整研究設計、原始量測、統計結果、設備／校正／準則快照及決策證據。
- 所有正式數值由後端單一權威計算，前端與報告不得重算。
- 讓檢驗人員依盲測與隨機順序可靠地執行研究。
- 讓 QA 管理者從風險與到期事項管理研究、設備與資料品質。
- 讓核准者能由結論逐層追到圖表、ANOVA、原始讀值與版本雜湊。
- 保持研究版本不可變、可重現及可獨立確效。
- 保持設備目前狀態與研究歷史快照分離，不因設備日後異動改寫舊報告。

### 3.2 非目標

- 首版不直接連線卡尺、CMM、硬度機或其他儀器。
- 不以 MSA 取代量測不確定度評估。
- 不自動用 OCR 解析校正證書。
- 不把 MSA 結果硬轉換成 SPC 能力指數。
- 不用現有檢驗資料反推 GRR；沒有零件、評價人與重複試驗結構時必須回報不適用。
- 不提供可任意修改公式的使用者腳本環境。

## 4. 架構與檔案邊界

### 4.1 後端

路由保持薄層，所有統計與工作流規則集中在服務層。

建議新增：

```text
backend/
├── routes/
│   ├── msa.py
│   └── measurement_equipment.py
├── services/
│   ├── msa_contracts.py
│   ├── msa_errors.py
│   ├── msa_permissions.py
│   ├── msa_equipment_service.py
│   ├── msa_import_service.py
│   ├── msa_criteria_service.py
│   ├── msa_study_service.py
│   ├── msa_design_service.py
│   ├── msa_variable_grr.py
│   ├── msa_bias_linearity.py
│   ├── msa_stability.py
│   ├── msa_attribute.py
│   ├── msa_nonrepeatable.py
│   ├── msa_report.py
│   └── msa_validation.py
├── tests/
│   ├── test_msa_routes.py
│   └── test_services/
│       ├── test_msa_models.py
│       ├── test_msa_equipment.py
│       ├── test_msa_import.py
│       ├── test_msa_workflow.py
│       ├── test_msa_variable_grr.py
│       ├── test_msa_bias_linearity.py
│       ├── test_msa_stability.py
│       ├── test_msa_attribute.py
│       ├── test_msa_nonrepeatable.py
│       ├── test_msa_report.py
│       └── test_msa_golden.py
└── migration/
    └── 44_create_msa_and_measurement_equipment.sql
```

實作前必須重新確認最新 migration 編號；若 44 已被占用，須使用下一個可用編號。

既有 `backend/models.py` 仍是 ORM 模型單一來源。`backend/app.py` 註冊兩個新 blueprint。

### 4.2 前端

```text
src_frontend/src/
├── pages/msa/
│   ├── MsaWorkspacePage.tsx
│   ├── MsaStudyListPage.tsx
│   ├── MsaStudyWizardPage.tsx
│   ├── MsaDataCollectionPage.tsx
│   ├── MsaResultPage.tsx
│   ├── MeasurementEquipmentPage.tsx
│   ├── MsaCriteriaPage.tsx
│   └── MsaImportHistoryPage.tsx
├── components/msa/
│   ├── workspace/
│   ├── study/
│   ├── collection/
│   ├── results/
│   ├── equipment/
│   ├── criteria/
│   └── imports/
├── hooks/
│   ├── useMsaStudies.ts
│   ├── useMsaEquipment.ts
│   ├── useMsaCriteria.ts
│   └── useMsaImports.ts
└── types/
    └── msa.ts
```

所有 API 仍使用既有 `services/api.ts` Axios instance。Server state 使用 React Query，不另建重複的資料存取層。

### 4.3 可安全重用的既有能力

- `AuditLog` 與 `log_audit`。
- 共用附件儲存與 MIME／檔案大小驗證。
- JWT、角色與權限驗證模式。
- 全域錯誤回應模式。
- 狀態轉換、不可變版本與資料雜湊的 SPC 設計原則。

不可直接重用 `SpcStudy`、`SpcStudyVersion` 或 `SpcStudySample`，因為 SPC 子組資料模型無法正確表示 MSA 的零件 × 評價人 × 試驗結構。

## 5. 權限與職責分離

| 權限 | 能力 |
|---|---|
| `msa.view` | 檢視研究、結果、設備、準則及報告 |
| `msa.execute` | 建立草稿、輸入／匯入量測值、完成個人量測任務 |
| `msa.manage` | 凍結計畫、啟動研究、修正資料、執行分析、送審、管理設備與準則草稿 |
| `msa.approve` | 核准／退回研究、核准設備校正與判定準則版本、作廢正式版本 |

建議初始角色映射：

- `inspector`：`msa.view`、`msa.execute`
- `qa_supervisor`：`msa.view`、`msa.execute`、`msa.manage`
- `qc_manager`：`msa.view`、`msa.approve`
- `admin`：全部 MSA 權限

即使是 `admin`，仍禁止核准自己建立、主要執行或輸入資料的研究。緊急例外不得繞過職責分離；必須改由另一名具 `msa.approve` 的使用者處理。

## 6. 資料模型

### 6.1 通用量測設備

#### `MeasurementEquipment`

保存穩定身分與目前管理狀態：

- 設備編號，唯一且不可重用。
- 名稱、設備類型、製造商、型號、序號。
- 量測範圍下限／上限、解析度、單位。
- 部門、存放位置、保管人。
- 狀態：`pending_review`、`active`、`maintenance`、`inactive`、`scrapped`。
- 校驗類別：`internal`、`external`、`exempt`。
- 校驗週期月數。
- 是否為參考標準、是否直接影響產品判定。
- 建立者、建立時間、更新者、更新時間。

已被研究引用的設備不得硬刪除。

#### `MeasurementEquipmentLink`

將通用設備主檔連到既有專用設備實體，例如 CQI-9 的 `Recorder`／`Thermocouple`：

- 設備 ID。
- 來源模組、來源實體類型與來源實體 ID。
- 是否為該來源的目前正式連結。

同一來源實體只能有一個正式連結。MSA 不複製或分叉 CQI-9 的校正真實來源；建立研究快照時由設備服務統一讀取連結實體與通用校正紀錄。

#### `EquipmentCalibrationRecord`

- 設備 ID。
- 校驗類型、校驗日期、有效日期、下次校驗日。
- 校驗機構、證書編號、追溯標準與不確定度說明。
- 結果：`pending`、`pass`、`fail`、`limited_use`。
- 限制條件與核准理由。
- 原始證書附件 ID。
- 建立者、核准者與時間。

核准後不可修改；更正須建立後繼版本。

#### `EquipmentCorrectionPoint`

- 校驗紀錄 ID。
- 量測模式，例如內側、外側、深度、溫度頻道。
- 名目值、器示值、誤差值、補正值與單位。
- 適用量程起訖。

#### `EquipmentStatusEvent`

- 設備 ID。
- 事件類型：校驗逾期、校驗失敗、維修、重大調整、停用、報廢、復用。
- 發生時間、原因、建立者。
- 是否觸發 MSA 再研究。

#### `EquipmentImportBatch` 與 `EquipmentImportRow`

批次保存：

- 原始檔名、SHA-256、大小、上傳者與時間。
- 匯入狀態、總列數、成功數、待確認數與拒絕數。
- 解析器版本。

逐列保存：

- 原始列號與原始 JSON。
- 正規化後 JSON。
- 問題代碼與說明。
- 對應設備 ID。
- 確認者與確認時間。

### 6.2 判定準則

#### `MsaCriteriaProfile`

- 名稱。
- 顧客、產品、產品族或品質特性範圍。
- 特性重要度。
- 適用研究類型。
- 目前啟用版本。

#### `MsaCriteriaVersion`

- Profile ID 與版本號。
- 方法版本與適用日期。
- %GRR 接受／條件接受／拒絕門檻。
- ndc 最低門檻。
- 顯著水準 alpha。
- Kappa、有效性、錯誤接受與錯誤拒收門檻。
- 穩定性規則組。
- 條件接受時的強制處置。
- 依據、建立者、核准者與核准時間。

核准後不可覆寫。每個結果版本保存完整準則快照。

### 6.3 MSA 研究

#### `MsaStudy`

- 研究編號，格式例如 `MSA-2026-0042`。
- 研究類型。
- 量測目的：`product_control` 或 `process_control`。
- 品質特性、單位、規格下限／上限與目標值。
- 顧客、產品、料號、製程與部門。
- 負責人與主要執行者。
- 工作流狀態。
- 再研究週期與下次到期日。
- 前一核准研究 ID。

一個研究可引用多件儀器、參考標準、夾具或軟體，不以單一 `equipment_id` 限制複合量測系統。

#### `MsaStudyEquipment`

- 研究 ID 與設備 ID。
- 角色：`primary_gauge`、`reference_standard`、`fixture`、`environment_monitor`、`software`。
- 量測模式與使用順序。
- 是否為必要設備。

同一研究至少要有一件 `primary_gauge`；偏倚與線性研究必須有可接受的參考值來源或 `reference_standard`。

#### `MsaPlanVersion`

- 研究 ID 與版本號。
- 方法代碼及方法版本。
- 零件數、評價人數、試驗次數。
- 設計類型：交叉、巢狀、分割樣本、連續配對、穩定性序列。
- 隨機種子與完整隨機量測順序。
- 設備與校正快照。
- 判定準則快照。
- 抽樣與環境說明。
- 計畫雜湊、建立者與建立時間。
- 凍結者與凍結時間。

凍結後不得更新。

#### `MsaPart`

- Plan version ID。
- 真實零件識別。
- 盲測代碼。
- 參考值、參考值來源與不確定度說明。
- 樣本來源、製程位置與規格區域。
- 是否為破壞性／不可重複樣本。

評價人畫面只顯示盲測代碼。

#### `MsaAppraiser`

- Plan version ID。
- 使用者 ID 或外部評價人名稱。
- 部門、資格／訓練證據。
- 是否為主要執行者。

#### `MsaObservation`

- Plan version ID。
- 零件 ID、評價人 ID、試驗次數。
- 研究要求順序與實際輸入順序。
- 計量讀值或計數型分類。
- 實際量測時間、輸入時間與輸入者。
- 來源：頁面逐筆、矩陣、Excel、未來儀器。
- 匯入批次與儲存格位置。
- `supersedes_id`、修正理由與是否有效。

不得直接更新或刪除既有觀測；修正建立後繼紀錄。

#### `MsaResultVersion`

- 研究 ID、Plan version ID 與結果版本號。
- 方法版本、程式版本與資料雜湊。
- 原始資料摘要。
- 前提與適用性結果。
- 結構化統計結果。
- 圖表資料。
- 判定準則快照與結論。
- 警告、阻擋條件及改善建議。
- 狀態：`analyzed`、`submitted`、`approved`、`rejected`、`superseded`、`voided`。
- 建立者與建立時間。

核准、退回或修正不得覆寫計算證據。

#### `MsaWorkflowDecision`

- 研究與結果版本 ID。
- 動作：送審、核准、退回、作廢、取代。
- 舊狀態、新狀態、理由。
- 操作者與時間。
- 職責分離檢查結果。

## 7. 設備清單初始匯入

來源 `measurements (1).csv` 有 108 筆設備及 14 個欄位。盤點時：

- 97 筆使用中、9 筆報廢、2 筆維修。
- 設備編號無重複。
- 107 筆缺少型號。
- 14 筆缺少操作者。
- 68 筆序號藏在備註。
- 32 筆提醒值含 HTML。
- 校驗類別包含一筆「遊校」。
- 以 2026-07-27 重新計算，97 筆使用中設備中有 31 筆校驗逾期。

匯入規則：

1. 去除 UTF-8 BOM，正規化欄名。
2. 設備編號為自然鍵；空白或重複編號阻止該列匯入。
3. `-` 轉為 `null`，日期解析後保存為真正日期型別。
4. 「效準提醒」不匯入；校驗狀態由日期與校驗結果動態計算。
5. HTML 一律清除，不直接保存或渲染。
6. 報廢與維修對應正式狀態。
7. 「遊校」不自動映射，標記 `CALIBRATION_TYPE_AMBIGUOUS` 待人工確認。
8. 備註中的 SN／NO、內側爪與外側爪補正值只建立「解析候選」，由人員確認後才寫入結構化欄位。
9. 無法確定量程、解析度、單位、型號或校驗證據時保留空值並標記待確認，不猜測。
10. 同一 SHA-256 的檔案再次確認匯入時回傳既有批次，不建立重複設備。
11. 每個設備編號代表一件可獨立追溯的實體；數量大於 1 時不得共用同一設備編號完成正式 MSA，必須拆成個別設備或標記待確認。

## 8. 方法選擇與統計引擎

### 8.1 共通規則

- 正式結果只能由後端計算。
- 每個方法均有穩定的代碼與版本，例如 `MSA4_GRR_ANOVA_1_0`。
- MSA 第四版正式研究變差預設使用 `6σ` 口徑。
- 歷史資料若使用 `5.15σ`，只能以明確的 legacy 方法版本保存與顯示，不能標成第四版正式結果。
- 所有常數、alpha、信賴水準、變差乘數及數值容許誤差都保存在方法版本與結果中。
- 負變差分量的處理必須依方法規格執行並留下原始估計及調整後值，不能靜默歸零。
- 非平衡資料不得偷偷套用平衡設計公式。
- 任一 NaN、Infinity、奇異模型或無法估計項目都產生結構化失敗。

### 8.2 計量型 GRR

#### 極差法

作為快速篩選方法，輸出整體 GRR 估計與適用性限制，不輸出無法由此設計辨識的詳細變差來源。

#### 平均值與極差法

輸出至少包括：

- 各評價人與零件的平均值及極差。
- X̄ 圖與 R 圖。
- EV、AV、GRR、PV、TV。
- %Study Variation、%Tolerance、%Process Variation。
- ndc。
- 圖形異常與適用性警告。

#### 交叉型 ANOVA

完整模型包含：

- 零件。
- 評價人。
- 零件 × 評價人交互作用。
- 重複性誤差。

保存 DF、SS、MS、F、p 值、期望均方、原始變差分量、調整後變差分量及信賴區間。交互作用不顯著時是否使用縮減模型由受控方法版本決定，兩個模型的證據都要保留。

### 8.3 偏倚

- 使用可追溯參考值。
- 一名正常操作者以正常方法重複量測。
- 計算平均值、偏倚、重複性標準差、t 值、p 值與信賴區間。
- 判定零是否位於信賴區間，以及是否超過校驗允許誤差。
- 參考值或校驗證據不足時不得宣告偏倚合格。

### 8.4 線性

- 參考件涵蓋正常操作量程。
- 保存每個參考值的重複讀值與偏倚。
- 計算偏倚對參考值的迴歸斜率、截距、p 值、R²、信賴帶及預測帶。
- 圖形顯示個別偏倚、平均偏倚、迴歸線、零偏倚線及信賴帶。
- 單看 R² 不得宣告線性合格；需同時檢查斜率、零偏倚線與殘差。

### 8.5 穩定性

- 以可追溯基準件或受控生產基準件按時間週期量測。
- 每期通常 3–5 次讀值，頻率由設備使用、校驗、維修與環境風險決定。
- 使用 X̄-R 或 X̄-S 控制圖；不可重複情境使用適用的個別值／移動極差或其他受控設計。
- 穩定性以控制圖與時間證據判定，不建立虛假的單一「穩定性指數」。

### 8.6 計數型

- 支援二分類與有限多分類。
- 保存評價人內、評價人間及相對參考標準的交叉表。
- 計算 Kappa 與信賴區間。
- 計算有效性、錯誤接受、錯誤拒收／錯誤警報。
- 顯示接近規格邊界的灰色區風險。
- 沒有可信參考決定時只能報告一致性，不能宣稱能正確辨識良品／不良品。

### 8.7 不可重複／破壞性

依資料與物理條件選擇：

- 分割樣本。
- 連續配對樣本。
- 穩定製程中隔離的同質樣本。
- 多試驗台比較。

系統必須先要求使用者確認樣本同質性、保存期限、製程穩定性與配對假設。無法滿足時回傳不適用，不套用標準交叉型 GRR。

## 9. 判定準則

內建第四版基準 Profile：

- `%GRR < 10%`：通常可接受。
- `10% ≤ %GRR ≤ 30%`：條件接受，需依特性風險、用途、設備成本與顧客要求決定，並強制填寫理由及改善／監控措施。
- `%GRR > 30%`：不可接受。
- `ndc ≥ 5`。
- 預設 `alpha = 0.05`；改用其他 alpha 必須引用核准準則版本。

計數型預設範例門檻可依手冊建立，但必須明確標示為受控組織準則，而不是不可變的統計定律。顧客或內部準則優先於內建基準。

判定輸出分三層：

1. 統計結果。
2. 套用準則後的系統判定。
3. 經授權的工程判斷與處置。

任何人工改判都不得改寫統計數值，必須保存原判定、改判結果、理由、操作者與時間。

## 10. 研究工作流

### 10.1 狀態

主要狀態：

```text
draft
→ ready
→ collecting
→ ready_for_analysis
→ analyzed
→ submitted
→ approved
```

例外狀態：

```text
rejected
voided
superseded
```

「即將到期／已到期」是核准研究的再研究狀態，不改寫其歷史核准事實。

### 10.2 建立與凍結

1. 選擇研究方法、量測目的、顧客、產品、品質特性、規格與設備。
2. 檢查設備狀態、校驗有效性、資料確認狀態與解析度。
3. 建議零件、評價人與試驗次數。
4. 選擇受控判定準則版本。
5. 建立零件、盲測代碼、評價人及隨機量測順序。
6. 凍結計畫、設備、校驗與準則快照。

### 10.3 資料收集

- 逐筆模式：顯示當前盲測代碼與量測欄位，隱藏參考值及前次讀值。
- 矩陣模式：僅對管理者開放完整性管理，不破壞盲測。
- Excel：先預覽與驗證，確認後才匯入。
- 所有輸入保存來源、順序、時間與操作者。
- 修正建立後繼紀錄並要求理由。

### 10.4 分析、送審與核准

- 分析前驗證完整性、設計平衡、設備快照、隨機化與資料型別。
- 分析建立不可變結果版本與資料雜湊。
- `msa.manage` 填寫結論與處置後送審。
- `msa.approve` 審查統計、圖形、原始讀值、設備、準則與稽核證據。
- 自我核准檢查同時在服務層與資料庫約束／交易邏輯執行。
- 退回後的任何資料修正都建立新結果版本。
- 核准後才能產生無浮水印正式報告。

## 11. 再研究

固定週期依準則 Profile 或研究計畫設定。

事件觸發包括：

- 設備維修或重大調整。
- 校驗失敗、校驗逾期或補正值重大改變。
- 量測方法、夾具、軟體或環境改變。
- 操作者群體重大改變。
- 製程、產品、規格或顧客要求改變。
- 前次研究失敗或條件接受的改善期限到期。

觸發事件建立再研究要求與待辦，不自動複製舊量測值。新研究核准後，前一版本標記為已取代，但保留完整歷史。

## 12. API 設計

### 12.1 設備

```text
GET    /api/measurement-equipment
POST   /api/measurement-equipment
GET    /api/measurement-equipment/:id
PATCH  /api/measurement-equipment/:id
POST   /api/measurement-equipment/:id/calibrations
POST   /api/measurement-equipment/:id/status-events
POST   /api/measurement-equipment/imports/preview
POST   /api/measurement-equipment/imports/:batchId/confirm
GET    /api/measurement-equipment/imports/:batchId
```

### 12.2 準則

```text
GET    /api/msa/criteria
POST   /api/msa/criteria
POST   /api/msa/criteria/:id/versions
POST   /api/msa/criteria/versions/:versionId/approve
```

### 12.3 研究

```text
GET    /api/msa/studies
POST   /api/msa/studies
GET    /api/msa/studies/:id
PATCH  /api/msa/studies/:id
POST   /api/msa/studies/:id/plans
POST   /api/msa/plans/:planId/freeze
GET    /api/msa/plans/:planId/tasks
POST   /api/msa/plans/:planId/observations
POST   /api/msa/plans/:planId/imports/preview
POST   /api/msa/plans/:planId/imports/:batchId/confirm
POST   /api/msa/plans/:planId/validate
POST   /api/msa/plans/:planId/analyze
POST   /api/msa/results/:versionId/submit
POST   /api/msa/results/:versionId/approve
POST   /api/msa/results/:versionId/reject
POST   /api/msa/results/:versionId/void
GET    /api/msa/studies/:id/history
GET    /api/msa/results/:versionId/report.pdf
GET    /api/msa/results/:versionId/report.xlsx
```

所有清單 API 使用有上限的分頁與白名單排序。所有狀態轉換 API 必須接受理由及目前版本識別，避免舊畫面覆蓋新狀態。

## 13. 錯誤處理與安全

### 13.1 穩定錯誤碼

| HTTP | 用途 |
|---|---|
| 400 | 欄位格式錯誤；回傳欄位或 Excel 儲存格位置 |
| 403 | 權限不足或違反職責分離 |
| 404 | 設備、研究、版本或附件不存在 |
| 409 | 版本、並發、重複送審或狀態衝突 |
| 422 | 方法不適用、設備不合格、設計不完整或統計前提不成立 |

代表性錯誤碼：

- `MSA_EQUIPMENT_CALIBRATION_EXPIRED`
- `MSA_EQUIPMENT_PENDING_REVIEW`
- `MSA_PLAN_ALREADY_FROZEN`
- `MSA_DESIGN_INCOMPLETE`
- `MSA_OBSERVATION_DUPLICATE`
- `MSA_OBSERVATION_INVALID`
- `MSA_DATA_CHANGED`
- `MSA_METHOD_NOT_APPLICABLE`
- `MSA_NUMERIC_FAILURE`
- `MSA_SELF_APPROVAL_FORBIDDEN`
- `MSA_VERSION_CONFLICT`

### 13.2 交易與並發

- 匯入確認以批次 SHA-256 保證冪等。
- 狀態轉換使用條件更新或列鎖。
- 統計計算、結果保存與狀態轉換在同一交易中完成。
- 任一步失敗不得留下半完成正式版本。
- 同一研究只允許一個目前送審版本。

### 13.3 上傳與輸出安全

- 限制副檔名、MIME、大小、列數與欄數。
- Excel 文字若以 `=`, `+`, `-`, `@` 開頭，匯出時防止公式注入。
- HTML 先淨化，前端不以 `dangerouslySetInnerHTML` 顯示匯入內容。
- 原始上傳檔儲存在受控附件位置，不以使用者檔名直接決定磁碟路徑。

## 14. 前端體驗與視覺方向

### 14.1 首頁：風險導向工作台

首頁優先呈現：

- 我的研究工作。
- 待送審／待核准。
- 校驗逾期或資料待確認設備。
- 即將到期與逾期再研究。
- 匯入錯誤批次。

主要動作為「建立研究」與「匯入設備」。完整研究、設備、判定準則與匯入歷程各有獨立頁面。

### 14.2 結果頁：分層證據

閱讀順序：

1. 系統判定與下一步。
2. %GRR、ndc、EV、AV、交互作用等關鍵證據。
3. 送審阻擋條件。
4. 圖形分析。
5. ANOVA 或其他方法明細。
6. 原始數據。
7. 設備與準則快照。
8. 版本稽核。

前端不得只顯示一個紅黃綠燈，也不得以顏色作為唯一訊息。

### 14.3 視覺語言

方向取自量測工作台與校驗標籤：

- 深墨綠 `#173F3B`：受控流程與主要導覽。
- 量測綠 `#216E67`：通過、可執行與主要動作。
- 校驗琥珀 `#D88936`：條件接受、到期與待處理。
- 警示紅 `#A63440`：阻擋、失敗與逾期。
- 鋁灰 `#E7ECEF`：設備、表格與中性背景。
- 紙白 `#FCFDFD`：證據內容。

中文使用系統可用的 `Noto Sans TC`／`Microsoft JhengHei` fallback；數值使用等寬字體與 tabular numbers，確保小數位容易比較。

辨識性元素是「證據軌」：每個結論旁固定顯示方法版本、資料雜湊、設備快照及阻擋條件，讓稽核證據不是藏在次級頁面。

### 14.4 無障礙與響應式

- 所有圖表提供文字摘要與可讀表格。
- 所有狀態同時使用文字、圖示與顏色。
- 所有控制可使用鍵盤，焦點狀態清楚。
- 表格有 caption、正確欄列標題與 `aria` 關係。
- 尊重 `prefers-reduced-motion`。
- 桌面顯示矩陣；行動裝置改為逐筆量測，不縮小密集矩陣。
- 長表格使用凍結標題、分頁或虛擬化，但不得隱藏資料完整性狀態。

## 15. PDF 與 Excel 報告

### 15.1 共通原則

- 報告只讀取已保存的 `MsaResultVersion`，不得重新計算。
- 草稿報告加上明顯浮水印。
- 正式報告包含研究編號、結果版本、方法版本、程式版本、資料雜湊、準則版本、設備與校正快照、核准者及時間。
- PDF 與 Excel 的版本及雜湊必須完全一致。

### 15.2 PDF

至少包括：

- 封面與正式結論。
- 研究目的與設計。
- 設備、校正、環境及樣本資訊。
- 統計摘要與判定。
- 圖形證據。
- ANOVA／偏倚／線性／穩定性／計數型明細。
- 阻擋條件、改善與再研究計畫。
- 簽核與版本稽核。

### 15.3 Excel

至少包括：

- `研究摘要`
- `原始數據`
- `隨機順序`
- `計算明細`
- `圖形分析`
- `ANOVA` 或對應方法頁
- `設備與準則快照`
- `版本稽核`

Excel 可提供公式作為可讀證據，但正式判定欄必須明確標示為後端保存結果；Excel 公式不得成為另一套權威計算引擎。

## 16. 驗證策略

### 16.1 TDD

每個新行為先建立會因功能缺失而失敗的窄測試，再實作最小功能。統計函式、工作流、權限、匯入及報告皆適用。

### 16.2 統計測試

- 手冊範例與獨立已知資料的精確數值比較。
- 極差法、X̄-R、ANOVA、偏倚、線性、穩定性、Kappa 與不可重複方法各有 Golden dataset。
- Golden result 保存完整數值、容許誤差、方法版本與預期警告，不只保存 PASS／FAIL。
- 性質測試：
  - 交換零件標籤不改變變差結果。
  - 交換評價人順序不改變整體結果。
  - 所有讀值加常數不改變 GRR。
  - 所有讀值乘常數時標準差等比例改變。
  - 重複相同匯入不增加資料。
- NaN、Infinity、零變差、單一評價人、缺格、非平衡設計、奇異模型與極端尺度都有失敗測試。

### 16.3 工作流與資料庫測試

- 凍結計畫不可修改。
- 原始讀值不可更新或刪除。
- 修正建立後繼紀錄。
- 設備逾期、維修、報廢與待確認會阻止正式研究。
- 自我核准被拒絕。
- 並發送審／核准只有一個成功。
- 核准研究的設備與準則快照不受目前主檔變動影響。
- 報告從保存版本重建，來源資料改變後舊報告仍一致。

### 16.4 前端測試

- 權限控制與導覽顯示。
- 研究精靈各步驟驗證。
- 盲測不顯示參考值或前次讀值。
- 隨機矩陣完整性。
- Excel 錯誤能定位列與儲存格。
- 結果頁由結論追到原始證據。
- 鍵盤操作、文字狀態與行動版逐筆流程。

### 16.5 報告與視覺驗證

- PDF 每次重要調整後渲染成圖片，檢查中文字型、重疊、截字、圖表與頁碼。
- Excel 檢查關鍵範圍、公式錯誤、工作表完整性及渲染。
- PDF 與 Excel 的研究版本、方法版本、資料雜湊與核准資料逐項一致。

### 16.6 完整驗證命令

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

需要 PostgreSQL 約束與並發證據的測試另以整合測試執行，不能只依 SQLite 測試宣告通過。

## 17. 驗收條件

1. 可由受控設備與準則建立所有已列入範圍的研究類型。
2. 不合格設備無法進入正式執行。
3. 盲測與隨機順序在頁面與 Excel 範本一致。
4. 原始讀值可追溯且不可覆寫。
5. 所有正式統計結果由後端產生並保存完整數值證據。
6. %GRR、ndc、偏倚、線性、穩定性與計數型判定依受控準則版本執行。
7. 不適用的方法回傳明確原因，不補近似結果。
8. 建立者／執行者無法核准自己的研究。
9. PDF 與 Excel 可由核准結果版本重建且內容一致。
10. 設備事件與固定週期都能產生再研究待辦。
11. 使用者提供的 108 筆設備清單可受控預覽、確認及追溯匯入。
12. 後端、前端、報告與整合驗證全部通過後，才能宣告實作完成。

## 18. 實作順序建議

1. 通用設備主檔、校正版本、初始 CSV 匯入與設備狀態防線。
2. MSA 權限、判定準則版本與研究主檔。
3. 計畫凍結、零件／評價人、隨機順序與原始讀值。
4. 計量型 GRR 三種方法與 Golden validation。
5. 偏倚、線性與穩定性。
6. 計數型研究。
7. 不可重複／破壞性研究。
8. 核准、版本、再研究與稽核。
9. 風險導向工作台與分層證據結果頁。
10. PDF／Excel 報告及完整確效。

每一階段都必須保持可驗證且不得以尚未完成的下一階段補足目前資料完整性。
