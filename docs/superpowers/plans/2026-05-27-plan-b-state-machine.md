# Plan B — 狀態機 + 軟刪除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 NCMR→CAPA→重工跨模組狀態轉移驗證與自動同步，並為主要資料表加入軟刪除機制。

**Architecture:** `SoftDeleteMixin` 作為 SQLAlchemy mixin 套用至四個主表；狀態驗證函數集中於 `utils.py`；跨模組同步邏輯置於各自的 service 層，路由不處理業務邏輯。

**Tech Stack:** Flask 3.1、SQLAlchemy、Flask-Migrate、PostgreSQL 16

**執行前提：** Plan A 已完成（utils.py 已有 `api_error` helper）

---

### Task 1：SoftDeleteMixin + 遷移

**Files:**
- Modify: `backend/models.py`
- Run: `flask db migrate` + `flask db upgrade`

- [ ] **Step 1：在 models.py 頂端新增 Mixin**

在 `from datetime import ...` 那行之後、`JsonType` 定義之前插入：

```python
class SoftDeleteMixin:
    """軟刪除 Mixin：加入 deleted_at 欄位，刪除時設時間戳而非真正 DELETE"""
    deleted_at = db.Column('刪除時間', db.DateTime, nullable=True, index=True)

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()

    @classmethod
    def active_query(cls):
        return cls.query.filter(cls.deleted_at.is_(None))
```

- [ ] **Step 2：套用 Mixin 至四個主表**

分別修改以下四個類別的繼承，加入 `SoftDeleteMixin`：

```python
class NCMR(SoftDeleteMixin, db.Model):
    ...

class CorrectiveAction(SoftDeleteMixin, db.Model):
    ...

class ReworkRequest(SoftDeleteMixin, db.Model):
    ...

class CustomerComplaint(SoftDeleteMixin, db.Model):
    ...
```

- [ ] **Step 3：產生並套用遷移**

```powershell
cd C:\QC_Database\backend
$env:FLASK_APP = "app.py"
flask db migrate -m "新增軟刪除欄位"
flask db upgrade
```

預期輸出：`Running upgrade ... done`

- [ ] **Step 4：Commit**

```powershell
git add backend/models.py backend/migrations/
git commit -m "feat(models): 新增 SoftDeleteMixin，NCMR/CAPA/重工/客訴支援軟刪除"
```

---

### Task 2：狀態轉移驗證函數

**Files:**
- Modify: `backend/utils.py`
- Test: `backend/tests/test_state_machine.py`（新建）

- [ ] **Step 1：撰寫測試**

建立 `backend/tests/test_state_machine.py`：

```python
import pytest
from backend.utils import validate_status_transition

def test_ncmr_valid_transition():
    # 不應拋錯
    validate_status_transition('NCMR', '新建', '處理中')
    validate_status_transition('NCMR', '處理中', '已驗證')
    validate_status_transition('NCMR', '已驗證', '已結案')
    validate_status_transition('NCMR', '新建', '已結案')

def test_ncmr_invalid_transition():
    with pytest.raises(ValueError, match='非法狀態轉移'):
        validate_status_transition('NCMR', '已結案', '新建')
    with pytest.raises(ValueError, match='非法狀態轉移'):
        validate_status_transition('NCMR', '已驗證', '新建')

def test_capa_valid_transition():
    validate_status_transition('CAPA', '進行中', '已結案')

def test_capa_invalid_transition():
    with pytest.raises(ValueError):
        validate_status_transition('CAPA', '已結案', '進行中')

def test_rework_valid_transitions():
    validate_status_transition('重工', '申請中', '執行中')
    validate_status_transition('重工', '執行中', '已完成')
    validate_status_transition('重工', '已完成', '已結案')
    validate_status_transition('重工', '申請中', '撤銷')

def test_rework_invalid_transition():
    with pytest.raises(ValueError):
        validate_status_transition('重工', '已結案', '申請中')
```

- [ ] **Step 2：確認測試失敗**

```powershell
cd C:\QC_Database
python -m pytest backend/tests/test_state_machine.py -v
```

預期：`ImportError: cannot import name 'validate_status_transition'`

- [ ] **Step 3：在 utils.py 新增函數**

在 `api_error` 函數之後插入：

