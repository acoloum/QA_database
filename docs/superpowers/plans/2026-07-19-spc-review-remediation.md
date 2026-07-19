# SPC 程式碼檢視修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 SPC 研究、OCAP、快取的併發與輸入風險，並降低研究歷程及 OCAP 同步成本。

**Architecture:** 以 PostgreSQL 唯一約束、短交易列鎖與 upsert 作資料完整性防線；服務層集中驗證並將衝突轉成穩定 API 錯誤。前端改以輕量事件回應校正本地狀態，歷程採分頁載入。

**Tech Stack:** Flask 3.1、SQLAlchemy、PostgreSQL 16、pytest、React 19、TypeScript、TanStack React Query、Vitest。

## Global Constraints

- 使用繁體中文撰寫說明、註解與 commit 訊息。
- 不修改 `tmp/` 或其他使用者既有未追蹤檔案。
- 所有行為修正先建立會因現況而失敗的測試，再寫最小實作。
- migration 必須可重複檢查約束是否存在，且不得自動合併或刪除既有稽核資料。

---

### Task 1: 鎖定資料完整性與 OCAP 輸入契約

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/services/spc_ocap_service.py`
- Modify: `backend/services/spc_study_service.py`
- Test: `backend/tests/test_services/test_spc_models.py`
- Test: `backend/tests/test_services/test_spc_ocap_service.py`
- Test: `backend/tests/test_services/test_spc_study_service.py`

**Interfaces:**
- Produces: `SpcOcapService.validate_payload(payload)`、研究自然唯一鍵、穩定的 409／422 錯誤碼。

- [ ] **Step 1: 寫入非法狀態、錯型 payload、布林責任人及自然鍵失敗測試。**
- [ ] **Step 2: 執行窄測試，確認因缺少驗證或約束而失敗。**
- [ ] **Step 3: 實作集中驗證、研究／事件列鎖與 IntegrityError rollback／轉譯。**
- [ ] **Step 4: 執行窄測試，確認全部通過。**

### Task 2: 將 SPC 預覽快取改為原子 upsert

**Files:**
- Modify: `backend/services/spc_study_service.py`
- Test: `backend/tests/test_services/test_spc_study_service.py`

**Interfaces:**
- Produces: `_upsert_preview_cache(cache_key, result, expires_at)`。

- [ ] **Step 1: 寫入重複 cache key 更新同一列的失敗測試。**
- [ ] **Step 2: 執行測試，確認現行新增流程無法符合原子更新契約。**
- [ ] **Step 3: 依 PostgreSQL／SQLite dialect 使用 `ON CONFLICT DO UPDATE`。**
- [ ] **Step 4: 執行快取與 SPC service 測試。**

### Task 3: 增加 migration 37 資料庫防線

**Files:**
- Create: `backend/migration/37_harden_spc_concurrency_and_status.sql`
- Modify: `docs/spc_migration_36_runbook.md`
- Test: `backend/tests/test_services/test_spc_models.py`

**Interfaces:**
- Produces: `uq_spc_study_identity`、`ck_spc_ocap_status`、`ck_spc_event_status`。

- [ ] **Step 1: 先讓模型約束測試因約束不存在而失敗。**
- [ ] **Step 2: 在 ORM 與 SQL migration 加入相同命名約束及重複資料 preflight。**
- [ ] **Step 3: 執行 SQLite 模型測試及 PostgreSQL transaction dry-run。**

### Task 4: 優化研究讀取與歷程分頁

**Files:**
- Modify: `backend/services/spc_study_service.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`
- Modify: `src_frontend/src/types/spc.ts`
- Modify: `src_frontend/src/components/spc/SpcStudyHistoryOffcanvas.tsx`
- Test: `backend/tests/test_spc_study_routes.py`
- Test: `src_frontend/src/hooks/useSpcStudies.test.tsx`
- Create: `src_frontend/src/components/spc/SpcStudyHistoryOffcanvas.test.tsx`

**Interfaces:**
- Produces: `SpcStudyHistoryPage`，包含 `items/total/page/per_page/pages`。

- [ ] **Step 1: 寫入歷程分頁 API 與 UI 失敗測試。**
- [ ] **Step 2: 執行測試，確認目前陣列契約不符合分頁需求。**
- [ ] **Step 3: 實作 eager loading、分頁 service/route/hook 與上一頁／下一頁。**
- [ ] **Step 4: 執行後端路由及前端歷程測試。**

### Task 5: 以輕量事件 API 校正 OCAP 狀態

**Files:**
- Modify: `backend/services/spc_ocap_service.py`
- Modify: `backend/routes/spc_studies.py`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`
- Create: `src_frontend/src/utils/spcEventState.ts`
- Create: `src_frontend/src/utils/spcEventState.test.ts`
- Modify: `src_frontend/src/components/spc/SpcStudyPanel.tsx`
- Modify: `src_frontend/src/components/spc/SpcStudyPanel.test.tsx`
- Test: `backend/tests/test_spc_study_routes.py`

**Interfaces:**
- Produces: `GET /api/spc/events/<event_id>`、`fetchSpcEvent(eventId)`、`replaceEvent(version, event)`。

- [ ] **Step 1: 寫入輕量事件查詢與前端不重抓整份研究的失敗測試。**
- [ ] **Step 2: 執行測試，確認目前仍呼叫完整 `refetchStudy()`。**
- [ ] **Step 3: 實作事件 API、工具函式與 guarded background reconciliation。**
- [ ] **Step 4: 執行事件 API、panel 與工具測試。**

### Task 6: 修正責任人錯誤狀態與前端契約

**Files:**
- Modify: `src_frontend/src/components/spc/SpcOcapOffcanvas.tsx`
- Modify: `src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`
- Modify: `src_frontend/src/types/spc.ts`

**Interfaces:**
- Produces: `SpcOcapStatus = 'open' | 'closed'`，責任人未確認／不可指派的分離語意。

- [ ] **Step 1: 寫入責任人載入失敗不得顯示不可指派的失敗測試。**
- [ ] **Step 2: 執行測試確認失敗。**
- [ ] **Step 3: 實作狀態 union、移除 `due_at`，並區分載入失敗與確認不可指派。**
- [ ] **Step 4: 執行 OCAP 與 TypeScript 測試。**

### Task 7: 完整驗證、提交與推送

**Files:**
- Verify: all changed files

- [ ] **Step 1: 執行 `venv\\Scripts\\python.exe -m pytest backend\\tests -q`。**
- [ ] **Step 2: 執行前端 `npm run lint`、`npm run build`、`npm test`、`npm audit`。**
- [ ] **Step 3: 執行 migration transaction dry-run、`git diff --check` 與狀態檢查。**
- [ ] **Step 4: 以繁體中文 commit 訊息提交所有本次追蹤檔案，不加入 `tmp/`。**
- [ ] **Step 5: push 到 `origin/master` 並確認遠端 commit。**
