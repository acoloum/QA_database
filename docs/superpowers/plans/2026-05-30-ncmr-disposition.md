# 不合格品處置管制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 NCMR 加入結構化的不合格品處置明細（含數量勾稽與結案 gate）與未授權放行風險報表，符合 IATF 16949 §8.7。

**Architecture:** 後端新增 `NcmrDisposition` 子表（一張 NCMR 對多筆處置），處置 CRUD 走既有 route→service 三層，結案 gate 加在既有 `NCMRService.update_ncmr`。前端升級既有 `DispositionModal.tsx` 成處置明細管理，新增風險報表頁，透過 React Query hooks 串接。

**Tech Stack:** Flask 3.1 / SQLAlchemy（中文欄位名）/ pytest（SQLite in-memory）/ React 19 + TypeScript / TanStack React Query / react-bootstrap。

**對應 spec：** `docs/superpowers/specs/2026-05-30-ncmr-disposition-design.md`

---

## 檔案結構

| 檔案 | 動作 | 責任 |
|------|------|------|
| `backend/models.py` | Modify | 新增 `NcmrDisposition` model + NCMR `dispositions` 關聯 |
| `backend/migration/20_add_ncmr_disposition.sql` | Create | 建子表與索引 |
| `backend/seeds/seed_roles.py` | Modify | 新增 `ncmr.disposition` 權限 |
| `backend/services/ncmr_service.py` | Modify | 處置 CRUD、寫入驗證、風險報表、結案 gate |
| `backend/routes/ncmr.py` | Modify | 處置 CRUD 端點 + 風險報表端點 |
| `backend/tests/test_services/test_ncmr_disposition.py` | Create | 處置驗證、結案 gate、風險報表測試 |
| `src_frontend/src/types/index.ts` | Modify | `NcmrDisposition` interface |
| `src_frontend/src/hooks/useNCMR.ts` | Modify | 處置 hooks + 風險報表 hook |
| `src_frontend/src/components/ncmr/DispositionModal.tsx` | Modify | 升級為處置明細管理 |
| `src_frontend/src/pages/ncmr/RiskReleasePage.tsx` | Create | 未授權放行風險報表頁 |
| `src_frontend/src/App.tsx` | Modify | 新增風險報表頁路由 |

---

## Task 1：NcmrDisposition Model 與 NCMR 關聯

**Files:**
- Modify: `backend/models.py`（NCMR class 約 297-327；於檔案中 NCMR 區段後新增 model）
- Test: `backend/tests/test_services/test_ncmr_disposition.py`

- [ ] **Step 1：寫失敗測試**

新建 `backend/tests/test_services/test_ncmr_disposition.py`：

```python
import datetime
import pytest
from backend.models import NCMR, NcmrDisposition, Inspector
from backend.extensions import db


def _make_ncmr(db_session, **kwargs):
    defaults = dict(
        ncmr_number='NCMR-DISP-001',
        date=datetime.date(2025, 1, 15),
        source='進料',
        vendor='TestVendor',
        material='6066-T6',
        product_info='38*3040',
        defect_quantity=100,
        status='待處理',
    )
    defaults.update(kwargs)
    n = NCMR(**defaults)
    db_session.add(n)
    db_session.commit()
    return n


def test_disposition_model_relationship(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        d = NcmrDisposition(ncmr_id=n.id, disposition_type='報廢', quantity=100)
        db_session.add(d)
        db_session.commit()
        fetched = NCMR.query.get(n.id)
        assert len(fetched.dispositions) == 1
        assert fetched.dispositions[0].disposition_type == '報廢'
        assert fetched.dispositions[0].quantity == 100
        assert fetched.dispositions[0].is_risk is False


def test_disposition_cascade_delete(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        db_session.add(NcmrDisposition(ncmr_id=n.id, disposition_type='報廢', quantity=100))
        db_session.commit()
        db_session.delete(n)
        db_session.commit()
        assert NcmrDisposition.query.count() == 0
```

- [ ] **Step 2：執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -v`
Expected: FAIL — `ImportError: cannot import name 'NcmrDisposition'`

- [ ] **Step 3：實作 model**

在 `backend/models.py` 的 NCMR class 結尾（`rework_requests` 關聯之後）新增關聯欄位：

```python
    dispositions = db.relationship('NcmrDisposition', backref='ncmr',
                                   cascade="all, delete-orphan")
