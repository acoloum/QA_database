# 不合格品處置管制設計（NCMR Disposition）

- 日期：2026-05-30
- 範圍：強化不合格品處理流程，符合 IATF 16949 §8.7（不合格輸出之管制）
- 分支：`feature/ncmr-disposition`

## 背景與目標

現行 NCMR 流程在「事後改善」（CAPA/8D、重工）已相當完整，但「不合格品本身的處置管制」有缺口：

1. 處置決定是 NCMR 主檔上的自由文字欄位 `判定結果`（`result`），未結構化、無數量、無驗證。
2. 結案前置檢查只驗關聯 CAPA／重工是否結案，**未檢查是否已填處置**，可讓無處置的 NCMR 直接結案。
3. 讓步放行（超出客戶規格仍放行）無任何記錄，IATF §8.7.1.1 要求須有客戶授權記錄。

本設計補齊以上三項（原規劃 P0），讓每筆不合格品都有可追溯、可勾稽、可稽核的處置決定。

## 範圍決策（來自需求釐清）

| 編號 | 決策 |
|------|------|
| Q1 | 處置由**單一授權人**決定，記錄處置人＋處置時間即可（不做多級會簽）|
| Q2/Q3/Q5 | 使用的處置類型：**矯正重工、報廢、挑選全檢、讓步放行**（不做退貨、不做客戶以外的特採型別）|
| Q4 | 放行的超差品**有時會超出客戶規格**（§8.7.1.1 適用）|
| Q5 | 讓步放行須記錄「是否超出客戶規格」；若超出 → 選「已取得授權」（填文號/有效期/數量上限）或「未取得授權」（必填理由，自動標記為風險項）|
| Q6 | 結案 gate 採**嚴謹**：處置須「執行完成」才能結案 |
| Q7 | 一張 NCMR **可拆成多種處置**（如 30 報廢 + 70 重工）→ 需處置明細子表 + 數量勾稽 |

## 一、資料模型

### 新增子表 `NcmrDisposition`（不合格品處置明細）

一張 NCMR 對多筆處置明細（`one-to-many`，`cascade="all, delete-orphan"`）。

| 欄位（中文 DB 名）| 屬性名 | 型別 | 說明 |
|------|--------|------|------|
| 識別碼 | id | Integer PK | |
| NCMR_ID | ncmr_id | Integer FK→不合格品單.識別碼 | 必填，index |
| 處置類型 | disposition_type | String(20) | `矯正重工` / `報廢` / `挑選全檢` / `讓步放行` |
| 處置數量 | quantity | Integer | 此筆處置件數，必填 |
| 處置人 | handler_id | Integer FK→品管人員.識別碼 | 記錄授權人 |
| 處置時間 | handled_at | DateTime | 預設 now |
| 備註 | note | Text | 自由文字 |
| **矯正重工專屬** | | | |
| 關聯重工單ID | rework_id | Integer FK→重工申請單.識別碼 nullable | |
| **挑選全檢專屬** | | | |
| 合格數 | pass_qty | Integer nullable | |
| 不合格數 | fail_qty | Integer nullable | |
| **讓步放行專屬** | | | |
| 是否超出客戶規格 | exceed_customer_spec | Boolean default False | |
| 授權狀態 | auth_status | String(10) nullable | `已取得` / `未取得`（僅當超出客戶規格）|
| 授權文號 | auth_doc_no | String(100) nullable | |
| 授權有效期 | auth_valid_until | Date nullable | |
| 授權數量上限 | auth_max_qty | Integer nullable | |
| 未授權放行理由 | unauth_reason | Text nullable | 未取得授權時必填 |
| 是否風險項 | is_risk | Boolean default False | 未取得授權時自動 True |

索引：`idx_ncmr_disp_ncmr`（NCMR_ID）、`idx_ncmr_disp_risk`（是否風險項）。

### NCMR 主檔調整

- 既有 `result`（判定結果）自由文字欄位**保留**，不破壞既有資料；前端改以處置明細為主，可顯示「處置摘要」字串（由明細彙整）。
- 新增關聯：`dispositions = relationship('NcmrDisposition', backref='ncmr', cascade='all, delete-orphan')`。

### Migration

新增 `backend/migration/20_add_ncmr_disposition.sql`，建立子表與索引；編號接續既有 19。

## 二、結案 Gate

NCMR 狀態轉移至 `已結案` 時，在既有 `update_ncmr` 的結案前置檢查中**追加**下列驗證，任一不過即拋 `ValueError` 並回明確訊息：

1. **至少一筆處置明細**（堵住無處置直接結案的漏洞）。
2. **數量勾稽**：所有處置明細 `處置數量` 加總 == NCMR `不良數量`（`defect_quantity`）。
3. **每筆處置已執行完成**：
   - `矯正重工` → `rework_id` 不為空，且該重工單狀態為「已結案」。
   - `報廢` → 有 `處置數量` 即視為確認。
   - `挑選全檢` → `合格數` 與 `不合格數` 皆已填，且 `合格數 + 不合格數 == 處置數量`。
     - **勾稽口徑（避免重複計算）**：挑選全檢視為**終端處置**，其 `處置數量` 已涵蓋該批（含挑出的不合格數），不需為挑出的不合格品另開報廢處置。挑出之不合格品的後續去向（報廢／回收等）記於 `備註`；若需正式追蹤，另開一張新的 NCMR，不在本 NCMR 的數量勾稽內重複計列。
   - `讓步放行` → 記錄完整；若 `是否超出客戶規格 == True` 且 `授權狀態 == '未取得'`，須已填 `未授權放行理由`。
