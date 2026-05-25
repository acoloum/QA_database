## Context

QC Database 為 Flask 3.1 + React 19 + PostgreSQL 16 全端系統，主要使用者為品保人員（單一角色）。既有 CAPA / CARA 模組僅以 D1–D8 文字欄位與「進行中 / 已結案」二元狀態運作，無附件、無進度視覺化、無工具引導、無報表產出。NCMR 模組為 CAPA / CARA 的主要源頭，但目前未串接客戶端外部不良（客訴）。

公司目標為「內部品質改善 + 長期 IATF 16949 認證」，車用客戶（安泰）已要求 AIAG 8D 標準報表。既有資料量不大但需保留可查，所有新欄位以「容許 NULL + 預設值」方式向後相容。

技術約束：
- 既有 Flask Blueprint + Service 三層架構必須延續
- 既有 React Query + Context 資料層延續
- 不引入額外資料庫，沿用 PostgreSQL
- 中文欄位名稱保留（既有慣例）
- 既有 JWT + RBAC 認證沿用，不增加新角色

## Goals / Non-Goals

**Goals:**

- CAPA 流程完整對應 AIAG 8D 八步驟，含 D0 立案判斷
- D4 真因分析提供 5Why（動態 3–7 層）與魚骨圖（6M）兩種工具，皆有 UI 引導，結果結構化儲存
- D7 預防再發自動產生橫展任務，D8 結案前必須關閉
- 客訴模組獨立於 NCMR，避免硬塞造成欄位語意混淆
- 任務模組設計為跨模組共用實體（CAPA / 未來稽核 / 未來其他）
- AIAG 8D 報表（PDF + Excel）以安泰版範本一次產出
- 「我的待辦」首頁區塊讓被指派者主動掌握任務
- 既有資料無破壞性遷移，遷移腳本一次完成

**Non-Goals:**

- 不在本變更實作量具校準、文件版次、訓練、PFMEA、控制計畫、內部稽核管理模組（屬後續階段）
- 不導入 email 通知（系統內提示為主）
- 不做行動裝置 RWD 強化
- 不做跨部門權限細分（仍維持品保單一角色）
- 不導入 BI / 多維度報表平台
- AIAG 報表僅做安泰版範本，其他客戶範本後續再加

## Decisions

### 決策 1：CAPA / CARA 用「對象」分類，不用「車用 vs 非車用」分類

**選擇：** CAPA = 我方執行矯正；CARA = 要求供應商矯正。CAPA 內加「嚴格度」欄位（完整 8D / 簡化 5D）。

**理由：** 原始分類將「對象」與「嚴格度」兩個獨立維度綁在一起，未來「非車用但需完整 8D」會打架。改成兩條獨立軸後，分類穩定，且嚴格度可由 D0 嚴重度預設聯動（Critical / Major → 完整 8D；Minor → 簡化 5D），仍可 override。

**替代方案：** 維持原分類（被否決：架構不穩）；合併 CAPA / CARA 成單一模組（被否決：對外與對內流程差異大，合併後條件分支過多）。

### 決策 2：CAPA 源頭強制為 NCMR 或客訴，不可獨立開單

**選擇：** `capa.source_type ENUM('ncmr', 'complaint')` + `source_id` 必填。

**理由：** 強制源頭可保證每張 CAPA 有可追溯的起因，符合 IATF 條款 8.7 / 10.2.6 的證據鏈要求；也避免 QA「為填表而開單」。

**替代方案：** 允許獨立開單（被否決：失去追溯）；只接 NCMR 一個源頭（被否決：外部不良不屬 NCMR 範圍，硬塞會混淆欄位語意 — 詳見決策 3）。

### 決策 3：客訴獨立模組，不擴充 NCMR

**選擇：** 新增 `customer_complaint` 資料表與模組，與 NCMR 並列為 CAPA 源頭。

**理由：** NCMR = Non-Conforming Material（內部不良），客訴 = 客戶端外部不良，兩者在「發現者、物品位置、廠商欄位、檢驗日語意、IATF 條款歸屬」皆不同。硬塞同表會：欄位語意混淆、報表分析失準（IQC 不良率被客訴拉動）、IATF 條款（8.7 vs 10.2.6）對應錯亂。獨立模組設計成本可控（路徑 A），且符合進階完整需求（重複客訴警示、Warranty / Field Failure 追蹤）。

