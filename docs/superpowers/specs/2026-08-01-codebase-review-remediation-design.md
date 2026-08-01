# 全庫審查修復設計

## 目標

依 2026-08-01 全庫審查結果，完整修復已重現的憑證曝露、認證撤銷、細粒度授權、NCMR 建立、稽核原子性與 Dashboard 日期邊界缺陷，並完成分析查詢、前端狀態管理、錯誤契約、模組邊界及測試回饋速度的改善。

本變更不得以近似資料、只在前端隱藏按鈕、吞掉稽核錯誤或降低測試門檻來換取表面通過。後端授權與資料庫交易是正式控制點；前端只提供一致的使用者體驗。

## 已批准的安全範圍

- 本分支移除目前版本中已追蹤的秘密，加入忽略規則、範本與自動掃描。
- Docker 缺少 `DB_PASSWORD` 或 `SECRET_KEY` 時必須拒絕啟動，不得使用固定 fallback。
- PostgreSQL 對主機的連接埠預設只綁定 `127.0.0.1`，容器間仍走內部網路。
- 不在本次程式變更中直接修改正式資料庫密碼、重寫 `master` 歷史或 force-push。
- 交付 runbook，明確列出憑證旋轉、既有 JWT 失效、Git 歷史清理與協作者重新同步步驟。

## 方案選擇

採用「分階段深模組修復」：先建立共用安全與交易介面，再逐領域遷移，最後做查詢與結構重整。每一階段均先有會失敗的回歸測試、最小修正、窄測試及獨立提交。

未採用下列方案：

- 大爆炸式重寫：雖可一次統一全部路由與模型，但無法清楚定位回歸來源，且對正式 QMS 風險過高。
- 只修 Critical／High：無法滿足「全部修復」，也會保留已確認的 N×查詢、巨型表單與測試回饋缺口。

## 一、秘密與部署安全

### 儲存庫內容

- 停止追蹤 `.claude/settings.local.json`，加入 `.gitignore`；只保留不含 token、密碼或個人命令的範本（若確有共享需求）。
- 以 `.env.docker.example` 取代含實值的 `.env.docker`，所有敏感欄位只放明確 placeholder。
- Dockerfile 不再把任何 `.env*` 複製進映像。
- `docker-compose.yml` 使用 `${DB_PASSWORD:?DB_PASSWORD is required}` 與 `${SECRET_KEY:?SECRET_KEY is required}`；不得存在預設秘密。
- 新增唯讀秘密掃描腳本，檢查 Git 追蹤檔案中的 JWT、`PGPASSWORD`、固定 `SECRET_KEY` 與常見私鑰格式；測試需證明目前追蹤樹通過。

### 部署控制

- PostgreSQL host port 改綁 `127.0.0.1`；應用容器仍使用 `db:5432`。
- Nginx／Flask 回應加入 `X-Content-Type-Options`、`Referrer-Policy`、`Permissions-Policy` 與可相容現有 Vite bundle 的 CSP。HSTS 只在確認 HTTPS／反向代理協定後啟用，避免 HTTP 開發環境自鎖。
- runbook 說明：先輪替資料庫密碼與 `SECRET_KEY`，再重建容器；`SECRET_KEY` 輪替會使所有既有 JWT 失效。

## 二、共用認證與 Token 撤銷

### User 模型與 migration

- User 新增 `token_version` 非空整數，預設 0。
- 新增 migration 50，對既有使用者回填 0 並建立非空／非負約束。
- JWT 必須包含 `token_version`；缺少版本的舊 JWT 在部署後一律視為失效。

### 認證介面

- `auth_required` 在驗證簽章後，依 `user_id` 讀取目前 User。
- 使用者不存在、已停用或 token version 不一致時回穩定 401，不得進入路由或 service。
- `request.user` 必須由目前資料庫狀態建立，不得沿用 JWT 內可能過期的 role。
- 需要 ORM 使用者的路由沿用 `current_user` 注入；舊式路由則從相同已驗證 User 產生字典。
- `/api/verify-token` 使用相同認證介面，回傳目前角色與權限。
- 停用帳號、修改角色及密碼／管理員重設憑證時增加 `token_version`，立即撤銷既有 token。
- MSA、校正與附件既有停用帳號防線保留為 defense in depth，但不得維持另一套互相矛盾的判定。

## 三、細粒度授權

### 後端為正式控制點

