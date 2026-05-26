# QC 品質流程改良 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 CARA 模組與舊版 CAR 模式（命名混亂遺留），把所有矯正行動統一走 CAPA；補齊客訴 ↔ CAPA 狀態同步、重工 ↔ 客訴追溯，並在重工結案時提示開立 CAPA。

**Architecture:** 先用 additive migration 把資料搬到新位置（CAPA、新增 `complaint_id` 欄位），再分批刪除舊程式碼，最後 destructive migration 砍掉舊欄位/舊表。每一步系統都保持可運作。

**Tech Stack:** Flask 3.1 + SQLAlchemy + PostgreSQL 18 / React 19 + TypeScript + React Query + React Bootstrap + pytest

---

## 執行原則

1. **每個 Task 必須 commit**，commit message 中文撰寫
2. **DB migration 跑在使用者本機 PostgreSQL**（`C:\Program Files\PostgreSQL\18\bin\psql.exe`，密碼 `swordfish1`，DB 名稱 `qa_database`）
3. **後端用 venv**：`C:\QC_Database\venv\Scripts\python.exe`
4. **後端啟動方式**：`python -m waitress --listen=*:5001 backend.app:app`
5. **每次後端代碼變更後，要重啟 waitress 才會生效**
6. **遇到不確定就 STOP 問使用者，不要硬猜**

---

## 任務總覽

| # | 任務 | 階段 |
|---|------|------|
| 1 | 備份資料庫並記錄基準 | 準備 |
| 2 | DB Migration：新增 `重工申請單.客訴_ID` 欄位（additive） | 資料庫 |
| 3 | DB Migration：8 筆 CARA → CAPA | 資料庫 |
| 4 | DB Migration：8 筆 CAR 的 `CAR單號` → `8D單號` | 資料庫 |
| 5 | 後端：`ReworkRequest.complaint_id` 模型 + service 支援 | 後端新功能 |
| 6 | 後端：CAPA close / delete 同步客訴狀態 | 後端新功能 |
| 7 | 後端：客訴開立 CAPA 時改成 `處理中` | 後端新功能 |
| 8 | 後端：移除 CARA 模組（route / service / model / blueprint / 附件白名單） | 後端清理 |
| 9 | 後端：移除舊版 CAR 模式（ncmr 路由、service、admin、utils、model 欄位、測試） | 後端清理 |
| 10 | 前端：刪除 CARA 模組（pages / components / hooks / App.tsx / Sidebar / types） | 前端清理 |
| 11 | 前端：移除舊版 CAR 模式（useNCMR / useDashboard / KPICards / NCMRPage） | 前端清理 |
| 12 | 前端：`ComplaintPage` 的 CAPA / 重工 badge 改成可點擊連結 | 前端新功能 |
| 13 | 前端：新增 `ReworkFollowUpModal` 元件 | 前端新功能 |
| 14 | 前端：`ReworkPage.handleCloseRework` 整合 FollowUp Modal | 前端新功能 |
| 15 | DB Migration：DROP `矯正措施要求` 表與 `關聯CARA_ID` 欄位（destructive） | 資料庫 |
| 16 | DB Migration：DROP `異常矯正單.CAR單號` 欄位（destructive） | 資料庫 |
| 17 | 端對端驗證 | 收尾 |

---

## Task 1: 備份資料庫並記錄基準

**Files:**
- Create: `migration/baseline_2026-05-26.md`（基準記錄）
- 備份位置：`C:\QC_Database\backups\qa_database_2026-05-26.dump`

- [ ] **Step 1: 建立備份資料夾**

```powershell
New-Item -ItemType Directory -Force -Path "C:\QC_Database\backups"
```

- [ ] **Step 2: 完整備份資料庫**

```powershell
$env:PGPASSWORD = "swordfish1"
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -F c -f "C:\QC_Database\backups\qa_database_2026-05-26.dump" qa_database
```
Expected: 沒有輸出代表成功，檢查檔案 size > 0。

- [ ] **Step 3: 驗證備份檔可讀取**

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" --list "C:\QC_Database\backups\qa_database_2026-05-26.dump" | Select-Object -First 20
```
Expected: 列出多個 TABLE / INDEX entry。

- [ ] **Step 4: 記錄遷移前的紀錄筆數**

執行下列 SQL 並把輸出貼到 `migration/baseline_2026-05-26.md`：

```powershell
$env:PGPASSWORD = "swordfish1"
@'
SELECT '矯正措施要求' AS tbl, COUNT(*) FROM "矯正措施要求"
UNION ALL SELECT '異常矯正單_CAR模式', COUNT(*) FROM "異常矯正單" WHERE "CAR單號" IS NOT NULL
UNION ALL SELECT '異常矯正單_8D模式', COUNT(*) FROM "異常矯正單" WHERE "8D單號" IS NOT NULL
UNION ALL SELECT '重工申請單', COUNT(*) FROM "重工申請單"
UNION ALL SELECT '客訴紀錄', COUNT(*) FROM "客訴紀錄";
'@ | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: 矯正措施要求=8、CAR模式=8、8D模式=1、重工/客訴依現況。

- [ ] **Step 5: 建立 baseline 紀錄**

`migration/baseline_2026-05-26.md` 內容：

```markdown
# 遷移前基準（2026-05-26）

- 矯正措施要求 (CARA): 8 筆
- 異常矯正單 CAR 模式 (CAR單號非空): 8 筆
- 異常矯正單 8D 模式 (8D單號非空): 1 筆
- 重工申請單：（執行時的實際筆數）
- 客訴紀錄：（執行時的實際筆數）

備份檔：C:\QC_Database\backups\qa_database_2026-05-26.dump
```

- [ ] **Step 6: Commit**

```bash
git add migration/baseline_2026-05-26.md
git commit -m "chore: 流程改良工程啟動 — 備份資料庫並記錄基準筆數

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: DB Migration — 新增 `重工申請單.客訴_ID` 欄位

**Files:**
- Create: `migration/add_rework_complaint_id.sql`

- [ ] **Step 1: 撰寫 migration SQL**

`migration/add_rework_complaint_id.sql`：

```sql
-- 重工申請單新增客訴 ID 欄位，用於追溯由客訴開立的重工單
ALTER TABLE "重工申請單"
    ADD COLUMN IF NOT EXISTS "客訴_ID" INTEGER;
```

- [ ] **Step 2: 執行 migration**

```powershell
$env:PGPASSWORD = "swordfish1"
Get-Content "C:\QC_Database\migration\add_rework_complaint_id.sql" -Raw | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `ALTER TABLE`

- [ ] **Step 3: 驗證欄位存在**

```powershell
$env:PGPASSWORD = "swordfish1"
'\d "重工申請單"' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database | Select-String "客訴_ID"
```
Expected: 看到 `客訴_ID | integer`

- [ ] **Step 4: Commit**

```bash
git add migration/add_rework_complaint_id.sql
git commit -m "feat(db): 重工申請單新增客訴_ID 追溯欄位

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: DB Migration — CARA 資料遷移到 CAPA

**Files:**
- Create: `migration/migrate_cara_to_capa.sql`

- [ ] **Step 1: 撰寫 migration SQL**

`migration/migrate_cara_to_capa.sql`：

```sql
-- 把 8 筆 CARA 資料 INSERT 到 CAPA（異常矯正單）表，保留 8D 單號為 'CARA-' 前綴以利追溯
-- 使用 NOT EXISTS 防止重複執行
BEGIN;

