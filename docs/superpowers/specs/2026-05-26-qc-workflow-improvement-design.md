# QC 品質流程改良 Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改良 NCMR / CARA / CAPA / 客訴四個模組之間的工作流程，解決 CARA 定位混亂、狀態不同步、追溯斷鏈、重工完成後無提示四個問題。

**Architecture:** 後端修改服務層邏輯與新增 DB 欄位，前端移除錯誤入口並補齊追溯連結與提示互動。不改動既有 API 路由的 URL，只調整行為與新增欄位。

**Tech Stack:** Flask 3.1 + SQLAlchemy + PostgreSQL 18 / React 19 + TypeScript + React Query + React Bootstrap

---

## 現有模組關係（改良前）

```
內部發現
  出貨/巡檢/IQC ──→ NCMR ──→ 重工（圍堵）
                        ├──→ CARA（供應商，僅 IQC）
                        └──→ CAPA（8D）

外部客訴
  客訴紀錄 ──→ CAPA（車用嚴重）
           ├──→ CARA（一般）   ← 語意錯誤，本次移除
           └──→ 重工
```

## 目標流程（改良後）

```
內部發現
  出貨/巡檢/IQC ──→ NCMR ──→ 重工（優先圍堵）
                        │      └──完成後提示──→ CARA 或 CAPA
                        ├──→ CARA（根因為供應商，IQC 限定）
                        └──→ CAPA（根因為製程/系統）

外部客訴
  客訴紀錄 ──→ CAPA（車用嚴重）  ← 狀態雙向同步
           └──→ 重工（有退貨實物）← 補 complaint_id 追溯
```

---

## 變更 1：CARA 嚴格化

### 問題
`ComplaintService.open_cara()` 與 `CARAService.create_from_complaint()` 讓客訴可以直接開立 CARA。CARA（矯正措施要求）業界定義為「發給供應商的要求」，客訴場景應使用 CAPA。

### 決策
- CARA 僅允許從 IQC 來料 NCMR 開立（現有邏輯保留）
- 客訴頁面移除「開立 CARA」按鈕
- 保留 `CustomerComplaint.related_cara_id` DB 欄位（避免 migration 風險），但不再寫入

### 後端變更
- `backend/services/complaint_service.py`：刪除 `open_cara()` 方法
- `backend/services/cara_service.py`：刪除 `create_from_complaint()` 方法
- `backend/routes/complaint.py`：刪除 `POST /api/complaints/<id>/open-cara` 路由

### 前端變更
- `src_frontend/src/pages/complaint/ComplaintPage.tsx`：
  - 移除「開立 CARA」按鈕與欄位
  - 移除 `useOpenCaraFromComplaint` hook 的呼叫
- `src_frontend/src/hooks/useComplaint.ts`：
  - 移除 `useOpenCaraFromComplaint` hook

---

## 變更 2：客訴 ↔ CAPA 狀態雙向同步

### 問題
客訴開立 CAPA 後，客訴狀態停留在「待處理」。CAPA 結案後，客訴不自動進入「已結案」。

### 狀態轉換規則

| 觸發動作 | 客訴狀態變化 |
|---------|-------------|
| 客訴成功開立 CAPA | `待處理` → `處理中` |
| 來源為客訴的 CAPA 結案（D8 完成） | `處理中` → `已結案` |
| 來源為客訴的 CAPA 被刪除 | `處理中` / `已結案` → `待處理`（回退） |

### 後端變更

**`backend/routes/complaint.py`**：
- `open_capa_from_complaint()` 路由（現有）：CAPA 建立並寫入 `related_capa_id` 後，加上 `complaint.status = '處理中'`；`db.session.commit()` 一併提交

**`backend/services/capa_service.py`**：
- `close()` 方法：結案後，若 `ca.source_type == 'complaint'`，查詢對應客訴並設 `complaint.status = '已結案'`
- `delete()` 方法：刪除前，若 `ca.source_type == 'complaint'`，將客訴狀態回退為 `'待處理'`

### 前端變更
- `src_frontend/src/pages/complaint/ComplaintPage.tsx`：
  - 「已開立 CAPA」badge 改為可點擊連結，導向對應 CAPA 頁面（`/capa?id=<related_capa_id>`）

---

## 變更 3：重工追溯補齊（complaint_id）

### 問題
`ReworkRequest` 從客訴開立時，重工單不知道來源客訴，只有客訴端記錄 `related_rework_id`，無法從重工頁面追溯。