```python
# ==================================================
# 狀態機驗證
# ==================================================
_STATUS_TRANSITIONS: dict = {
    'NCMR': {
        '新建':   {'處理中', '已驗證', '已結案'},
        '處理中': {'已驗證', '已結案'},
        '已驗證': {'已結案'},
        '已結案': set(),
    },
    'CAPA': {
        '進行中': {'已結案'},
        '已結案': set(),
    },
    '重工': {
        '申請中': {'執行中', '撤銷'},
        '執行中': {'已完成'},
        '已完成': {'已結案'},
        '已結案': set(),
        '撤銷':   set(),
    },
}

def validate_status_transition(model: str, current: str, new: str) -> None:
    """驗證狀態轉移合法性，不合法拋出 ValueError"""
    allowed = _STATUS_TRANSITIONS.get(model, {}).get(current, set())
    if new not in allowed:
        raise ValueError(f'非法狀態轉移：{model} {current!r} → {new!r}')
```

- [ ] **Step 4：確認測試通過**

```powershell
python -m pytest backend/tests/test_state_machine.py -v
```

預期：全部 PASSED

- [ ] **Step 5：Commit**

```powershell
git add backend/utils.py backend/tests/test_state_machine.py
git commit -m "feat(utils): 新增狀態機轉移驗證 validate_status_transition"
```

---

### Task 3：NCMR service 整合狀態驗證 + 軟刪除

**Files:**
- Modify: `backend/services/ncmr_service.py`

- [ ] **Step 1：找到 update 方法，加入狀態驗證**

在 `ncmr_service.py` 的 `update` 方法中，取得新 status 值之後立即加入驗證：

```python
from ..utils import validate_status_transition

# 在取得 new_status 之後：
new_status = data.get('status')
if new_status and new_status != ncmr.status:
    validate_status_transition('NCMR', ncmr.status, new_status)
```

- [ ] **Step 2：找到 delete 方法，改為軟刪除**

將原本的：

```python
db.session.delete(ncmr)
db.session.commit()
```

替換為：

```python
ncmr.soft_delete()
db.session.commit()
```

- [ ] **Step 3：所有列表查詢改用 active_query()**

將所有 `NCMR.query` 或 `NCMR.query.filter(...)` 的起點改為 `NCMR.active_query()`：

```python
# 修改前
items = NCMR.query.filter(...).all()

# 修改後
items = NCMR.active_query().filter(...).all()
```

- [ ] **Step 4：加入結案前置檢查**

在 NCMR update 方法中，若 `new_status == '已結案'`，加入前置檢查：

```python
if new_status == '已結案':
    # 若有關聯 CAPA，需確認 CAPA 已結案
    if ncmr.related_capa_id:
        from ..models import CorrectiveAction
        capa = CorrectiveAction.query.get(ncmr.related_capa_id)
        if capa and capa.status != '已結案':
            raise ValueError('CAPA 尚未結案，無法將 NCMR 結案')
    # 若有關聯重工，需確認重工已完成
    open_reworks = [r for r in ncmr.rework_requests
                    if r.deleted_at is None and r.status not in ('已結案', '撤銷')]
    if open_reworks:
        raise ValueError('尚有未結案的重工申請單，無法將 NCMR 結案')
```

- [ ] **Step 5：Commit**

```powershell
git add backend/services/ncmr_service.py
git commit -m "feat(ncmr): 整合狀態機驗證、結案前置檢查、軟刪除"
```

---

### Task 4：CAPA service 整合 + 跨模組同步

**Files:**
- Modify: `backend/services/capa_service.py`

- [ ] **Step 1：update 加入狀態驗證**

在 capa_service.py 的 update 方法中：

```python
from ..utils import validate_status_transition

new_status = data.get('status')
if new_status and new_status != ca.status:
    validate_status_transition('CAPA', ca.status, new_status)
```

- [ ] **Step 2：CAPA 結案時自動更新來源 NCMR 狀態**

在 CAPA 結案（status → '已結案'）的邏輯之後加入：

```python
# CAPA 結案時，若來源為 NCMR，自動更新 NCMR 狀態為「已驗證」
if new_status == '已結案' and ca.source_type == 'ncmr' and ca.source_id:
    from ..models import NCMR
    ncmr = NCMR.query.get(ca.source_id)
    if ncmr and ncmr.status == '處理中':
        ncmr.status = '已驗證'
```

