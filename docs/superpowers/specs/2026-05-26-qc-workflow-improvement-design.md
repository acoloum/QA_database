# QC 品質流程改良 Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除 CARA 模組（語意誤用），把所有品質改善統一走 CAPA；補齊 NCMR/客訴 → 重工/CAPA 的狀態同步與追溯；重工完成後加入 CAPA 開立提醒。

**Architecture:** 後端刪除整個 `矯正措施要求` 表與 CARA service/route，將既有 8 筆 CARA 紀錄遷移至 CAPA（簡化 5D）；前端移除 CARA 頁面、Sidebar 連結與所有引用；客訴/重工加狀態同步與雙向追溯。

**Tech Stack:** Flask 3.1 + SQLAlchemy + PostgreSQL 18 / React 19 + TypeScript + React Query + React Bootstrap

---

## 命名混亂提醒（重要）

程式碼裡有兩個都叫「CARA / CAR」但實際上是不同東西的命名遺留：

| 名稱 | 實際指向 | 本次處理 |
|------|---------|---------|
| **「真 CARA」** | `CARARecord` / `矯正措施要求` 表 / `cara_service.py` / `routes/cara.py` / 前端 `pages/cara` | ✅ **本次完全移除**（變更 1–5） |
| **「假 CARA / CAR」** | `CorrectiveAction.car_number != null`（CAPA 表的舊命名）／`routes/ncmr.py` 的 `/api/cara/*` ／`NCMRService.get_cara_list()` 等 / 前端 `useCreateCARA` / NCMR 「轉為 CAR」按鈕 / Dashboard CAR 卡 | ✅ **本次一併清理，整合進 CAPA**（變更 6） |

本次把兩條命名混亂都處理乾淨。整合完成後系統只剩 CAPA 一個矯正行動概念。

---

## 現有模組關係（改良前）

```
內部發現
  出貨/巡檢/IQC ──→ NCMR ──→ 重工（圍堵）
                        ├──→ 真 CARA（供應商，僅 IQC）  ← 本次移除
                        ├──→ CAR（CAPA 的舊版/簡化）   ← 本次合併進 CAPA
                        └──→ CAPA / 8D

外部客訴
  客訴紀錄 ──→ CAPA（車用嚴重）
           ├──→ 真 CARA（一般）   ← 本次移除
           └──→ 重工
```

## 目標流程（改良後）

```
內部發現
  出貨/巡檢/IQC ──→ NCMR ──→ 重工（優先圍堵）
                        │      └──完成後提示──→ CAPA
                        └──→ CAPA（不分根因類別，統一 8D 或簡化 5D）

外部客訴
  客訴紀錄 ──→ CAPA（不分車用/非車用，統一 8D）  ← 狀態雙向同步
           └──→ 重工（有退貨實物） ← 補 complaint_id 追溯
```

---

## 變更 1：CARA 資料遷移（8 筆 → CAPA）

### 既有資料
資料庫 `矯正措施要求` 表有 8 筆紀錄：1 筆進行中、7 筆已結案。需保留歷史，全部轉成 CAPA（`異常矯正單` 表）。

### 欄位對應
| CARA (`矯正措施要求`) | CAPA (`異常矯正單`) | 備註 |
|----------------------|--------------------|------|
| `識別碼` | （產生新 ID） | CAPA 自己的 PK |
| `CARA單號` | `8D單號` | 直接複製，加前綴避免衝突 |
| `狀態` | `狀態` | 進行中 / 已結案 |
| `NCMR_ID` | `NCMR_ID` & `來源ID` | 都填同一個值 |
| — | `來源類型` | 固定填 `'ncmr'` |
| — | `嚴格度` | 固定填 `'簡化5D'`（因 CARA 只有 5 步） |
| `D2_What` / `D2_Where` / `D2_When` / `D2_Who` / `D2_Why` / `D2_How` / `D2_HowMany` | 對應 D2 各欄位 | 直接對應 |
| `D2_問題描述` | `D2_問題描述` | 舊版欄位也搬 |
| `D3_對策內容` / `D3_生效日` / `D3_有效性驗證` | 對應 D3 欄位 | 直接對應 |
| `D3_暫時對策` | `D3_暫時對策` | 舊版欄位 |
| `D4_工具` / `D4_5Why資料` / `D4_魚骨圖資料` / `D4_根本原因` | 對應 D4 欄位 | 直接對應 |
| `D4_真因分析` | `D4_真因分析` | 舊版欄位 |
| `D6_實施日` / `D6_驗證結果` / `D6_驗證通過` | 對應 D6 欄位 | 直接對應 |
| `D6_成效驗證` | `D6_成效驗證` | 舊版欄位 |
| `D8_結案日期` / `D8_結案確認` | 對應 D8 欄位 | 直接對應 |
| `負責人員` / `D1_Leader` | 對應欄位 | 直接對應 |
| `建立時間` / `結案時間` | 對應欄位 | 直接對應 |
| `廠商` | （無對應） | NCMR 已有，不重複存 |
| — | `D0_severity` | NULL（CARA 沒這資訊） |
| — | `D1_champion` / `D1_team` | NULL |
| — | `D5_*` / `D7_*` | NULL |