**替代方案：** 擴充 NCMR 加「來源」欄位（被否決：抽象過度，違反單一職責）；先用 Word 處理（被否決：CAPA 上線後遇客訴會卡）。

### 決策 4：任務模組為共用實體，含「我的待辦」

**選擇：** 新增 `task` 資料表，含 `source_type` / `source_id` 多型外鍵，初期僅 `source_type='capa'`，預留未來稽核 / 其他模組。Dashboard 新增「我的待辦」區塊查 `task.assignee_id = current_user`。

**理由：** D7 橫展任務需被指派者看到，否則「寫了沒人做」；做成共用實體可避免階段 4 內部稽核時又重做一套。

**替代方案：** 任務內嵌 CAPA 表（被否決：被指派者要進 CAPA 才看得到，且未來無法複用）；用第三方任務管理工具（被否決：跨系統整合成本高）。

### 決策 5：D4 同時提供 5Why（動態 3–7 層）與魚骨圖（6M 固定 + 自動 SVG）

**選擇：**
- 5Why：JSON 結構 `[{"q": "...", "a": "..."}]`，UI 動態增刪層數（最少 3、最多 7）
- 魚骨圖：JSON 結構 `{"man": [...], "machine": [...], "material": [...], "method": [...], "measurement": [...], "environment": [...]}`，前端輸入後以 SVG 渲染標準魚骨圖
- 兩工具可單用或併用（D4 欄位有 `tool ENUM('5why','fishbone','both')`）
- 根本原因 = 5Why 最後一層 OR 從魚骨圖中標記為「採用」者，自動帶入 `root_cause` 欄位（可手動編輯）

**理由：** 5Why 簡單但能逼出系統性原因；魚骨圖適合多重因子並行分析。兩者結構化儲存後，AIAG 報表可直接渲染，避免 QA 另開 Excel 畫圖再上傳。

**替代方案：** 純文字 textarea（被否決：當前痛點）；外掛圖形編輯器（被否決：複雜度過高）。

### 決策 6：D7 橫展任務 → D8 結案 gate

**選擇：** D7 勾選需橫展類型（PFMEA / 控制計畫 / SOP / 訓練 / 其他料號 / 通知客戶 / 其他），系統為每項建 `task` 記錄。D8 結案 API 檢查所有相關 `task.status IN ('completed', 'waived')`，否則拒絕結案。

**理由：** 把「寫了忘了」變成「系統盯著做完」，對應 IATF 10.2.3 + 10.2.4。豁免（waived）需備註理由，保留逃生口。

**替代方案：** 純提示不擋（被否決：失去 gate 意義）；強制完成不可豁免（被否決：現實必有特例）。

### 決策 7：附件模組共用，依 `entity_type + entity_id + d_step` 分類

**選擇：** 新增 `attachment` 資料表，欄位含 `entity_type ENUM('capa','cara','task','complaint')`、`entity_id`、`d_step INT NULL`（CAPA / CARA 用，0–8；task / complaint 為 NULL）。檔案儲存於本機檔案系統（路徑 `backend/uploads/{entity_type}/{entity_id}/`）。

**理由：** 共用表簡化開發、利於統一權限與生命週期管理；`d_step` 欄位讓 AIAG 報表能依步驟正確渲染附件。本機儲存對單一品保使用者規模足夠，未來可換 S3。

**替代方案：** 每個實體一個附件表（被否決：重複）；雲端儲存（被否決：超規模、引入新相依）。

### 決策 8：AIAG 8D 報表用 reportlab（PDF）+ openpyxl（Excel）+ 安泰範本

**選擇：** PDF 用 reportlab（純 Python，無系統字型相依）；Excel 用既有 openpyxl 開既有範本。安泰範本檔置於 `backend/templates/aiag_8d_antai.xlsx` 與對應的 reportlab Python 樣板。

**理由：** reportlab 中文字型可內嵌，跨平台一致；openpyxl 已是專案相依不增負擔。安泰範本一份先行，未來加客戶以「客戶 → 範本」對應表擴張。