INSERT INTO "異常矯正單" (
    "8D單號", "狀態",
    "來源類型", "來源ID", "NCMR_ID",
    "嚴格度",
    "D2_What", "D2_Where", "D2_When", "D2_Who",
    "D2_Why", "D2_How", "D2_HowMany",
    "D2_問題描述",
    "D3_對策內容", "D3_生效日", "D3_有效性驗證", "D3_暫時對策",
    "D4_工具", "D4_5Why資料", "D4_魚骨圖資料", "D4_根本原因", "D4_真因分析",
    "D6_實施日", "D6_驗證結果", "D6_驗證通過", "D6_成效驗證",
    "D8_結案日期", "D8_結案確認",
    "負責人員", "D1_Leader",
    "建立時間", "結案時間"
)
SELECT
    'CARA-' || c."CARA單號", c."狀態",
    'ncmr', c."NCMR_ID", c."NCMR_ID",
    '簡化5D',
    c."D2_What", c."D2_Where", c."D2_When", c."D2_Who",
    c."D2_Why", c."D2_How", c."D2_HowMany",
    c."D2_問題描述",
    c."D3_對策內容", c."D3_生效日", c."D3_有效性驗證", c."D3_暫時對策",
    c."D4_工具", c."D4_5Why資料", c."D4_魚骨圖資料", c."D4_根本原因", c."D4_真因分析",
    c."D6_實施日", c."D6_驗證結果", c."D6_驗證通過", c."D6_成效驗證",
    c."D8_結案日期", c."D8_結案確認",
    c."負責人員", c."D1_Leader",
    c."建立時間", c."結案時間"
FROM "矯正措施要求" c
WHERE NOT EXISTS (
    SELECT 1 FROM "異常矯正單" ca
    WHERE ca."8D單號" = 'CARA-' || c."CARA單號"
);

COMMIT;
```

- [ ] **Step 2: 執行 migration**

```powershell
$env:PGPASSWORD = "swordfish1"
Get-Content "C:\QC_Database\migration\migrate_cara_to_capa.sql" -Raw | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `BEGIN`, `INSERT 0 8`, `COMMIT`

- [ ] **Step 3: 驗證 8 筆都成功遷移**

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT COUNT(*) AS migrated FROM "異常矯正單" WHERE "8D單號" LIKE ''CARA-%'';' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `migrated = 8`

- [ ] **Step 4: 抽查一筆內容**

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT "8D單號", "狀態", "嚴格度", "來源類型", "NCMR_ID" FROM "異常矯正單" WHERE "8D單號" LIKE ''CARA-%'' LIMIT 1;' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: 8D 單號開頭為 `CARA-`、嚴格度為 `簡化5D`、來源類型為 `ncmr`、`NCMR_ID` 有值。

- [ ] **Step 5: Commit**

```bash
git add migration/migrate_cara_to_capa.sql
git commit -m "feat(db): CARA 資料遷移到 CAPA — 8 筆紀錄保留為簡化 5D 模式

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: DB Migration — CAR 紀錄的 CAR單號 搬到 8D單號

**Files:**
- Create: `migration/migrate_car_to_capa.sql`

- [ ] **Step 1: 撰寫 migration SQL**

`migration/migrate_car_to_capa.sql`：

```sql
-- 把舊版 CAR 模式 (CAR單號非空) 紀錄的 CAR單號 搬到 8D單號，加 'CAR-' 前綴避免衝突
-- 同時清空 CAR單號 避免之後 DROP COLUMN 時資料遺失歷史追溯
BEGIN;

UPDATE "異常矯正單"
SET "8D單號" = 'CAR-' || "CAR單號"
WHERE "CAR單號" IS NOT NULL
  AND "8D單號" IS NULL;

COMMIT;
```

- [ ] **Step 2: 執行 migration**

```powershell
$env:PGPASSWORD = "swordfish1"
Get-Content "C:\QC_Database\migration\migrate_car_to_capa.sql" -Raw | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `BEGIN`, `UPDATE 8`, `COMMIT`

- [ ] **Step 3: 驗證 8 筆都成功**

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT COUNT(*) AS migrated FROM "異常矯正單" WHERE "8D單號" LIKE ''CAR-%'';' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `migrated = 8`

- [ ] **Step 4: 驗證沒有任何 CAR單號 有值但 8D單號 為空的孤兒**

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT COUNT(*) AS orphans FROM "異常矯正單" WHERE "CAR單號" IS NOT NULL AND "8D單號" IS NULL;' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `orphans = 0`

- [ ] **Step 5: Commit**

```bash
git add migration/migrate_car_to_capa.sql
git commit -m "feat(db): 舊版 CAR 模式合併到 CAPA — CAR單號 → 8D單號（加 CAR- 前綴）

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 後端 `ReworkRequest.complaint_id` 模型與 service 支援

**Files:**
- Modify: `backend/models.py`（`ReworkRequest` 加 `complaint_id`）
- Modify: `backend/services/rework_service.py`（`create_from_complaint` 填入 complaint_id；`get_application_list` 回傳 complaint 資訊）

- [ ] **Step 1: 修改 `ReworkRequest` 模型**

`backend/models.py`，找到 `class ReworkRequest`，在 `actual_finish_date` 欄位之後（約 line 381）加入：

```python
    complaint_id = db.Column('客訴_ID', db.Integer, nullable=True)
```

- [ ] **Step 2: 修改 `ReworkService.create_from_complaint`**

`backend/services/rework_service.py` 找到 `create_from_complaint` 方法，加上 `complaint_id`：

```python
@staticmethod
def create_from_complaint(complaint) -> Dict[str, Any]:
    """從客訴直接開立重工申請單（不需 NCMR）"""
    from ..models import CustomerComplaint
    if not isinstance(complaint, CustomerComplaint):
        raise ValueError('無效的客訴物件')
    try:
        rework_number = generate_number('RW', "重工申請單", "申請單號")
        req = ReworkRequest(
            ncmr_id      = None,
            complaint_id = complaint.id,
            rework_number= rework_number,
            applicant_id = None,
            product_info = f'{complaint.product_no} / {complaint.customer}',
            reason       = complaint.description,
            urgency      = '普通',
            department   = '',
            status       = '申請中',
        )
        db.session.add(req)
        db.session.commit()
        return {'rework_id': req.id, 'rework_number': req.rework_number}
    except Exception as e:
        db.session.rollback()
        raise e
```

- [ ] **Step 3: 修改 `get_application_list` 回傳 complaint 資訊**

在 `backend/services/rework_service.py` 的 `get_application_list` 方法中，找到組裝 `item` 字典的地方（約 line 127），在最後加入：

```python
                    "客訴_ID": r.complaint_id,
                    "客訴單號": "",  # 預填空字串，下面 N+1 補
```

接著在 `data.append(item)` 之前，加 N+1 查詢補上 `客訴單號`：

```python
            # 補上客訴單號（從 CustomerComplaint 反查）
            from ..models import CustomerComplaint
            complaint_ids = [r.complaint_id for r in rs if r.complaint_id]
            if complaint_ids:
                complaints = {
                    c.id: c.complaint_no
                    for c in CustomerComplaint.query.filter(CustomerComplaint.id.in_(complaint_ids)).all()
                }
                for item in data:
                    cid = item.get("客訴_ID")
                    if cid:
                        item["客訴單號"] = complaints.get(cid, "")
```
（這段應該在 `return data` 之前）

> ⚠️ **若 `get_application_list` 結構與此預期不同，停下來請示使用者，不要硬塞。**

- [ ] **Step 4: 重啟後端**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3
```

- [ ] **Step 5: 端對端驗證 — 建立客訴 → 開立重工 → 確認 complaint_id 填入**