### Migration SQL
- 檔案：`migration/migrate_cara_to_capa.sql`
- 使用 `INSERT INTO 異常矯正單 (...) SELECT ... FROM 矯正措施要求 WHERE NOT EXISTS (...)`，避免重複執行
- 8D 單號規則：`'CARA-' || cara_no`（保留追溯記號，避免與既有 CAPA 8D 單號衝突）

### 移除附件多型支援
`Attachment.entity_type` 接受的值從 `{'capa', 'cara', 'task', 'complaint'}` 改為 `{'capa', 'task', 'complaint'}`；既有 `entity_type='cara'` 的附件需手動處理（資料庫查確認後再決定刪除或保留）。

---

## 變更 2：CARA 模組完全移除

### 後端刪除清單
| 檔案/物件 | 動作 |
|----------|------|
| `backend/routes/cara.py` | **刪除整個檔案** |
| `backend/services/cara_service.py` | **刪除整個檔案** |
| `backend/models.py` :: `CARARecord` 類別（含所有 relationship） | **刪除** |
| `backend/app.py` 的 `from .routes.cara import cara_bp` | **刪除** import |
| `backend/app.py` 的 `app.register_blueprint(cara_bp)` | **刪除** |
| `backend/services/complaint_service.py` :: `open_cara()` 方法 | **刪除**（已存在） |
| `backend/services/complaint_service.py` :: `_to_dict()` 的 `related_cara_id` 欄位 | **刪除** |
| `backend/routes/complaint.py` :: `open_cara_from_complaint` 路由 | **刪除** |
| `backend/services/attachment_service.py` :: `VALID_ENTITY_TYPES` 移除 `'cara'` | **修改** |

### 前端刪除清單
| 檔案/物件 | 動作 |
|----------|------|
| `src_frontend/src/pages/cara/CARAPage.tsx` | **刪除** |
| `src_frontend/src/components/cara/CARAModal.tsx` | **刪除** |
| `src_frontend/src/hooks/useCARA.ts` | **刪除** |
| `src_frontend/src/App.tsx` 的 `import CARAPage` 和 `<Route path="/cara">` | **刪除** |
| `src_frontend/src/components/Sidebar.tsx` 的 `{ title: 'CAR 要求', path: '/cara' }` | **刪除** |
| `src_frontend/src/components/complaint/*` 或 `pages/complaint/*` 任何 CARA 按鈕 | **刪除** |
| `src_frontend/src/hooks/useComplaint.ts` :: `useOpenCaraFromComplaint` | **刪除** |
| `src_frontend/src/types/index.ts` 的 CARA 相關 type | **刪除** |

### DB 變更
```sql
-- migration/drop_cara_module.sql（在 migrate_cara_to_capa.sql 執行成功後才能跑）
ALTER TABLE "客訴紀錄" DROP COLUMN IF EXISTS "關聯CARA_ID";
DROP TABLE IF EXISTS "矯正措施要求";
```

### 執行順序（必須按此順序）
1. **備份資料庫** — `pg_dump` 整個 `qa_database`
2. 跑 `migration/migrate_cara_to_capa.sql` — 把 8 筆 CARA 搬到 CAPA
3. 跑 SQL 驗證查詢，確認 8 筆都成功遷移
4. 跑 `migration/drop_cara_module.sql` — 刪欄位與表
5. 部署移除 CARA 程式碼的新版本

