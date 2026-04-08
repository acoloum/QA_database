# NCMR / CAR / CAPA 分頁與篩選功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 NCMR、CAR、CAPA 三個清單頁面加入後端分頁與篩選，同時修正 NCMR 清單顯示不合格數量並移除 NCMRModal 的產品數量欄位。

**Architecture:** 後端三支 GET API 改接收 `page/per_page` 與各篩選 query params，service 層用 SQLAlchemy filter + offset/limit 實作；前端新增共用 `FilterBar` 和 `PaginationBar` 元件，各頁 React Query key 包含 params 自動重取，CAR/CAPA 頁順便改用 React Query。

**Tech Stack:** Flask 3.1 + SQLAlchemy (Flask-SQLAlchemy 3.1.1) + React 19 + TypeScript + TanStack React Query + React Bootstrap

---

## 檔案清單

| 路徑 | 動作 |
|------|------|
| `backend/services/ncmr_service.py` | 修改：`get_ncmr_list`, `get_cara_list`, `get_capa_list` |
| `backend/routes/ncmr.py` | 修改：`get_ncmr_list`, `get_cara_list`, `get_capa_list` 三支 route |
| `backend/tests/test_services/test_ncmr.py` | 新增：service 層分頁/篩選測試 |
| `src_frontend/src/types/index.ts` | 修改：新增 `PaginatedResponse<T>` 型別 |
| `src_frontend/src/components/common/FilterBar.tsx` | 新增 |
| `src_frontend/src/components/common/PaginationBar.tsx` | 新增 |
| `src_frontend/src/hooks/useNCMR.ts` | 修改：`useNCMRList` 加 params；新增 `useCARAList`, `useCAPAList` |
| `src_frontend/src/pages/ncmr/NCMRPage.tsx` | 修改：加篩選/分頁，改顯示不合格數量 |
| `src_frontend/src/pages/cara/CARAPage.tsx` | 修改：加篩選/分頁，改用 React Query |
| `src_frontend/src/pages/capa/CAPAPage.tsx` | 修改：加篩選/分頁，改用 React Query |
| `src_frontend/src/components/ncmr/NCMRModal.tsx` | 修改：移除產品數量欄位 |

---

## Task 1：後端 — 更新 `get_ncmr_list` service

**Files:**
- Modify: `backend/services/ncmr_service.py:21-90`
- Create: `backend/tests/test_services/test_ncmr.py`

- [ ] **Step 1：寫失敗測試**

新建 `backend/tests/test_services/test_ncmr.py`：

```python
import pytest
import datetime
from backend.models import NCMR, Inspector
from backend.services.ncmr_service import NCMRService


def _make_ncmr(db_session, **kwargs):
    defaults = dict(
        ncmr_number='NCMR-TEST-001',
        date=datetime.date(2025, 1, 15),
        source='進料',
        vendor='TestVendor',
        material='6066-T6',
        product_info='38*3040',
        defect_quantity=5,
        status='待處理',
    )
    defaults.update(kwargs)
    n = NCMR(**defaults)
    db_session.add(n)
    db_session.commit()
    return n


def test_get_ncmr_list_pagination(app, db_session):
    with app.app_context():
        for i in range(25):
            _make_ncmr(db_session, ncmr_number=f'NCMR-{i:03}')
        result = NCMRService.get_ncmr_list(page=1, per_page=20)
        assert result['total'] == 25
        assert len(result['data']) == 20
        result2 = NCMRService.get_ncmr_list(page=2, per_page=20)
        assert len(result2['data']) == 5


def test_get_ncmr_list_filter_vendor(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-A', vendor='AluCorp')
        _make_ncmr(db_session, ncmr_number='NCMR-B', vendor='SteelInc')
        result = NCMRService.get_ncmr_list(vendor='alu')
        assert result['total'] == 1
        assert result['data'][0]['廠商'] == 'AluCorp'


def test_get_ncmr_list_filter_source(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-C', source='進料')
        _make_ncmr(db_session, ncmr_number='NCMR-D', source='巡檢')
        result = NCMRService.get_ncmr_list(source='進料')
        assert result['total'] == 1
        assert result['data'][0]['來源'] == '進料'


def test_get_ncmr_list_filter_date_range(app, db_session):
    with app.app_context():
        _make_ncmr(db_session, ncmr_number='NCMR-E', date=datetime.date(2025, 1, 10))
        _make_ncmr(db_session, ncmr_number='NCMR-F', date=datetime.date(2025, 3, 20))
        result = NCMRService.get_ncmr_list(date_from='2025-01-01', date_to='2025-02-28')
        assert result['total'] == 1
        assert result['data'][0]['日期'] == '2025-01-10'
```

- [ ] **Step 2：執行測試確認失敗**

```bash
cd C:/QC_Database
python -m pytest backend/tests/test_services/test_ncmr.py -v
```

預期：`FAILED` 因 `get_ncmr_list` 回傳格式不符。

- [ ] **Step 3：更新 `get_ncmr_list` service**

修改 `backend/services/ncmr_service.py`，將 `get_ncmr_list` 方法替換為：

```python
@staticmethod
def get_ncmr_list(
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    vendor: Optional[str] = None,
    material: Optional[str] = None,
    product_info: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        query = NCMR.query.options(
            joinedload(NCMR.inspector),
            subqueryload(NCMR.corrective_actions),
            subqueryload(NCMR.rework_requests).subqueryload(ReworkRequest.executions)
        )

        if status:
            query = query.filter(NCMR.status == status)
        if date_from:
            query = query.filter(NCMR.date >= datetime.date.fromisoformat(date_from))
        if date_to:
            query = query.filter(NCMR.date <= datetime.date.fromisoformat(date_to))
        if source:
            query = query.filter(NCMR.source == source)
        if vendor:
            query = query.filter(NCMR.vendor.ilike(f'%{vendor}%'))
        if material:
            query = query.filter(NCMR.material.ilike(f'%{material}%'))
        if product_info:
            query = query.filter(NCMR.product_info.ilike(f'%{product_info}%'))

        total = query.count()
        ncmrs = query.order_by(NCMR.id.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()

        data = []
        for n in ncmrs:
            car_status = None
            capa_status = None

            cars = [ca for ca in n.corrective_actions if ca.car_number]
            if cars:
                latest_car = sorted(cars, key=lambda x: x.id, reverse=True)[0]
                car_status = latest_car.status

            capas = [ca for ca in n.corrective_actions if ca.eight_d_number]
            if capas:
                latest_capa = sorted(capas, key=lambda x: x.id, reverse=True)[0]
                capa_status = latest_capa.status

            rework_count = 0
            rework_status = None
            if n.rework_requests:
                rework_count = sum(len(req.executions) for req in n.rework_requests)
                latest_rework = sorted(n.rework_requests, key=lambda x: x.id, reverse=True)[0]
                rework_status = latest_rework.status

            inspector_name = n.inspector.name if n.inspector else ""

            item = {
                "識別碼": n.id,
                "單號": n.ncmr_number,
                "日期": n.date.strftime('%Y-%m-%d') if n.date else "",
                "來源": n.source,
                "產品資訊": n.product_info,
                "產品數量": format_value(n.quantity),
                "材質": n.material,
                "廠商": n.vendor,
                "批號": n.batch_num,
                "不良描述": n.description,
                "不合格數量": format_value(n.defect_quantity),
                "判定結果": n.result,
                "狀態": n.status,
                "不良原因大類": n.defect_category,
                "不良原因細項": n.defect_detail,
                "發現人員姓名": inspector_name,
                "CAR狀態": car_status,
                "CAPA狀態": capa_status,
                "重工執行次數": rework_count,
                "重工狀態": rework_status
            }
            data.append(item)

        return {"data": data, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        raise e
```