```

並在 NCMR class 之後（`CorrectiveAction` class 之前）新增 model：

```python
class NcmrDisposition(db.Model):
    """不合格品處置明細 — 一張 NCMR 可有多筆處置（IATF 16949 §8.7）"""
    __tablename__ = '不合格品處置明細'
    __table_args__ = (
        db.Index('idx_ncmr_disp_ncmr', 'NCMR_ID'),
        db.Index('idx_ncmr_disp_risk', '是否風險項'),
    )

    id          = db.Column('識別碼',   db.Integer, primary_key=True)
    ncmr_id     = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'), nullable=False)
    disposition_type = db.Column('處置類型', db.String(20), nullable=False)
    # '矯正重工' | '報廢' | '挑選全檢' | '讓步放行'
    quantity    = db.Column('處置數量', db.Integer, nullable=False)
    handler_id  = db.Column('處置人',   db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    handled_at  = db.Column('處置時間', db.DateTime, default=datetime.utcnow)
    note        = db.Column('備註',     db.Text, nullable=True)

    # 矯正重工專屬
    rework_id   = db.Column('關聯重工單ID', db.Integer, db.ForeignKey('重工申請單.識別碼'), nullable=True)

    # 挑選全檢專屬
    pass_qty    = db.Column('合格數',   db.Integer, nullable=True)
    fail_qty    = db.Column('不合格數', db.Integer, nullable=True)

    # 讓步放行專屬
    exceed_customer_spec = db.Column('是否超出客戶規格', db.Boolean, default=False)
    auth_status     = db.Column('授權狀態',       db.String(10), nullable=True)  # '已取得' | '未取得'
    auth_doc_no     = db.Column('授權文號',       db.String(100), nullable=True)
    auth_valid_until= db.Column('授權有效期',     db.Date, nullable=True)
    auth_max_qty    = db.Column('授權數量上限',   db.Integer, nullable=True)
    unauth_reason   = db.Column('未授權放行理由', db.Text, nullable=True)
    is_risk         = db.Column('是否風險項',     db.Boolean, default=False, nullable=False)

    handler = db.relationship('Inspector', foreign_keys=[handler_id])
    rework  = db.relationship('ReworkRequest', foreign_keys=[rework_id])
```

> 注意：`datetime` 已於 `models.py` 頂部 `from datetime import date, datetime, timezone` 匯入，直接用 `datetime.utcnow`。

- [ ] **Step 4：執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5：Commit**

```bash
git add backend/models.py backend/tests/test_services/test_ncmr_disposition.py
git commit -m "feat(ncmr): 新增 NcmrDisposition 處置明細 model

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2：資料庫 Migration SQL

**Files:**
- Create: `backend/migration/20_add_ncmr_disposition.sql`

- [ ] **Step 1：撰寫 migration SQL**

建立 `backend/migration/20_add_ncmr_disposition.sql`：

```sql
-- Migration 20：新增不合格品處置明細子表（IATF 16949 §8.7）
-- 套用：psql -U postgres -d qa_database -f backend/migration/20_add_ncmr_disposition.sql

CREATE TABLE IF NOT EXISTS "不合格品處置明細" (
    "識別碼"           SERIAL PRIMARY KEY,
    "NCMR_ID"          INTEGER NOT NULL REFERENCES "不合格品單"("識別碼"),
    "處置類型"         VARCHAR(20) NOT NULL,
    "處置數量"         INTEGER NOT NULL,
    "處置人"           INTEGER REFERENCES "品管人員"("識別碼"),
    "處置時間"         TIMESTAMP DEFAULT NOW(),
    "備註"             TEXT,
    "關聯重工單ID"     INTEGER REFERENCES "重工申請單"("識別碼"),
    "合格數"           INTEGER,
    "不合格數"         INTEGER,
    "是否超出客戶規格" BOOLEAN DEFAULT FALSE,
    "授權狀態"         VARCHAR(10),
    "授權文號"         VARCHAR(100),
    "授權有效期"       DATE,
    "授權數量上限"     INTEGER,
    "未授權放行理由"   TEXT,
    "是否風險項"       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS "idx_ncmr_disp_ncmr" ON "不合格品處置明細" ("NCMR_ID");
CREATE INDEX IF NOT EXISTS "idx_ncmr_disp_risk" ON "不合格品處置明細" ("是否風險項");
```

- [ ] **Step 2：驗證 SQL 語法（不需連線資料庫，僅人工檢查）**

確認欄位名與 Task 1 model 的 `db.Column('中文名', ...)` 完全一致；外鍵指向的表名 `不合格品單`、`品管人員`、`重工申請單` 與 `models.py` 的 `__tablename__` 相符。

- [ ] **Step 3：Commit**

```bash
git add backend/migration/20_add_ncmr_disposition.sql
git commit -m "chore(ncmr): 新增處置明細子表 migration 20

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3：新增 ncmr.disposition 權限

**Files:**
- Modify: `backend/seeds/seed_roles.py`（qa_supervisor 約 23-32、qc_manager 約 34-45、admin 約 47-59）

- [ ] **Step 1：加入權限到三個授權角色**

在 `seed_roles.py` 中，於 `qa_supervisor`、`qc_manager`、`admin` 三個角色的 `permissions` dict 內，`'ncmr.edit': True,` 同行區塊新增 `'ncmr.disposition': True,`。

qa_supervisor 區塊改為：

```python
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.view': True,
            'ncmr.disposition': True,
```

qc_manager 區塊改為：

```python
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.delete': True, 'ncmr.view': True,
            'ncmr.disposition': True,
```

admin 區塊改為：

```python
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.delete': True, 'ncmr.view': True,
            'ncmr.disposition': True,
```

> `inspector` 角色**不**加此權限（呼應 Q1：處置由授權人決定）。

- [ ] **Step 2：Commit**

```bash
git add backend/seeds/seed_roles.py
git commit -m "feat(ncmr): 新增 ncmr.disposition 權限至主管以上角色

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4：處置 CRUD Service 與寫入驗證

**Files:**
- Modify: `backend/services/ncmr_service.py`（於 NCMRService class 內，`get_source_info` 之後新增方法）
- Test: `backend/tests/test_services/test_ncmr_disposition.py`

- [ ] **Step 1：寫失敗測試**

在 `test_ncmr_disposition.py` 末尾追加：

```python
from backend.services.ncmr_service import NCMRService


def test_create_disposition_scrap(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {
            '處置類型': '報廢', '處置數量': 100,
        }, handler_id=None)
        d = NcmrDisposition.query.get(did)
        assert d.disposition_type == '報廢'
        assert d.quantity == 100


def test_create_disposition_concession_unauthorized_sets_risk(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {
            '處置類型': '讓步放行', '處置數量': 100,
            '是否超出客戶規格': True, '授權狀態': '未取得',
            '未授權放行理由': '客戶急需出貨',
        }, handler_id=None)
        d = NcmrDisposition.query.get(did)
        assert d.is_risk is True


def test_create_disposition_concession_unauthorized_requires_reason(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        with pytest.raises(ValueError, match='未授權放行理由'):
            NCMRService.create_disposition(n.id, {
                '處置類型': '讓步放行', '處置數量': 100,
                '是否超出客戶規格': True, '授權狀態': '未取得',
            }, handler_id=None)


def test_create_disposition_sorting_qty_mismatch(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        with pytest.raises(ValueError, match='合格數'):
            NCMRService.create_disposition(n.id, {
                '處置類型': '挑選全檢', '處置數量': 100,
                '合格數': 60, '不合格數': 30,
            }, handler_id=None)


def test_delete_disposition(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        did = NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 100}, handler_id=None)
        NCMRService.delete_disposition(did)
        assert NcmrDisposition.query.get(did) is None
```

- [ ] **Step 2：執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -v`
Expected: FAIL — `AttributeError: type object 'NCMRService' has no attribute 'create_disposition'`

- [ ] **Step 3：實作 service 方法**

在 `backend/services/ncmr_service.py` 頂部 import 區，將 model import 補上 `NcmrDisposition`：

```python
from ..models import NCMR, CorrectiveAction, Inspector, Vendor, PatrolMain, ShippingData, ReworkRequest, ReworkExecution, NcmrDisposition
```

在 `NCMRService` class 內 `get_source_info` 方法之後新增：

```python
    # ==================================================
    # 不合格品處置（IATF 16949 §8.7）
    # ==================================================
    @staticmethod
    def _validate_disposition(data: Dict[str, Any]) -> None:
        """處置寫入驗證；不合法拋 ValueError"""
        dtype = data.get('處置類型')
        if dtype not in ('矯正重工', '報廢', '挑選全檢', '讓步放行'):
            raise ValueError(f'無效的處置類型：{dtype!r}')
        if data.get('處置數量') in (None, ''):
            raise ValueError('處置數量為必填')

        if dtype == '挑選全檢':
            pass_qty = data.get('合格數')
            fail_qty = data.get('不合格數')
            if pass_qty is not None and fail_qty is not None:
                if int(pass_qty) + int(fail_qty) != int(data['處置數量']):
                    raise ValueError('合格數 + 不合格數 必須等於處置數量')

        if dtype == '讓步放行' and data.get('是否超出客戶規格'):
            if not data.get('授權狀態'):
                raise ValueError('超出客戶規格時，授權狀態為必填')
            if data.get('授權狀態') == '未取得' and not data.get('未授權放行理由'):
                raise ValueError('未取得授權時，未授權放行理由為必填')

    @staticmethod
    def get_dispositions(ncmr_id: int) -> List[Dict[str, Any]]:
        rows = NcmrDisposition.query.filter_by(ncmr_id=ncmr_id)\
            .order_by(NcmrDisposition.id).all()
        result = []
        for d in rows:
            result.append({
                '識別碼': d.id, 'NCMR_ID': d.ncmr_id,
                '處置類型': d.disposition_type, '處置數量': d.quantity,
                '處置人': d.handler_id, '處置人姓名': d.handler.name if d.handler else '',
                '處置時間': d.handled_at.strftime('%Y-%m-%d %H:%M:%S') if d.handled_at else '',
                '備註': d.note,
                '關聯重工單ID': d.rework_id,
                '合格數': d.pass_qty, '不合格數': d.fail_qty,
                '是否超出客戶規格': d.exceed_customer_spec,
                '授權狀態': d.auth_status, '授權文號': d.auth_doc_no,
                '授權有效期': d.auth_valid_until.strftime('%Y-%m-%d') if d.auth_valid_until else '',
                '授權數量上限': d.auth_max_qty,
                '未授權放行理由': d.unauth_reason, '是否風險項': d.is_risk,
            })
        return result

    @staticmethod
    def _apply_disposition_fields(d: NcmrDisposition, data: Dict[str, Any]) -> None:
        """將輸入資料套用到處置物件（建立/更新共用）"""
        d.disposition_type = data['處置類型']
        d.quantity = int(data['處置數量'])
        d.note = data.get('備註')
        d.rework_id = data.get('關聯重工單ID') or None
        d.pass_qty = int(data['合格數']) if data.get('合格數') not in (None, '') else None
        d.fail_qty = int(data['不合格數']) if data.get('不合格數') not in (None, '') else None
        d.exceed_customer_spec = bool(data.get('是否超出客戶規格'))
        d.auth_status = data.get('授權狀態') or None
        d.auth_doc_no = data.get('授權文號') or None
        d.auth_max_qty = int(data['授權數量上限']) if data.get('授權數量上限') not in (None, '') else None
        valid = data.get('授權有效期')
        d.auth_valid_until = datetime.datetime.strptime(valid, '%Y-%m-%d').date() if valid else None
        d.unauth_reason = data.get('未授權放行理由') or None
        # 未取得授權 → 自動標記風險項
        d.is_risk = bool(d.exceed_customer_spec and d.auth_status == '未取得')

    @staticmethod
    def create_disposition(ncmr_id: int, data: Dict[str, Any], handler_id: Optional[int]) -> int:
        try:
            ncmr = NCMR.active_query().filter_by(id=ncmr_id).first()
            if not ncmr:
                raise ValueError('找不到該 NCMR')
            NCMRService._validate_disposition(data)
            d = NcmrDisposition(ncmr_id=ncmr_id, handler_id=handler_id)
            NCMRService._apply_disposition_fields(d, data)
            db.session.add(d)
            db.session.commit()
            return d.id
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def update_disposition(disposition_id: int, data: Dict[str, Any]) -> bool:
        try:
            d = NcmrDisposition.query.get(disposition_id)
            if not d:
                raise ValueError('找不到該處置記錄')
            NCMRService._validate_disposition(data)
            NCMRService._apply_disposition_fields(d, data)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete_disposition(disposition_id: int) -> bool:
        try:
            d = NcmrDisposition.query.get(disposition_id)
            if d:
                db.session.delete(d)
                db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise
```

> 注意：`ncmr_service.py` 頂部已 `import datetime`（模組），故使用 `datetime.datetime.strptime`，與既有 `update_ncmr` 寫法一致。

- [ ] **Step 4：執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -v`
Expected: PASS（全部 disposition 測試通過）

- [ ] **Step 5：Commit**

```bash
git add backend/services/ncmr_service.py backend/tests/test_services/test_ncmr_disposition.py
git commit -m "feat(ncmr): 處置 CRUD service 與寫入驗證

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5：結案 Gate（核心 IATF 邏輯）

**Files:**
- Modify: `backend/services/ncmr_service.py`（`update_ncmr` 的結案前置檢查區塊，約 157-167）
- Test: `backend/tests/test_services/test_ncmr_disposition.py`

- [ ] **Step 1：寫失敗測試**

在 `test_ncmr_disposition.py` 末尾追加：

```python
from backend.models import ReworkRequest


def _close(ncmr_id):
    return NCMRService.update_ncmr({'識別碼': ncmr_id, '狀態': '已結案'})


def test_close_blocked_without_disposition(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session)
        with pytest.raises(ValueError, match='處置'):
            _close(n.id)


def test_close_blocked_qty_mismatch(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=100)
        NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 60}, handler_id=None)
        with pytest.raises(ValueError, match='數量'):
            _close(n.id)