```powershell
$env:PGPASSWORD = "swordfish1"
.\venv\Scripts\python.exe -c @'
from backend.app import app
import json
with app.test_client() as c:
    token = json.loads(c.post('/api/login', json={'username':'admin','password':'admin'}).get_data(as_text=True))['token']
    h = {'Authorization': f'Bearer {token}'}
    # 建客訴
    cr = c.post('/api/complaints', json={
        'customer': 'TaskN-Test', 'complaint_date': '2026-05-26',
        'product_no': 'P-N', 'description': 'task5 test'
    }, headers=h)
    cid = json.loads(cr.get_data(as_text=True))['id']
    # 開重工
    rr = c.post(f'/api/complaints/{cid}/open-rework', headers=h)
    print('Rework response:', rr.get_data(as_text=True))
    rid = json.loads(rr.get_data(as_text=True))['rework_id']
    print(f'Created complaint {cid}, rework {rid}')
'@
```
Expected: 收到 rework_id。

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT "識別碼", "申請單號", "客訴_ID" FROM "重工申請單" ORDER BY "識別碼" DESC LIMIT 1;' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `客訴_ID` 不為空。

- [ ] **Step 6: 清理測試資料**

```powershell
$env:PGPASSWORD = "swordfish1"
'DELETE FROM "重工申請單" WHERE "申請單號" LIKE ''RW-2026%'' AND "客訴_ID" IS NOT NULL; DELETE FROM "客訴紀錄" WHERE "客戶" = ''TaskN-Test'';' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```

- [ ] **Step 7: Commit**

```bash
git add backend/models.py backend/services/rework_service.py
git commit -m "feat(rework): 重工申請單支援 complaint_id 追溯欄位

- ReworkRequest 加 complaint_id 欄位
- create_from_complaint 自動寫入 complaint.id
- get_application_list 回傳 客訴_ID 與 客訴單號 供前端追溯

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 後端 — CAPA close / delete 同步客訴狀態

**Files:**
- Modify: `backend/services/capa_service.py`（`close()` 與 `delete()`）

- [ ] **Step 1: 修改 `CAPAService.close`**

`backend/services/capa_service.py`，找到 `close()` 方法（約 line 256），在 `db.session.commit()` **之前**插入客訴狀態同步：

```python
        ca.status         = '已結案'
        ca.d8_confirmation= confirmation
        ca.d8_recognition = recognition
        ca.d8_close_date  = date.today()
        ca.closed_at      = datetime.utcnow()

        # 若來源為客訴，同步將客訴狀態設為已結案
        if ca.source_type == 'complaint' and ca.source_id:
            from ..models import CustomerComplaint
            complaint = CustomerComplaint.query.get(ca.source_id)
            if complaint:
                complaint.status = '已結案'

        db.session.commit()
        return CAPAService._to_dict(ca)
```

- [ ] **Step 2: 修改 `CAPAService.delete`**

`backend/services/capa_service.py`，找到 `delete()` 方法（約 line 285），在 `db.session.delete(ca)` **之前**插入：

```python
        # 同步刪除關聯任務（pending 狀態）
        ActionTask.query.filter_by(
            source_type='capa', source_id=capa_id, status='pending'
        ).delete(synchronize_session=False)

        # 若來源為客訴，將客訴狀態回退為待處理並清空 related_capa_id
        if ca.source_type == 'complaint' and ca.source_id:
            from ..models import CustomerComplaint
            complaint = CustomerComplaint.query.get(ca.source_id)
            if complaint:
                complaint.status = '待處理'
                complaint.related_capa_id = None

        db.session.delete(ca)
        db.session.commit()
        return True
```

- [ ] **Step 3: 重啟後端並驗證 close 同步**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Start-Process -FilePath "C:\QC_Database\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3

Set-Location C:\QC_Database
.\venv\Scripts\python.exe -c @'
from backend.app import app
from backend.extensions import db
from backend.models import CustomerComplaint, CorrectiveAction
from datetime import date

with app.app_context():
    # 建立 mock 客訴 + CAPA
    c = CustomerComplaint(
        customer='Task6-Close', complaint_date=date.today(),
        product_no='P', description='task6 close test', status='處理中'
    )
    db.session.add(c); db.session.flush()

    ca = CorrectiveAction(
        eight_d_number='TEST-CLOSE-001', source_type='complaint',
        source_id=c.id, status='進行中', d6_verified=True
    )
    db.session.add(ca); db.session.commit()

    from backend.services.capa_service import CAPAService
    CAPAService.close(ca.id, '結案確認')

    db.session.refresh(c)
    print(f'Complaint status after CAPA close: {c.status}')
    assert c.status == '已結案', f'Expected 已結案, got {c.status}'
    # cleanup
    db.session.delete(ca); db.session.delete(c); db.session.commit()
    print('OK')
'@
```
Expected: `Complaint status after CAPA close: 已結案` 與 `OK`

- [ ] **Step 4: 驗證 delete 同步**

```powershell
Set-Location C:\QC_Database
.\venv\Scripts\python.exe -c @'
from backend.app import app
from backend.extensions import db
from backend.models import CustomerComplaint, CorrectiveAction
from datetime import date

with app.app_context():
    c = CustomerComplaint(
        customer='Task6-Del', complaint_date=date.today(),
        product_no='P', description='task6 del test', status='處理中'
    )
    db.session.add(c); db.session.flush()

    ca = CorrectiveAction(
        eight_d_number='TEST-DEL-001', source_type='complaint',
        source_id=c.id, status='進行中'
    )
    db.session.add(ca); db.session.commit()

    c.related_capa_id = ca.id
    db.session.commit()

    from backend.services.capa_service import CAPAService
    CAPAService.delete(ca.id)

    db.session.refresh(c)
    print(f'Complaint after CAPA delete: status={c.status}, related_capa_id={c.related_capa_id}')
    assert c.status == '待處理' and c.related_capa_id is None
    db.session.delete(c); db.session.commit()
    print('OK')
'@
```
Expected: `Complaint after CAPA delete: status=待處理, related_capa_id=None` 與 `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/services/capa_service.py
git commit -m "feat(capa): CAPA 結案/刪除時同步更新來源客訴狀態

- close(): 來源為客訴時，將客訴狀態設為已結案
- delete(): 來源為客訴時，將客訴狀態回退為待處理並清空 related_capa_id

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: 後端 — 客訴開立 CAPA 時改成「處理中」

**Files:**
- Modify: `backend/routes/complaint.py`（`open_capa_from_complaint` 路由）

- [ ] **Step 1: 修改路由**

`backend/routes/complaint.py`，找到 `open_capa_from_complaint` 函式，找到 `c.related_capa_id = capa['id']` 那行，緊接著加：

```python
        # 更新客訴關聯
        from ..models import CustomerComplaint
        c = CustomerComplaint.query.get(complaint_id)
        if c:
            c.related_capa_id = capa['id']
            c.status = '處理中'
            from ..extensions import db
            db.session.commit()
```
（若原本沒有 status 變更，加上去；若已經有，確認狀態是 `'處理中'`）

- [ ] **Step 2: 重啟後端並端對端測試**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3

.\venv\Scripts\python.exe -c @'
from backend.app import app
import json
with app.test_client() as c:
    token = json.loads(c.post('/api/login', json={'username':'admin','password':'admin'}).get_data(as_text=True))['token']
    h = {'Authorization': f'Bearer {token}'}
    r = c.post('/api/complaints', json={
        'customer': 'Task7', 'complaint_date': '2026-05-26',
        'product_no': 'P7', 'description': 't7'
    }, headers=h)
    cid = json.loads(r.get_data(as_text=True))['id']
    print(f'Status before: {json.loads(r.get_data(as_text=True))["status"]}')

    cap = c.post(f'/api/complaints/{cid}/open-capa', headers=h)
    print(f'CAPA created: {cap.status_code}')

    detail = c.get(f'/api/complaints/{cid}', headers=h)
    body = json.loads(detail.get_data(as_text=True))
    print(f'Status after open-capa: {body["status"]}')
    assert body["status"] == '處理中'

    # cleanup
    capa_id = body['related_capa_id']
    c.delete(f'/api/capa/{capa_id}', headers=h) if False else None
    print('OK')
'@
```
Expected: `Status after open-capa: 處理中`