---

## 變更 3：客訴 ↔ CAPA 狀態雙向同步

### 狀態轉換規則

| 觸發動作 | 客訴狀態變化 |
|---------|-------------|
| 客訴成功開立 CAPA | `待處理` → `處理中` |
| 來源為客訴的 CAPA 結案（D8 完成） | `處理中` → `已結案` |
| 來源為客訴的 CAPA 被刪除 | `處理中` / `已結案` → `待處理`（回退） |

### 後端變更

**`backend/routes/complaint.py`**：
- `open_capa_from_complaint()` 路由：CAPA 建立並寫入 `c.related_capa_id` 後，加上 `c.status = '處理中'`；`db.session.commit()` 一併提交

**`backend/services/capa_service.py`**：
- `close()` 方法：結案後，若 `ca.source_type == 'complaint'`，查 `CustomerComplaint.query.get(ca.source_id)` 並設 `complaint.status = '已結案'`
- `delete()` 方法：刪除前，若 `ca.source_type == 'complaint'`，將客訴 `related_capa_id = None` 並 `status = '待處理'`

### 前端變更
- `src_frontend/src/pages/complaint/ComplaintPage.tsx`：
  - 「已開立 CAPA」badge 改為可點擊連結，導向 `/capa?id=<related_capa_id>`

---

## 變更 4：重工追溯補齊（complaint_id）

### 問題
`ReworkRequest` 從客訴開立時，重工單不知道來源客訴，只有客訴端記錄 `related_rework_id`。

### DB 變更
```sql
-- migration/add_rework_complaint_id.sql
ALTER TABLE "重工申請單"
    ADD COLUMN IF NOT EXISTS "客訴_ID" INTEGER;
```

### 模型變更
**`backend/models.py`** :: `ReworkRequest`：
```python
complaint_id = db.Column('客訴_ID', db.Integer, nullable=True)
```

### 服務變更
**`backend/services/rework_service.py`**：
- `create_from_complaint()`：建立 `ReworkRequest` 時填入 `complaint_id = complaint.id`
- `get_application_list()`：回傳資料加入 `complaint_id` 與 `complaint_no`（透過 join 或 N+1 查詢取得）

### 前端變更
- 重工列表 / 編輯頁面：若 `complaint_id` 有值，顯示「來源客訴：CC-XXXXXXXX-XXX」連結
- `src_frontend/src/pages/complaint/ComplaintPage.tsx`：「已開立重工」badge 改為可點擊

---

## 變更 5：重工完成後提醒開立 CAPA

### 問題
NCMR 的重工完成後，使用者常忘記開立後續 CAPA。

### 觸發時機
重工執行記錄（`ReworkExecution`）狀態變更為「已完成」時觸發。

### 互動流程
```
使用者點「完成重工」
  → 更新狀態成功
  → 彈出確認 Modal：

┌─────────────────────────────────────────┐
│  重工已完成，是否需要開立 CAPA？             │
│                                         │
│  根因若為製程/系統問題，建議開立 CAPA           │
│  進行根本原因分析與系統性矯正                  │
│                                         │
│  [ 開立 CAPA ]  [ 暫不處理 ]                │
└─────────────────────────────────────────┘

選「開立 CAPA」→ 跳轉至 CAPA 建立，預填 source_type='ncmr', source_id=ncmr_id
選「暫不處理」→ 關閉 Modal
```

### 限制條件
- 只在重工有關聯 NCMR（`ncmr_id != null`）時顯示（從客訴開的重工已有上層客訴在追蹤，不重複提示）
- 若 NCMR 已有 `related_capa_id`，不顯示提示

### 前端變更
- `src_frontend/src/components/rework/EditExecutionModal.tsx`：完成後觸發 `ReworkFollowUpModal`
- 新增 `src_frontend/src/components/rework/ReworkFollowUpModal.tsx` 元件

### 後端
- 無需新 API，前端跳轉時直接呼叫既有的 CAPA 建立 API

---

## DB Migration 清單