def test_close_ok_scrap_full_qty(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=100)
        NCMRService.create_disposition(n.id, {'處置類型': '報廢', '處置數量': 100}, handler_id=None)
        assert _close(n.id) is True
        assert NCMR.query.get(n.id).status == '已結案'


def test_close_blocked_rework_not_closed(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=50)
        rw = ReworkRequest(ncmr_id=n.id, rework_number='RW-001', status='執行中')
        db_session.add(rw)
        db_session.commit()
        NCMRService.create_disposition(n.id, {
            '處置類型': '矯正重工', '處置數量': 50, '關聯重工單ID': rw.id,
        }, handler_id=None)
        with pytest.raises(ValueError, match='重工'):
            _close(n.id)


def test_close_ok_rework_closed(app, db_session):
    with app.app_context():
        n = _make_ncmr(db_session, defect_quantity=50)
        rw = ReworkRequest(ncmr_id=n.id, rework_number='RW-002', status='已結案')
        db_session.add(rw)
        db_session.commit()
        NCMRService.create_disposition(n.id, {
            '處置類型': '矯正重工', '處置數量': 50, '關聯重工單ID': rw.id,
        }, handler_id=None)
        assert _close(n.id) is True
```

> 注意：既有 `update_ncmr` 結案檢查會先驗「關聯重工單須結案」（`rework_requests` 關聯）。本測試中重工單透過 `ncmr_id` 關聯到 NCMR，故 `test_close_blocked_rework_not_closed` 的「執行中」重工單同時會被既有檢查擋下 —— 兩道檢查都會拋 `ValueError`，測試以 `match='重工'` 通過即可。

- [ ] **Step 2：執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -k close -v`
Expected: FAIL — `test_close_blocked_without_disposition`、`test_close_blocked_qty_mismatch` 失敗（目前無 gate，會放行結案）