- [ ] **Step 3: 清理測試資料**

```powershell
$env:PGPASSWORD = "swordfish1"
'DELETE FROM "異常矯正單" WHERE "來源類型" = ''complaint'' AND "來源ID" IN (SELECT "識別碼" FROM "客訴紀錄" WHERE "客戶" = ''Task7''); DELETE FROM "客訴紀錄" WHERE "客戶" = ''Task7'';' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```

- [ ] **Step 4: Commit**

```bash
git add backend/routes/complaint.py
git commit -m "feat(complaint): 開立 CAPA 後客訴狀態自動改為處理中

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: 後端 — 移除 CARA 模組

**Files:**
- Delete: `backend/routes/cara.py`
- Delete: `backend/services/cara_service.py`
- Modify: `backend/app.py`（移除 blueprint 註冊）
- Modify: `backend/models.py`（刪除 `CARARecord` 類別）
- Modify: `backend/services/complaint_service.py`（移除 `open_cara`、`_to_dict` 的 `related_cara_id`）
- Modify: `backend/routes/complaint.py`（移除 `open_cara_from_complaint` 路由）
- Modify: `backend/services/attachment_service.py`（VALID_ENTITY_TYPES 移除 `'cara'`）

- [ ] **Step 1: 刪除 CARA service 與 route 檔案**

```powershell
Remove-Item C:\QC_Database\backend\routes\cara.py
Remove-Item C:\QC_Database\backend\services\cara_service.py
```

- [ ] **Step 2: `backend/app.py` 移除 import 與 blueprint 註冊**

刪除這兩行：
```python
from .routes.cara import cara_bp
```
```python
app.register_blueprint(cara_bp)
```

- [ ] **Step 3: `backend/models.py` 刪除 `CARARecord` 類別**

刪除整個 `class CARARecord(db.Model):` 區段（從 `# 1.6 CARARecord` 註解開頭到最後一行 `leader = db.relationship('Inspector', foreign_keys=[d1_leader_id], backref='cara_led')`）。

注意：`CustomerComplaint.related_cara_id` 欄位**先保留**（等 Task 15 destructive migration 一起 drop）。

- [ ] **Step 4: `backend/services/complaint_service.py` 移除 `open_cara`**

找到 `open_cara` static method 整段（從 `# ── 從客訴開立 CARA ──` 註解到 `return cara`），全部刪除。

- [ ] **Step 5: `backend/services/complaint_service.py` 移除 `_to_dict` 的 `related_cara_id`**

找到 `_to_dict` 方法裡這行：

```python
            'related_cara_id':   c.related_cara_id,
```
刪除。

- [ ] **Step 6: `backend/routes/complaint.py` 移除 `open_cara_from_complaint` 路由**

刪除整個 `@complaint_bp.route('/api/complaints/<int:complaint_id>/open-cara', methods=['POST'])` 路由區塊（包含其上方 `# ── 從客訴開立 CARA ──` 註解）。

- [ ] **Step 7: `backend/services/attachment_service.py` 移除 'cara'**

找到 `VALID_ENTITY_TYPES = {'capa', 'cara', 'task', 'complaint'}`，改為：

```python
VALID_ENTITY_TYPES = {'capa', 'task', 'complaint'}
```

- [ ] **Step 8: 重啟後端**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3
```

- [ ] **Step 9: 驗證後端能啟動且沒有 CARA route**

```powershell
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/caras" -Method GET -TimeoutSec 5 -SkipHttpErrorCheck
    Write-Host "Status: $($r.StatusCode)"
} catch { Write-Host "Error: $($_.Exception.Message)" }
```
Expected: `Status: 404`（路由已刪除）

- [ ] **Step 10: 驗證後端登入仍正常**

```powershell
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/login" -Method POST -ContentType "application/json" -Body '{"username":"admin","password":"admin"}' -TimeoutSec 5 -SkipHttpErrorCheck
    Write-Host "Login: $($r.StatusCode)"
} catch { Write-Host "Error: $($_.Exception.Message)" }
```
Expected: `Login: 200`

- [ ] **Step 11: Commit**

```bash
git add -A backend/
git commit -m "refactor(backend): 移除 CARA 模組

- 刪除 backend/routes/cara.py 與 backend/services/cara_service.py
- 從 app.py 移除 cara_bp blueprint 註冊
- 從 models.py 刪除 CARARecord 類別 (CustomerComplaint.related_cara_id 暫留)
- 從 ComplaintService 移除 open_cara() 與 _to_dict() 的 related_cara_id
- 從 routes/complaint.py 移除 open_cara_from_complaint 路由
- attachment_service.VALID_ENTITY_TYPES 移除 'cara'

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 後端 — 移除舊版 CAR 模式

**Files:**
- Modify: `backend/routes/ncmr.py`（刪除 `/api/cara/*` 5 條路由）
- Modify: `backend/services/ncmr_service.py`（刪除 `get_cara_list/create_cara/get_cara_detail/update_cara/delete_cara`）
- Modify: `backend/routes/admin.py`（刪除 `count_pending_cara`、`cara_row` 統計）
- Modify: `backend/utils.py`（刪除 `generate_car_number`）
- Modify: `backend/models.py`（移除 `CorrectiveAction.car_number` 欄位）
- Modify: `backend/tests/test_services/test_ncmr.py`（刪除 `test_get_cara_list_*` 等測試）

- [ ] **Step 1: `backend/routes/ncmr.py` 刪除 5 條 CAR 路由**

刪除 `# ==================================================` `# 【CAR矯正】API` 段落下的所有 5 個路由（從 line ~155 到 line ~225），確認以下都刪掉：
- `/api/cara` GET
- `/api/cara/create` POST
- `/api/cara/detail/<int:id>` GET
- `/api/cara/update` POST
- `/api/cara/delete` POST

- [ ] **Step 2: `backend/services/ncmr_service.py` 刪除 5 個 cara 方法**

刪除：
- `get_cara_list`
- `create_cara`
- `get_cara_detail`
- `update_cara`
- `delete_cara`

注意：`get_cara_detail` 可能被其他方法引用（grep 一下），如果 `get_8d_detail` 或類似方法呼叫 `return NCMRService.get_cara_detail(capa_id)`，這些方法也需要重寫或刪除。

```powershell
Set-Location C:\QC_Database
Select-String -Path "backend\services\ncmr_service.py" -Pattern "get_cara_detail|update_cara|delete_cara"
```
若還有殘留引用，連同呼叫端一起改寫成直接操作 `CorrectiveAction`。

- [ ] **Step 3: `backend/routes/admin.py` 移除 CAR 統計**

刪除：
1. `count_pending_cara()` 內部函式（約 line 35）
2. `cara_row = db.session.query(...)` 整段（約 line 125–138）
3. dashboard 回傳資料裡 `"cara": { ... }` 區段（約 line 189–192）
4. recent activity 裡 `"type": "cara"` 區段（約 line 288–294）

- [ ] **Step 4: `backend/utils.py` 刪除 `generate_car_number`**

找到並刪除 `def generate_car_number()` 整個函式。同時檢查 `_NUMBER_FIELD_WHITELIST` 與 `_NUMBER_PAIR_WHITELIST`，若 `'異常矯正單', 'CAR單號'` 有列入，**保留**（為了測試資料庫 schema 在 Task 16 之前的相容性）。

- [ ] **Step 5: `backend/models.py` 移除 `CorrectiveAction.car_number` 欄位**

找到 `class CorrectiveAction` 裡的：
```python
    car_number = db.Column('CAR單號', db.String, ...)  # 確切寫法請看現場
```
**註解掉**（不是刪除），加註：
```python
    # car_number 欄位已在 Task 16 destructive migration 中刪除
    # car_number = db.Column('CAR單號', db.String)
```