- [ ] **Step 4：執行測試確認通過**

```bash
cd C:/QC_Database
python -m pytest backend/tests/test_services/test_ncmr.py -v
```

預期：4 個測試全部 `PASSED`。

- [ ] **Step 5：Commit**

```bash
cd C:/QC_Database
git add backend/services/ncmr_service.py backend/tests/test_services/test_ncmr.py
git commit -m "feat(ncmr): get_ncmr_list 支援分頁與篩選"
```

---

## Task 2：後端 — 更新 `get_cara_list` service

**Files:**
- Modify: `backend/services/ncmr_service.py:308-341`
- Modify: `backend/tests/test_services/test_ncmr.py`

- [ ] **Step 1：新增 CAR list 測試**

在 `backend/tests/test_services/test_ncmr.py` 補上：

```python
from backend.models import CorrectiveAction


def _make_car(db_session, ncmr, **kwargs):
    defaults = dict(
        ncmr_id=ncmr.id,
        car_number='CAR-TEST-001',
        status='進行中',
    )
    defaults.update(kwargs)
    ca = CorrectiveAction(**defaults)
    db_session.add(ca)
    db_session.commit()
    return ca


def test_get_cara_list_pagination(app, db_session):
    with app.app_context():
        for i in range(5):
            n = _make_ncmr(db_session, ncmr_number=f'NCMR-CAR-{i}')
            _make_car(db_session, n, car_number=f'CAR-{i:03}')
        result = NCMRService.get_cara_list(page=1, per_page=3)
        assert result['total'] == 5
        assert len(result['data']) == 3


def test_get_cara_list_filter_vendor(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-V1', vendor='VendorAlpha')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-V2', vendor='VendorBeta')
        _make_car(db_session, n1, car_number='CAR-V1')
        _make_car(db_session, n2, car_number='CAR-V2')
        result = NCMRService.get_cara_list(vendor='alpha')
        assert result['total'] == 1
        assert result['data'][0]['ncmr_vendor'] == 'VendorAlpha'


def test_get_cara_list_filter_status(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-S1')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-S2')
        _make_car(db_session, n1, car_number='CAR-S1', status='進行中')
        _make_car(db_session, n2, car_number='CAR-S2', status='已結案')
        result = NCMRService.get_cara_list(status='已結案')
        assert result['total'] == 1
        assert result['data'][0]['狀態'] == '已結案'
```

- [ ] **Step 2：執行測試確認失敗**

```bash
cd C:/QC_Database
python -m pytest backend/tests/test_services/test_ncmr.py::test_get_cara_list_pagination -v
```

預期：`FAILED`。

- [ ] **Step 3：更新 `get_cara_list` service**

將 `get_cara_list` 方法替換為：

```python
@staticmethod
def get_cara_list(
    page: int = 1,
    per_page: int = 20,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    vendor: Optional[str] = None,
    material: Optional[str] = None,
    product_info: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        query = CorrectiveAction.query\
            .filter(CorrectiveAction.car_number != None)\
            .join(NCMR, CorrectiveAction.ncmr_id == NCMR.id)\
            .options(joinedload(CorrectiveAction.ncmr), joinedload(CorrectiveAction.owner))

        if status:
            query = query.filter(CorrectiveAction.status == status)
        if date_from:
            query = query.filter(CorrectiveAction.created_at >= datetime.date.fromisoformat(date_from))
        if date_to:
            query = query.filter(CorrectiveAction.created_at <= datetime.datetime.fromisoformat(date_to + 'T23:59:59'))
        if vendor:
            query = query.filter(NCMR.vendor.ilike(f'%{vendor}%'))
        if material:
            query = query.filter(NCMR.material.ilike(f'%{material}%'))
        if product_info:
            query = query.filter(NCMR.product_info.ilike(f'%{product_info}%'))

        total = query.count()
        cas = query.order_by(CorrectiveAction.id.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()

        data = []
        for ca in cas:
            ncmr = ca.ncmr
            item = {
                "識別碼": ca.id,
                "NCMR_ID": ca.ncmr_id,
                "CAR單號": ca.car_number,
                "單號": ca.car_number,
                "8D單號": ca.eight_d_number,
                "負責人員": ca.owner_id,
                "狀態": ca.status,
                "ncmr_id": ca.ncmr_id,
                "ncmr_number": ncmr.ncmr_number if ncmr else "",
                "ncmr_date": format_value(ncmr.date) if ncmr else "",
                "ncmr_source": ncmr.source if ncmr else "",
                "ncmr_description": ncmr.description if ncmr else "",
                "ncmr_vendor": ncmr.vendor if ncmr else "",
                "ncmr_material": ncmr.material if ncmr else "",
                "ncmr_product": ncmr.product_info if ncmr else "",
                "負責人員姓名": ca.owner.name if ca.owner else ""
            }
            for k, v in item.items():
                item[k] = format_value(v)
            data.append(item)

        return {"data": data, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        raise e
```

- [ ] **Step 4：執行測試確認通過**

```bash
cd C:/QC_Database
python -m pytest backend/tests/test_services/test_ncmr.py -k "cara" -v
```

預期：3 個 CAR 測試全部 `PASSED`。

- [ ] **Step 5：Commit**

```bash
cd C:/QC_Database
git add backend/services/ncmr_service.py backend/tests/test_services/test_ncmr.py
git commit -m "feat(cara): get_cara_list 支援分頁與篩選"
```

---