- [ ] **Step 3：在 update_ncmr 加入 gate**

在 `backend/services/ncmr_service.py` 的 `update_ncmr` 內，找到結案前置檢查區塊：

```python
            # 結案前置檢查
            if new_status == '已結案':
                # 若有關聯 CAPA，需確認 CAPA 已結案
                open_capas = [ca for ca in ncmr.corrective_actions
                              if ca.deleted_at is None and ca.status != '已結案']
                if open_capas:
                    raise ValueError('CAPA 尚未結案，無法將 NCMR 結案')
                # 若有關聯重工，需確認重工已完成
                open_reworks = [r for r in ncmr.rework_requests
                                if r.deleted_at is None and r.status not in ('已結案', '撤銷')]
                if open_reworks:
                    raise ValueError('尚有未結案的重工申請單，無法將 NCMR 結案')
```

在該區塊的 `if open_reworks:` 判斷之後（仍在 `if new_status == '已結案':` 內）追加：

```python
                # IATF §8.7 處置 gate
                dispositions = ncmr.dispositions
                if not dispositions:
                    raise ValueError('尚未填寫不合格品處置，無法結案')

                total_disp = sum(int(d.quantity or 0) for d in dispositions)
                defect_total = int(ncmr.defect_quantity or 0)
                if total_disp != defect_total:
                    raise ValueError(
                        f'處置數量加總（{total_disp}）與不良總數（{defect_total}）不符，無法結案'
                    )

                for d in dispositions:
                    if d.disposition_type == '矯正重工':
                        if not d.rework_id:
                            raise ValueError('矯正重工處置須關聯重工單')
                        rw = db.session.get(ReworkRequest, d.rework_id)
                        if not rw or rw.status != '已結案':
                            raise ValueError('關聯重工單尚未結案，無法將 NCMR 結案')
                    elif d.disposition_type == '挑選全檢':
                        if d.pass_qty is None or d.fail_qty is None:
                            raise ValueError('挑選全檢處置須填寫合格數與不合格數')
                    elif d.disposition_type == '讓步放行':
                        if d.exceed_customer_spec and d.auth_status == '未取得' and not d.unauth_reason:
                            raise ValueError('未授權放行須填寫未授權放行理由')
```

- [ ] **Step 4：執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -k close -v`
Expected: PASS（5 個 close 測試全通過）

- [ ] **Step 5：執行全部既有測試確認無回歸**

Run: `python -m pytest backend/tests/ -v`
Expected: 既有測試全數 PASS（特別注意 `test_state_machine.py`、`test_ncmr.py` 不受影響）

- [ ] **Step 6：Commit**

```bash
git add backend/services/ncmr_service.py backend/tests/test_services/test_ncmr_disposition.py
git commit -m "feat(ncmr): 結案 gate — 處置數量勾稽與執行完成驗證（IATF 8.7）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6：風險報表 Service 與所有處置端點

