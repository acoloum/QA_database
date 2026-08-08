# 全庫優化與缺陷修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正已重現的交易、錯誤契約、部署、查詢與測試缺口，並在不破壞既有公開 interface 的前提下改善內部 locality。

**Architecture:** 以外層 mutation 的單一交易 seam 統一 CAPA/附件行為；以共用 error envelope 與部署設定集中跨模組契約；查詢優先 SQL 聚合，內部大型模組則採私有 seam 漸進拆分。

**Tech Stack:** Flask 3.1、SQLAlchemy 2、PostgreSQL/SQLite 測試、React 19、React Query、Vitest、Vite、GitHub Actions。

## Global Constraints

- 不改資料表名、欄位名、既有路由 URL、React Query 公開 hook 名稱。
- 不直接執行正式資料庫 migration；只新增可檢查與可測試的 migration 工具。
- 所有 production code 變更先有會失敗的 regression test。
- 所有回應與程式碼備註使用繁體中文。

### Task 1: CAPA D7 單一交易

**Files:**
- Modify: `backend/services/task_service.py`
- Modify: `backend/services/capa_service.py`
- Test: `backend/tests/test_services/test_capa_workflow.py`

- [ ] 先新增 D7 後段失敗時 CAPA 欄位與新任務均不存在的測試。
- [ ] 執行該測試確認目前因 `TaskService.create()` 內部 commit 而失敗。
- [ ] 新增 private `_build_task`/`_create_without_commit` seam，讓 CAPA 只 `add/flush`。
- [ ] 執行 CAPA workflow tests 與 transaction regression。

### Task 2: 錯誤 envelope 與資料庫錯誤攤平

**Files:**
- Modify: `backend/routes/calibration_adapters.py`
- Modify: `backend/routes/tolerance.py`, `backend/routes/extrusion_tolerance.py`, `backend/routes/mechanical.py`, `backend/routes/pyrometry.py`
- Test: `backend/tests/test_pyrometry_route_errors.py`, new route error regression tests
- Modify: `src_frontend/src/services/api.test.ts` and API adapter only if backend envelope remains incompatible

- [ ] 先新增 calibration error 與 DB error message type regression tests。
- [ ] 執行確認現在 envelope/message_type 失敗。
- [ ] 改用共用 `api_error`，保留 domain code/details。
- [ ] 執行後端 route tests 與前端 API tests。

### Task 3: 附件刪除原子性

**Files:**
- Modify: `backend/services/attachment_service.py`
- Test: `backend/tests/test_services/test_attachment_service.py`

- [ ] 新增非 MSA DB commit 失敗且實體檔仍可恢復的測試。
- [ ] 執行確認目前先刪檔的行為失敗。
- [ ] 實作資料庫先提交、實體檔刪除失敗時恢復 link 的補償流程。
- [ ] 執行附件完整測試。

### Task 4: 限流、body limit、UTF-8 與 CI gate

**Files:**
- Modify: `backend/extensions.py`, `backend/app.py`, `backend/config.py`
- Modify: `backend/tests/test_repository_security.py`
- Modify: `.github/workflows/ci.yml`, `Dockerfile`, `nginx/default.conf`
- Test: new configuration and limiter tests

- [ ] 先新增 forwarded address、MAX_CONTENT_LENGTH、UTF-8 scanner regression tests。
- [ ] 執行確認目前設定不符合預期。
- [ ] 實作 trusted proxy/全域 body limit/明確 subprocess encoding。
- [ ] 將必要 integration skip 變成 CI failure，加入 Python 3.12/3.14 matrix。
- [ ] 執行 backend security/config tests。

### Task 5: 查詢聚合與效能

**Files:**
- Modify: `backend/services/quality_analytics_service.py`
- Modify: `backend/services/mechanical_service.py`
- Test: `backend/tests/test_services/test_quality_analytics.py`, `backend/tests/test_services/test_mechanical_service.py`

- [ ] 先新增 SQL statement/結果一致性測試，證明不載入全部 NCMR 或 mechanical children。
- [ ] 執行確認目前查詢會 `.all()` 後 Python 聚合。
- [ ] 改用 group-by/having 與可索引條件，維持回傳契約。
- [ ] 執行查詢服務完整測試。

### Task 6: Migration ledger 與無效 route cleanup

**Files:**
- Create: `backend/migration/ledger.py`
- Create: `backend/migration/README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: affected routes removing only redundant bare re-raise blocks
- Test: `backend/tests/test_migration_ledger.py`

- [ ] 先新增 migration filename/version/checksum 與重複套用檢查測試。
- [ ] 實作唯讀 `status` 與 dry-run ledger commands，不直接連正式 DB。
- [ ] 移除無效 `try/except: raise`，不改預期例外處理。
- [ ] 執行 route tests、ledger tests 與 `git diff --check`。

### Task 7: 依賴與前端內部 seam

**Files:**
- Modify: `src_frontend/package.json`, `src_frontend/package-lock.json`
- Modify: `src_frontend/src/components/shipping/ShippingModal.test.tsx`
- Create/Modify: calibration form reducer/serializer private modules only after focused tests

- [ ] 先把 debounce regression 改成 fake timers 並確認測試能捕捉 stale result。
- [ ] 執行該測試確認原始 behavior assertion 仍有效。
- [ ] 升級開發依賴並執行 `npm audit --omit=dev`、full audit。
- [ ] 只抽出純函式表單 seam，執行前端 full test/lint/build。

### Task 8: 完整驗證與回報

- [ ] `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 venv\Scripts\python.exe -m pytest backend\tests -q`
- [ ] `npm test`
- [ ] `npm run lint`
- [ ] `npm run build`
- [ ] `npm audit --omit=dev`
- [ ] `venv\Scripts\python.exe -m pip check`
- [ ] `git diff --check`、工作樹與 migration 變更清單檢查
