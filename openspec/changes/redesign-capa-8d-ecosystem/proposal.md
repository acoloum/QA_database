## Why

現有 CAPA / CARA 模組僅有 D1–D8 文字輸入與「進行中 / 已結案」兩種狀態，缺少進度視覺化、引導性工具（5Why、魚骨圖）、附件支援、橫展開追蹤與 AIAG 標準報表，無法滿足車用客戶（安泰）的 8D 提交要求，也無法支撐 IATF 16949 對「問題解決」與「預防再發」（條款 10.2.3、10.2.4）的證據鏈需求。此外，外部不良（客訴）目前沒有對應模組，所有跨部門矯正措施散落在紙本與 Word，無法做重複問題識別與閉環追蹤。

## What Changes

- **重新設計 CAPA 流程**：加入 D0 立案、D1 結構化小組（Champion / Leader / Members）、D2 5W2H 引導、D4 同時提供 5Why（動態 3–7 層）與魚骨圖（6M 自動產生 SVG）、D6 驗證 gate、D7 橫展任務產生器、D8 觸發 AIAG 8D 報表（安泰版）
- **CAPA / CARA 重新分類**：用「對象」分（CAPA = 我方執行；CARA = 要求供應商），不再用「車用 vs 非車用」分；CAPA 內加「嚴格度」欄位（完整 8D / 簡化 5D），由 D0 嚴重度預設聯動可 override
- **CAPA 源頭強制化**：CAPA 必須從 NCMR 或客訴開立，不可獨立開單
- **新增客訴模組（進階完整）**：含登錄、應答時效、回覆內容、客戶滿意度、客戶 / 料號維度統計、重複客訴自動警示、Warranty / Field Failure 追蹤
- **新增任務模組**：跨模組共用，支援橫展任務、「我的待辦」首頁區塊；D8 結案前必須所有橫展任務完成或備註豁免
- **新增附件模組**：每 D 步驟可獨立附件，共用於 CAPA / CARA / 任務 / 客訴
- **NCMR 微調**：新增「關聯 CAPA」欄位，作為 CAPA 源頭追溯
- **既有資料遷移**：既有 CAPA / CARA 紀錄強制套用新欄位，D0 留空待補，D1 自動帶入「負責人 → Leader」，rigor 預設「完整 8D」
- **BREAKING**：CAPA 不可獨立開單（必須從 NCMR / 客訴），既有獨立開單流程失效；CAPA 資料表結構新增多欄位，相關 API 回應格式變更

## Capabilities

### New Capabilities

- `capa-8d`: 完整 D0–D8 流程、嚴格度聯動、5Why / 魚骨圖工具、橫展任務產生器、AIAG 報表產出
- `cara`: 對供應商之矯正要求簡化流程（D2 / D3 / D4 / D6 / D8）與回覆追蹤
- `customer-complaint`: 客訴登錄、應答時效、回覆內容、滿意度、重複警示、Warranty / Field Failure 追蹤
- `task-management`: 跨模組任務、指派 / 期限 / 完成證明、「我的待辦」、橫展任務與 D8 結案 gate
- `attachment`: 共用附件儲存、依實體（CAPA / CARA / 任務 / 客訴）與 D 步驟分類管理

### Modified Capabilities

（無，本專案尚無既有 spec 檔案；NCMR 為直接的程式碼變更，影響於 Impact 段落說明）

## Impact

- **資料表新增**：`capa`（重設計）、`cara`（重設計）、`customer_complaint`、`task`、`attachment`，並建立外鍵與索引
- **既有資料表變更**：`ncmr` 新增「關聯 CAPA」欄位；既有 `capa` / `cara` 欄位擴增與資料遷移腳本
- **後端**：新增 / 重寫 `backend/routes/capa.py`、`backend/routes/cara.py`、`backend/routes/complaint.py`、`backend/routes/task.py`、`backend/routes/attachment.py` 及對應 services；新增 AIAG 8D 報表產出服務（PDF / Excel，安泰範本）
- **前端**：重寫 `src_frontend/src/pages/capa`、`src_frontend/src/pages/cara`、`src_frontend/src/components/capa`、`src_frontend/src/components/cara`；新增 `pages/complaint`、`pages/task`、`components/common/AttachmentUploader`、`components/common/MyTasksWidget`（Dashboard 區塊）
- **使用者體驗**：CAPA 開單入口由首頁改為「從 NCMR / 客訴明細頁開立」；Dashboard 新增「我的待辦」與「逾期 CAPA」區塊
- **相依套件**：新增 SVG 渲染（魚骨圖）、PDF 產出（reportlab 或 weasyprint）；既有 openpyxl 沿用於 AIAG Excel 範本
- **使用者**：僅品保人員（單一角色），不增加跨部門權限；既有 RBAC 不變
- **上線策略**：全部模組一次上線；既有 CAPA / CARA 資料於遷移腳本完成後即可使用新介面