**Files:**
- Modify: `backend/services/ncmr_service.py`（新增 `get_risk_releases`）
- Modify: `backend/routes/ncmr.py`（新增處置 CRUD 與風險報表端點）
- Test: `backend/tests/test_services/test_ncmr_disposition.py`

- [ ] **Step 1：寫失敗測試（風險報表 service）**

在 `test_ncmr_disposition.py` 末尾追加：

```python
def test_risk_releases_only_returns_unauthorized(app, db_session):
    with app.app_context():
        n1 = _make_ncmr(db_session, ncmr_number='NCMR-R1', defect_quantity=10)
        n2 = _make_ncmr(db_session, ncmr_number='NCMR-R2', defect_quantity=10)
        # 風險項：超出客戶規格 + 未取得授權
        NCMRService.create_disposition(n1.id, {
            '處置類型': '讓步放行', '處置數量': 10,
            '是否超出客戶規格': True, '授權狀態': '未取得', '未授權放行理由': '趕交期',
        }, handler_id=None)
        # 非風險：一般報廢
        NCMRService.create_disposition(n2.id, {'處置類型': '報廢', '處置數量': 10}, handler_id=None)
        rows = NCMRService.get_risk_releases()
        assert len(rows) == 1
        assert rows[0]['NCMR單號'] == 'NCMR-R1'
        assert rows[0]['未授權放行理由'] == '趕交期'
```

- [ ] **Step 2：執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -k risk -v`
Expected: FAIL — `AttributeError: ... has no attribute 'get_risk_releases'`

- [ ] **Step 3：實作 get_risk_releases**

在 `backend/services/ncmr_service.py` 的 `delete_disposition` 之後新增：

```python
    @staticmethod
    def get_risk_releases() -> List[Dict[str, Any]]:
        """未授權放行清單（風險項）— IATF §8.7.1.1 風險追蹤"""
        rows = db.session.query(NcmrDisposition, NCMR)\
            .join(NCMR, NcmrDisposition.ncmr_id == NCMR.id)\
            .filter(NcmrDisposition.is_risk.is_(True))\
            .filter(NCMR.deleted_at.is_(None))\
            .order_by(NcmrDisposition.handled_at.desc())\
            .all()
        result = []
        for d, n in rows:
            result.append({
                'NCMR單號': n.ncmr_number,
                '產品資訊': n.product_info,
                '材質': n.material,
                '廠商': n.vendor,
                '處置數量': d.quantity,
                '未授權放行理由': d.unauth_reason,
                '處置人姓名': d.handler.name if d.handler else '',
                '處置時間': d.handled_at.strftime('%Y-%m-%d %H:%M:%S') if d.handled_at else '',
            })
        return result
```

- [ ] **Step 4：執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_ncmr_disposition.py -k risk -v`
Expected: PASS

- [ ] **Step 5：新增路由端點**

在 `backend/routes/ncmr.py` 的 `get_ncmr_info`（約 159-168）之後、CAPA 區段註解之前，新增：

```python
# ==================================================
# 【不合格品處置】Disposition API（IATF 16949 §8.7）
# ==================================================

@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/dispositions', methods=['GET'])
@auth_required
def get_dispositions(ncmr_id):
    try:
        return jsonify(NCMRService.get_dispositions(ncmr_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/dispositions', methods=['POST'])
@auth_required
@require_permission('ncmr.disposition')
def create_disposition(current_user, ncmr_id):
    try:
        handler_id = current_user.inspector_id if current_user else None
        did = NCMRService.create_disposition(ncmr_id, request.json or {}, handler_id)
        try:
            log_audit(current_user.id if current_user else None, 'create', 'NCMR_DISPOSITION',
                      record_id=did, new_val=request.json)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": True, "id": did})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/dispositions/<int:disposition_id>', methods=['PUT'])
@auth_required
@require_permission('ncmr.disposition')
def update_disposition(current_user, disposition_id):
    try:
        NCMRService.update_disposition(disposition_id, request.json or {})
        try:
            log_audit(current_user.id if current_user else None, 'update', 'NCMR_DISPOSITION',
                      record_id=disposition_id, new_val=request.json)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/dispositions/<int:disposition_id>', methods=['DELETE'])
@auth_required
@require_permission('ncmr.disposition')
def delete_disposition(current_user, disposition_id):
    try:
        NCMRService.delete_disposition(disposition_id)
        try:
            log_audit(current_user.id if current_user else None, 'delete', 'NCMR_DISPOSITION',
                      record_id=disposition_id)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/risk-releases', methods=['GET'])
@auth_required
def get_risk_releases():
    try:
        return jsonify(NCMRService.get_risk_releases())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

> `current_user` 是 `User` ORM 物件，其 `inspector_id` 對應 `品管人員`；以此作為處置人。

- [ ] **Step 6：執行全部後端測試**

Run: `python -m pytest backend/tests/ -v`
Expected: 全數 PASS

- [ ] **Step 7：Commit**

```bash
git add backend/services/ncmr_service.py backend/routes/ncmr.py backend/tests/test_services/test_ncmr_disposition.py
git commit -m "feat(ncmr): 處置 CRUD 與風險報表端點

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7：前端型別與 hooks

**Files:**
- Modify: `src_frontend/src/types/index.ts`（新增 interface）
- Modify: `src_frontend/src/hooks/useNCMR.ts`（新增 hooks）

- [ ] **Step 1：新增型別**

在 `src_frontend/src/types/index.ts` 末尾新增：