## Task 3：後端 — 更新 `get_capa_list` service

**Files:**
- Modify: `backend/services/ncmr_service.py:487-562`
- Modify: `backend/tests/test_services/test_ncmr.py`

- [ ] **Step 1：新增 CAPA list 測試**

在 `backend/tests/test_services/test_ncmr.py` 補上：

```python
def _make_capa(db_session, ncmr, **kwargs):
    defaults = dict(
        ncmr_id=ncmr.id,
        eight_d_number='8D-TEST-001',
        status='進行中',
    )
    defaults.update(kwargs)
    ca = CorrectiveAction(**defaults)
    db_session.add(ca)
    db_session.commit()
    return ca


def test_get_capa_list_pagination(app, db_session):
    with app.app_context():
        for i in range(5):
            n = _make_ncmr(db_session, ncmr_number=f'NCMR-CAPA-{i}')
            _make_capa(db_session, n, eight_d_number=f'8D-{i:03}')
        result = NCMRService.get_capa_list(page=1, per_page=3)
        assert result['total'] == 5
        assert len(result['data']) == 3


def test_get_capa_list_filter_material(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-M1', material='6066-T6')
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-M2', material='A380')
        _make_capa(db_session, n1, eight_d_number='8D-M1')
        _make_capa(db_session, n2, eight_d_number='8D-M2')
        result = NCMRService.get_capa_list(material='6066')
        assert result['total'] == 1
        assert result['data'][0]['材質'] == '6066-T6'
```

- [ ] **Step 2：執行測試確認失敗**

```bash
cd C:/QC_Database
python -m pytest backend/tests/test_services/test_ncmr.py -k "capa" -v
```

預期：`FAILED`。

- [ ] **Step 3：更新 `get_capa_list` service**

將 `get_capa_list` 方法替換為：

```python
@staticmethod
def get_capa_list(
    page: int = 1,
    per_page: int = 20,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    vendor: Optional[str] = None,
    material: Optional[str] = None,
    product_info: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        query = CorrectiveAction.query\
            .filter(CorrectiveAction.eight_d_number != None)\
            .join(NCMR, CorrectiveAction.ncmr_id == NCMR.id)\
            .options(joinedload(CorrectiveAction.ncmr), joinedload(CorrectiveAction.owner))

        if status:
            query = query.filter(CorrectiveAction.status == status)
        if date_from:
            query = query.filter(CorrectiveAction.created_at >= datetime.date.fromisoformat(date_from))
        if date_to:
            query = query.filter(CorrectiveAction.created_at <= datetime.datetime.fromisoformat(date_to + 'T23:59:59'))
        if vendor:
            query = query.filter(NCMR.vendor.ilike(f'%{vendor}%'))
        if material:
            query = query.filter(NCMR.material.ilike(f'%{material}%'))
        if product_info:
            query = query.filter(NCMR.product_info.ilike(f'%{product_info}%'))

        total = query.count()
        cas = query.order_by(CorrectiveAction.id.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()

        data = []
        for ca in cas:
            ncmr = ca.ncmr
            item = {
                "識別碼": ca.id,
                "NCMR_ID": ca.ncmr_id,
                "8D單號": ca.eight_d_number,
                "CAR單號": ca.car_number,
                "負責人員": ca.owner_id,
                "狀態": ca.status,
                "建立日期": format_value(ca.created_at),
                "結案日期": format_value(ca.closed_at),
                "負責人員姓名": ca.owner.name if ca.owner else "",
                "來源": ncmr.source if ncmr else "",
                "不良描述": ncmr.description if ncmr else "",
                "廠商": ncmr.vendor if ncmr else "",
                "材質": ncmr.material if ncmr else "",
                "規格": ncmr.product_info if ncmr else "",
                "NCMR單號": ncmr.ncmr_number if ncmr else "",
                "ncmr_date": format_value(ncmr.date) if ncmr else ""
            }
            item["問題描述"] = ca.d2 or ""
            item["根本原因"] = ca.d4 or ""
            item["矯正措施"] = ca.d5 or ""
            item["預防措施"] = ca.d7 or ""
            for k, v in item.items():
                item[k] = format_value(v)
            data.append(item)

        return {"data": data, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        raise e
```

- [ ] **Step 4：執行所有 NCMR 相關測試**

```bash
cd C:/QC_Database
python -m pytest backend/tests/test_services/test_ncmr.py -v
```

預期：全部測試 `PASSED`。

- [ ] **Step 5：Commit**

```bash
cd C:/QC_Database
git add backend/services/ncmr_service.py backend/tests/test_services/test_ncmr.py
git commit -m "feat(capa): get_capa_list 支援分頁與篩選"
```

---

## Task 4：後端 — 更新三支 GET routes

**Files:**
- Modify: `backend/routes/ncmr.py`

- [ ] **Step 1：更新 `get_ncmr_list` route**

將 `backend/routes/ncmr.py` 的 `get_ncmr_list` 函式替換：