### DB 變更
```sql
-- migration/add_rework_complaint_id.sql
ALTER TABLE "重工申請單"
    ADD COLUMN IF NOT EXISTS "客訴_ID" INTEGER;
```

### 模型變更
**`backend/models.py`**：`ReworkRequest` 加入：
```python
complaint_id = db.Column('客訴_ID', db.Integer, nullable=True)
```

### 服務變更
**`backend/services/rework_service.py`**：`create_from_complaint()` 方法在建立 `ReworkRequest` 時，填入 `complaint_id = complaint.id`

### 序列化變更
**`backend/services/rework_service.py`**：`get_application_list()` 回傳資料加入 `complaint_id` 欄位

### 前端變更
- `src_frontend/src/components/rework/ApplyModal.tsx` 或重工列表頁：若 `complaint_id` 有值，顯示「來源客訴：CC-XXXXXXXX-XXX」連結
- `src_frontend/src/pages/complaint/ComplaintPage.tsx`：「已開立重工」badge 改為可點擊（導向重工列表並帶 filter）

---

## 變更 4：重工完成後提醒開立矯正行動

### 問題
NCMR 的重工完成後，使用者常忘記開立後續矯正行動（CARA 或 CAPA）。

### 觸發時機
重工執行記錄（`ReworkExecution`）狀態變更為「已完成」時觸發。

### 互動流程
```
使用者點「完成重工」
  → 更新狀態成功
  → 彈出確認 Modal：

┌─────────────────────────────────────────┐
│  重工已完成，是否需要開立後續矯正行動？         │
│                                         │
│  根因為供應商  →  [ 開立 CARA ]           │
│  根因為製程    →  [ 開立 CAPA ]           │
│                   [ 暫不處理 ]           │
└─────────────────────────────────────────┘

選「開立 CARA」→ 跳轉至 CARA 建立，預填 ncmr_id
選「開立 CAPA」→ 跳轉至 CAPA 建立，預填 source_type='ncmr', source_id
選「暫不處理」→ 關閉 Modal，不做任何動作
```

### 限制條件
- 只在重工有關聯 NCMR（`ncmr_id != null`）時顯示此 Modal（從客訴開的重工無需此提示）
- 若 NCMR 已有關聯 CAPA 或 CARA，不重複提示

### 前端變更
- `src_frontend/src/components/rework/EditExecutionModal.tsx`（或現有完成按鈕所在元件）：完成後顯示 `ReworkFollowUpModal`
- 新增元件 `src_frontend/src/components/rework/ReworkFollowUpModal.tsx`

### 後端變更
- 不需要新 API，前端完成後跳轉時直接帶參數到 CARA / CAPA 建立流程

---

## DB Migration 清單

| 檔案 | 內容 |
|------|------|
| `migration/add_rework_complaint_id.sql` | `重工申請單` 加 `客訴_ID` 欄位 |

`CustomerComplaint.related_cara_id` 已存在，保留不動。

---

## 受影響檔案清單

### 後端
| 檔案 | 變更類型 |
|------|---------|
| `backend/models.py` | 新增 `ReworkRequest.complaint_id` |
| `backend/services/complaint_service.py` | 刪除 `open_cara()`；`open_capa()` 加狀態同步 |
| `backend/services/capa_service.py` | `close()` 和 `delete()` 加客訴狀態回寫 |
| `backend/services/cara_service.py` | 刪除 `create_from_complaint()` |
| `backend/services/rework_service.py` | `create_from_complaint()` 填入 `complaint_id` |
| `backend/routes/complaint.py` | 刪除 `open-cara` 路由 |

### 前端
| 檔案 | 變更類型 |
|------|---------|
| `src_frontend/src/hooks/useComplaint.ts` | 刪除 `useOpenCaraFromComplaint` |
| `src_frontend/src/pages/complaint/ComplaintPage.tsx` | 移除 CARA 按鈕；badge 改連結 |
| `src_frontend/src/components/rework/EditExecutionModal.tsx` | 完成後觸發提示 |
| `src_frontend/src/components/rework/ReworkFollowUpModal.tsx` | 新增元件 |

### 資料庫
| 檔案 | 內容 |
|------|------|
| `migration/add_rework_complaint_id.sql` | 新增欄位 |

---

## 不在本次範圍

- NCMR `來源` 欄位標準化（free text → enum）— 獨立改善項目
- NCMR → CARA 追溯補齊 `related_cara_id`（CARA 已有 `ncmr_id` 可反查，暫不處理）
- 客訴 ↔ 重工狀態連動（重工完成不自動結案客訴，需人工判斷）
