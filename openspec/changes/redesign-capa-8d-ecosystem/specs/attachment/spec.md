## ADDED Requirements

### Requirement: 附件為跨模組共用資源

附件 SHALL 為獨立資料表 `attachment`，含 `entity_type`、`entity_id`、`d_step`、`file_path`、`file_name`、`mime_type`、`uploaded_by`、`uploaded_at`、`file_size` 欄位。`entity_type` 限定 ('capa', 'cara', 'task', 'complaint')。

#### Scenario: 上傳附件至 CAPA D2
- **WHEN** QA 在 CAPA D2 步驟點擊「上傳附件」並選擇檔案
- **THEN** 系統建立 `attachment` 紀錄，`entity_type='capa'`、`entity_id=CAPA.id`、`d_step=2`，檔案存於 `backend/uploads/capa/{capa_id}/`

#### Scenario: 上傳附件至客訴
- **WHEN** QA 在客訴頁面上傳附件
- **THEN** 系統建立 `attachment` 紀錄，`entity_type='complaint'`、`d_step=NULL`

### Requirement: 附件大小與類型限制

單個附件 SHALL 不可超過 10 MB。允許的檔案類型 SHALL 為圖片（jpg, jpeg, png, gif）、文件（pdf, doc, docx, xls, xlsx, ppt, pptx）、文字（txt, csv）。

#### Scenario: 超過大小限制
- **WHEN** QA 上傳超過 10 MB 的檔案
- **THEN** 系統回傳 400 錯誤，訊息為「檔案大小不可超過 10 MB」

#### Scenario: 不允許的檔案類型
- **WHEN** QA 上傳 .exe 或其他不允許類型的檔案
- **THEN** 系統回傳 400 錯誤，訊息列出允許的檔案類型

### Requirement: 附件查詢依實體分類

系統 SHALL 提供 API 依 `entity_type + entity_id` 查詢所有附件，若指定 `d_step` 則僅回傳該步驟附件。

#### Scenario: 查詢 CAPA 所有附件
- **WHEN** 前端呼叫 `GET /api/attachments?entity_type=capa&entity_id=123`
- **THEN** 系統回傳該 CAPA 所有附件，按 `d_step` 與 `uploaded_at` 排序

#### Scenario: 查詢 CAPA 特定步驟附件
- **WHEN** 前端呼叫 `GET /api/attachments?entity_type=capa&entity_id=123&d_step=4`
- **THEN** 系統僅回傳 D4 步驟的附件

### Requirement: 附件下載與刪除權限

附件下載 SHALL 開放給已登入使用者。附件刪除 SHALL 僅限上傳者本人或品保主管角色。

#### Scenario: 下載附件
- **WHEN** 已登入使用者點擊附件下載連結
- **THEN** 系統回傳檔案內容（含正確的 Content-Type）

#### Scenario: 非上傳者無法刪除
- **WHEN** 非上傳者且非品保主管的使用者嘗試刪除附件
- **THEN** 系統回傳 403 錯誤

### Requirement: AIAG 報表整合附件

AIAG 8D 報表產出時 SHALL 依 D 步驟順序內嵌對應附件（圖片直接內嵌、其他類型於報表末附件清單列出）。

#### Scenario: 報表內嵌 D2 圖片附件
- **WHEN** 系統產出 AIAG 8D PDF 且 D2 有圖片附件
- **THEN** PDF 於 D2 區塊內嵌該圖片

#### Scenario: 非圖片附件列於清單
- **WHEN** 系統產出 AIAG 8D 報表且某 D 步驟有 PDF / Excel 附件
- **THEN** 報表末附件清單列出檔名、上傳日期、所屬 D 步驟