**替代方案：** weasyprint（被否決：需系統相依，Docker 內較麻煩）；fpdf2（被否決：中文字型支援較弱）。

### 決策 9：既有資料遷移 — 強制新欄位，舊資料保留可編輯

**選擇：**
- 對既有 `capa` 表：新增 D0 欄位（NULL）、D1 結構化欄位（從現有「負責人」帶入 `leader_id`，Champion / Members 為空）、`rigor` 預設 `'完整 8D'`、`source_type` / `source_id` 從關聯 NCMR 帶入
- 對既有 `cara` 表：同上處理（rigor 固定簡化）
- 對既有 CAPA / CARA 不回填 `task` 記錄（橫展任務僅新單適用）
- 既有資料可開啟編輯，但提示「此單為舊版資料」

**理由：** 強制統一資料模型避免分支邏輯；D0 留空讓 QA 視需求補；不回填任務避免造假紀錄。

**替代方案：** 既有資料封存唯讀（被否決：使用者體驗差）；新舊欄位並存（被否決：模型分裂）。

### 決策 10：上線策略 — 全部一次上線（不分波次）

**選擇：** 全部模組（CAPA 重設計 + CARA 微調 + 客訴 + 任務 + 附件 + NCMR 微調）開發完成後一次部署。

**理由：** 模組間依賴緊密（CAPA 依賴任務、附件、客訴源頭），分波次反而需要寫過渡橋接代碼；使用者僅品保，學習成本可一次承受。

**替代方案：** 分波次（被否決：橋接成本反而高，且 QA 一個人不存在「分批訓練」需求）。

## Risks / Trade-offs

- **既有資料 D0 / D1 結構化欄位留空** → 列表頁顯示「待補」標記；管理頁可批次提示 QA 補填，不擋既有單編輯
- **D8 結案 gate 卡住舊單** → 既有 CAPA 因無關聯任務不會觸發 gate；僅新單適用
- **AIAG 報表中文字型內嵌增加 PDF 體積** → 接受（單份 PDF < 5MB，不影響使用）
- **任務模組為共用實體但初期僅 CAPA 用** → 接受過度設計風險，因階段 4 內部稽核明確會用到，重做成本更高
- **本機檔案儲存的容量與備份** → 限制單檔 ≤ 10MB；備份策略納入既有 PostgreSQL 備份流程（額外掛載 `uploads/` 目錄）
- **PostgreSQL JSON 欄位查詢效能（5Why / 魚骨圖 / 橫展任務清單）** → 此類欄位僅讀寫不參與篩選，無索引需求
- **客訴模組「進階完整」開發量大** → 已納入 N=a「全部一次上線」估算內；若實作遇阻可降級為基本完整，再以後續變更補回進階功能
- **使用者僅品保人員，任務指派可能限縮於 QA 內部** → 接受；任務模組欄位允許未來新增其他角色，無需改 schema
- **既有 CAPA / CARA URL 與 modal 行為已有使用者習慣** → 維持現有 URL 結構與 editId 參數，僅改 modal 內部 UI

## Migration Plan

1. **資料庫遷移腳本**（Alembic）：
   - 新增 `customer_complaint`、`task`、`attachment` 三張新表
   - 既有 `ncmr` 加 `related_capa_id` / `related_capa_source` 欄位
   - 既有 `capa` 加 D0 欄位群、D1 結構化欄位群、`rigor`、`source_type`、`source_id`、`tool`、`five_why_data`、`fishbone_data`、`root_cause`、各 D 步驟期限與驗證欄位
   - 既有 `cara` 同步加結構化欄位（D1 / D5 仍為 NULL）
2. **資料回填**：
   - 既有 capa → leader_id 從原「負責人」對應；rigor = '完整 8D'；source_type / source_id 從 NCMR 關聯帶入
   - 既有 cara → 同上（無 D1 / D5）
3. **部署**：先升 PostgreSQL（執行 migration）→ 後端（含新 API + AIAG 範本）→ 前端
4. **回滾策略**：保留資料庫快照；新欄位皆 NULLABLE，舊版前端可降級不顯示新欄位
5. **使用者通知**：上線當日由 QA 主管說明新流程；既有單會出現「舊版資料」標記