| 檔案 | 內容 | 執行順序 |
|------|------|---------|
| `migration/migrate_cara_to_capa.sql` | 把 8 筆 CARA 資料 INSERT 到 CAPA | 1 |
| `migration/migrate_car_to_capa.sql` | 8 筆 CAR 紀錄的 `CAR單號` → `8D單號` | 2 |
| `migration/add_rework_complaint_id.sql` | `重工申請單` 加 `客訴_ID` 欄位 | 3 |
| `migration/drop_cara_module.sql` | 刪 `關聯CARA_ID` 欄位、DROP `矯正措施要求` 表 | 4 |
| `migration/drop_car_number_column.sql` | 刪 `異常矯正單.CAR單號` 欄位 | 5（最後） |

---

## 受影響檔案總清單

### 後端（刪除）
- `backend/routes/cara.py`
- `backend/services/cara_service.py`

### 後端（修改）
- `backend/models.py` — 刪除 `CARARecord` 類別；`CorrectiveAction` 移除 `car_number`；`ReworkRequest` 加 `complaint_id`；`CustomerComplaint` 移除 `related_cara_id`
- `backend/app.py` — 移除 `cara_bp` 註冊
- `backend/services/complaint_service.py` — 刪除 `open_cara()`；`_to_dict()` 移除 `related_cara_id`
- `backend/services/capa_service.py` — `close()` / `delete()` 加客訴狀態同步
- `backend/services/rework_service.py` — `create_from_complaint()` 填入 `complaint_id`；`get_application_list()` 回傳加 complaint 資訊
- `backend/services/attachment_service.py` — `VALID_ENTITY_TYPES` 移除 `'cara'`
- `backend/services/ncmr_service.py` — 刪除 `get_cara_list/create_cara/get_cara_detail/update_cara/delete_cara`
- `backend/routes/complaint.py` — 刪除 `open_cara_from_complaint` 路由；`open_capa_from_complaint` 加狀態同步
- `backend/routes/ncmr.py` — 刪除 `/api/cara/*` 5 條路由
- `backend/routes/admin.py` — 刪除 `count_pending_cara()` 與 dashboard `cara` 統計區段
- `backend/utils.py` — 刪除 `generate_car_number()`
- `backend/tests/test_services/test_ncmr.py` — 刪除 `test_get_cara_list_*` 測試

### 前端（刪除）
- `src_frontend/src/pages/cara/CARAPage.tsx`
- `src_frontend/src/components/cara/CARAModal.tsx`
- `src_frontend/src/hooks/useCARA.ts`

### 前端（修改）
- `src_frontend/src/App.tsx` — 移除 CARA 路由與 import
- `src_frontend/src/components/Sidebar.tsx` — 移除「CAR 要求」項目
- `src_frontend/src/types/index.ts` — 移除 CARA 相關 type 與 `car_number`；`CustomerComplaint` 移除 `related_cara_id`
- `src_frontend/src/hooks/useComplaint.ts` — 移除 `useOpenCaraFromComplaint`；移除 `queryKey: ['caraList']` 失效
- `src_frontend/src/hooks/useNCMR.ts` — 移除 `useCreateCARA`、`useCARAList`；`CARListParams` 重新命名為 `CAPAListParams`（並移除 type alias）
- `src_frontend/src/hooks/useDashboard.ts` — 移除 `cara` 型別欄位與 `'cara'` recent activity type
- `src_frontend/src/components/dashboard/KPICards.tsx` — 移除「CAR 要求」KPI 卡片
- `src_frontend/src/pages/complaint/ComplaintPage.tsx` — 移除 CARA 按鈕；CAPA / 重工 badge 改連結
- `src_frontend/src/pages/ncmr/NCMRPage.tsx` — 移除 `convertToCAR()` 與「轉為 CAR」按鈕
- `src_frontend/src/components/rework/EditExecutionModal.tsx` — 完成時觸發新 Modal

### 前端（新增）
- `src_frontend/src/components/rework/ReworkFollowUpModal.tsx`

### 資料庫
- `migration/migrate_cara_to_capa.sql`
- `migration/migrate_car_to_capa.sql`
- `migration/add_rework_complaint_id.sql`
- `migration/drop_cara_module.sql`
- `migration/drop_car_number_column.sql`

