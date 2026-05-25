## 1. 資料庫 Schema 與遷移

- [x] 1.1 設計新表 `customer_complaint` ORM model（含 complaint_type、嚴重度、應答期限、回覆內容、滿意度、Warranty 額外欄位）
- [x] 1.2 設計新表 `task` ORM model（含 source_type、source_id、category、assignee_id、status、due_date、completion_proof）
- [x] 1.3 設計新表 `attachment` ORM model（含 entity_type、entity_id、d_step、file_path、mime_type、file_size）
- [x] 1.4 擴充 `ncmr` model 加 `related_capa_id` / `related_capa_source` 欄位
- [x] 1.5 擴充 `capa` model 加 D0 欄位群（symptom、criteria、severity、rigor）、D1 結構化（champion_id、leader_id、members_ids）、source_type、source_id、tool、five_why_data、fishbone_data、root_cause、各 D 期限與驗證欄位
- [x] 1.6 擴充 `cara` model 加同 capa 對應欄位（D1 / D5 為 NULL，rigor 固定簡化）
- [x] 1.7 撰寫 Alembic migration 腳本：建立新表、新增欄位、建立外鍵與索引
- [x] 1.8 撰寫資料回填腳本：既有 capa 負責人 → leader_id、rigor 預設「完整 8D」、source_type/id 從 ncmr 帶入；既有 cara 同步
- [x] 1.9 於本機資料庫驗證 migration 與回填腳本可正確執行與回滾

## 2. 附件模組（共用）

- [x] 2.1 後端 `backend/services/attachment_service.py`：upload、list、download、delete、依 entity 查詢
- [x] 2.2 後端 `backend/routes/attachment.py`：POST /upload、GET /list、GET /download/<id>、DELETE /<id>
- [x] 2.3 實作檔案大小（≤10MB）與類型白名單檢查
- [x] 2.4 實作儲存路徑 `backend/uploads/{entity_type}/{entity_id}/`，並加入 `.gitignore`
- [x] 2.5 實作權限檢查：下載 = 已登入；刪除 = 上傳者或品保主管
- [x] 2.6 前端 `src_frontend/src/components/common/AttachmentUploader.tsx`：拖拉上傳、進度條、檔案類型提示
- [x] 2.7 前端 `src_frontend/src/components/common/AttachmentList.tsx`：清單顯示、下載、刪除按鈕
- [ ] 2.8 撰寫附件模組單元測試（後端 + 前端）

## 3. 任務模組

- [x] 3.1 後端 `backend/services/task_service.py`：create、update_status、list（含篩選）、delete、依 source 查詢
- [x] 3.2 後端 `backend/routes/task.py`：CRUD endpoints + 「我的待辦」endpoint（GET /my-tasks）
- [x] 3.3 實作狀態機驗證：pending→in_progress/waived；in_progress→completed/waived；終態不可改
- [x] 3.4 實作 completed 需 completion_proof、waived 需備註理由
- [x] 3.5 前端 `src_frontend/src/pages/task/TaskListPage.tsx`：列表、篩選（負責人、狀態、類別、期限區間）
- [x] 3.6 前端 `src_frontend/src/components/task/TaskDetailModal.tsx`：明細、狀態切換、附件
- [x] 3.7 前端 `src_frontend/src/components/common/MyTasksWidget.tsx`：Dashboard 區塊、逾期紅色標示、依期限排序
- [x] 3.8 整合 MyTasksWidget 至 `DashboardPage.tsx`
- [ ] 3.9 撰寫任務模組單元測試（含狀態機）

## 4. 客訴模組（進階完整）

- [x] 4.1 後端 `backend/services/complaint_service.py`：CRUD、應答期限計算、重複客訴偵測（12 個月內相同客戶+料號+不良類別）
- [x] 4.2 後端 `backend/services/complaint_stats_service.py`：依客戶 / 料號 / 不良類別 / 月份維度統計
- [x] 4.3 後端 `backend/routes/complaint.py`：CRUD + 統計 endpoint + 開立 CAPA endpoint
- [x] 4.4 實作 complaint_type ENUM 與 Warranty/Field Failure 額外欄位驗證
- [x] 4.5 前端 `src_frontend/src/pages/complaint/ComplaintPage.tsx`：列表、篩選、新增
- [x] 4.6 前端 `src_frontend/src/components/complaint/ComplaintModal.tsx`：表單（含類別切換顯示額外欄位）、重複客訴警示對話框
- [ ] 4.7 前端 `src_frontend/src/pages/complaint/ComplaintStatsPage.tsx`：統計圖表（依客戶、依料號、Warranty 獨立）
- [ ] 4.8 整合「開立 CAPA」按鈕至客訴明細頁
- [ ] 4.9 撰寫客訴模組單元測試（含重複偵測、統計）

## 5. CAPA 重設計