```python
@ncmr_bp.route('/api/ncmr', methods=['GET'])
@auth_required
def get_ncmr_list():
    try:
        params = {
            'page': int(request.args.get('page', 1)),
            'per_page': min(int(request.args.get('per_page', 20)), 100),
            'status': request.args.get('status') or None,
            'date_from': request.args.get('date_from') or None,
            'date_to': request.args.get('date_to') or None,
            'source': request.args.get('source') or None,
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_ncmr_list(**params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2：更新 `get_cara_list` route**

將 `get_cara_list` 函式替換：

```python
@ncmr_bp.route('/api/cara', methods=['GET'])
@auth_required
def get_cara_list():
    try:
        params = {
            'page': int(request.args.get('page', 1)),
            'per_page': min(int(request.args.get('per_page', 20)), 100),
            'status': request.args.get('status') or None,
            'date_from': request.args.get('date_from') or None,
            'date_to': request.args.get('date_to') or None,
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_cara_list(**params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 3：更新 `get_capa_list` route**

將 `get_capa_list` 函式替換：

```python
@ncmr_bp.route('/api/capa', methods=['GET'])
@auth_required
def get_capa_list():
    try:
        params = {
            'page': int(request.args.get('page', 1)),
            'per_page': min(int(request.args.get('per_page', 20)), 100),
            'status': request.args.get('status') or None,
            'date_from': request.args.get('date_from') or None,
            'date_to': request.args.get('date_to') or None,
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_capa_list(**params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4：啟動後端確認無啟動錯誤**

```bash
cd C:/QC_Database/backend
python app.py
```

預期：`Running on http://127.0.0.1:5001` 正常啟動。

- [ ] **Step 5：Commit**

```bash
cd C:/QC_Database
git add backend/routes/ncmr.py
git commit -m "feat(routes): ncmr/cara/capa GET routes 支援分頁與篩選 query params"
```

---

## Task 5：前端型別 + `FilterBar` 元件

**Files:**
- Modify: `src_frontend/src/types/index.ts`
- Create: `src_frontend/src/components/common/FilterBar.tsx`

- [ ] **Step 1：新增 `PaginatedResponse` 型別**

在 `src_frontend/src/types/index.ts` 頂部加入：

```typescript
export interface PaginatedResponse<T> {
    data: T[];
    total: number;
    page: number;
    per_page: number;
}
```

- [ ] **Step 2：建立 `FilterBar` 元件**

新建 `src_frontend/src/components/common/FilterBar.tsx`：

```tsx
import { Button, Col, Form, Row } from 'react-bootstrap';

interface FilterBarProps {
    onReset: () => void;
    children: React.ReactNode;
}

const FilterBar = ({ onReset, children }: FilterBarProps) => {
    return (
        <div className="bg-light border rounded p-3 mb-3">
            <Row className="g-2 align-items-end">
                {children}
                <Col xs="auto">
                    <Button variant="outline-secondary" size="sm" onClick={onReset}>
                        <i className="bi bi-x-circle me-1"></i>清除篩選
                    </Button>
                </Col>
            </Row>
        </div>
    );
};

export default FilterBar;
```

- [ ] **Step 3：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/types/index.ts src_frontend/src/components/common/FilterBar.tsx
git commit -m "feat(ui): 新增 PaginatedResponse 型別與 FilterBar 元件"
```

---

## Task 6：前端 `PaginationBar` 元件

**Files:**
- Create: `src_frontend/src/components/common/PaginationBar.tsx`

- [ ] **Step 1：建立 `PaginationBar` 元件**

新建 `src_frontend/src/components/common/PaginationBar.tsx`：

```tsx
import { Pagination } from 'react-bootstrap';

interface PaginationBarProps {
    page: number;
    perPage: number;
    total: number;
    onPageChange: (page: number) => void;
}

const PaginationBar = ({ page, perPage, total, onPageChange }: PaginationBarProps) => {
    const totalPages = Math.ceil(total / perPage);
    if (totalPages <= 1) return null;

    const getPageNumbers = () => {
        const pages: (number | 'ellipsis-start' | 'ellipsis-end')[] = [];
        if (totalPages <= 7) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
        } else {
            pages.push(1);
            if (page > 3) pages.push('ellipsis-start');
            for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
                pages.push(i);
            }
            if (page < totalPages - 2) pages.push('ellipsis-end');
            pages.push(totalPages);
        }
        return pages;
    };

    return (
        <div className="d-flex justify-content-between align-items-center mt-3">
            <small className="text-muted">
                共 {total} 筆，第 {page} / {totalPages} 頁
            </small>
            <Pagination size="sm" className="mb-0">
                <Pagination.Prev disabled={page === 1} onClick={() => onPageChange(page - 1)} />
                {getPageNumbers().map((p, idx) =>
                    p === 'ellipsis-start' || p === 'ellipsis-end'
                        ? <Pagination.Ellipsis key={p} disabled />
                        : <Pagination.Item key={idx} active={p === page} onClick={() => onPageChange(p as number)}>{p}</Pagination.Item>
                )}
                <Pagination.Next disabled={page === totalPages} onClick={() => onPageChange(page + 1)} />
            </Pagination>
        </div>
    );
};

export default PaginationBar;
```

- [ ] **Step 2：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/components/common/PaginationBar.tsx
git commit -m "feat(ui): 新增 PaginationBar 元件"
```

---

## Task 7：前端 — 更新 React Query hooks

**Files:**
- Modify: `src_frontend/src/hooks/useNCMR.ts`

- [ ] **Step 1：更新 `useNCMRList` 並新增 `useCARAList`、`useCAPAList`**

將 `src_frontend/src/hooks/useNCMR.ts` 的 `useNCMRList` 替換，並在其後加入新 hooks：

```typescript
// useNCMRList 的 params 型別
export interface NCMRListParams {
    page?: number;
    per_page?: number;
    date_from?: string;
    date_to?: string;
    source?: string;
    vendor?: string;
    material?: string;
    product_info?: string;
    status?: string;
}

export interface CARListParams {
    page?: number;
    per_page?: number;
    date_from?: string;
    date_to?: string;
    vendor?: string;
    material?: string;
    product_info?: string;
    status?: string;
}

export type CAPAListParams = CARListParams;

export const useNCMRList = (params: NCMRListParams = {}) => {
    return useQuery({
        queryKey: ['ncmrList', params],
        queryFn: async () => {
            const res = await api.get<{ data: NCMR[]; total: number; page: number; per_page: number }>(
                '/ncmr', { params }
            );
            const mapped = res.data.data.map((item: NCMR) => ({
                id: item.識別碼 ?? item.id,
                no: item.單號 || item.no,
                date: item.日期 || item.發現日期 || item.date,
                source: item.來源 || item.source,
                vendor: item.廠商 || item.vendor,
                material: item.材質 || item.material,
                product_info: item.產品資訊 || item.product_info,
                product_qty: item.產品數量 || item.product_qty,
                defect_qty: item.不合格數量 ?? item.defect_qty,
                defect_desc: item.不良描述 || item.defect_desc,
                defect_category: item.不良原因大類 || item.defect_category,
                defect_reason: item.不良原因細項 || item.defect_reason,
                result: item.判定結果 || item.result,
                status: item.狀態 || item.status,
                car_status: item.CAR狀態 || item.car狀態 || item.car_status,
                capa_status: item.CAPA狀態 || item.capa狀態 || item.capa_status,
                rework_status: item.重工狀態 || item.rework_status,
                rework_count: item.重工執行次數 || item.rework_count
            } as NCMR));
            return {
                data: mapped,
                total: res.data.total,
                page: res.data.page,
                per_page: res.data.per_page,
            };
        },
    });
};

export const useCARAList = (params: CARListParams = {}) => {
    return useQuery({
        queryKey: ['caraList', params],
        queryFn: async () => {
            const res = await api.get<{ data: Record<string, unknown>[]; total: number; page: number; per_page: number }>(
                '/cara', { params }
            );
            const mapped = res.data.data.map((item) => ({
                id: item.識別碼 as number,
                no: item.單號,
                ncmr_no: item.ncmr_number || item.ncmr_id,
                source: item.ncmr_source,
                vendor: item.ncmr_vendor,
                material: item.ncmr_material,
                product: item.ncmr_product,
                create_date: item.建立日期 || item.ncmr_date,
                owner: item.負責人員姓名,
                status: item.狀態,
            }));
            return { data: mapped, total: res.data.total, page: res.data.page, per_page: res.data.per_page };
        },
    });
};

export const useCAPAList = (params: CAPAListParams = {}) => {
    return useQuery({
        queryKey: ['capaList', params],
        queryFn: async () => {
            const res = await api.get<{ data: Record<string, unknown>[]; total: number; page: number; per_page: number }>(
                '/capa', { params }
            );
            const mapped = res.data.data.map((item) => ({
                id: item.識別碼 as number,
                no: item['8D單號'] || item.識別碼,
                ncmr_no: item.NCMR單號 || ('#' + item.NCMR_ID),
                source: item.來源,
                vendor: item.廠商,
                material: item.材質,
                spec: item.規格,
                create_date: item.ncmr_date || item.建立日期,
                owner: item.負責人員姓名,
                status: item.狀態,
            }));
            return { data: mapped, total: res.data.total, page: res.data.page, per_page: res.data.per_page };
        },
    });
};
```