4. **既有檢查保留**：關聯 CAPA 須已結案；關聯重工單須已結案／撤銷。

狀態機 `待處理 → 已結案` 的捷徑**保留**（輕微不合格可快速結案），但一律須通過上述 gate。

### 寫入時驗證（建立／修改處置）

- `讓步放行`：若 `是否超出客戶規格 == True` → `授權狀態` 必填；`未取得` → `是否風險項` 自動設 True、`未授權放行理由` 必填；`已取得` → 建議填授權文號（非強制，警示）。
- `挑選全檢`：`合格數 + 不合格數` 若皆有值須 == `處置數量`（防呆）。
- 所有處置寫入／修改記入既有 `AuditLog`。

## 三、後端 API

沿用既有 blueprint + service 三層慣例（`routes/ncmr.py`、`services/ncmr_service.py`）。處置建立／修改／刪除以既有 `require_role` 限定授權角色（呼應 Q1 單一授權人）。

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ncmr/<id>/dispositions` | 取某 NCMR 的處置明細清單 |
| POST | `/api/ncmr/<id>/dispositions` | 新增一筆處置（require_role）|
| PUT | `/api/ncmr/dispositions/<did>` | 修改處置（require_role）|
| DELETE | `/api/ncmr/dispositions/<did>` | 刪除處置（require_role）|
| GET | `/api/ncmr/risk-releases` | 風險報表：未授權放行清單（`是否風險項=true`）|

結案邏輯仍走既有 `update_ncmr`，於原結案前置檢查追加第二節 gate。

風險報表回傳欄位：NCMR 單號、產品資訊、材質、廠商、處置數量、未授權放行理由、處置人、處置時間。

## 四、前端

### 改造 `components/ncmr/DispositionModal.tsx`（升級既有元件，不新建）

由「單選自由文字」改為「處置明細管理」：

- **明細清單**：可新增多筆處置（呼應 Q7），每筆顯示 類型／數量／狀態，可編輯／刪除。
- **數量勾稽列**：即時顯示「不良總數 N　已處置 X　未處置 N−X」；未歸零時提示、結案鈕禁用。
- **依類型動態欄位**（條件渲染，對應子表）：
  - 矯正重工 → 下拉選關聯重工單；或沿用既有 `convertToRework` 開新重工單。
  - 挑選全檢 → 合格數／不合格數。
  - 讓步放行 → 是否超出客戶規格 → 授權狀態 →（已取得：文號／有效期／數量上限）／（未取得：必填理由，紅字警示「將標記為風險項」）。
  - 報廢 → 僅數量。
- 既有「轉開 CAPA／轉重工」按鈕保留。
- 處置類型選項對齊：移除 `特採`（改 `讓步放行`）、`選別及補數`（改 `挑選全檢`）、移除 `退貨`。

### 新增風險報表

`pages/ncmr/RiskReleasePage.tsx`（或在 `NCMRPage` 加分頁），列出未授權放行清單，沿用既有表格樣式。

### API / hooks / types

- `hooks/useNCMR.ts` 新增：`useDispositions(ncmrId)`、`useCreateDisposition`、`useUpdateDisposition`、`useDeleteDisposition`、`useRiskReleases`。
- `types/index.ts` 新增 `NcmrDisposition` interface，欄位對齊子表。

## 五、測試（pytest，沿用 `tests/test_services` 結構）

- 數量勾稽：處置加總 ≠ 不良數 → 擋下結案。
- 無處置 → 擋下結案。
- 矯正重工：重工單未結案 → 擋下；已結案 → 放行。
- 挑選全檢：合格＋不合格 ≠ 處置數量 → 擋下。
- 讓步放行：超出客戶規格＋未授權但缺理由 → 擋下；填理由 → 放行且 `是否風險項=true`。
- 風險報表：只回未授權放行記錄。
- 處置寫入產生 AuditLog。

## 六、明確排除（YAGNI，本次不做）

- 客戶通知機制、疑似品管控、重工前風險分析（原 P2）。
- CAPA D6 驗證 gate（原 P1，另案）。
- 退貨、客戶以外的特採型別。
- 多級會簽（Q1 已定單一授權人）。

## 對應 IATF 16949 條款

| 條款 | 本設計如何滿足 |
|------|----------------|
| §8.7.1 不合格輸出管制 | 結構化處置類型 + 數量勾稽 + 結案 gate |
| §8.7.1.1 讓步放行需客戶授權 | 讓步放行記錄授權狀態／文號／有效期／數量上限；未授權標記風險項並可報表追蹤 |
| §8.7.1.2 重工管制 | 矯正重工連動重工單，結案須重工已結案（事後再驗沿用既有 ReworkInspection）|
| §7.5 記錄 | 所有處置寫入 AuditLog，子表保存可追溯 |
