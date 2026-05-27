# Plan A — Quick Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 DB 複合索引、統一 API 回傳格式 helper、修正 N+1 查詢。

**Architecture:** 純後端改動。索引透過 `__table_args__` 加入 models.py，API helper 加入 utils.py，N+1 透過 SQLAlchemy `joinedload` 修正。前端無需改動。

**Tech Stack:** Flask 3.1、SQLAlchemy、Flask-Migrate、PostgreSQL 16

---

### Task 1：新增 DB 複合索引

**Files:**
- Modify: `backend/models.py`（NCMR、CorrectiveAction、ReworkRequest、CustomerComplaint）
- Run: `flask db migrate` + `flask db upgrade`

- [ ] **Step 1：在 NCMR 新增 `__table_args__`**

開啟 `backend/models.py`，在 `NCMR` 類別的 `create_date` 欄位之後、`inspector` relationship 之前插入：

```python
    __table_args__ = (
        db.Index('idx_ncmr_status_date', '狀態', '發現日期'),
    )
```

- [ ] **Step 2：在 CorrectiveAction 新增索引**

在 `CorrectiveAction` 類別的 `created_at` 欄位之後插入：

```python
    __table_args__ = (
        db.Index('idx_capa_source', '來源類型', '來源ID'),
        db.Index('idx_capa_status_deadline', '狀態', 'D0_客戶要求結案日'),
    )
```

- [ ] **Step 3：在 ReworkRequest 新增索引**

找到 `ReworkRequest` 模型（含 `status`、`created_at` 欄位），在類別結尾插入：

```python
    __table_args__ = (
        db.Index('idx_rework_status_created', '狀態', '建立時間'),
    )
```

- [ ] **Step 4：在 CustomerComplaint 新增索引**

找到 `CustomerComplaint` 模型，在 `creator` relationship 之前插入：

```python
    __table_args__ = (
        db.Index('idx_complaint_repeat_date', '是否重複客訴', '客訴日期'),
    )
```

- [ ] **Step 5：產生並套用遷移**

```powershell
cd C:\QC_Database\backend
$env:FLASK_APP = "app.py"
flask db migrate -m "新增複合索引"
flask db upgrade
```

預期輸出：`Running upgrade ... done`

- [ ] **Step 6：Commit**

```powershell
git add backend/models.py backend/migrations/
git commit -m "perf(db): 新增 NCMR/CAPA/重工/客訴複合索引"
```

---

### Task 2：統一 API 回傳格式 Helper

**Files:**
- Modify: `backend/utils.py`（新增 `api_success`、`api_error`）
- Test: `backend/tests/test_api_helpers.py`（新建）

- [ ] **Step 1：撰寫測試**

建立 `backend/tests/test_api_helpers.py`：

```python
import pytest
from backend.app import create_app

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_api_success_default(app):
    with app.app_context():
        from backend.utils import api_success
        resp, code = api_success(data={'id': 1})
        assert code == 200
        json_data = resp.get_json()
        assert json_data['success'] is True
        assert json_data['data'] == {'id': 1}
        assert json_data['message'] == '操作成功'

def test_api_success_custom_code(app):
    with app.app_context():
        from backend.utils import api_success
        resp, code = api_success(data={'id': 2}, code=201)
        assert code == 201

def test_api_error_default(app):
    with app.app_context():
        from backend.utils import api_error
        resp, code = api_error('資料不存在')
        assert code == 400
        json_data = resp.get_json()
        assert json_data['success'] is False
        assert json_data['error'] == '資料不存在'

def test_api_error_custom_code(app):
    with app.app_context():
        from backend.utils import api_error
        resp, code = api_error('未授權', code=403)
        assert code == 403
```

- [ ] **Step 2：確認測試失敗**

```powershell
cd C:\QC_Database
python -m pytest backend/tests/test_api_helpers.py -v
```

預期：`FAILED` — `ImportError: cannot import name 'api_success'`

- [ ] **Step 3：在 utils.py 新增 helper**