- [x] 5.1 後端 `backend/services/capa_service.py` 重寫：D0–D8 各步驟驗證、進度計算、結案 gate、源頭強制
- [x] 5.2 後端實作 D0 嚴重度→嚴格度預設聯動邏輯（可 override）
- [x] 5.3 後端實作 D6 verified gate（未驗證阻擋進 D7）
- [x] 5.4 後端實作 D7 橫展任務自動產生（勾選→建 task；取消勾選→依任務狀態決定刪除/阻擋）
- [x] 5.5 後端實作 D8 結案 gate（檢查所有關聯任務狀態）
- [x] 5.6 後端 `backend/routes/capa.py` 重寫：CRUD、開單需附 source_type/id、各步驟更新 endpoint
- [ ] 5.7 前端 `src_frontend/src/pages/capa/CAPAPage.tsx` 微調：移除直接「新增」按鈕（改由 NCMR/客訴頁開立）
- [ ] 5.8 前端 `src_frontend/src/components/capa/CAPAModal.tsx` 重寫：進度條、D0–D8 各步驟元件
- [ ] 5.9 前端 D0 元件：症狀、判斷準則多選、嚴重度、嚴格度（聯動）、客戶要求結案日
- [ ] 5.10 前端 D1 元件：Champion / Leader / Members 結構化選擇器
- [ ] 5.11 前端 D2 元件：5W2H 七欄位 + 附件
- [ ] 5.12 前端 D3 元件：對策、生效日、有效性驗證 + 附件
- [ ] 5.13 前端 D4 元件：工具切換、5Why 動態 3–7 層編輯器、魚骨圖 6M 編輯器、根本原因自動匯入
- [ ] 5.14 前端魚骨圖 SVG 渲染元件（依 6M 結構產生標準魚骨圖）
- [ ] 5.15 前端 D5 元件：永久對策、實施日、驗證計畫
- [ ] 5.16 前端 D6 元件：實施日、驗證結果、verified checkbox（gate）
- [ ] 5.17 前端 D7 元件：橫展類型勾選器、每項建立任務（指派/期限）、橫展任務狀態顯示
- [ ] 5.18 前端 D8 元件：結案確認、團隊表揚、結案按鈕（觸發 gate 檢查）
- [ ] 5.19 撰寫 CAPA 重設計單元測試（後端 + 前端，含各 gate）

## 6. CARA 調整

- [x] 6.1 後端 `backend/services/cara_service.py` 調整：簡化流程驗證、開單限制（僅 IQC 來料 NCMR）
- [x] 6.2 後端 `backend/routes/cara.py` 微調
- [ ] 6.3 前端 `src_frontend/src/components/cara/CARAModal.tsx` 微調：進度條僅顯示 5 步驟、移除 AIAG 報表按鈕
- [ ] 6.4 整合附件模組至 CARA 各 D 步驟
- [ ] 6.5 撰寫 CARA 調整單元測試

## 7. NCMR 微調

- [x] 7.1 後端 `backend/routes/ncmr.py` 加「開立 CAPA」endpoint
- [ ] 7.2 前端 `src_frontend/src/pages/ncmr/NCMRPage.tsx` 加「開立 CAPA」按鈕
- [ ] 7.3 前端 NCMR 明細顯示「關聯 CAPA」資訊（若已開立）
- [ ] 7.4 撰寫 NCMR 微調單元測試

## 8. AIAG 8D 報表產出

- [ ] 8.1 設計安泰版 AIAG 8D Excel 範本 `backend/templates/aiag_8d_antai.xlsx`
- [ ] 8.2 設計安泰版 AIAG 8D PDF 樣板（reportlab Python 樣板）
- [ ] 8.3 安裝 reportlab 與中文字型（內嵌於專案）
- [ ] 8.4 後端 `backend/services/aiag_8d_report_service.py`：依 CAPA id 產出 PDF / Excel
- [ ] 8.5 實作報表附件嵌入（圖片直接內嵌、其他類型於附件清單列出）
- [ ] 8.6 後端 `backend/routes/capa.py` 加 GET /capa/<id>/report/pdf 與 /report/excel endpoints
- [ ] 8.7 前端 CAPA 明細頁加「下載 8D 報表」按鈕（僅結案後顯示）
- [ ] 8.8 撰寫報表產出單元測試（驗證欄位對應正確）

## 9. Dashboard 整合

- [x] 9.1 Dashboard 加「我的待辦」區塊
- [x] 9.2 Dashboard 加「逾期 CAPA」區塊（依 D0 客戶要求結案日計算）
- [x] 9.3 Dashboard 加「逾期客訴」區塊（依應答期限計算）
- [x] 9.4 Dashboard 加「重複客訴」區塊（過去 30 天觸發過警示者）

## 10. 整合測試與部署

- [ ] 10.1 端對端測試：NCMR → CAPA → D0–D8 完整流程 → 結案 → 產報表
- [ ] 10.2 端對端測試：客訴 → CAPA → 完整流程
- [ ] 10.3 端對端測試：來料 NCMR → CARA → 簡化流程結案
- [ ] 10.4 端對端測試：D7 任務 → 「我的待辦」顯示 → 完成 → D8 結案
- [ ] 10.5 既有資料遷移驗證：開啟舊 CAPA / CARA 確認顯示「舊版」標記與欄位正常
- [ ] 10.6 效能測試：附件上傳大檔（接近 10MB）、列表分頁、統計查詢
- [ ] 10.7 撰寫使用者操作手冊（給 QA 主管說明新流程）
- [ ] 10.8 Docker 容器更新（含 reportlab 字型、uploads 目錄掛載）
- [ ] 10.9 PostgreSQL 備份策略納入 uploads 目錄
- [ ] 10.10 正式上線部署