- [ ] **Step 3：delete 改軟刪除，query 改 active_query**

```python
# delete
ca.soft_delete()
db.session.commit()

# 所有列表查詢
CorrectiveAction.active_query().filter(...)
```

- [ ] **Step 4：Commit**

```powershell
git add backend/services/capa_service.py
git commit -m "feat(capa): 整合狀態機驗證、結案自動同步 NCMR、軟刪除"
```

---

### Task 5：重工 service 整合 + 跨模組同步

**Files:**
- Modify: `backend/services/rework_service.py`

- [ ] **Step 1：update 加入狀態驗證**

```python
from ..utils import validate_status_transition

new_status = data.get('status')
if new_status and new_status != req.status:
    validate_status_transition('重工', req.status, new_status)
```

- [ ] **Step 2：重工完成時自動同步 NCMR（無關聯 CAPA 時）**

```python
# 重工狀態變為「已完成」時
if new_status == '已完成' and req.ncmr_id:
    from ..models import NCMR
    ncmr = NCMR.query.get(req.ncmr_id)
    if ncmr and ncmr.status == '處理中' and not ncmr.related_capa_id:
        ncmr.status = '已驗證'
```

- [ ] **Step 3：delete 改軟刪除，query 改 active_query**

```python
req.soft_delete()
db.session.commit()

ReworkRequest.active_query().filter(...)
```

- [ ] **Step 4：Commit**

```powershell
git add backend/services/rework_service.py
git commit -m "feat(rework): 整合狀態機驗證、完成自動同步 NCMR、軟刪除"
```

---

### Task 6：客訴 service 軟刪除

**Files:**
- Modify: `backend/services/complaint_service.py`

- [ ] **Step 1：delete 方法改軟刪除**

```python
def delete(complaint_id: int) -> bool:
    c = CustomerComplaint.query.get(complaint_id)
    if not c:
        raise ValueError('客訴不存在')
    c.soft_delete()
    db.session.commit()
    return True
```

- [ ] **Step 2：所有列表查詢改 active_query()**

```python
q = CustomerComplaint.active_query()
```

- [ ] **Step 3：Commit**

```powershell
git add backend/services/complaint_service.py
git commit -m "feat(complaint): 客訴改用軟刪除"
```

---

### Task 7：整合測試

**Files:**
- Test: `backend/tests/test_services/test_state_machine_integration.py`（新建）

- [ ] **Step 1：撰寫整合測試**

建立 `backend/tests/test_services/test_state_machine_integration.py`：

```python
import pytest
from datetime import date
from backend.extensions import db as _db
from backend.models import NCMR, CorrectiveAction

@pytest.fixture
def ncmr(app):
    with app.app_context():
        n = NCMR(
            ncmr_number='NCMR-TEST-001',
            date=date.today(),
            status='新建',
            description='測試用 NCMR',
        )
        _db.session.add(n)
        _db.session.commit()
        yield n
        _db.session.rollback()

def test_ncmr_soft_delete(app, ncmr):
    with app.app_context():
        ncmr_id = ncmr.id
        ncmr.soft_delete()
        _db.session.commit()
        # active_query 應查不到
        result = NCMR.active_query().filter_by(id=ncmr_id).first()
        assert result is None
        # 直接 query 還能找到
        result_raw = NCMR.query.filter_by(id=ncmr_id).first()
        assert result_raw is not None
        assert result_raw.deleted_at is not None

def test_ncmr_invalid_transition_raises(app, ncmr):
    with app.app_context():
        from backend.services.ncmr_service import NCMRService
        with pytest.raises(ValueError, match='非法狀態轉移'):
            NCMRService.update(ncmr.id, {'status': '已驗證'})  # 新建 → 已驗證 非法
```

- [ ] **Step 2：執行測試**

```powershell
python -m pytest backend/tests/test_services/test_state_machine_integration.py -v
```

預期：全部 PASSED

- [ ] **Step 3：Commit**

```powershell
git add backend/tests/test_services/test_state_machine_integration.py
git commit -m "test(state-machine): 新增軟刪除與狀態機整合測試"
```

---

### Task 8：推送

- [ ] **Push to GitHub**

```powershell
cd C:\QC_Database
git push origin master
```