在 `backend/utils.py` 頂端 import 區之後，`sanitize_html` 函數之前插入：

```python
# ==================================================
# API 回傳格式 Helper
# ==================================================
def api_success(data=None, message: str = '操作成功', code: int = 200):
    """統一成功回傳格式"""
    return jsonify({'success': True, 'data': data, 'message': message}), code

def api_error(message: str, code: int = 400, detail=None):
    """統一錯誤回傳格式"""
    return jsonify({'success': False, 'error': message, 'detail': detail}), code
```

- [ ] **Step 4：確認測試通過**

```powershell
python -m pytest backend/tests/test_api_helpers.py -v
```

預期：4 個 PASSED

- [ ] **Step 5：Commit**

```powershell
git add backend/utils.py backend/tests/test_api_helpers.py
git commit -m "feat(utils): 新增 api_success / api_error 統一回傳 helper"
```

---

### Task 3：修正 shipping_service.py N+1

**Files:**
- Modify: `backend/services/shipping_service.py`

- [ ] **Step 1：找到列表查詢並加入 joinedload**

開啟 `backend/services/shipping_service.py`，找到回傳列表的查詢（通常是 `ShippingData.query` 或 `db.session.query(ShippingData)`）。

在查詢上加入 `options`：

```python
from sqlalchemy.orm import joinedload

# 修改前（範例）：
# items = ShippingData.query.filter(...).all()

# 修改後：
items = ShippingData.query\
    .options(
        joinedload(ShippingData.inspector),
        joinedload(ShippingData.vendor),
    )\
    .filter(...)\
    .order_by(ShippingData.date.desc())\
    .all()
```

- [ ] **Step 2：確認序列化時不觸發額外查詢**

確認 `_to_dict()` 或序列化方法中存取 `item.inspector.name` 和 `item.vendor.name` 時，不再使用 `getattr` 動態查詢，直接存取即可（joinedload 已預載入）。

- [ ] **Step 3：手動測試（後端需啟動）**

```powershell
# 啟動後端
cd C:\QC_Database\backend
..\venv\Scripts\Activate.ps1
python app.py
```

```powershell
# 另開終端，用 admin/admin 登入取得 token 後測試
curl -H "Authorization: Bearer <token>" http://localhost:5001/api/shipping
```

確認回傳正常，無 500 錯誤。

- [ ] **Step 4：Commit**

```powershell
git add backend/services/shipping_service.py
git commit -m "perf(shipping): 使用 joinedload 修正 N+1 查詢"
```

---

### Task 4：修正 ncmr_service.py、patrol_service.py、complaint_service.py N+1

**Files:**
- Modify: `backend/services/ncmr_service.py`
- Modify: `backend/services/patrol_service.py`
- Modify: `backend/services/complaint_service.py`

- [ ] **Step 1：修正 ncmr_service.py**

找到列表查詢，加入：

```python
from sqlalchemy.orm import joinedload

items = NCMR.query\
    .options(joinedload(NCMR.inspector))\
    .filter(...)\
    .order_by(NCMR.date.desc())\
    .all()
```

- [ ] **Step 2：修正 patrol_service.py**

找到巡線列表查詢，加入：

```python
from sqlalchemy.orm import joinedload

items = PatrolMain.query\
    .options(
        joinedload(PatrolMain.inspector),
        joinedload(PatrolMain.details),
    )\
    .filter(...)\
    .all()
```

- [ ] **Step 3：修正 complaint_service.py**

找到 `list_complaints` 方法，在 `q = CustomerComplaint.query` 之後加入：

```python
from sqlalchemy.orm import joinedload

q = CustomerComplaint.query.options(joinedload(CustomerComplaint.creator))
```

- [ ] **Step 4：Commit**

```powershell
git add backend/services/ncmr_service.py backend/services/patrol_service.py backend/services/complaint_service.py
git commit -m "perf(services): 修正 NCMR/巡線/客訴列表 N+1 查詢"
```