```typescript
// 不合格品處置明細（IATF 16949 §8.7）
export type DispositionType = '矯正重工' | '報廢' | '挑選全檢' | '讓步放行';

export interface NcmrDisposition {
    識別碼?: number;
    NCMR_ID?: number;
    處置類型: DispositionType;
    處置數量: number;
    處置人?: number | null;
    處置人姓名?: string;
    處置時間?: string;
    備註?: string | null;
    關聯重工單ID?: number | null;
    合格數?: number | null;
    不合格數?: number | null;
    是否超出客戶規格?: boolean;
    授權狀態?: '已取得' | '未取得' | null;
    授權文號?: string | null;
    授權有效期?: string | null;
    授權數量上限?: number | null;
    未授權放行理由?: string | null;
    是否風險項?: boolean;
}

export interface RiskRelease {
    NCMR單號: string;
    產品資訊: string;
    材質: string;
    廠商: string;
    處置數量: number;
    未授權放行理由: string;
    處置人姓名: string;
    處置時間: string;
}
```

- [ ] **Step 2：新增 hooks**

在 `src_frontend/src/hooks/useNCMR.ts` import 區補上型別：

```typescript
import type { NCMR, NCMRCreateInput, NCMRUpdateInput, NcmrDisposition, RiskRelease } from '../types';
```

在檔案末尾（`useCreateCAPA` 之後）新增：

```typescript
// --- 不合格品處置（IATF §8.7）---

export const useDispositions = (ncmrId: number | null) => {
    return useQuery({
        queryKey: ['ncmrDispositions', ncmrId],
        queryFn: async () => {
            if (!ncmrId) return [];
            const res = await api.get<NcmrDisposition[]>(`/ncmr/${ncmrId}/dispositions`);
            return res.data;
        },
        enabled: !!ncmrId,
    });
};

export const useCreateDisposition = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ ncmrId, data }: { ncmrId: number; data: NcmrDisposition }) => {
            const res = await api.post(`/ncmr/${ncmrId}/dispositions`, data);
            return res.data;
        },
        onSuccess: (_, variables) => {
            toast.success('已新增處置');
            queryClient.invalidateQueries({ queryKey: ['ncmrDispositions', variables.ncmrId], exact: false });
        },
    });
};

export const useUpdateDisposition = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: NcmrDisposition }) => {
            const res = await api.put(`/ncmr/dispositions/${id}`, data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('已更新處置');
            queryClient.invalidateQueries({ queryKey: ['ncmrDispositions'], exact: false });
        },
    });
};

export const useDeleteDisposition = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.delete(`/ncmr/dispositions/${id}`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('已刪除處置');
            queryClient.invalidateQueries({ queryKey: ['ncmrDispositions'], exact: false });
        },
    });
};

export const useRiskReleases = () => {
    return useQuery({
        queryKey: ['riskReleases'],
        queryFn: async () => {
            const res = await api.get<RiskRelease[]>('/ncmr/risk-releases');
            return res.data;
        },
    });
};
```

- [ ] **Step 3：型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無錯誤（若 `NCMRCreateInput`/`NCMRUpdateInput` 已存在於 types，import 不報錯）

- [ ] **Step 4：Commit**

```bash
git add src_frontend/src/types/index.ts src_frontend/src/hooks/useNCMR.ts
git commit -m "feat(ncmr): 前端處置與風險報表型別與 hooks

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8：升級 DispositionModal 為處置明細管理

**Files:**
- Modify: `src_frontend/src/components/ncmr/DispositionModal.tsx`（整體改寫）

- [ ] **Step 1：改寫元件**

將 `src_frontend/src/components/ncmr/DispositionModal.tsx` 整體改寫為處置明細管理。保留既有 props 介面與「轉開 CAPA／轉重工」按鈕，新增明細清單、數量勾稽列、依類型動態欄位、結案按鈕（勾稽未歸零時禁用）：

```tsx
import { useState } from 'react';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import type { NCMR, NcmrDisposition, DispositionType } from '../../types';
import {
    useDispositions, useCreateDisposition, useDeleteDisposition,
    useUpdateNCMR, useCreateCAPA,
} from '../../hooks/useNCMR';

interface DispositionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    item: NCMR | null;
}

const DISPOSITION_TYPES: DispositionType[] = ['矯正重工', '報廢', '挑選全檢', '讓步放行'];

const emptyForm = (): NcmrDisposition => ({
    處置類型: '報廢',
    處置數量: 0,
    是否超出客戶規格: false,
});