- 建立集中且可測試的「路由動作 → 權限」矩陣；mutation 不得只使用 `auth_required`。
- NCMR：建立 `ncmr.create`、一般編輯 `ncmr.edit`、本人發現且具 `ncmr.edit_own` 可編輯、刪除 `ncmr.delete`、處置 `ncmr.disposition`。
- CAPA：建立／由來源開立 `capa.create`、內容更新 `capa.edit`、結案與刪除 `capa.close`。
- 客訴：建立 `complaint.create`、更新 `complaint.edit`、刪除 `complaint.delete`；開立 CAPA／重工另需目標模組的 create 權限。
- 重工：申請與申請內容更新 `rework.create`、審核與結案 `rework.approve`、執行／成本／檢驗寫入也使用 `rework.create`、刪除任何重工資料使用 `rework.delete`。
- 所有領域 GET 清單／明細使用對應 `.view` 權限；管理與共用選項端點依最小必要權限設定。
- admin 維持超級管理員語意，但仍必須是目前存在且啟用的帳號。

### 前端體驗

- 新增通用 `PermissionRoute`，保護 NCMR、CAPA、重工、客訴、出貨、巡檢、pyrometry、mechanical、分析及報表頁。
- 寫入按鈕依 `hasPermission` 隱藏或停用並附理由；不得把前端 gate 當成安全控制。
- 403 使用一致訊息，不清除登入狀態；401 才登出並導向登入。

### 驗收測試

- 停用帳號對代表性 GET 與 mutation 均為 401 且零寫入。
- 只有 view 權限的角色對每個 mutation 均為 403 且零寫入。
- `edit_own` 僅能編輯與自身 inspector 關聯的 NCMR。
- 角色降權後，舊 JWT 不可沿用舊權限。

## 四、NCMR 輸入與稽核原子性

### 輸入契約

- route 只把 Marshmallow `load()` 回傳的正規化物件交給 service。
- 建立與更新使用明確 schema；日期保持 `date`、數量保持整數，未知欄位拒絕或依既定契約排除，不得把錯誤值靜默改成 `None`。
- JSON body 必須是物件；空 body、錯誤 MIME、錯誤日期與越界數量回穩定 400／422，而非 500。

### 交易 seam

- 每個 mutation 只有一個模組擁有 commit；route 不直接 `db.session.commit()`。
- service 在同一交易中完成：鎖定／驗證、業務異動、AuditLog、flush、commit。
- AuditLog 寫入失敗必須使業務異動整體 rollback，並回 500；不得回成功。
- NCMR CRUD、處置、CAPA close/delete、客訴 delete/open、重工 apply/approve/delete 先完成遷移；再掃描其他 route-level commit，全部移入對應 service。
- audit 內容至少包含 actor、action、module、record id，以及對更新有意義的 old/new snapshot。

## 五、錯誤契約與可觀測性

- 正式錯誤 envelope 統一為 `{ "success": false, "error": { "code", "message", "details" } }`。
- `api_error()` 改產生上述 envelope，並保留前端相容解析期；前端不再依賴多種巢狀形狀。
- route 只捕捉預期的 domain／validation／not-found／conflict 錯誤。未預期例外交給全域 handler。
- 全域 handler 記錄完整 traceback 與 request correlation id；5xx 回應不得包含 `str(exception)`、SQL、路徑或參數。
- 逐檔移除 `except Exception: return ... str(e)`；若必須補償或 rollback，記錄後重新 raise。
- 移除無意義的 `except Exception as e: raise e`，改成直接呼叫或裸 `raise`，保留原始 traceback。

## 六、日期與查詢正確性

### Dashboard

- 將 Dashboard 統計移至 `DashboardService`，route 只解析參數與回傳。
- Date 欄位使用含首尾日期；DateTime 欄位使用 `[start 00:00, end + 1 day 00:00)` 半開區間。
- 拒絕 `start > end`，並限制最大查詢期間，避免誤用造成全表掃描。
- 測試結束日中午、月底、跨年、空期間與軟刪除資料。

### PostgreSQL 連線設定

- 使用 SQLAlchemy `URL.create()` 組合連線 URL，確保密碼中的 `@`、`:`、`/` 等字元正確處理。

## 七、廠商績效

- 建立嚴格 `parse_period("YYYY-MM") -> (start_date, end_date)`；格式錯誤或月份越界回 400。
- GET 只讀：以集合式查詢計算當期結果，不 commit、不建立 snapshot。
- 出貨檢驗依 `vendor_id` 一次 `GROUP BY`；CAPA／客訴以單次查詢取得所有廠商聚合，避免每家廠商重複查詢。
- 新增具 `vendor.manage` 權限的明確 refresh mutation，以單交易 bulk upsert 月度 snapshot；依唯一鍵處理並發衝突。
- history 只讀既有 snapshot，查詢加入 period 排序與上限。
- 查詢計數測試需證明廠商數增加不會造成線性 SQL statement 數。

## 八、Quality Analytics

- Pareto、趨勢與重複問題改以 SQL `GROUP BY` 聚合，只選必要欄位。
- 月趨勢使用可在 PostgreSQL 與 SQLite 測試環境穩定運作的月份表達式 adapter。
- CAPA aging 的 bucket／平均結案天數由資料庫聚合；逾期清單只查回實際顯示欄位並限制筆數。
- 所有 `limit`、`top_n`、日期範圍使用共用 bounded parser；錯誤輸入回 400。
- vendor ranking 重用集合式 VendorPerformance 模組，不重新實作評分規則。