同時更新 `useDeleteNCMR`、`useCreateNCMR`、`useUpdateNCMR` 的 `invalidateQueries` 從 `['ncmrList']` 改為 `{ queryKey: ['ncmrList'], exact: false }` 以配合新的 key 結構（此時 key 為 `['ncmrList', params]`）。

- [ ] **Step 2：確認 TypeScript 編譯無錯誤**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | head -30
```

預期：無 TypeScript 錯誤（或僅有不相關的既有 warning）。

- [ ] **Step 3：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/hooks/useNCMR.ts
git commit -m "feat(hooks): useNCMRList 加入分頁/篩選 params；新增 useCARAList、useCAPAList"
```

---

## Task 8：前端 — 更新 `NCMRPage`

**Files:**
- Modify: `src_frontend/src/pages/ncmr/NCMRPage.tsx`

- [ ] **Step 1：更新 NCMRPage**

將 `NCMRPage.tsx` 內容替換為以下（保留原有的列印、操作按鈕邏輯，新增篩選列與分頁列）：

```tsx
import { useState, useEffect } from 'react';
import { Button, Card, Table, Badge, Col, Form } from 'react-bootstrap';
import type { NCMR } from '../../types';
import NCMRModal from '../../components/ncmr/NCMRModal';
import DispositionModal from '../../components/ncmr/DispositionModal';
import FilterBar from '../../components/common/FilterBar';
import PaginationBar from '../../components/common/PaginationBar';
import { useNavigate } from 'react-router-dom';
import { useNCMRList, useDeleteNCMR, useCreateCARA, useCreateCAPA, useNCMRDetail } from '../../hooks/useNCMR';
import type { NCMRListParams } from '../../hooks/useNCMR';

const EMPTY_FILTERS: NCMRListParams = {
    page: 1, per_page: 20,
    date_from: '', date_to: '', source: '', vendor: '', material: '', product_info: '', status: ''
};

const NCMRPage = () => {
    const navigate = useNavigate();
    const [filters, setFilters] = useState<NCMRListParams>(EMPTY_FILTERS);
    const [page, setPage] = useState(1);

    const activeParams: NCMRListParams = {
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
        page,
        per_page: 20,
    };

    const { data: result, isLoading } = useNCMRList(activeParams);
    const ncmrList = result?.data ?? [];
    const total = result?.total ?? 0;

    const deleteMutation = useDeleteNCMR();
    const createCARAMutation = useCreateCARA();
    const createCAPAMutation = useCreateCAPA();

    const [showModal, setShowModal] = useState(false);
    const [showDisposeModal, setShowDisposeModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [disposeItem, setDisposeItem] = useState<NCMR | null>(null);
    const [printItem, setPrintItem] = useState<NCMR | null>(null);

    const { data: printDetail } = useNCMRDetail(printItem?.id || null);

    const handleFilterChange = (key: string, value: string) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    const handleReset = () => {
        setFilters(EMPTY_FILTERS);
        setPage(1);
    };

    useEffect(() => {
        if (printItem && printDetail) {
            const d = printDetail;
            const formatQty = (val: unknown) => val ? Math.floor(Number(val)).toString() : '';
            const ncmrNo = d.NCMR單號 || d.單號 || (d.識別碼 ? `NCMR-${d.識別碼}` : '');
            const printContent = `<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><title>不合格品異常單 - ${ncmrNo}</title>