const DispositionModal = ({ show, handleClose, onSuccess, item }: DispositionModalProps) => {
    const ncmrId = item?.id ?? null;
    const { data: dispositions = [] } = useDispositions(show ? ncmrId : null);
    const createDisp = useCreateDisposition();
    const deleteDisp = useDeleteDisposition();
    const updateNCMR = useUpdateNCMR();
    const createCAPA = useCreateCAPA();

    const [form, setForm] = useState<NcmrDisposition>(emptyForm());

    const defectTotal = Number(item?.defect_qty ?? 0);
    const disposed = dispositions.reduce((s, d) => s + Number(d.處置數量 || 0), 0);
    const remaining = defectTotal - disposed;
    const canClose = remaining === 0 && dispositions.length > 0;

    const setField = (k: keyof NcmrDisposition, v: unknown) =>
        setForm(prev => ({ ...prev, [k]: v }));

    const handleAdd = async () => {
        if (!ncmrId) return;
        try {
            await createDisp.mutateAsync({ ncmrId, data: form });
            setForm(emptyForm());
        } catch (e) {
            console.error(e);
        }
    };

    const handleDelete = async (id?: number) => {
        if (!id) return;
        if (!window.confirm('確定刪除此處置？')) return;
        await deleteDisp.mutateAsync(id);
    };

    const handleCloseNcmr = async () => {
        if (!item) return;
        try {
            await updateNCMR.mutateAsync({ 識別碼: item.id, 狀態: '已結案' });
            onSuccess();
            handleClose();
        } catch (e) {
            console.error(e);
        }
    };

    const convertToRework = () => {
        if (!item) return;
        if (window.confirm('確定要針對此異常單開立重工申請嗎？')) {
            window.open(`/rework?ncmr_id=${item.id}&ncmr_no=${item.no || item.id}`, '_blank');
        }
    };

    const handleCreateCAPA = async () => {
        if (!item) return;
        if (!window.confirm('確定要針對此異常單開立 8D 矯正措施嗎？')) return;
        try {
            const res = await createCAPA.mutateAsync(item.id);
            const capaId = res.id;
            handleClose();
            window.location.href = `/capa?editId=${capaId}`;
        } catch (e) {
            console.error(e);
        }
    };

    const t = form.處置類型;

    return (
        <Modal show={show} onHide={handleClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>異常處置 (單號: {item?.no || item?.id})</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Alert variant={remaining === 0 ? 'success' : 'warning'}>
                    不良總數 {defectTotal}　已處置 {disposed}　未處置 {remaining}
                </Alert>

                <Table size="sm" bordered>
                    <thead>
                        <tr><th>類型</th><th>數量</th><th>風險</th><th></th></tr>
                    </thead>
                    <tbody>
                        {dispositions.map(d => (
                            <tr key={d.識別碼}>
                                <td>{d.處置類型}</td>
                                <td>{d.處置數量}</td>
                                <td>{d.是否風險項 ? <span className="text-danger">⚠ 未授權放行</span> : ''}</td>
                                <td>
                                    <Button variant="outline-danger" size="sm"
                                        onClick={() => handleDelete(d.識別碼)}>刪除</Button>
                                </td>
                            </tr>
                        ))}
                        {dispositions.length === 0 && (
                            <tr><td colSpan={4} className="text-muted text-center">尚無處置</td></tr>
                        )}
                    </tbody>
                </Table>

                <hr />
                <h6>新增處置</h6>
                <Form>
                    <div className="row g-2">
                        <div className="col-md-6">
                            <Form.Label>處置類型</Form.Label>
                            <Form.Select value={t}
                                onChange={e => setField('處置類型', e.target.value as DispositionType)}>
                                {DISPOSITION_TYPES.map(x => <option key={x} value={x}>{x}</option>)}
                            </Form.Select>
                        </div>
                        <div className="col-md-6">
                            <Form.Label>處置數量</Form.Label>
                            <Form.Control type="number" value={form.處置數量}
                                onChange={e => setField('處置數量', Number(e.target.value))} />
                        </div>
                    </div>

                    {t === '挑選全檢' && (
                        <div className="row g-2 mt-1">
                            <div className="col-md-6">
                                <Form.Label>合格數</Form.Label>
                                <Form.Control type="number" value={form.合格數 ?? ''}
                                    onChange={e => setField('合格數', Number(e.target.value))} />
                            </div>
                            <div className="col-md-6">
                                <Form.Label>不合格數</Form.Label>
                                <Form.Control type="number" value={form.不合格數 ?? ''}
                                    onChange={e => setField('不合格數', Number(e.target.value))} />
                            </div>
                        </div>
                    )}

                    {t === '讓步放行' && (
                        <div className="mt-2">
                            <Form.Check type="checkbox" label="超出客戶規格"
                                checked={!!form.是否超出客戶規格}
                                onChange={e => setField('是否超出客戶規格', e.target.checked)} />
                            {form.是否超出客戶規格 && (
                                <>
                                    <Form.Label className="mt-2">授權狀態</Form.Label>
                                    <Form.Select value={form.授權狀態 ?? ''}
                                        onChange={e => setField('授權狀態', e.target.value)}>
                                        <option value="">請選擇</option>
                                        <option value="已取得">已取得客戶授權</option>
                                        <option value="未取得">未取得授權</option>
                                    </Form.Select>
                                    {form.授權狀態 === '已取得' && (
                                        <div className="row g-2 mt-1">
                                            <div className="col-md-4">
                                                <Form.Label>授權文號</Form.Label>
                                                <Form.Control value={form.授權文號 ?? ''}
                                                    onChange={e => setField('授權文號', e.target.value)} />
                                            </div>
                                            <div className="col-md-4">
                                                <Form.Label>有效期</Form.Label>
                                                <Form.Control type="date" value={form.授權有效期 ?? ''}
                                                    onChange={e => setField('授權有效期', e.target.value)} />
                                            </div>
                                            <div className="col-md-4">
                                                <Form.Label>數量上限</Form.Label>
                                                <Form.Control type="number" value={form.授權數量上限 ?? ''}
                                                    onChange={e => setField('授權數量上限', Number(e.target.value))} />
                                            </div>
                                        </div>
                                    )}
                                    {form.授權狀態 === '未取得' && (
                                        <div className="mt-1">
                                            <Form.Label className="text-danger">未授權放行理由（將標記為風險項）</Form.Label>
                                            <Form.Control as="textarea" rows={2}
                                                value={form.未授權放行理由 ?? ''}
                                                onChange={e => setField('未授權放行理由', e.target.value)} />
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}

                    <Form.Label className="mt-2">備註</Form.Label>
                    <Form.Control as="textarea" rows={1} value={form.備註 ?? ''}
                        onChange={e => setField('備註', e.target.value)} />

                    <Button className="mt-2" variant="success" size="sm"
                        onClick={handleAdd} disabled={createDisp.isPending}>新增此處置</Button>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <div className="d-flex w-100 justify-content-between">
                    <div>
                        <Button variant="warning" size="sm" className="me-1"
                            onClick={handleCreateCAPA}>轉開 CAPA</Button>
                        <Button variant="info" size="sm" onClick={convertToRework}>轉重工</Button>
                    </div>
                    <Button variant="primary" onClick={handleCloseNcmr}
                        disabled={!canClose || updateNCMR.isPending}>
                        結案（{canClose ? '可結案' : '處置未完成'}）
                    </Button>
                </div>
            </Modal.Footer>
        </Modal>
    );
};

export default DispositionModal;
```

> 矯正重工的「關聯重工單」以既有「轉重工」按鈕開單流程處理；本 modal 不內嵌重工單下拉（避免相依重工查詢 hook，YAGNI）。若需關聯既有重工單，於備註填單號，後續可擴充。

- [ ] **Step 2：Lint 與型別檢查**

Run: `cd src_frontend && npm run lint && npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 3：建置確認**

Run: `cd src_frontend && npm run build`
Expected: build 成功

- [ ] **Step 4：Commit**

```bash
git add src_frontend/src/components/ncmr/DispositionModal.tsx
git commit -m "feat(ncmr): DispositionModal 升級為處置明細管理與結案 gate

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9：風險報表頁與路由

**Files:**
- Create: `src_frontend/src/pages/ncmr/RiskReleasePage.tsx`
- Modify: `src_frontend/src/App.tsx`（新增路由）

- [ ] **Step 1：建立頁面**

建立 `src_frontend/src/pages/ncmr/RiskReleasePage.tsx`：

```tsx
import { Table, Card, Spinner } from 'react-bootstrap';
import { useRiskReleases } from '../../hooks/useNCMR';

const RiskReleasePage = () => {
    const { data = [], isLoading } = useRiskReleases();

    return (
        <Card className="m-3">
            <Card.Header>
                <h5 className="mb-0">未授權放行風險清單（IATF 16949 §8.7.1.1）</h5>
                <small className="text-muted">超出客戶規格但未取得客戶授權即放行的記錄</small>
            </Card.Header>
            <Card.Body>
                {isLoading ? <Spinner animation="border" /> : (
                    <Table bordered hover responsive size="sm">
                        <thead>
                            <tr>
                                <th>NCMR單號</th><th>產品資訊</th><th>材質</th><th>廠商</th>
                                <th>處置數量</th><th>未授權放行理由</th><th>處置人</th><th>處置時間</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((r, i) => (
                                <tr key={i}>
                                    <td>{r.NCMR單號}</td>
                                    <td>{r.產品資訊}</td>
                                    <td>{r.材質}</td>
                                    <td>{r.廠商}</td>
                                    <td>{r.處置數量}</td>
                                    <td className="text-danger">{r.未授權放行理由}</td>
                                    <td>{r.處置人姓名}</td>
                                    <td>{r.處置時間}</td>
                                </tr>
                            ))}
                            {data.length === 0 && (
                                <tr><td colSpan={8} className="text-center text-muted">無風險放行記錄</td></tr>
                            )}
                        </tbody>
                    </Table>
                )}
            </Card.Body>
        </Card>
    );
};

export default RiskReleasePage;
```

- [ ] **Step 2：加入路由**

在 `src_frontend/src/App.tsx` 中，依既有受保護路由的寫法（參考既有 `ncmr` 相關 `<Route>`），加入：

```tsx
import RiskReleasePage from './pages/ncmr/RiskReleasePage';
```

並在 `<ProtectedRoute>` 包裹的路由群組內，仿照既有 NCMR 路由格式新增一條（路徑 `/ncmr/risk-releases`）：

```tsx
<Route path="/ncmr/risk-releases" element={<RiskReleasePage />} />
```

> 實作時請先讀 `App.tsx` 確認既有 `<Route>` 的精確包裹結構（是否在 layout 內、是否需 `element={<ProtectedRoute>...`），照同樣格式插入。側邊欄連結為選配，可於 `components/Sidebar.tsx` 比照既有 NCMR 連結新增一條指向 `/ncmr/risk-releases`。

- [ ] **Step 3：Lint、型別、建置**

Run: `cd src_frontend && npm run lint && npx tsc --noEmit && npm run build`
Expected: 全部成功

- [ ] **Step 4：Commit**

```bash
git add src_frontend/src/pages/ncmr/RiskReleasePage.tsx src_frontend/src/App.tsx
git commit -m "feat(ncmr): 未授權放行風險報表頁

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10：整合驗證

**Files:** 無（驗證用）

- [ ] **Step 1：後端全測試**

Run: `python -m pytest backend/tests/ -v`
Expected: 全數 PASS

- [ ] **Step 2：前端建置與 lint**

Run: `cd src_frontend && npm run lint && npm run build`
Expected: 全數成功

- [ ] **Step 3：套用 migration 與重新種入角色權限（實機環境）**

Run:
```bash
psql -U postgres -d qa_database -f backend/migration/20_add_ncmr_disposition.sql
python -m backend.seeds.seed_roles
```
Expected: 子表建立、角色權限更新（含 `ncmr.disposition`）

- [ ] **Step 4：手動煙霧測試（依 CLAUDE.md 於 venv 啟動後端、`npm run dev` 啟動前端）**

驗證流程：
1. 以 qa_supervisor 以上帳號登入，開啟某 NCMR 的處置 modal。
2. 新增「報廢」處置，數量 < 不良總數 → 結案鈕禁用、勾稽列顯示未處置數。
3. 補足處置使加總 = 不良總數 → 結案鈕啟用 → 結案成功。
4. 新增「讓步放行」+ 超出客戶規格 + 未取得授權 + 填理由 → 清單顯示 ⚠ 風險標記。
5. 開啟 `/ncmr/risk-releases` → 該筆出現於風險清單。

Expected: 行為與上述一致。

---

## 完成準則

- 後端：`NcmrDisposition` model、migration、處置 CRUD、結案 gate、風險報表，全部測試通過。
- 前端：處置明細管理 modal、風險報表頁，build/lint 通過。
- IATF §8.7 / §8.7.1.1 缺口（處置結構化、數量勾稽、結案 gate、未授權放行追蹤）獲得補強。