## 九、前端狀態與可存取性

- `useReworkPageData` 改由 React Query 同時管理清單與統計，mutation 成功使用精確 query invalidation。
- Pyrometry 編輯 hydration 改為單一 reducer／form state action，避免二十多次同步 state update。
- Mechanical 表單以 keyed form session 或 reducer 在 `testId` 改變時重建狀態；衍生錯誤不以 effect 同步保存。
- MSA blind entry 以 task key 重建輸入元件，焦點 effect 只處理 DOM focus，不同步清 state。
- 把非 React export 移出 component 檔，消除 Fast Refresh warning。
- 所有既有 keyboard、dialog、tab、responsive table acceptance 保持不變；重構需使用現有 RTL 測試及新增必要的 keyboard regression。

## 十、模組深度與檔案結構

### 路由與服務

- `backend/routes/admin.py` 的 Dashboard 商業查詢搬入 `backend/services/dashboard_service.py`。
- 校正讀值保存保留單一公開 `save_readings()` 介面，將 payload normalization、point calculation input 與 ORM apply 拆成私有模組；外部呼叫端不增加新知識。
- error mapping、permission policy、period parsing、date window 只各有一個正式 seam，其他模組不得複製。

### ORM

- 將 74 個模型依 `auth_audit`、`inspection`、`spc`、`calibration`、`msa`、`quality_workflow`、`pyrometry`、`mechanical` 拆至 `backend/models/`。
- `backend/models/__init__.py` 保留現有匯入名稱，避免呼叫端一次改寫；資料表名、欄位名、relationship 字串、constraints、event listeners 與 migration 行為不得改變。
- 先加 model registry／metadata parity 測試，再移動類別；測試比較 table names、columns、constraints 與 mapper relationships。

## 十一、測試與 CI

- 所有行為修復採 TDD：先看見測試因既有缺陷失敗，再做最小修正。
- 新增 pytest markers：`unit`、`integration`、`postgresql`、`slow`，讓本機短迭代與正式閘門分離。
- 新增 PostgreSQL CI lane，設定 migration 38、49、50 與 concurrency runner 所需資料庫 URL；199 個環境型 skip 不得在正式 CI 靜默略過。
- 前端 lint 必須 0 errors、0 warnings；build 與完整 Vitest 都是獨立閘門。
- 保留完整驗收：`pytest backend/tests -q`、`npm test`、`npm run lint`、`npm run build`、`npm audit --omit=dev`、`pip check`、`git diff --check`。
- migration／Docker 變更完成後，需在隔離測試資料庫與容器執行 smoke；未啟動正式服務時不得宣稱 live UI 或正式部署驗證。

## 分階段交付與提交

1. 秘密與 Docker fail-closed。
2. Token version、停用帳號與目前角色認證。
3. 後端權限矩陣與前端 PermissionRoute。
4. NCMR schema 與原子稽核。
5. 統一錯誤契約與 route 清理。
6. Dashboard 日期視窗與 service seam。
7. Vendor Performance 集合式查詢。
8. Quality Analytics SQL 聚合。
9. React Query／表單 reducer／lint warning 清理。
10. 深模組與 ORM 分檔。
11. 測試分層、PostgreSQL CI、完整驗證與部署 runbook。

每個提交都必須能獨立通過其窄測試；跨階段介面由先行提交建立，後續只消費，不建立相互循環依賴。

## 驗收條件

- 前一輪五個最小探針全部反轉：停用 JWT 401、唯讀 mutation 403、合法 NCMR 建立成功、稽核失敗零業務寫入、Dashboard 結束日資料被計入。
- Git 追蹤樹與 Docker build context 不含已知秘密或固定 fallback。
- 所有 5xx 回應不含原始 exception 字串。
- Vendor Performance GET 零寫入，查詢數不隨廠商數線性增加；月份越界不寫入。
- Quality Analytics 不載入完整 ORM collection 再聚合。
- ESLint 0 warning，前端完整測試與 build 通過。
- 後端完整 SQLite suite 通過；PostgreSQL migration／concurrency lane 通過或明確回報尚缺外部環境，不得把 skip 說成通過。
- 無未預期 schema 變更，migration 50 可重複安全檢查且有 rollback／runbook 說明。

## 基線證據

- Worktree：`C:\QC_Database\.worktrees\codebase-review-all`
- 分支：`fix/codebase-review-all`
- 後端：`1677 passed, 199 skipped in 278.87s`
- 前端：`133 files passed, 706 tests passed in 94.09s`
- `npm ci`：0 vulnerabilities