---

## 變更 6：舊版 CAR 模式整合進 CAPA

### 背景
程式碼歷史包袱讓 NCMR 模組同時有「轉為 CAR」和「開立 8D」兩個並列按鈕，背後都建立 `CorrectiveAction` 紀錄，差別只在用 `CAR單號` 或 `8D單號` 欄位。資料庫實際狀況：

- 8 筆 CAR 紀錄（`CAR單號` 有值、`8D單號` 為空、嚴格度='完整8D'）
- 1 筆 8D 紀錄（`8D單號` 有值、`CAR單號` 為空）
- 兩者 `嚴格度` 都已是 `'完整8D'`

CAR 和 8D 本質是同一個東西，本次統一只留 CAPA（內含 rigor 欄位區分 8D / 簡化 5D）。

### 資料遷移
**檔案：`migration/migrate_car_to_capa.sql`**

```sql
-- 把 8 筆 CAR 紀錄的 CAR單號 搬到 8D單號，保留追溯
UPDATE "異常矯正單"
SET "8D單號" = 'CAR-' || "CAR單號"
WHERE "CAR單號" IS NOT NULL
  AND "8D單號" IS NULL;
```

### DB 變更
**檔案：`migration/drop_car_number_column.sql`**（在 `migrate_car_to_capa.sql` 成功後執行）

```sql
ALTER TABLE "異常矯正單" DROP COLUMN IF EXISTS "CAR單號";
```

### 後端刪除清單
| 檔案/物件 | 動作 |
|----------|------|
| `backend/routes/ncmr.py` :: `/api/cara` GET / POST / PUT / DELETE / detail（5 條） | **刪除** |
| `backend/services/ncmr_service.py` :: `get_cara_list()` / `create_cara()` / `get_cara_detail()` / `update_cara()` / `delete_cara()` | **刪除** |
| `backend/routes/admin.py` :: `count_pending_cara()` 函式 | **刪除** |
| `backend/routes/admin.py` :: dashboard `cara_row` 統計與 `_cara_current` / `_cara_previous` / `'cara'` 區段 | **刪除** |
| `backend/utils.py` :: `generate_car_number()` | **刪除**（無人呼叫後） |
| `backend/models.py` :: `CorrectiveAction.car_number` 欄位 | **刪除** |
| `backend/tests/test_services/test_ncmr.py` :: `test_get_cara_list_*` 等測試 | **刪除** |

### 前端刪除清單
| 檔案/物件 | 動作 |
|----------|------|
| `src_frontend/src/hooks/useNCMR.ts` :: `useCreateCARA` | **刪除** |
| `src_frontend/src/pages/ncmr/NCMRPage.tsx` :: `convertToCAR()` 函式與「轉為 CAR」按鈕 | **刪除** |
| `src_frontend/src/types/index.ts` 若有 `car_number` 相關 type | **刪除** |
| Dashboard 元件若有顯示 CAR 統計 | **刪除** |

### 執行順序（追加在 CARA 遷移之後）
1. 跑 `migration/migrate_car_to_capa.sql` — CAR 單號搬到 8D 單號
2. 部署移除 `car_number` 引用的後端與前端
3. 跑 `migration/drop_car_number_column.sql` — 刪欄位

---

## 不在本次範圍

- **NCMR `來源` 欄位標準化** — 維持現狀（free text）
- **客訴 ↔ 重工狀態連動** — 重工完成不自動結案客訴，需人工判斷

---

## 風險與回滾

| 風險 | 影響 | 緩解 |
|------|------|------|
| Migration 部分成功，部分失敗 | 8 筆 CARA 有些遷移有些沒 | 用 transaction 包整批 INSERT，失敗就 ROLLBACK |
| Drop table 後發現遷移漏資料 | 無法回復 | Step 1 必須先 `pg_dump` 完整備份 |
| 前端 build 失敗（殘留 CARA import） | 部署後白屏 | 全文搜尋 `cara`、`CARA` 確認無殘留再合併 |
| 既有附件 `entity_type='cara'` 變成孤兒 | 附件無法顯示 | Migration 前先查 `SELECT COUNT(*) FROM 附件 WHERE 實體類型='cara'`，視結果處理 |