> ⚠️ 之所以註解而非直接刪除：DB 還有這個欄位，先讓 Python 端不再寫入；Task 16 才實際 DROP COLUMN。

- [ ] **Step 6: `backend/tests/test_services/test_ncmr.py` 刪除 cara 測試**

刪除所有 `test_get_cara_list_*` 系列測試函式（grep 一下確認都刪掉）：

```powershell
Set-Location C:\QC_Database
Select-String -Path "backend\tests\test_services\test_ncmr.py" -Pattern "def test_get_cara"
```
Expected: 0 matches after edit.

- [ ] **Step 7: 重啟後端**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3
```

- [ ] **Step 8: 驗證 — `/api/cara` 應該 404；登入仍正常；dashboard 仍能回傳**

```powershell
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/cara" -Method GET -TimeoutSec 5 -SkipHttpErrorCheck
    Write-Host "/api/cara: $($r.StatusCode)"
} catch { Write-Host $_ }

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/login" -Method POST -ContentType "application/json" -Body '{"username":"admin","password":"admin"}' -SkipHttpErrorCheck
    $token = ($r.Content | ConvertFrom-Json).token
    $r2 = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/dashboard/stats" -Headers @{Authorization="Bearer $token"} -SkipHttpErrorCheck
    Write-Host "Dashboard: $($r2.StatusCode)"
} catch { Write-Host $_ }
```
Expected: `/api/cara: 404` 與 `Dashboard: 200`

- [ ] **Step 9: 跑既有測試確認沒有 regression**

```powershell
Set-Location C:\QC_Database
.\venv\Scripts\python.exe -m pytest backend/tests/test_services/test_ncmr.py -v 2>&1 | Select-Object -Last 30
```
Expected: 所有測試 pass。

- [ ] **Step 10: Commit**

```bash
git add -A backend/
git commit -m "refactor(backend): 移除舊版 CAR 模式 — 整合進 CAPA