<style>body{font-family:'Microsoft JhengHei',Arial,sans-serif;padding:20px}table{width:100%;border-collapse:collapse;margin-bottom:20px}th,td{border:1px solid #333;padding:8px;font-size:14px}th{background:#f0f0f0;text-align:center;width:150px}</style>
</head><body>
<div style="text-align:center"><h2>不合格品異常單 (NCMR)</h2></div>
<table>
<tr><th>單號</th><td>${ncmrNo}</td><th>發現日期</th><td>${d.日期 || d.發現日期 || ''}</td></tr>
<tr><th>來源</th><td>${d.來源 || ''}</td><th>廠商</th><td>${d.廠商 || ''}</td></tr>
<tr><th>材質</th><td>${d.材質 || ''}</td><th>規格</th><td>${d.產品資訊 || ''}</td></tr>
<tr><th>不合格數量</th><td colspan="3">${formatQty(d.不合格數量)}</td></tr>
<tr><th>批號/訂單號</th><td colspan="3">${d.批號 || ''}</td></tr>
<tr><th>不良描述</th><td colspan="3">${d.不良描述 || ''}</td></tr>
<tr><th>不良原因大類</th><td>${d.不良原因大類 || ''}</td><th>不良原因細項</th><td>${d.不良原因細項 || ''}</td></tr>
<tr><th>發現人員</th><td>${d.發現人員姓名 || ''}</td><th>判定結果</th><td>${d.判定結果 || ''}</td></tr>
<tr><th>狀態</th><td>${d.狀態 || ''}</td><th>建立日期</th><td>${d.建立日期 || d.日期 || ''}</td></tr>
</table>
<div style="text-align:center;margin-top:20px">
<button onclick="window.print()" style="padding:10px 20px;font-size:16px;cursor:pointer">列印</button>
<button onclick="window.close()" style="padding:10px 20px;font-size:16px;cursor:pointer;margin-left:10px">關閉</button>
</div></body></html>`;
            const pw = window.open('', '_blank', 'width=800,height=600');
            if (pw) { pw.document.write(printContent); pw.document.close(); }
            setPrintItem(null);
        }
    }, [printItem, printDetail]);

    const handleDelete = async (id: number) => {
        if (window.confirm(`確定要刪除異常單 #${id} 嗎？此動作無法復原。`)) {
            deleteMutation.mutate(id);
        }
    };

    const convertToRework = (id: number, no: string) => {
        if (window.confirm('確定要針對此異常單開立重工申請嗎？')) {
            window.open(`/rework?ncmr_id=${id}&ncmr_no=${no || id}`, '_blank');
        }
    };

    const convertToCAR = (id: number) => {
        if (!window.confirm('確定要將此異常單轉為CAR嗎？')) return;
        createCARAMutation.mutate(id);
    };

    const convertTo8D = async (id: number) => {
        if (!window.confirm('確定要針對此異常單開立 8D 矯正措施嗎？')) return;
        try {
            const res = await createCAPAMutation.mutateAsync(id);
            if (res.id) window.location.href = `/capa?editId=${res.id}`;
        } catch { /* handled by toast */ }
    };

    const renderStatusBadge = (status: string) => {
        let bg = 'secondary';
        if (status === '已結案') bg = 'success';
        else if (status === '轉CAPA') bg = 'primary';
        else if (status === '待處理') bg = 'warning';
        return <Badge bg={bg} text={bg === 'warning' ? 'dark' : 'white'}>{status}</Badge>;
    };

    const renderProgress = (item: NCMR) => {
        const badges = [];
        if (item.car_status) badges.push(<Badge key="car" bg={item.car_status === '已結案' ? 'success' : 'info'} className="d-block mb-1">CAR: {item.car_status}</Badge>);
        if (item.capa_status) badges.push(<Badge key="capa" bg={item.capa_status === '已結案' ? 'success' : 'warning'} text="dark" className="d-block mb-1">8D: {item.capa_status}</Badge>);
        if (item.rework_count && item.rework_count > 0) {
            badges.push(<Badge key="rework" bg={item.rework_status === '已完成' ? 'success' : 'primary'} className="d-block mb-1">重工: {item.rework_status === '已完成' ? '已完成' : `執行 ${item.rework_count} 次`}</Badge>);
        }
        return badges.length > 0 ? badges : '-';
    };

    return (
        <div className="p-0">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-danger fw-bold"><i className="bi bi-exclamation-octagon"></i> 不合格品管理 (NCMR)</h2>
                <div>
                    <Button className="btn-back-home me-2" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </Button>
                    <Button variant="primary" onClick={() => { setEditId(null); setShowModal(true); }}>
                        <i className="bi bi-plus-lg"></i> 新增異常單
                    </Button>
                </div>
            </div>

            <FilterBar onReset={handleReset}>
                <Col md={2}><Form.Label className="small mb-1">日期（起）</Form.Label><Form.Control size="sm" type="date" value={filters.date_from ?? ''} onChange={e => handleFilterChange('date_from', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">日期（迄）</Form.Label><Form.Control size="sm" type="date" value={filters.date_to ?? ''} onChange={e => handleFilterChange('date_to', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">來源</Form.Label>
                    <Form.Select size="sm" value={filters.source ?? ''} onChange={e => handleFilterChange('source', e.target.value)}>
                        <option value="">全部</option>
                        <option value="進料">進料</option>
                        <option value="巡檢">巡檢</option>
                        <option value="出貨檢">出貨檢</option>
                        <option value="客訴">客訴</option>
                        <option value="退貨">退貨</option>
                    </Form.Select>
                </Col>
                <Col md={2}><Form.Label className="small mb-1">廠商</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.vendor ?? ''} onChange={e => handleFilterChange('vendor', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">材質</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.material ?? ''} onChange={e => handleFilterChange('material', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">規格</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.product_info ?? ''} onChange={e => handleFilterChange('product_info', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">狀態</Form.Label>
                    <Form.Select size="sm" value={filters.status ?? ''} onChange={e => handleFilterChange('status', e.target.value)}>
                        <option value="">全部</option>
                        <option value="待處理">待處理</option>
                        <option value="CAR處理中">CAR處理中</option>
                        <option value="矯正中">矯正中</option>
                        <option value="轉重工">轉重工</option>
                        <option value="已結案">已結案</option>
                    </Form.Select>
                </Col>
            </FilterBar>

            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <Table hover className="align-middle table-compact mb-0">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th><th>日期</th><th>來源</th><th>廠商</th><th>材質</th>
                                <th>規格</th><th>不合格數量</th><th>不良描述</th><th>不良原因</th>
                                <th>判定結果</th><th>狀態</th><th>處理進度</th><th className="action-column">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={13} className="text-center py-4">載入中...</td></tr>
                            ) : ncmrList.length === 0 ? (
                                <tr><td colSpan={13} className="text-center py-4">無資料</td></tr>
                            ) : (
                                ncmrList.map((item: NCMR) => (
                                    <tr key={item.id}>
                                        <td>{item.no || item.id}</td>
                                        <td>{item.date}</td>
                                        <td><Badge bg="secondary">{item.source}</Badge></td>
                                        <td>{item.vendor || '-'}</td>
                                        <td>{item.material || '-'}</td>
                                        <td>{item.product_info || '-'}</td>
                                        <td>{item.defect_qty ?? '-'}</td>
                                        <td>{item.defect_desc || '-'}</td>
                                        <td>{item.defect_reason ? <Badge bg="info">{item.defect_reason.split(':')[0]}</Badge> : item.defect_category ? <Badge bg="secondary">{item.defect_category}</Badge> : '-'}</td>
                                        <td onClick={() => { setDisposeItem(item); setShowDisposeModal(true); }} style={{ cursor: 'pointer', textDecoration: 'underline' }} title="點擊進行處置">{item.result || '-'}</td>
                                        <td>{renderStatusBadge(item.status)}</td>
                                        <td>{renderProgress(item)}</td>
                                        <td>
                                            <div className="action-buttons">
                                                <Button variant="outline-dark" size="sm" onClick={() => setPrintItem(item)}>列印</Button>
                                                <Button variant="outline-primary" size="sm" onClick={() => { setEditId(item.id); setShowModal(true); }}>編輯</Button>
                                                <Button variant="outline-warning" size="sm" onClick={() => convertToRework(item.id, item.no || String(item.id))}>轉重工</Button>
                                                <Button variant="outline-info" size="sm" onClick={() => convertToCAR(item.id)}>轉CAR</Button>
                                                <Button variant="outline-success" size="sm" onClick={() => convertTo8D(item.id)}>轉8D</Button>
                                                <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>刪除</Button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            <PaginationBar page={page} perPage={20} total={total} onPageChange={setPage} />

            <NCMRModal show={showModal} handleClose={() => { setShowModal(false); setEditId(null); }} onSuccess={() => {}} editId={editId} />
            <DispositionModal show={showDisposeModal} handleClose={() => setShowDisposeModal(false)} onSuccess={() => {}} item={disposeItem} />
        </div>
    );
};

export default NCMRPage;
```

- [ ] **Step 2：確認 TypeScript 編譯無錯誤**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | head -30
```

- [ ] **Step 3：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/pages/ncmr/NCMRPage.tsx
git commit -m "feat(ncmr-page): 加入篩選列、分頁列，數量欄改顯示不合格數量"
```

---

## Task 9：前端 — 更新 `CARAPage`

**Files:**
- Modify: `src_frontend/src/pages/cara/CARAPage.tsx`

- [ ] **Step 1：更新 CARAPage**

將 `src_frontend/src/pages/cara/CARAPage.tsx` 內容替換為：

```tsx
import { useState } from 'react';
import { Button, Card, Table, Badge, Col, Form } from 'react-bootstrap';
import CARAModal from '../../components/cara/CARAModal';
import FilterBar from '../../components/common/FilterBar';
import PaginationBar from '../../components/common/PaginationBar';
import { useNavigate } from 'react-router-dom';
import { useCARAList } from '../../hooks/useNCMR';
import type { CARListParams } from '../../hooks/useNCMR';
import api from '../../services/api';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

const EMPTY_FILTERS: CARListParams = {
    date_from: '', date_to: '', vendor: '', material: '', product_info: '', status: ''
};

const CARAPage = () => {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [filters, setFilters] = useState<CARListParams>(EMPTY_FILTERS);
    const [page, setPage] = useState(1);
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    const activeParams: CARListParams = {
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
        page,
        per_page: 20,
    };

    const { data: result, isLoading } = useCARAList(activeParams);
    const data = result?.data ?? [];
    const total = result?.total ?? 0;

    const handleFilterChange = (key: string, value: string) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    const handleReset = () => { setFilters(EMPTY_FILTERS); setPage(1); };

    const handleDelete = async (id: number) => {
        if (!window.confirm(`確定要刪除 CAR #${id} 嗎？`)) return;
        try {
            await api.post('/cara/delete', { id });
            toast.success('刪除成功');
            queryClient.invalidateQueries({ queryKey: ['caraList'], exact: false });
        } catch {
            toast.error('刪除失敗');
        }
    };

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-shield-check"></i> 矯正措施要求 (CAR)</h2>
                <Button className="btn-back-home" onClick={() => navigate('/')}>
                    <i className="bi bi-arrow-left"></i> 回首頁
                </Button>
            </div>

            <FilterBar onReset={handleReset}>
                <Col md={2}><Form.Label className="small mb-1">日期（起）</Form.Label><Form.Control size="sm" type="date" value={filters.date_from ?? ''} onChange={e => handleFilterChange('date_from', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">日期（迄）</Form.Label><Form.Control size="sm" type="date" value={filters.date_to ?? ''} onChange={e => handleFilterChange('date_to', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">廠商</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.vendor ?? ''} onChange={e => handleFilterChange('vendor', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">材質</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.material ?? ''} onChange={e => handleFilterChange('material', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">規格</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.product_info ?? ''} onChange={e => handleFilterChange('product_info', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">狀態</Form.Label>
                    <Form.Select size="sm" value={filters.status ?? ''} onChange={e => handleFilterChange('status', e.target.value)}>
                        <option value="">全部</option>
                        <option value="進行中">進行中</option>
                        <option value="已結案">已結案</option>
                    </Form.Select>
                </Col>
            </FilterBar>

            <Card className="shadow-sm">
                <Card.Body>
                    <Table hover responsive className="align-middle">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th><th>關聯異常單</th><th>廠商</th><th>材質</th><th>規格</th>
                                <th>建立日期</th><th>負責人</th><th>狀態</th><th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={9} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={9} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
                                    <tr key={Number(item.id)}>
                                        <td className="fw-bold">{String(item.no ?? '')}</td>
                                        <td>#{String(item.ncmr_no ?? '')} ({String(item.source ?? '')})</td>
                                        <td>{String(item.vendor ?? '') || '-'}</td>
                                        <td>{String(item.material ?? '') || '-'}</td>
                                        <td>{String(item.product ?? '') || '-'}</td>
                                        <td>{String(item.create_date ?? '').substring(0, 10) || '-'}</td>
                                        <td>{String(item.owner ?? '') || '-'}</td>
                                        <td><Badge bg={item.status === '已結案' ? 'success' : 'primary'}>{String(item.status ?? '')}</Badge></td>
                                        <td>
                                            <Button variant="outline-primary" size="sm" className="me-2" onClick={() => { setEditId(item.id); setShowModal(true); }}>處理</Button>
                                            <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>刪除</Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            <PaginationBar page={page} perPage={20} total={total} onPageChange={setPage} />

            <CARAModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={() => queryClient.invalidateQueries({ queryKey: ['caraList'], exact: false })}
                editId={editId}
            />
        </div>
    );
};

export default CARAPage;
```

- [ ] **Step 2：確認 TypeScript 編譯無錯誤**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | head -30
```

- [ ] **Step 3：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/pages/cara/CARAPage.tsx
git commit -m "feat(cara-page): 加入篩選列、分頁列，改用 React Query"
```

---

## Task 10：前端 — 更新 `CAPAPage`

**Files:**
- Modify: `src_frontend/src/pages/capa/CAPAPage.tsx`

- [ ] **Step 1：更新 CAPAPage**

將 `src_frontend/src/pages/capa/CAPAPage.tsx` 內容替換為：

```tsx
import { useState, useEffect } from 'react';
import { Button, Card, Table, Badge, Col, Form } from 'react-bootstrap';
import CAPAModal from '../../components/capa/CAPAModal';
import FilterBar from '../../components/common/FilterBar';
import PaginationBar from '../../components/common/PaginationBar';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useCAPAList } from '../../hooks/useNCMR';
import type { CAPAListParams } from '../../hooks/useNCMR';
import api from '../../services/api';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

const EMPTY_FILTERS: CAPAListParams = {
    date_from: '', date_to: '', vendor: '', material: '', product_info: '', status: ''
};

const CAPAPage = () => {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [searchParams] = useSearchParams();
    const [filters, setFilters] = useState<CAPAListParams>(EMPTY_FILTERS);
    const [page, setPage] = useState(1);
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    useEffect(() => {
        const queryEditId = searchParams.get('editId');
        if (queryEditId) {
            setEditId(Number(queryEditId));
            setShowModal(true);
        }
    }, [searchParams]);

    const activeParams: CAPAListParams = {
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
        page,
        per_page: 20,
    };

    const { data: result, isLoading } = useCAPAList(activeParams);
    const data = result?.data ?? [];
    const total = result?.total ?? 0;

    const handleFilterChange = (key: string, value: string) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    const handleReset = () => { setFilters(EMPTY_FILTERS); setPage(1); };

    const handleDelete = async (id: number) => {
        if (!window.confirm(`確定要刪除 CAPA #${id} 嗎？`)) return;
        try {
            await api.post('/capa/delete', { id });
            toast.success('刪除成功');
            queryClient.invalidateQueries({ queryKey: ['capaList'], exact: false });
        } catch {
            toast.error('刪除失敗');
        }
    };

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-shield-check"></i> 異常矯正措施 (CAPA)</h2>
                <Button className="btn-back-home" onClick={() => navigate('/')}>
                    <i className="bi bi-arrow-left"></i> 回首頁
                </Button>
            </div>

            <FilterBar onReset={handleReset}>
                <Col md={2}><Form.Label className="small mb-1">日期（起）</Form.Label><Form.Control size="sm" type="date" value={filters.date_from ?? ''} onChange={e => handleFilterChange('date_from', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">日期（迄）</Form.Label><Form.Control size="sm" type="date" value={filters.date_to ?? ''} onChange={e => handleFilterChange('date_to', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">廠商</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.vendor ?? ''} onChange={e => handleFilterChange('vendor', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">材質</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.material ?? ''} onChange={e => handleFilterChange('material', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">規格</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.product_info ?? ''} onChange={e => handleFilterChange('product_info', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">狀態</Form.Label>
                    <Form.Select size="sm" value={filters.status ?? ''} onChange={e => handleFilterChange('status', e.target.value)}>
                        <option value="">全部</option>
                        <option value="進行中">進行中</option>
                        <option value="已結案">已結案</option>
                    </Form.Select>
                </Col>
            </FilterBar>

            <Card className="shadow-sm">
                <Card.Body>
                    <Table hover responsive className="align-middle">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th><th>關聯異常單</th><th>廠商</th><th>材質</th><th>規格</th>
                                <th>建立日期</th><th>負責人</th><th>狀態</th><th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={9} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={9} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
                                    <tr key={Number(item.id)}>
                                        <td className="fw-bold">{String(item.no ?? '')}</td>
                                        <td>{String(item.ncmr_no ?? '')} ({String(item.source ?? '')})</td>
                                        <td>{String(item.vendor ?? '') || '-'}</td>
                                        <td>{String(item.material ?? '') || '-'}</td>
                                        <td>{String(item.spec ?? '') || '-'}</td>
                                        <td>{String(item.create_date ?? '').substring(0, 10) || '-'}</td>
                                        <td>{String(item.owner ?? '') || '-'}</td>
                                        <td><Badge bg={item.status === '已結案' ? 'success' : 'warning'} text="dark">{String(item.status ?? '')}</Badge></td>
                                        <td>
                                            <Button variant="outline-primary" size="sm" className="me-2" onClick={() => { setEditId(item.id); setShowModal(true); }}>處理</Button>
                                            <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>刪除</Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            <PaginationBar page={page} perPage={20} total={total} onPageChange={setPage} />

            <CAPAModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={() => queryClient.invalidateQueries({ queryKey: ['capaList'], exact: false })}
                editId={editId}
            />
        </div>
    );
};

export default CAPAPage;
```

- [ ] **Step 2：確認 TypeScript 編譯無錯誤**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | head -30
```

- [ ] **Step 3：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/pages/capa/CAPAPage.tsx
git commit -m "feat(capa-page): 加入篩選列、分頁列，改用 React Query"
```

---

## Task 11：前端 — NCMRModal 移除產品數量欄位

**Files:**
- Modify: `src_frontend/src/components/ncmr/NCMRModal.tsx`

- [ ] **Step 1：移除 `productQty` state 與欄位**

在 `NCMRModal.tsx` 中：
1. 刪除 `const [productQty, setProductQty] = useState('');`
2. 刪除 `setProductQty('');`（在 `resetForm` 中）
3. 刪除 `setProductQty(d.產品數量 ? Math.floor(Number(d.產品數量)).toString() : '');`（在 `useEffect` 中）
4. 刪除 `handleSubmit` payload 中的 `"產品數量": productQty`
5. 刪除 JSX 中的產品數量 `<Col md={6}>` 區塊

產品數量欄位在 JSX 中的位置：
```tsx
<Col md={6}><Form.Label>產品數量</Form.Label><Form.Control type="number" value={productQty} onChange={e => setProductQty(e.target.value)} /></Col>
```
刪除這整個 `<Col>` 。

- [ ] **Step 2：確認 TypeScript 編譯無錯誤**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | head -30
```

- [ ] **Step 3：Commit**

```bash
cd C:/QC_Database
git add src_frontend/src/components/ncmr/NCMRModal.tsx
git commit -m "feat(ncmr-modal): 移除產品數量欄位"
```

---

## Task 12：全套測試與最終驗證

- [ ] **Step 1：執行全部後端測試**

```bash
cd C:/QC_Database
python -m pytest backend/tests/ -v
```

預期：全部 `PASSED`，無 `FAILED`。

- [ ] **Step 2：啟動後端並手動驗證 API**

```bash
cd C:/QC_Database/backend
python app.py
```

用瀏覽器或 curl 確認：
- `GET /api/ncmr?page=1&per_page=5` → 回傳 `{"data":[...],"total":N,"page":1,"per_page":5}`
- `GET /api/ncmr?vendor=xxx` → 只回傳廠商含 xxx 的資料
- `GET /api/cara?page=1&per_page=5` → 同上格式
- `GET /api/capa?page=1&per_page=5` → 同上格式

- [ ] **Step 3：啟動前端確認畫面**

```bash
cd C:/QC_Database/src_frontend
npm run dev
```

開啟 `http://localhost:5173`，確認：
- NCMR 頁面顯示篩選列與分頁列
- CAR 頁面顯示篩選列與分頁列
- CAPA 頁面顯示篩選列與分頁列
- NCMR 清單「不合格數量」欄位正確顯示
- NCMRModal 無「產品數量」欄位

- [ ] **Step 4：最終 Commit（如有剩餘變更）**

```bash
cd C:/QC_Database
git status
# 若有未提交的變更
git add -A
git commit -m "chore: 完成 NCMR/CAR/CAPA 分頁與篩選功能"
```