- routes/ncmr.py 刪除 /api/cara/* 5 條路由
- ncmr_service.py 刪除 get_cara_list/create_cara/get_cara_detail/update_cara/delete_cara
- admin.py 移除 count_pending_cara 與 dashboard 的 cara 統計區段
- utils.py 刪除 generate_car_number
- models.py 註解 CorrectiveAction.car_number (DB 欄位待 Task 16 drop)
- 刪除 test_ncmr.py 中的 test_get_cara_list_* 測試

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: 前端 — 刪除 CARA 模組

**Files:**
- Delete: `src_frontend/src/pages/cara/CARAPage.tsx`
- Delete: `src_frontend/src/components/cara/CARAModal.tsx`
- Delete: `src_frontend/src/hooks/useCARA.ts`
- Modify: `src_frontend/src/App.tsx`（移除 CARA route 與 import）
- Modify: `src_frontend/src/components/Sidebar.tsx`（移除「CAR 要求」menu）
- Modify: `src_frontend/src/types/index.ts`（移除 CARA 相關 type 與 `CustomerComplaint.related_cara_id`）
- Modify: `src_frontend/src/hooks/useComplaint.ts`（移除 `useOpenCaraFromComplaint`）
- Modify: `src_frontend/src/pages/complaint/ComplaintPage.tsx`（移除 CARA 按鈕、`related_cara_id` 引用）

- [ ] **Step 1: 刪除 CARA 三個檔案**

```powershell
Remove-Item C:\QC_Database\src_frontend\src\pages\cara\CARAPage.tsx
Remove-Item C:\QC_Database\src_frontend\src\components\cara\CARAModal.tsx
Remove-Item C:\QC_Database\src_frontend\src\hooks\useCARA.ts
# 移除空目錄
Remove-Item C:\QC_Database\src_frontend\src\pages\cara
Remove-Item C:\QC_Database\src_frontend\src\components\cara
```

- [ ] **Step 2: `src_frontend/src/App.tsx` 移除 CARA**

刪除：
```typescript
import CARAPage from './pages/cara/CARAPage';
```
與：
```tsx
              <Route path="/cara" element={<CARAPage />} />
```

- [ ] **Step 3: `src_frontend/src/components/Sidebar.tsx` 移除「CAR 要求」**

刪除：
```typescript
{ title: 'CAR 要求', path: '/cara', icon: 'fa-bullhorn' },
```

- [ ] **Step 4: `src_frontend/src/types/index.ts` 移除 CARA 與 related_cara_id**

刪除所有 `CARADetail`、`CARAStep` 等 type 定義；找到 `CustomerComplaint` interface，刪除：

```typescript
    related_cara_id?: number | null;
```

- [ ] **Step 5: `src_frontend/src/hooks/useComplaint.ts` 移除 `useOpenCaraFromComplaint`**

刪除整個 `useOpenCaraFromComplaint` hook（從 export 到結尾 `};`）。同時刪除任何 `qc.invalidateQueries({ queryKey: ['caraList'] })` 的呼叫。

- [ ] **Step 6: `src_frontend/src/pages/complaint/ComplaintPage.tsx` 移除 CARA**

刪除：
- `useOpenCaraFromComplaint` 的 import
- `openCaraMutation` 變數宣告
- `handleOpenCara` 函式整段
- 表格欄位中「開立 CARA」按鈕與 `related_cara_id` 顯示（badge）
- 任何 `c.related_cara_id` 的條件判斷
- table head 對應的「CARA」欄位（如果有單獨欄位的話）

> ⚠️ 若不確定要刪哪些 JSX 區塊，停下來問使用者。

- [ ] **Step 7: 驗證前端 build**

```powershell
Set-Location C:\QC_Database\src_frontend
npm run build 2>&1 | Select-Object -Last 20
```
Expected: build 成功，無 TypeScript error。

> 如果 build 失敗，typically 是還有殘留 import 或型別引用。grep 一下：
> ```powershell
> Select-String -Path "src\**\*.tsx", "src\**\*.ts" -Pattern "CARA|caraId|related_cara"
> ```

- [ ] **Step 8: Commit**

```bash
git add -A src_frontend/
git commit -m "refactor(frontend): 刪除 CARA 模組

- 刪除 pages/cara/、components/cara/、hooks/useCARA.ts
- App.tsx 移除 CARA route
- Sidebar 移除「CAR 要求」menu
- types/index.ts 移除 CARA 相關 type 與 CustomerComplaint.related_cara_id
- useComplaint.ts 移除 useOpenCaraFromComplaint
- ComplaintPage.tsx 移除開立 CARA 按鈕與 CARA badge

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: 前端 — 移除舊版 CAR 模式

**Files:**
- Modify: `src_frontend/src/hooks/useNCMR.ts`（移除 `useCARAList`、`useCreateCARA`；`CARListParams` → `CAPAListParams`）
- Modify: `src_frontend/src/hooks/useDashboard.ts`（移除 `cara` 型別欄位）
- Modify: `src_frontend/src/components/dashboard/KPICards.tsx`（移除「CAR 要求」KPI 卡）
- Modify: `src_frontend/src/pages/ncmr/NCMRPage.tsx`（移除 `convertToCAR()` 與按鈕）

- [ ] **Step 1: `src_frontend/src/hooks/useNCMR.ts` 重新命名與刪除**

(a) 把 `interface CARListParams` 重新命名為 `interface CAPAListParams`：

```typescript
export interface CAPAListParams {
    page?: number;
    per_page?: number;
    status?: string;
    date_from?: string;
    date_to?: string;
    vendor?: string;
    material?: string;
    product_info?: string;
}
```

(b) 刪除 `export type CAPAListParams = CARListParams;`（type alias，已重複）

(c) 刪除整個 `export const useCARAList = ...` 區塊

(d) 刪除整個 `export const useCreateCARA = ...` 區塊

(e) 確保 `useCAPAList` 簽名是 `(params: CAPAListParams = {})`

- [ ] **Step 2: `src_frontend/src/hooks/useDashboard.ts` 移除 cara**

刪除：
```typescript
    cara: { current: number; previous: number; pending: number; trend: string; change_pct: number };
```

並把 recent activity 的 type union：
```typescript
    type: 'ncmr' | 'capa' | 'rework' | 'cara';
```
改為：
```typescript
    type: 'ncmr' | 'capa' | 'rework';
```

- [ ] **Step 3: `src_frontend/src/components/dashboard/KPICards.tsx` 移除 CAR 卡**

找到陣列中的 CAR 卡片物件（`label: 'CAR 要求', key: 'cara', ...`），整個物件移除（包括逗號）。

- [ ] **Step 4: `src_frontend/src/pages/ncmr/NCMRPage.tsx` 移除 CAR**

(a) 從 import 移除 `useCreateCARA`：
```typescript
import { useNCMRList, useDeleteNCMR, useCreateCAPA, useNCMRDetail } from '../../hooks/useNCMR';
```

(b) 刪除 `const createCARAMutation = useCreateCARA();`

(c) 刪除 `const convertToCAR = (id: number) => { ... };` 整個函式

(d) 在 JSX 中找到「轉為 CAR」按鈕（呼叫 `convertToCAR`），整個 `<Button>` 刪除

- [ ] **Step 5: 驗證 build**

```powershell
Set-Location C:\QC_Database\src_frontend
npm run build 2>&1 | Select-Object -Last 20
```
Expected: build 成功。

- [ ] **Step 6: 全文搜尋確認無殘留**

```powershell
Set-Location C:\QC_Database\src_frontend
Select-String -Path "src\**\*.ts", "src\**\*.tsx" -Pattern "useCreateCARA|useCARAList|convertToCAR|car_number|CAR單號|CARListParams"
```
Expected: 0 matches.

- [ ] **Step 7: Commit**

```bash
git add -A src_frontend/
git commit -m "refactor(frontend): 移除舊版 CAR 模式

- useNCMR.ts 刪除 useCARAList、useCreateCARA，CARListParams 重命名為 CAPAListParams
- useDashboard.ts 移除 cara 型別欄位
- KPICards.tsx 移除「CAR 要求」KPI 卡
- NCMRPage.tsx 移除 convertToCAR 與「轉為 CAR」按鈕

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: 前端 — ComplaintPage 的 CAPA / 重工 badge 改成可點擊連結

**Files:**
- Modify: `src_frontend/src/pages/complaint/ComplaintPage.tsx`

- [ ] **Step 1: 找到 CAPA badge**

`ComplaintPage.tsx` 找到顯示 `c.related_capa_id` 的 `<Badge bg="success">已開立</Badge>` 區塊，改為：

```tsx
{c.related_capa_id ? (
    <Badge
        bg="success"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate(`/capa?editId=${c.related_capa_id}`)}
        title="點擊查看 CAPA"
    >
        已開立
    </Badge>
) : (
    <Button
        variant="outline-warning"
        size="sm"
        style={{ fontSize: '0.7rem' }}
        onClick={() => handleOpenCapa(c)}
        disabled={openCapaMutation.isPending}
    >
        開立 CAPA
    </Button>
)}
```

- [ ] **Step 2: 加上重工 badge / 按鈕**

在 CAPA 欄位旁邊（或同欄）加上重工欄位：

```tsx
<td>
    {c.related_rework_id ? (
        <Badge
            bg="info"
            text="dark"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/rework?id=${c.related_rework_id}`)}
            title="點擊查看重工單"
        >
            已開立
        </Badge>
    ) : (
        <Button
            variant="outline-secondary"
            size="sm"
            style={{ fontSize: '0.7rem' }}
            onClick={() => handleOpenRework(c)}
            disabled={openReworkMutation.isPending}
        >
            開立重工
        </Button>
    )}
</td>
```

並在 table head 加 `<th>重工</th>`（如果原本沒有），同時 `colSpan` 對應更新。

- [ ] **Step 3: 加上 `handleOpenRework` 函式**

在元件函式內，與 `handleOpenCapa` 並列加：

```tsx
const handleOpenRework = (c: CustomerComplaint) => {
    if (c.related_rework_id) {
        navigate(`/rework?id=${c.related_rework_id}`);
        return;
    }
    if (window.confirm(`確定從客訴「${c.complaint_no}」開立重工申請單？`)) {
        openReworkMutation.mutate(c.id);
    }
};
```

- [ ] **Step 4: 加上 `useOpenReworkFromComplaint` hook（若尚未存在）**

檢查 `useComplaint.ts` 是否已有：

```powershell
Set-Location C:\QC_Database\src_frontend
Select-String -Path "src\hooks\useComplaint.ts" -Pattern "useOpenReworkFromComplaint"
```
若不存在，在 `useComplaint.ts` 加：

```typescript
// ── 從客訴開立重工 ────────────────────────────────────────────
export const useOpenReworkFromComplaint = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (complaintId: number) => {
            const res = await api.post(`/complaints/${complaintId}/open-rework`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('重工申請單已開立');
            qc.invalidateQueries({ queryKey: ['complaintList'] });
            qc.invalidateQueries({ queryKey: ['reworkApplications'] });
        },
        onError: (err: Error) => {
            toast.error(`開立失敗：${err.message}`);
        },
    });
};
```

- [ ] **Step 5: 在 ComplaintPage 引用該 hook**

`ComplaintPage.tsx`：
```typescript
import {
    useComplaintList,
    useDeleteComplaint,
    useOpenCapaFromComplaint,
    useOpenReworkFromComplaint,
    COMPLAINT_TYPE_LABELS,
    COMPLAINT_STATUS_VARIANT,
} from '../../hooks/useComplaint';
```

並在 component 內：
```typescript
const openReworkMutation = useOpenReworkFromComplaint();
```

- [ ] **Step 6: 驗證 build**

```powershell
Set-Location C:\QC_Database\src_frontend
npm run build 2>&1 | Select-Object -Last 20
```
Expected: build 成功。

- [ ] **Step 7: Commit**

```bash
git add -A src_frontend/
git commit -m "feat(complaint): 客訴頁面 CAPA / 重工 badge 改為可點擊連結

- 已開立 CAPA badge 點擊跳轉到 /capa?editId=<id>
- 新增「開立重工」按鈕與已開立重工 badge
- 已開立重工 badge 點擊跳轉到 /rework?id=<id>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 13: 前端 — 新增 ReworkFollowUpModal 元件

**Files:**
- Create: `src_frontend/src/components/rework/ReworkFollowUpModal.tsx`

- [ ] **Step 1: 撰寫元件**

`src_frontend/src/components/rework/ReworkFollowUpModal.tsx`：

```tsx
import { Modal, Button } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';

interface ReworkFollowUpModalProps {
    show: boolean;
    onHide: () => void;
    ncmrId: number;
    ncmrNumber: string;
}

const ReworkFollowUpModal = ({ show, onHide, ncmrId, ncmrNumber }: ReworkFollowUpModalProps) => {
    const navigate = useNavigate();

    const handleOpenCapa = () => {
        onHide();
        navigate(`/ncmr?openCapaFor=${ncmrId}`);
    };

    return (
        <Modal show={show} onHide={onHide} centered>
            <Modal.Header closeButton>
                <Modal.Title>重工已完成</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <p>
                    NCMR 單號 <strong>{ncmrNumber}</strong> 的重工已結案。
                </p>
                <p className="text-muted">
                    若根因為製程或系統性問題，建議開立 CAPA 進行根本原因分析與系統性矯正。
                </p>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>
                    暫不處理
                </Button>
                <Button variant="primary" onClick={handleOpenCapa}>
                    開立 CAPA
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ReworkFollowUpModal;
```

- [ ] **Step 2: 驗證 build**

```powershell
Set-Location C:\QC_Database\src_frontend
npm run build 2>&1 | Select-Object -Last 20
```
Expected: build 成功。

- [ ] **Step 3: Commit**

```bash
git add src_frontend/src/components/rework/ReworkFollowUpModal.tsx
git commit -m "feat(rework): 新增重工完成提示開立 CAPA 的 Modal 元件

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 14: 前端 — ReworkPage.handleCloseRework 整合 FollowUp Modal

**Files:**
- Modify: `src_frontend/src/pages/rework/ReworkPage.tsx`

- [ ] **Step 1: 加入 Modal state**

在 `ReworkPage` 元件內，與其他 `useState` 並列：

```typescript
const [followUpModal, setFollowUpModal] = useState<{
    show: boolean;
    ncmrId: number;
    ncmrNumber: string;
} | null>(null);
```

- [ ] **Step 2: 修改 `handleCloseRework`**

找到現有的 `handleCloseRework` 函式，改為：

```typescript
const handleCloseRework = async (reworkId: number) => {
    if (!confirm('確定要結案此重工申請嗎？')) return;
    try {
        await api.post('/rework/close', { rework_id: reworkId });
        alert('結案成功');

        // 結案後，若該重工關聯 NCMR 且 NCMR 尚未開 CAPA，提示開立
        const rework = reworkData.find(r => r.識別碼 === reworkId);
        const ncmrId = rework?.NCMR_ID;
        if (ncmrId) {
            try {
                const ncmrRes = await api.get(`/ncmr/detail/${ncmrId}`);
                const ncmr = ncmrRes.data;
                if (!ncmr.related_capa_id) {
                    setFollowUpModal({
                        show: true,
                        ncmrId,
                        ncmrNumber: ncmr.NCMR單號 || ncmr.ncmr_number || String(ncmrId),
                    });
                }
            } catch {
                // 取不到 NCMR 詳細也不影響結案流程
            }
        }

        reloadDetailData();
    } catch (error: unknown) {
        const err = error as { response?: { data?: { error?: string } } };
        alert(err.response?.data?.error || '結案失敗');
    }
};
```

> ⚠️ 上述 `reworkData` 與 `reloadDetailData` 是現有變數名稱，若實際命名不同，請對照修正。如果取不到 rework 列表中的 NCMR_ID，也可改成直接呼叫 `/rework/application/<reworkId>` 取詳細。**遇到不確定就停下來問。**

- [ ] **Step 3: 引用 Modal 元件**

`ReworkPage.tsx` 上方加 import：

```typescript
import ReworkFollowUpModal from '../../components/rework/ReworkFollowUpModal';
```

並在 JSX 最外層 `<>` 內加 Modal 顯示：

```tsx
{followUpModal && (
    <ReworkFollowUpModal
        show={followUpModal.show}
        onHide={() => setFollowUpModal(null)}
        ncmrId={followUpModal.ncmrId}
        ncmrNumber={followUpModal.ncmrNumber}
    />
)}
```

- [ ] **Step 4: 驗證 build**

```powershell
Set-Location C:\QC_Database\src_frontend
npm run build 2>&1 | Select-Object -Last 20
```
Expected: build 成功。

- [ ] **Step 5: 手動驗證**

啟動前端 `npm run dev`，登入後到「重工管理」頁，找一張有 NCMR 關聯且 NCMR 尚未開 CAPA 的重工單，按結案，預期看到 Modal 跳出。按「開立 CAPA」應跳到 NCMR 頁面。

> ⚠️ 若沒有合適的測試資料，跳過此步驟並在最後 Task 17 一起驗證。

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/pages/rework/ReworkPage.tsx
git commit -m "feat(rework): 重工結案後若 NCMR 尚未開 CAPA 則提示開立

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 15: DB Migration — DROP CARA 模組（destructive）

**Files:**
- Create: `migration/drop_cara_module.sql`

- [ ] **Step 1: 確認 baseline — CARA 表資料已成功遷移**

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT (SELECT COUNT(*) FROM "矯正措施要求") AS cara_remaining, (SELECT COUNT(*) FROM "異常矯正單" WHERE "8D單號" LIKE ''CARA-%'') AS migrated;' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `cara_remaining = 8`、`migrated = 8`。**如果不一致，STOP 並 rollback。**

- [ ] **Step 2: 撰寫 SQL**

`migration/drop_cara_module.sql`：

```sql
-- 警告：destructive，執行前必須先確認 migrate_cara_to_capa.sql 已成功
BEGIN;

-- 客訴紀錄移除 related_cara_id 欄位
ALTER TABLE "客訴紀錄" DROP COLUMN IF EXISTS "關聯CARA_ID";

-- DROP CARA 表
DROP TABLE IF EXISTS "矯正措施要求";

COMMIT;
```

- [ ] **Step 3: 執行**

```powershell
$env:PGPASSWORD = "swordfish1"
Get-Content "C:\QC_Database\migration\drop_cara_module.sql" -Raw | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `BEGIN`、`ALTER TABLE`、`DROP TABLE`、`COMMIT`

- [ ] **Step 4: 驗證表已不存在**

```powershell
$env:PGPASSWORD = "swordfish1"
'\dt "矯正措施要求"' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `Did not find any relation named "矯正措施要求".`

- [ ] **Step 5: 驗證 `客訴紀錄.關聯CARA_ID` 已不存在**

```powershell
$env:PGPASSWORD = "swordfish1"
'\d "客訴紀錄"' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database | Select-String "關聯CARA_ID"
```
Expected: 0 matches.

- [ ] **Step 6: 重啟後端確認沒問題**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/login" -Method POST -ContentType "application/json" -Body '{"username":"admin","password":"admin"}' -SkipHttpErrorCheck
    Write-Host "Login: $($r.StatusCode)"
} catch { Write-Host $_ }
```
Expected: `Login: 200`

- [ ] **Step 7: Commit**

```bash
git add migration/drop_cara_module.sql
git commit -m "feat(db): DROP 矯正措施要求 表與 客訴紀錄.關聯CARA_ID 欄位

destructive migration，執行前已確認 CARA 資料完成遷移到 CAPA。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 16: DB Migration — DROP `異常矯正單.CAR單號` 欄位（destructive）

**Files:**
- Create: `migration/drop_car_number_column.sql`
- Modify: `backend/models.py`（移除註解的 `car_number` 行）

- [ ] **Step 1: 確認沒有任何紀錄需要 CAR單號**

```powershell
$env:PGPASSWORD = "swordfish1"
'SELECT COUNT(*) AS still_orphan FROM "異常矯正單" WHERE "CAR單號" IS NOT NULL AND "8D單號" IS NULL;' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `still_orphan = 0`。**若不為 0，STOP 並 rollback。**

- [ ] **Step 2: 撰寫 SQL**

`migration/drop_car_number_column.sql`：

```sql
-- 警告：destructive，執行前必須確認所有 CAR 紀錄已透過 migrate_car_to_capa.sql 搬到 8D單號
ALTER TABLE "異常矯正單" DROP COLUMN IF EXISTS "CAR單號";
```

- [ ] **Step 3: 執行**

```powershell
$env:PGPASSWORD = "swordfish1"
Get-Content "C:\QC_Database\migration\drop_car_number_column.sql" -Raw | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected: `ALTER TABLE`

- [ ] **Step 4: 驗證欄位已不存在**

```powershell
$env:PGPASSWORD = "swordfish1"
'\d "異常矯正單"' | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database | Select-String "CAR單號"
```
Expected: 0 matches.

- [ ] **Step 5: 從 `models.py` 移除註解的 `car_number` 行**

找到 `backend/models.py` 中 Task 9 留下的：
```python
    # car_number 欄位已在 Task 16 destructive migration 中刪除
    # car_number = db.Column('CAR單號', db.String)
```
**完全刪除**這兩行。

- [ ] **Step 6: 重啟後端確認**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/login" -Method POST -ContentType "application/json" -Body '{"username":"admin","password":"admin"}' -SkipHttpErrorCheck
    Write-Host "Login: $($r.StatusCode)"
} catch { Write-Host $_ }
```
Expected: `Login: 200`

- [ ] **Step 7: 跑既有測試**

```powershell
Set-Location C:\QC_Database
.\venv\Scripts\python.exe -m pytest backend/tests -v 2>&1 | Select-Object -Last 30
```
Expected: 所有測試 pass。

- [ ] **Step 8: Commit**

```bash
git add migration/drop_car_number_column.sql backend/models.py
git commit -m "feat(db): DROP 異常矯正單.CAR單號 欄位並清理 models.py 註解

destructive migration，CAR 模式整合完成。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 17: 端對端驗證

**Files:** None（手動操作）

- [ ] **Step 1: 後端 boot smoke test**

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Start-Sleep -Seconds 1
Set-Location C:\QC_Database
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m", "waitress", "--listen=*:5001", "backend.app:app" -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/login" -Method POST -ContentType "application/json" -Body '{"username":"admin","password":"admin"}' -SkipHttpErrorCheck
    Write-Host "Login: $($r.StatusCode)"
    $token = ($r.Content | ConvertFrom-Json).token
    foreach ($ep in @('/api/complaints', '/api/dashboard/stats', '/api/rework/applications', '/api/ncmr/list', '/api/capa')) {
        try {
            $r2 = Invoke-WebRequest -Uri "http://127.0.0.1:5001$ep" -Headers @{Authorization="Bearer $token"} -SkipHttpErrorCheck
            Write-Host "$ep -> $($r2.StatusCode)"
        } catch { Write-Host "$ep -> ERROR: $_" }
    }
} catch { Write-Host $_ }
```
Expected: 每個 endpoint 都回 200。

- [ ] **Step 2: 前端 build smoke test**

```powershell
Set-Location C:\QC_Database\src_frontend
npm run build 2>&1 | Select-Object -Last 10
```
Expected: build 成功。

- [ ] **Step 3: 確認 CAR 與 CARA 都已完全清除**

```powershell
Set-Location C:\QC_Database
Select-String -Path "src_frontend\src\**\*.ts", "src_frontend\src\**\*.tsx" -Pattern "CARA|useCreateCARA|convertToCAR|car_number|CAR單號|related_cara_id" 2>&1 | Out-String
Select-String -Path "backend\**\*.py" -Pattern "CARARecord|generate_car_number|/api/cara\b" -CaseSensitive:$false 2>&1 | Out-String
```
Expected: 0 matches。

- [ ] **Step 4: 端對端：客訴 → 開 CAPA → 結案 → 客訴自動變已結案**

啟動前端：
```powershell
Set-Location C:\QC_Database\src_frontend
npm run dev
```

手動操作（瀏覽器或 Claude Preview）：
1. 登入 → 客訴管理 → 新增一筆測試客訴
2. 點「開立 CAPA」→ 確認 confirm dialog → 確認成功
3. 確認該客訴狀態變為「處理中」
4. 進到 CAPA 頁面 → 找到剛建立的 CAPA → 填 D6 verified → 結案
5. 回客訴頁面 → 確認狀態為「已結案」

- [ ] **Step 5: 端對端：客訴 → 開重工 → 確認雙向追溯**

1. 客訴管理 → 新增測試客訴 B
2. 點「開立重工」→ 確認
3. 客訴頁面顯示「已開立」badge（重工欄）→ 點擊跳到重工頁面
4. 重工頁面該筆顯示「客訴單號：CC-XXX」

- [ ] **Step 6: 端對端：NCMR → 結案重工 → FollowUp Modal**

1. 找一筆有 NCMR 關聯且 NCMR 尚未開 CAPA 的重工單
2. 點結案 → 確認 alert → 預期 Modal 跳出
3. 點「開立 CAPA」→ 應跳轉到 NCMR 頁面

- [ ] **Step 7: 端對端：UI 上完全看不到 CARA 與 CAR**

- Sidebar 沒有「CAR 要求」
- Dashboard 沒有「CAR 要求」卡片
- NCMR 頁面操作欄位沒有「轉為 CAR」按鈕

- [ ] **Step 8: 端對端：確認資料庫狀態**

```powershell
$env:PGPASSWORD = "swordfish1"
@'
\d "矯正措施要求"
\d "異常矯正單"
\d "客訴紀錄"
\d "重工申請單"
'@ | & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d qa_database
```
Expected:
- `矯正措施要求` 表不存在
- `異常矯正單` 沒有 `CAR單號` 欄位
- `客訴紀錄` 沒有 `關聯CARA_ID` 欄位
- `重工申請單` 有 `客訴_ID` 欄位

- [ ] **Step 9: 撰寫驗證報告**

`migration/post_migration_report_2026-05-26.md`：

```markdown
# 流程改良工程完成報告（2026-05-26）

## DB 狀態
- 矯正措施要求表：已 DROP
- 異常矯正單.CAR單號：已 DROP
- 客訴紀錄.關聯CARA_ID：已 DROP
- 重工申請單.客訴_ID：已新增

## 資料完整性
- 8 筆 CARA → 異常矯正單（8D單號以 CARA- 前綴）
- 8 筆 CAR → 異常矯正單（8D單號以 CAR- 前綴）
- 1 筆原有 8D：保留
- 異常矯正單目前總筆數：（執行時實際數）

## 功能驗證
- [x] 客訴開立 CAPA → 狀態自動進「處理中」
- [x] CAPA 結案 → 客訴自動進「已結案」
- [x] CAPA 刪除 → 客訴回退「待處理」
- [x] 客訴開立重工 → 重工有 complaint_id，客訴有 related_rework_id
- [x] 重工結案 → 若 NCMR 未開 CAPA 顯示提示 Modal
- [x] Sidebar / Dashboard / NCMRPage 完全看不到 CARA 與 CAR
```

- [ ] **Step 10: Commit**

```bash
git add migration/post_migration_report_2026-05-26.md
git commit -m "docs: 流程改良工程完成驗證報告

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

- [ ] **Step 11: 完成宣告**

工程完成。提醒使用者：
1. 備份檔 `C:\QC_Database\backups\qa_database_2026-05-26.dump` 保留至少 30 天
2. 若需 rollback，使用 `pg_restore` 從備份還原

---

## 自我審查

**1. Spec coverage:** 對照 spec 的六大變更：
- ✅ 變更 1（CARA 資料遷移）→ Task 3
- ✅ 變更 2（CARA 模組移除）→ Task 8 + Task 10 + Task 15
- ✅ 變更 3（客訴↔CAPA 狀態同步）→ Task 6 + Task 7
- ✅ 變更 4（重工追溯 complaint_id）→ Task 2 + Task 5 + Task 12（badge 連結）
- ✅ 變更 5（重工完成提示 CAPA）→ Task 13 + Task 14
- ✅ 變更 6（舊版 CAR 整合）→ Task 4 + Task 9 + Task 11 + Task 16

**2. Placeholder scan:** 無 TBD / TODO / 「適當處理錯誤」等模糊字眼。Task 5 Step 3 有「⚠️ 若結構與預期不同，停下來」這是明確的安全閥，不是 placeholder。

**3. Type consistency:**
- `ReworkRequest.complaint_id` 欄位名稱在 Task 2、5、12 一致
- `CustomerComplaint.related_cara_id` 在 Task 8 保留欄位，Task 15 才刪欄位，一致
- 8D 單號前綴 `'CARA-'`、`'CAR-'` 在 Task 3、4 一致

無問題。
