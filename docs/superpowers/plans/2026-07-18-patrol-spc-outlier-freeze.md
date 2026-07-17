# 巡檢 SPC 擴充：離群值排除與管制界限凍結 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把出貨（shipping）模組已完成的 AIAG-VDA SPC 2026 兩項合規功能——§6.6 離群值標示/排除、§9.4 管制界限凍結/解除凍結——擴充到巡檢（patrol）SPC 頁面。

**Architecture:** 巡檢的量測明細（`PatrolDetail`：group+item+position+min_val+max_val）與出貨的量測明細（`ShippingMeasurement`：編號樣本）結構不同，因此離群值標示無法直接重用出貨的 API/元件，需另建一套（`get_patrol_details`/`set_patrol_detail_exclusion`、`PatrolOutlierManagerModal`）。管制界限凍結則重用既有的 `SpcControlLimit` 資料表（已預留 `資料來源` 欄位區分 shipping/patrol），但巡檢多一個「位置」維度（前/中/後段），需新增欄位並擴充唯一鍵。兩者都整合進 `PatrolService.get_spc`，比照 `ShippingService.get_stats` 的既有模式（`skip_frozen_limits` 參數、`excluded_count`/`limits_frozen` 回傳欄位）。前端沿用已泛用化的 `SpcChartData`/`SpcDashboardPanel`（`excluded_count`/`limits_frozen` 已是可選欄位，無需改型別），只需在 `PatrolCharts.tsx` 加上與 `ShippingCharts.tsx` 對稱的操作 UI。

**重要差異（與出貨模組相比）：**
- 巡檢 `get_spc` **沒有** SPCCache 快取層，因此不需要處理 `_invalidate_spc_cache` 這類快取失效問題。
- 巡檢的「特性識別鍵」是 `(材質, 規格, 項目, 位置)`，**不含廠商**——因為 `get_spc` 現有的公差查詢本來就未使用 `customer_id`/vendor_id（呼叫 `ToleranceService.check_tolerance` 時固定傳 `'vendor_id': ''`）。凍結界限的鍵沿用這個既有行為，不引入新的廠商維度。
- `SpcControlLimit.source` 欄位已存在且已用來區分 `'shipping'`/`'patrol'`，新增的「位置」欄位對 shipping 那批既有資料一律是空字串（DB 預設值），**不需要修改 `shipping_service.py`**——`source` 本身已完全區隔兩邊資料，位置欄位對 shipping 只是恆為空字串的多餘維度，不影響其唯一性語意。

**Tech Stack:** Flask 3.1 + SQLAlchemy（後端）、React 19 + TypeScript + TanStack Query（前端）、PostgreSQL 16（raw SQL migration）。

**測試指令：**
- 後端：`cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_patrol.py tests/test_services/test_spc_control_limits.py tests/test_permission_gating.py -v`
- 前端：`cd src_frontend && npx vitest run src/components/spc/PatrolOutlierManagerModal.test.tsx src/components/patrol/PatrolCharts.test.tsx`
- 全量驗證：`cd backend && venv/Scripts/python.exe -m pytest tests -q` 與 `cd src_frontend && npm run build && npm run lint && npm test`

---

## Task 1: Migration 35 + 資料模型欄位

**Files:**
- Create: `backend/migration/35_add_patrol_spc_columns.sql`
- Modify: `backend/models.py:116-124`（`PatrolDetail`）
- Modify: `backend/models.py:256-277`（`SpcControlLimit`）

- [ ] **Step 1: 建立 migration SQL**

```sql
-- backend/migration/35_add_patrol_spc_columns.sql
-- 巡檢 SPC 合規擴充：
--   §6.6 離群值排除（巡檢子檔量測明細）
--   §9.4 管制界限凍結新增「位置」維度（巡檢特有的前/中/後段，出貨無此維度固定為空字串）

ALTER TABLE "巡檢子檔" ADD COLUMN IF NOT EXISTS "排除統計" BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "巡檢子檔" ADD COLUMN IF NOT EXISTS "排除原因" VARCHAR(200);

ALTER TABLE "SPC管制界限" ADD COLUMN IF NOT EXISTS "位置" VARCHAR(20) NOT NULL DEFAULT '';
ALTER TABLE "SPC管制界限" DROP CONSTRAINT IF EXISTS uq_spc_limits;
ALTER TABLE "SPC管制界限" ADD CONSTRAINT uq_spc_limits UNIQUE ("資料來源","廠商","材質","規格","量測項目","位置");
```

- [ ] **Step 2: 更新 `PatrolDetail` 模型**

`backend/models.py:116-124` 現況：

```python
class PatrolDetail(db.Model):
    __tablename__ = '巡檢子檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    main_id = db.Column('主檔ID', db.Integer, db.ForeignKey('巡檢主檔.識別碼'))
    group = db.Column('組別', db.Integer)
    item = db.Column('測量項目', db.String)
    position = db.Column('測量位置', db.String)
    min_val = db.Column('最小值', db.Numeric)
    max_val = db.Column('最大值', db.Numeric)
```

改為：

```python
class PatrolDetail(db.Model):
    __tablename__ = '巡檢子檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    main_id = db.Column('主檔ID', db.Integer, db.ForeignKey('巡檢主檔.識別碼'))
    group = db.Column('組別', db.Integer)
    item = db.Column('測量項目', db.String)
    position = db.Column('測量位置', db.String)
    min_val = db.Column('最小值', db.Numeric)
    max_val = db.Column('最大值', db.Numeric)
    # §6.6 離群值：標示無效並保留追溯，不得刪除；排除於統計計算之外
    excluded         = db.Column('排除統計', db.Boolean, default=False, nullable=False)
    exclusion_reason = db.Column('排除原因', db.String(200), nullable=True)
```

- [ ] **Step 3: 更新 `SpcControlLimit` 模型**

`backend/models.py:256-277` 現況（節錄關鍵欄位）：

```python
class SpcControlLimit(db.Model):
    """SPC 管制界限凍結檔 — §9.4 界限經確認後凍結，重算須留紀錄"""
    __tablename__ = 'SPC管制界限'
    __table_args__ = (
        db.UniqueConstraint('資料來源', '廠商', '材質', '規格', '量測項目', name='uq_spc_limits'),
    )
    id         = db.Column('識別碼', db.Integer, primary_key=True)
    source     = db.Column('資料來源', db.String(20), nullable=False, default='shipping')
    vendor     = db.Column('廠商', db.String(100), nullable=False, default='')
    material   = db.Column('材質', db.String(100), nullable=False, default='')
    spec       = db.Column('規格', db.String(100), nullable=False, default='')
    field      = db.Column('量測項目', db.String(30), nullable=False)
    x_cl       = db.Column('X中心線', db.Numeric(14, 6), nullable=False)
```

改為（新增 `position` 欄位並擴充唯一鍵）：

```python
class SpcControlLimit(db.Model):
    """SPC 管制界限凍結檔 — §9.4 界限經確認後凍結，重算須留紀錄"""
    __tablename__ = 'SPC管制界限'
    __table_args__ = (
        db.UniqueConstraint('資料來源', '廠商', '材質', '規格', '量測項目', '位置', name='uq_spc_limits'),
    )
    id         = db.Column('識別碼', db.Integer, primary_key=True)
    source     = db.Column('資料來源', db.String(20), nullable=False, default='shipping')
    vendor     = db.Column('廠商', db.String(100), nullable=False, default='')
    material   = db.Column('材質', db.String(100), nullable=False, default='')
    spec       = db.Column('規格', db.String(100), nullable=False, default='')
    field      = db.Column('量測項目', db.String(30), nullable=False)
    # 巡檢特有的位置維度（前/中/後段）；出貨無此維度，恆為空字串
    position   = db.Column('位置', db.String(20), nullable=False, default='')
    x_cl       = db.Column('X中心線', db.Numeric(14, 6), nullable=False)
```

（其餘欄位 `x_ucl`…`updated_at` 不變，僅在 `field` 與 `x_cl` 之間插入 `position`。）

- [ ] **Step 4: 對正式資料庫套用 migration**

repo 根目錄執行（讀取 `.env` 的 DB 連線資訊，psql CLI 未安裝，改用 psycopg2）：

```python
# 暫存腳本，執行後可刪除
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(
    host=os.environ['DB_HOST'], port=os.environ['DB_PORT'],
    dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
)
with conn, conn.cursor() as cur:
    cur.execute(open('backend/migration/35_add_patrol_spc_columns.sql', encoding='utf-8').read())
print("migration 35 完成")
```

執行後以 `information_schema` 查詢驗證（不可只信任「無錯誤」）：

```sql
SELECT column_name FROM information_schema.columns WHERE table_name = '巡檢子檔' AND column_name IN ('排除統計','排除原因');
SELECT column_name FROM information_schema.columns WHERE table_name = 'SPC管制界限' AND column_name = '位置';
SELECT conname FROM pg_constraint WHERE conname = 'uq_spc_limits';
```

Expected: 前兩個查詢各回傳對應欄位，第三個查詢回傳 `uq_spc_limits`（確認舊約束已被新約束取代，而非殘留兩個）。

- [ ] **Step 5: Commit**

```bash
git add backend/migration/35_add_patrol_spc_columns.sql backend/models.py
git commit -m "巡檢SPC:新增量測明細離群排除欄位與管制界限位置維度(migration 35)"
```

---

## Task 2: 巡檢離群值管理 service 方法

**Files:**
- Modify: `backend/services/patrol_service.py`（新增方法，置於 `get_spc` 之後、`get_detail` 之前）
- Test: `backend/tests/test_services/test_patrol.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/test_services/test_patrol.py` 檔案末尾新增：

```python
def test_get_patrol_details_returns_all_rows_with_exclusion_status(app, db_session):
    """取得單筆巡檢記錄的全部量測明細，含各筆的排除狀態"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.8, max_val=10.2
        ))
        db_session.commit()

        details = PatrolService.get_patrol_details(patrol.id)
        assert len(details) == 1
        assert details[0]['測量項目'] == '外徑'
        assert details[0]['最小值'] == pytest.approx(9.8)
        assert details[0]['排除統計'] is False
        assert details[0]['排除原因'] is None


def test_set_patrol_detail_exclusion_requires_reason(app, db_session):
    """標示離群值時，未填原因應拋出 ValueError（§6.6）"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        detail = PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.8, max_val=10.2
        )
        db_session.add(detail)
        db_session.commit()

        with pytest.raises(ValueError, match='原因'):
            PatrolService.set_patrol_detail_exclusion(detail.id, excluded=True, reason='')


def test_set_patrol_detail_exclusion_round_trips(app, db_session):
    """標示離群後可恢復計入，恢復時清除排除原因"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        detail = PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.8, max_val=10.2
        )
        db_session.add(detail)
        db_session.commit()

        result = PatrolService.set_patrol_detail_exclusion(detail.id, excluded=True, reason='量測儀器故障')
        assert result['排除統計'] is True
        assert result['排除原因'] == '量測儀器故障'

        result = PatrolService.set_patrol_detail_exclusion(detail.id, excluded=False, reason='')
        assert result['排除統計'] is False
        assert result['排除原因'] is None


def test_set_patrol_detail_exclusion_raises_for_missing_id(app, db_session):
    with app.app_context():
        with pytest.raises(ValueError, match='不存在'):
            PatrolService.set_patrol_detail_exclusion(999999, excluded=True, reason='測試')
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_patrol.py -k exclusion -v`
Expected: FAIL（`AttributeError: type object 'PatrolService' has no attribute 'get_patrol_details'`）

- [ ] **Step 3: 實作 service 方法**

於 `backend/services/patrol_service.py` 的 `get_spc` 方法結尾（`return {...}` 之後）與 `get_detail` 之間插入：

```python
    @staticmethod
    def get_patrol_details(main_id: int) -> List[Dict[str, Any]]:
        """取得單筆巡檢記錄的全部量測明細（供離群值管理 UI）"""
        rows = PatrolDetail.query.filter_by(main_id=main_id).order_by(
            PatrolDetail.item, PatrolDetail.group, PatrolDetail.position
        ).all()
        return [{
            "識別碼": d.id, "組別": d.group, "測量項目": d.item, "測量位置": d.position,
            "最小值": float(d.min_val) if d.min_val is not None else None,
            "最大值": float(d.max_val) if d.max_val is not None else None,
            "排除統計": d.excluded, "排除原因": d.exclusion_reason,
        } for d in rows]

    @staticmethod
    def set_patrol_detail_exclusion(detail_id: int, excluded: bool, reason: Optional[str]) -> Dict[str, Any]:
        """標示/解除巡檢量測明細離群排除（§6.6：不刪除、保留追溯、排除統計）"""
        d = db.session.get(PatrolDetail, detail_id)
        if d is None:
            raise ValueError("量測明細不存在")
        if excluded and not (reason or "").strip():
            raise ValueError("標示離群值必須填寫原因（§6.6）")
        d.excluded = excluded
        d.exclusion_reason = (reason or "").strip() or None if excluded else None
        db.session.commit()
        return {"id": d.id, "排除統計": d.excluded, "排除原因": d.exclusion_reason}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_patrol.py -k exclusion -v`
Expected: 全 PASS（4 項）

- [ ] **Step 5: Commit**

```bash
git add backend/services/patrol_service.py backend/tests/test_services/test_patrol.py
git commit -m "巡檢SPC:離群值標示/排除 service 方法(§6.6)"
```

---

## Task 3: 巡檢管制界限凍結 service 方法

**Files:**
- Modify: `backend/services/patrol_service.py`（新增於 class 開頭 `get_options` 之前）
- Test: `backend/tests/test_services/test_spc_control_limits.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/test_services/test_spc_control_limits.py` 檔案末尾新增（先確認檔案頂部已 `import pytest` 與匯入 `PatrolService`；若尚未匯入則加上 `from backend.services.patrol_service import PatrolService`）：

```python
def test_patrol_get_frozen_limits_returns_none_when_absent(app, db_session):
    with app.app_context():
        assert PatrolService.get_frozen_limits({
            "material": "6061", "spec": "10*2", "item": "外徑", "position": ""
        }) is None


def test_patrol_freeze_and_unfreeze_control_limits_round_trip(app, db_session):
    with app.app_context():
        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        PatrolService.freeze_control_limits(key, limits, note="製程確認穩定")
        frozen = PatrolService.get_frozen_limits(key)
        assert frozen is not None
        assert frozen["x_cl"] == pytest.approx(10.0)
        assert frozen["note"] == "製程確認穩定"

        PatrolService.unfreeze_control_limits(key)
        assert PatrolService.get_frozen_limits(key) is None


def test_patrol_freeze_control_limits_is_scoped_by_position(app, db_session):
    """同一材質/規格/項目但位置不同時，凍結界限互不影響（巡檢特有的位置維度）"""
    with app.app_context():
        key_front = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        key_mid = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "中段"}
        limits_front = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}
        limits_mid = {"x_cl": 20.0, "x_ucl": 20.9, "x_lcl": 19.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        PatrolService.freeze_control_limits(key_front, limits_front)
        PatrolService.freeze_control_limits(key_mid, limits_mid)

        assert PatrolService.get_frozen_limits(key_front)["x_cl"] == pytest.approx(10.0)
        assert PatrolService.get_frozen_limits(key_mid)["x_cl"] == pytest.approx(20.0)


def test_patrol_and_shipping_control_limits_do_not_collide(app, db_session):
    """相同材質/規格/項目時，巡檢與出貨的凍結界限彼此獨立（source 欄位區隔）"""
    with app.app_context():
        from backend.services.shipping_service import ShippingService

        shipping_key = {"vendor": "", "material": "6061", "spec": "10*2", "field": "外徑"}
        patrol_key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": ""}
        limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}
        limits_patrol = {"x_cl": 50.0, "x_ucl": 50.9, "x_lcl": 49.1, "r_cl": 0.5, "r_ucl": 1.2, "r_lcl": 0, "avg_n": 5}

        ShippingService.freeze_control_limits(shipping_key, limits)
        PatrolService.freeze_control_limits(patrol_key, limits_patrol)

        assert ShippingService.get_frozen_limits(shipping_key)["x_cl"] == pytest.approx(10.0)
        assert PatrolService.get_frozen_limits(patrol_key)["x_cl"] == pytest.approx(50.0)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_spc_control_limits.py -k patrol -v`
Expected: FAIL（`AttributeError: type object 'PatrolService' has no attribute 'get_frozen_limits'`）

- [ ] **Step 3: 實作 service 方法**

於 `backend/services/patrol_service.py` 的 `class PatrolService:` 宣告之後、`get_options` 方法之前插入：

```python
    @staticmethod
    def _limits_key_filter(key: Dict[str, str]):
        from ..models import SpcControlLimit
        return SpcControlLimit.query.filter_by(
            source='patrol',
            vendor='',
            material=key.get('material') or '',
            spec=key.get('spec') or '',
            field=key['item'],
            position=key.get('position') or '',
        )

    @staticmethod
    def get_frozen_limits(key: Dict[str, str]) -> Optional[Dict[str, float]]:
        """查詢巡檢是否已凍結管制界限（§9.4）；若無則回傳 None。"""
        rec = PatrolService._limits_key_filter(key).first()
        if rec is None:
            return None
        return {
            "x_cl": float(rec.x_cl), "x_ucl": float(rec.x_ucl), "x_lcl": float(rec.x_lcl),
            "r_cl": float(rec.r_cl), "r_ucl": float(rec.r_ucl), "r_lcl": float(rec.r_lcl),
            "avg_n": rec.avg_n, "note": rec.note,
            "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
        }

    @staticmethod
    def freeze_control_limits(key: Dict[str, str], limits: Dict[str, float], note: str = "") -> Dict[str, Any]:
        """凍結巡檢目前管制界限（§9.4）：確認後鎖定，避免每次請求都重新計算。"""
        from ..models import SpcControlLimit
        rec = PatrolService._limits_key_filter(key).first()
        if rec is None:
            rec = SpcControlLimit(
                source='patrol', vendor='',
                material=key.get('material') or '', spec=key.get('spec') or '',
                field=key['item'], position=key.get('position') or '',
            )
            db.session.add(rec)
        rec.x_cl, rec.x_ucl, rec.x_lcl = limits["x_cl"], limits["x_ucl"], limits["x_lcl"]
        rec.r_cl, rec.r_ucl, rec.r_lcl = limits["r_cl"], limits["r_ucl"], limits.get("r_lcl", 0)
        rec.avg_n = limits.get("avg_n", 5)
        rec.note = note
        db.session.commit()
        return {"X中心線": float(rec.x_cl), "識別碼": rec.id}

    @staticmethod
    def unfreeze_control_limits(key: Dict[str, str]) -> None:
        """解除巡檢管制界限凍結（§9.4）：恢復每次請求自動重新計算。"""
        PatrolService._limits_key_filter(key).delete()
        db.session.commit()

```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_spc_control_limits.py -v`
Expected: 全 PASS（含既有出貨測試與新增的 4 項巡檢測試）

- [ ] **Step 5: Commit**

```bash
git add backend/services/patrol_service.py backend/tests/test_services/test_spc_control_limits.py
git commit -m "巡檢SPC:管制界限凍結/解除凍結 service 方法(§9.4)"
```

---

## Task 4: `get_spc` 整合離群排除與管制界限凍結

**Files:**
- Modify: `backend/services/patrol_service.py:1-29`（import 區塊）
- Modify: `backend/services/patrol_service.py:52-247`（`get_spc` 方法全文）
- Test: `backend/tests/test_services/test_patrol.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/test_services/test_patrol.py` 檔案末尾新增：

```python
def test_get_spc_excludes_marked_outlier_from_stats(app, db_session):
    """標示為離群的量測明細應排除於統計計算之外，並反映於 excluded_count"""
    with app.app_context():
        for i in range(6):
            patrol = PatrolMain(date=date(2026, 1, i + 1), material='6061', spec='10*2')
            db_session.add(patrol)
            db_session.flush()
            db_session.add(PatrolDetail(
                main_id=patrol.id, group=1, item='外徑', position='前段',
                min_val=9.9, max_val=10.1
            ))
        db_session.commit()

        baseline = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert baseline['excluded_count'] == 0
        assert len(baseline['avgs']) == 6

        target_detail = PatrolDetail.query.join(PatrolMain).filter(
            PatrolMain.date == date(2026, 1, 1)
        ).first()
        PatrolService.set_patrol_detail_exclusion(target_detail.id, excluded=True, reason='量測異常')

        result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert result['excluded_count'] == 1
        assert len(result['avgs']) == 5


def test_get_spc_applies_frozen_limits(app, db_session):
    """管制界限凍結後，get_spc 回傳的界限應為凍結值而非重新計算值"""
    with app.app_context():
        for i in range(6):
            patrol = PatrolMain(date=date(2026, 1, i + 1), material='6061', spec='10*2')
            db_session.add(patrol)
            db_session.flush()
            db_session.add(PatrolDetail(
                main_id=patrol.id, group=1, item='外徑', position='前段',
                min_val=9.9 + i * 0.05, max_val=10.1 + i * 0.05
            ))
        db_session.commit()

        result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert result['limits_frozen'] is False

        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        PatrolService.freeze_control_limits(key, {
            "x_cl": 99.0, "x_ucl": 100.0, "x_lcl": 98.0,
            "r_cl": 1.0, "r_ucl": 2.0, "r_lcl": 0, "avg_n": 2,
        })

        frozen_result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert frozen_result['limits_frozen'] is True
        assert frozen_result['x_cl'] == pytest.approx(99.0)

        skip_result = PatrolService.get_spc(
            {'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'},
            skip_frozen_limits=True,
        )
        assert skip_result['x_cl'] != pytest.approx(99.0)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_patrol.py -k "excludes_marked or applies_frozen" -v`
Expected: FAIL（`excluded_count`/`limits_frozen` 鍵不存在，或 `TypeError: get_spc() got an unexpected keyword argument 'skip_frozen_limits'`）

- [ ] **Step 3: 修改 import 區塊**

`backend/services/patrol_service.py:1-29` 現況：

```python
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import func, text
from sqlalchemy.orm import selectinload
from ..extensions import db
from ..models import PatrolMain, PatrolDetail, Machine, Operator, Inspector, Vendor
from .extrusion_tolerance_service import ExtrusionToleranceService
from .spc_analysis_service import (
    calculate_control_limits,
    calculate_cpk_trend,
    calculate_distribution_stats,
    calculate_process_capability,
)
from .spc_distribution import assess_distribution
from .spc_stability import evaluate_stability
from .patrol_excel_utils import (
    build_patrol_measurements_from_row,
    copy_spc_workbook_sheets,
    sanitize_sheet_name,
)
from ..utils import (
    bounded_int,
    format_value,
    validate_excel_shape,
    validate_patrol_data,
    handle_db_error
)
```

新增一行 `from .spc_constants import SPC_CONSTANTS`（供凍結界限套用時重算 `d2`）：

```python
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import func, text
from sqlalchemy.orm import selectinload
from ..extensions import db
from ..models import PatrolMain, PatrolDetail, Machine, Operator, Inspector, Vendor
from .extrusion_tolerance_service import ExtrusionToleranceService
from .spc_analysis_service import (
    calculate_control_limits,
    calculate_cpk_trend,
    calculate_distribution_stats,
    calculate_process_capability,
)
from .spc_constants import SPC_CONSTANTS
from .spc_distribution import assess_distribution
from .spc_stability import evaluate_stability
from .patrol_excel_utils import (
    build_patrol_measurements_from_row,
    copy_spc_workbook_sheets,
    sanitize_sheet_name,
)
from ..utils import (
    bounded_int,
    format_value,
    validate_excel_shape,
    validate_patrol_data,
    handle_db_error
)
```

- [ ] **Step 4: 取代 `get_spc` 方法全文**

將 `backend/services/patrol_service.py:52-247` 的完整 `get_spc` 方法（含函式簽名到 `return {...}` 結尾）取代為：

```python
    @staticmethod
    def get_spc(args: Dict[str, Any], skip_frozen_limits: bool = False) -> Dict[str, Any]:
        """獲取巡檢 SPC 統計數據（含公差界限、製程能力、分佈統計）

        skip_frozen_limits: 內部專用（凍結路由呼叫時使用），略過凍結界限套用，
        確保取得的是依目前資料即時重新計算的數值，不受既有凍結值影響（§9.4）。
        不對外部 API 參數開放。
        """
        item = args.get('item', '厚度')
        pos = args.get('pos', '')
        material = args.get('mat', '')
        spec = args.get('spec', '')

        # --- 1. 公差查詢 ---
        tolerance_limits = {"USL": None, "LSL": None, "found": False}
        char_class = "其他"
        if material:
            try:
                from ..services.tolerance_service import ToleranceService

                tol_result = ToleranceService.check_tolerance({
                    'material': material,
                    'spec': spec or '',
                    'vendor_id': ''
                })

                if tol_result.get('found'):
                    tolerance_limits["found"] = True
                    nominal_from_spec = {}
                    if spec:
                        s = str(spec).strip().replace('×', '*').replace('x', '*').replace('X', '*')
                        while '**' in s: s = s.replace('**', '*')
                        parts = s.split('*')
                        try:
                            nums = [float(p.strip()) for p in parts if p.strip()]
                            if len(nums) >= 2:
                                nominal_from_spec['外徑'] = nums[0]
                                val2 = nums[1]
                                if val2 < (nums[0] / 2):
                                    nominal_from_spec['厚度'] = val2
                                    nominal_from_spec['內徑'] = nums[0] - (val2 * 2)
                                else:
                                    nominal_from_spec['內徑'] = val2
                                    nominal_from_spec['厚度'] = (nums[0] - val2) / 2
                                if len(nums) >= 3:
                                    nominal_from_spec['長度'] = nums[2]
                            elif len(nums) == 1:
                                nominal_from_spec['外徑'] = nums[0]
                        except (ValueError, TypeError):
                            pass

                    for t in tol_result.get('tolerances', []):
                        if t.get('項目') == item:
                            char_class = t.get('特性重要度') or "其他"
                            tolerance_limits["公差下限"] = t.get('公差下限')
                            tolerance_limits["公差上限"] = t.get('公差上限')
                            tolerance_limits["尺寸下限"] = t.get('尺寸下限')
                            tolerance_limits["尺寸上限"] = t.get('尺寸上限')

                            dim_min = t.get('尺寸下限')
                            dim_max = t.get('尺寸上限')
                            if dim_min is not None and dim_max is not None:
                                tolerance_limits["LSL"] = dim_min
                                tolerance_limits["USL"] = dim_max
                            else:
                                tol_min = t.get('公差下限')
                                tol_max = t.get('公差上限')
                                std = t.get('標準值')
                                if std is None and item in nominal_from_spec:
                                    std = nominal_from_spec[item]
                                if tol_min is not None and tol_max is not None and std is not None:
                                    tolerance_limits["LSL"] = std - abs(tol_min)
                                    tolerance_limits["USL"] = std + abs(tol_max)
                            break
            except Exception:
                pass

        # --- 2. 資料查詢 ---
        query = db.session.query(
            PatrolMain.date, PatrolDetail.main_id, PatrolDetail.group,
            PatrolDetail.min_val, PatrolDetail.max_val, PatrolDetail.excluded,
        ).join(PatrolDetail).filter(PatrolDetail.item == item)

        if pos:
            query = query.filter(PatrolDetail.position == pos)
        if args.get('s_date'):
            query = query.filter(PatrolMain.date >= args['s_date'])
        if args.get('e_date'):
            query = query.filter(PatrolMain.date <= args['e_date'])
        if args.get('m_id'):
            query = query.filter(PatrolMain.machine_id == args['m_id'])
        if args.get('op_id'):
            query = query.filter(PatrolMain.operator_id == args['op_id'])
        if args.get('cust_id'):
            query = query.filter(PatrolMain.customer_id == args['cust_id'])
        if material:
            query = query.filter(PatrolMain.material.like(f"%{material}%"))
        if spec:
            query = query.filter(PatrolMain.spec.like(f"%{spec}%"))

        query = query.order_by(PatrolMain.date.asc(), PatrolDetail.group.asc())
        rows = query.all()

        if not rows:
            return {"labels": [], "avgs": [], "ranges": []}

        # --- 3. 分組聚合（排除標示為離群的量測值，§6.6）---
        from collections import OrderedDict
        groups: Dict[str, List[float]] = OrderedDict()
        group_dates: Dict[str, str] = {}
        group_ids: Dict[str, int] = {}
        excluded_count = 0

        for r in rows:
            val1 = r[3]
            val2 = r[4]
            if val1 is None or val2 is None:
                continue
            if r[5]:
                excluded_count += 1
                continue

            date_str = r[0].strftime('%m/%d') if hasattr(r[0], 'strftime') else str(r[0])
            full_date = r[0].strftime('%Y-%m-%d') if hasattr(r[0], 'strftime') else str(r[0])
            key = f"{date_str}-#{r[1]}-G{r[2]}"

            try:
                fv1, fv2 = float(val1), float(val2)
                groups.setdefault(key, []).extend([fv1, fv2])
                group_dates[key] = full_date
                group_ids[key] = r[1]
            except ValueError:
                continue

        labels = list(groups.keys())
        avgs = []
        ranges_list = []
        subgroup_sizes = []
        all_values = []
        ids_valid = []
        dates_valid = []

        for k in labels:
            vals = groups[k]
            avgs.append(float(np.mean(vals)))
            ranges_list.append(float(np.ptp(vals)))
            subgroup_sizes.append(len(vals))
            all_values.extend(vals)
            ids_valid.append(str(group_ids[k]))
            dates_valid.append(group_dates[k])

        # --- 4. SPC 統計計算 ---
        control_limits = calculate_control_limits(avgs, ranges_list, subgroup_sizes)
        usl = tolerance_limits.get("USL")
        lsl = tolerance_limits.get("LSL")

        # 管制界限凍結（§9.4）：若已凍結，套用凍結值取代重新計算的結果
        limits_frozen = False
        if not skip_frozen_limits:
            frozen = PatrolService.get_frozen_limits({
                "material": material, "spec": spec, "item": item, "position": pos,
            })
            limits_frozen = frozen is not None
            if limits_frozen:
                control_limits.update({k: frozen[k] for k in
                    ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl", "avg_n")})
                # d2 須對應凍結當下的子組大小，避免 sigma_within = r_cl/d2
                # 混用「凍結的 r_cl」與「目前資料的 avg_n 所查到的 d2」
                frozen_avg_n = max(2, min(10, int(frozen["avg_n"])))
                control_limits["d2"] = SPC_CONSTANTS[frozen_avg_n][3]

        # 穩定性判定（§9.2.2）— 決定回報能力(C)或績效(P)指數
        stability = evaluate_stability(
            avgs,
            control_limits["x_cl"],
            control_limits["x_ucl"],
            control_limits["x_lcl"],
        )
        # 分布評估僅算一次（MLE 擬合成本高），供能力計算與分布統計共用
        dist = assess_distribution(all_values, field=item)
        process_capability = calculate_process_capability(
            avgs,
            all_values,
            control_limits["r_cl"],
            control_limits["d2"],
            tolerance_limits,
            include_reason=False,
            stability=stability,
            characteristic_class=char_class,
            field=item,
            dist=dist,
        )
        distribution_stats = calculate_distribution_stats(all_values, field=item, dist=dist)
        cpk_trend = calculate_cpk_trend(all_values, dates_valid, subgroup_sizes, usl, lsl)

        return {
            "labels": labels,
            "ids": ids_valid,
            "dates": dates_valid,
            "avgs": [float(x) for x in avgs],
            "ranges": [float(x) for x in ranges_list],
            "subgroup_sizes": subgroup_sizes,
            "all_values": [round(v, 4) for v in all_values],
            "x_cl": control_limits["x_cl"],
            "x_ucl": control_limits["x_ucl"],
            "x_lcl": control_limits["x_lcl"],
            "r_cl": control_limits["r_cl"],
            "r_ucl": control_limits["r_ucl"],
            "r_lcl": control_limits["r_lcl"],
            "avg_subgroup_size": control_limits["avg_n"] if len(avgs) >= 5 else 5,
            "tolerance": tolerance_limits,
            "process_capability": process_capability,
            "distribution_stats": distribution_stats,
            "cpk_trend": cpk_trend,
            "stability": stability,
            "characteristic_class": char_class,
            "excluded_count": excluded_count,
            "limits_frozen": limits_frozen,
        }
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_services/test_patrol.py tests/test_services/test_spc_control_limits.py -v`
Expected: 全 PASS

- [ ] **Step 6: 跑受影響的整合測試（export_excel 依賴 get_spc）**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_patrol_excel_utils.py -q`
Expected: PASS（`get_spc` 回傳結構新增鍵不影響既有 Excel 匯出邏輯，因為 `SpcReportService.generate_report` 讀取欄位皆用 `.get()`）

- [ ] **Step 7: Commit**

```bash
git add backend/services/patrol_service.py backend/tests/test_services/test_patrol.py
git commit -m "巡檢SPC:get_spc整合離群排除與管制界限凍結(§6.6,§9.4)"
```

---

## Task 5: 離群值與管制界限 API 路由

**Files:**
- Modify: `backend/routes/patrol.py`
- Test: `backend/tests/test_permission_gating.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/test_permission_gating.py` 檔案末尾新增（沿用檔案既有的 `_make_user`/`_headers` helper）：

```python
@pytest.fixture
def patrol_roles(db_session):
    """patrol_editor 具備 patrol.edit；patrol_viewer 僅有 patrol.view。"""
    db_session.add(Role(code='patrol_editor', name='巡檢可編輯',
                        permissions={'patrol.edit': True, 'patrol.view': True}))
    db_session.add(Role(code='patrol_viewer', name='巡檢唯讀',
                        permissions={'patrol.view': True}))
    db_session.commit()


def test_patrol_exclusion_route_requires_patrol_edit_permission(client, db_session, patrol_roles):
    from backend.models import PatrolMain, PatrolDetail
    from datetime import date

    patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
    db_session.add(patrol)
    db_session.flush()
    detail = PatrolDetail(main_id=patrol.id, group=1, item='外徑', position='前段', min_val=9.8, max_val=10.2)
    db_session.add(detail)
    db_session.commit()

    viewer = _make_user(db_session, 'patrol_viewer1', 'patrol_viewer')
    resp = client.patch(f'/api/patrol-details/{detail.id}/exclusion',
                         headers=_headers(viewer), json={'排除統計': True, '排除原因': '測試'})
    assert resp.status_code == 403

    editor = _make_user(db_session, 'patrol_editor1', 'patrol_editor')
    resp = client.patch(f'/api/patrol-details/{detail.id}/exclusion',
                         headers=_headers(editor), json={'排除統計': True, '排除原因': '測試'})
    assert resp.status_code != 403


def test_patrol_control_limits_routes_require_patrol_edit_permission(client, db_session, patrol_roles):
    viewer = _make_user(db_session, 'patrol_viewer2', 'patrol_viewer')
    body = {'material': '6061', 'spec': '10*2', 'item': '外徑', 'position': ''}

    resp = client.post('/api/patrol/control-limits', headers=_headers(viewer), json=body)
    assert resp.status_code == 403

    resp = client.delete(
        '/api/patrol/control-limits?material=6061&spec=10*2&item=外徑&position=',
        headers=_headers(viewer),
    )
    assert resp.status_code == 403

    # GET（查詢）不受權限限制，僅需登入
    resp = client.get(
        '/api/patrol/control-limits?material=6061&spec=10*2&item=外徑&position=',
        headers=_headers(viewer),
    )
    assert resp.status_code != 403
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_permission_gating.py -k patrol -v`
Expected: FAIL（404，路由尚不存在）

- [ ] **Step 3: 新增路由**

於 `backend/routes/patrol.py` 的 `patrol_detail` 路由（`/api/patrol/detail/<int:id>`）之後插入：

```python
@patrol_bp.route('/api/patrol/<int:main_id>/details', methods=['GET'])
@auth_required
def get_patrol_details_route(main_id):
    """取得單筆巡檢記錄的量測明細（含離群標記）"""
    try:
        return jsonify(PatrolService.get_patrol_details(main_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol-details/<int:detail_id>/exclusion', methods=['PATCH'])
@auth_required
@require_perm('patrol.edit')
def set_patrol_detail_exclusion_route(detail_id):
    """標示/解除巡檢量測明細離群排除（AIAG-VDA SPC 2026 §6.6）"""
    try:
        body = request.get_json(silent=True) or {}
        result = PatrolService.set_patrol_detail_exclusion(
            detail_id,
            excluded=bool(body.get('排除統計')),
            reason=body.get('排除原因'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/control-limits', methods=['GET'])
@auth_required
def get_patrol_control_limits_route():
    """查詢巡檢管制界限凍結狀態（AIAG-VDA SPC 2026 §9.4）"""
    try:
        key = {
            "material": request.args.get('material', ''),
            "spec": request.args.get('spec', ''),
            "item": request.args.get('item', '外徑'),
            "position": request.args.get('position', ''),
        }
        return jsonify(PatrolService.get_frozen_limits(key) or {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/control-limits', methods=['POST'])
@auth_required
@require_perm('patrol.edit')
def freeze_patrol_control_limits_route():
    """凍結巡檢目前管制界限（AIAG-VDA SPC 2026 §9.4）"""
    try:
        body = request.get_json(silent=True) or {}
        key = {
            "material": body.get('material', ''),
            "spec": body.get('spec', ''),
            "item": body.get('item', '外徑'),
            "position": body.get('position', ''),
        }
        # skip_frozen_limits=True：即使此 key 已凍結，也要取得依目前資料重新計算
        # 的數值，避免「重新凍結」只是把舊的凍結值原封不動寫回去（§9.4）
        stats = PatrolService.get_spc(
            {'mat': key['material'], 'spec': key['spec'], 'item': key['item'], 'pos': key['position']},
            skip_frozen_limits=True,
        )
        limits = {k: stats[k] for k in ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl")}
        limits["avg_n"] = stats.get("avg_subgroup_size", 5)
        result = PatrolService.freeze_control_limits(key, limits, note=body.get('note', ''))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/control-limits', methods=['DELETE'])
@auth_required
@require_perm('patrol.edit')
def unfreeze_patrol_control_limits_route():
    """解除巡檢管制界限凍結（AIAG-VDA SPC 2026 §9.4）"""
    try:
        key = {
            "material": request.args.get('material', ''),
            "spec": request.args.get('spec', ''),
            "item": request.args.get('item', '外徑'),
            "position": request.args.get('position', ''),
        }
        PatrolService.unfreeze_control_limits(key)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_permission_gating.py -v`
Expected: 全 PASS（含既有 pyrometry 測試與新增的 2 項巡檢測試）

- [ ] **Step 5: Commit**

```bash
git add backend/routes/patrol.py backend/tests/test_permission_gating.py
git commit -m "巡檢SPC:離群值與管制界限凍結API路由(patrol.edit權限保護)"
```

---

## Task 6: 前端 `usePatrol.ts` hooks

**Files:**
- Modify: `src_frontend/src/hooks/usePatrol.ts`

- [ ] **Step 1: 新增型別與 hooks**

於 `src_frontend/src/hooks/usePatrol.ts` 檔案末尾（`useImportPatrol` 之後）新增：

```typescript
// --- 離群值管理（AIAG-VDA SPC 2026 §6.6）---

export interface PatrolDetailItem {
    識別碼: number;
    組別: number;
    測量項目: string;
    測量位置: string;
    最小值: number | null;
    最大值: number | null;
    排除統計: boolean;
    排除原因: string | null;
}

export const usePatrolDetails = (mainId: number | null) =>
    useQuery<PatrolDetailItem[]>({
        queryKey: ['patrol-details', mainId],
        queryFn: async () => (await api.get(`/patrol/${mainId}/details`)).data,
        enabled: mainId != null,
    });

export const useSetPatrolDetailExclusion = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (p: { id: number; excluded: boolean; reason: string }) =>
            (await api.patch(`/patrol-details/${p.id}/exclusion`, { 排除統計: p.excluded, 排除原因: p.reason })).data,
        onSuccess: (_data, variables) => {
            toast.success(variables.excluded ? '已標示為離群值' : '已恢復計入統計');
            queryClient.invalidateQueries({ queryKey: ['patrol-details'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
        },
        onError: (err: Error) => {
            toast.error(`操作失敗：${err.message}`);
        },
    });
};

// --- 管制界限凍結（AIAG-VDA SPC 2026 §9.4）---

export interface PatrolControlLimitsKey {
    material: string;
    spec: string;
    item: string;
    position: string;
}

export const useFreezePatrolLimits = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (key: PatrolControlLimitsKey & { note?: string }) =>
            (await api.post('/patrol/control-limits', key)).data,
        onSuccess: () => {
            toast.success('管制界限已凍結');
            queryClient.invalidateQueries({ queryKey: ['patrol-control-limits'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
        },
        onError: (err: Error) => {
            toast.error(`凍結失敗：${err.message}`);
        },
    });
};

export const useUnfreezePatrolLimits = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (key: PatrolControlLimitsKey) => {
            const params = new URLSearchParams({
                material: key.material, spec: key.spec, item: key.item, position: key.position,
            });
            return (await api.delete(`/patrol/control-limits?${params.toString()}`)).data;
        },
        onSuccess: () => {
            toast.success('已解除管制界限凍結');
            queryClient.invalidateQueries({ queryKey: ['patrol-control-limits'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
        },
        onError: (err: Error) => {
            toast.error(`解除失敗：${err.message}`);
        },
    });
};
```

- [ ] **Step 2: 型別檢查**

Run: `cd src_frontend && npx tsc -b --noEmit`
Expected: 無錯誤

- [ ] **Step 3: Commit**

```bash
git add src_frontend/src/hooks/usePatrol.ts
git commit -m "巡檢SPC:前端離群值與管制界限凍結hooks"
```

---

## Task 7: `PatrolOutlierManagerModal.tsx`

**Files:**
- Create: `src_frontend/src/components/spc/PatrolOutlierManagerModal.tsx`
- Test: `src_frontend/src/components/spc/PatrolOutlierManagerModal.test.tsx`

- [ ] **Step 1: 寫失敗測試**

```typescript
// src_frontend/src/components/spc/PatrolOutlierManagerModal.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PatrolOutlierManagerModal from './PatrolOutlierManagerModal';
import * as usePatrolHooks from '../../hooks/usePatrol';

vi.mock('../../hooks/usePatrol', async () => {
    const actual = await vi.importActual('../../hooks/usePatrol');
    return { ...actual, usePatrolDetails: vi.fn(), useSetPatrolDetailExclusion: vi.fn() };
});

const renderWithClient = (ui: React.ReactElement) => {
    const client = new QueryClient();
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
};

describe('PatrolOutlierManagerModal', () => {
    const mutate = vi.fn();

    beforeEach(() => {
        mutate.mockClear();
        vi.mocked(usePatrolHooks.usePatrolDetails).mockReturnValue({
            data: [{
                識別碼: 1, 組別: 1, 測量項目: '外徑', 測量位置: '前段',
                最小值: 9.8, 最大值: 10.2, 排除統計: false, 排除原因: null,
            }],
            isLoading: false,
        } as never);
        vi.mocked(usePatrolHooks.useSetPatrolDetailExclusion).mockReturnValue({
            mutate, isPending: false,
        } as never);
    });

    it('顯示量測明細列表', () => {
        renderWithClient(<PatrolOutlierManagerModal mainId={123} show onHide={() => {}} />);
        expect(screen.getByText('外徑')).toBeInTheDocument();
        expect(screen.getByText('9.8 / 10.2')).toBeInTheDocument();
        expect(screen.getByText('計入統計')).toBeInTheDocument();
    });

    it('未填原因時無法標示離群', () => {
        renderWithClient(<PatrolOutlierManagerModal mainId={123} show onHide={() => {}} />);
        const btn = screen.getByRole('button', { name: '標示離群' });
        expect(btn).toBeDisabled();
    });

    it('填寫原因後可標示離群', async () => {
        renderWithClient(<PatrolOutlierManagerModal mainId={123} show onHide={() => {}} />);
        const input = screen.getByPlaceholderText('離群原因（必填）');
        fireEvent.change(input, { target: { value: '量測儀器故障' } });
        const btn = screen.getByRole('button', { name: '標示離群' });
        await waitFor(() => expect(btn).not.toBeDisabled());
        fireEvent.click(btn);
        expect(mutate).toHaveBeenCalledWith(
            { id: 1, excluded: true, reason: '量測儀器故障' },
            expect.anything(),
        );
    });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run src/components/spc/PatrolOutlierManagerModal.test.tsx`
Expected: FAIL（模組不存在）

- [ ] **Step 3: 實作元件**

```tsx
// src_frontend/src/components/spc/PatrolOutlierManagerModal.tsx
import { useState } from 'react';
import { Alert, Badge, Button, Form, Modal, Table } from 'react-bootstrap';
import { useSetPatrolDetailExclusion, usePatrolDetails } from '../../hooks/usePatrol';

interface PatrolOutlierManagerModalProps {
    mainId: number | null;
    show: boolean;
    onHide: () => void;
}

/** 巡檢離群值管理（AIAG-VDA SPC 2026 §6.6）：標示無效、保留追溯、排除統計，不得刪除 */
const PatrolOutlierManagerModal = ({ mainId, show, onHide }: PatrolOutlierManagerModalProps) => {
    const { data: details = [], isLoading } = usePatrolDetails(show ? mainId : null);
    const setExclusion = useSetPatrolDetailExclusion();
    const [reasons, setReasons] = useState<Record<number, string>>({});

    const toggle = (id: number, currentlyExcluded: boolean) => {
        const reason = reasons[id] ?? '';
        if (!currentlyExcluded && !reason.trim()) return; // 標示離群必填原因
        setExclusion.mutate({ id, excluded: !currentlyExcluded, reason }, {
            // 成功後清除本地暫存原因，避免下次排除時誤用舊原因造成追溯紀錄錯誤
            onSuccess: () => setReasons(prev => {
                const next = { ...prev };
                delete next[id];
                return next;
            }),
        });
    };

    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>離群值管理（巡檢記錄 #{mainId}）</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Alert variant="info" className="small py-2">
                    依 AIAG-VDA SPC 手冊 §6.6：離群值不得刪除，標示後保留於資料庫供追溯，
                    但排除於管制圖與能力指數計算之外。標示時必須填寫原因。
                </Alert>
                {isLoading ? <div className="text-center py-3">載入中…</div> : (
                    <Table size="sm" bordered hover>
                        <thead className="table-light text-center">
                            <tr><th>項目</th><th>組別</th><th>位置</th><th>量測值</th><th>狀態</th><th>原因</th><th></th></tr>
                        </thead>
                        <tbody>
                            {details.map(d => (
                                <tr key={d.識別碼} className={d.排除統計 ? 'table-secondary' : ''}>
                                    <td>{d.測量項目}</td>
                                    <td className="text-center">{d.組別}</td>
                                    <td className="text-center">{d.測量位置 || '—'}</td>
                                    <td className="text-center">
                                        {d.最小值 != null ? `${d.最小值} / ${d.最大值}` : '—'}
                                    </td>
                                    <td className="text-center">
                                        {d.排除統計
                                            ? <Badge bg="secondary">已排除</Badge>
                                            : <Badge bg="success">計入統計</Badge>}
                                    </td>
                                    <td>
                                        {d.排除統計 ? (d.排除原因 || '') : (
                                            <Form.Control size="sm" placeholder="離群原因（必填）"
                                                value={reasons[d.識別碼] ?? ''}
                                                onChange={e => setReasons(prev => ({ ...prev, [d.識別碼]: e.target.value }))} />
                                        )}
                                    </td>
                                    <td className="text-center">
                                        <Button size="sm"
                                            variant={d.排除統計 ? 'outline-success' : 'outline-danger'}
                                            disabled={setExclusion.isPending || (!d.排除統計 && !(reasons[d.識別碼] ?? '').trim())}
                                            onClick={() => toggle(d.識別碼, d.排除統計)}>
                                            {d.排除統計 ? '恢復計入' : '標示離群'}
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Modal.Body>
        </Modal>
    );
};

export default PatrolOutlierManagerModal;
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd src_frontend && npx vitest run src/components/spc/PatrolOutlierManagerModal.test.tsx`
Expected: 全 PASS（3 項）

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/spc/PatrolOutlierManagerModal.tsx src_frontend/src/components/spc/PatrolOutlierManagerModal.test.tsx
git commit -m "巡檢SPC:新增離群值管理Modal(§6.6)"
```

---

## Task 8: `PatrolCharts.tsx` 整合 UI

**Files:**
- Modify: `src_frontend/src/components/patrol/PatrolCharts.tsx`
- Test: `src_frontend/src/components/patrol/PatrolCharts.test.tsx`（若不存在則新建）

- [ ] **Step 1: 檢查既有測試檔是否 mock 了 `usePatrol` hooks**

Run: `cd src_frontend && ls src/components/patrol/PatrolCharts.test.tsx 2>&1 || echo "不存在"`

若檔案存在且有 `vi.mock('../../hooks/usePatrol', ...)`，需在該 mock 中補上 `usePatrolDetails`、`useSetPatrolDetailExclusion`、`useFreezePatrolLimits`、`useUnfreezePatrolLimits` 的回傳值（否則元件內無條件呼叫這些 hooks 會讓既有測試因 mock 缺漏而拋錯）。若檔案不存在，執行下一步建立新檔。

- [ ] **Step 2: 寫/補充測試**

在 `src_frontend/src/components/patrol/PatrolCharts.test.tsx`（若無則新建，並仿照 `src_frontend/src/components/shipping/ShippingCharts.test.tsx` 的 mock 慣例）新增：

```typescript
// 若為新建檔案，補上必要的 import 與既有 mock（usePatrolStats/useExportPatrolSpcReport）
// 以下僅列出本次新增/需要的 mock 與測試案例

vi.mock('../../hooks/usePatrol', async () => {
    const actual = await vi.importActual('../../hooks/usePatrol');
    return {
        ...actual,
        usePatrolStats: vi.fn(),
        useExportPatrolSpcReport: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
        useFreezePatrolLimits: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
        useUnfreezePatrolLimits: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
    };
});

it('顯示管制界限凍結狀態徽章與操作按鈕', () => {
    vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({
        data: { ...baseStatsData, limits_frozen: true },
    } as never);
    render(<PatrolCharts {...defaultProps} />);
    expect(screen.getByText('管制界限已凍結')).toBeInTheDocument();
});

it('未凍結時顯示逐次重算徽章', () => {
    vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({
        data: { ...baseStatsData, limits_frozen: false },
    } as never);
    render(<PatrolCharts {...defaultProps} />);
    expect(screen.getByText('界限逐次重算中')).toBeInTheDocument();
});

it('離群值管理按鈕於未選擇記錄時停用', () => {
    vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({ data: baseStatsData } as never);
    render(<PatrolCharts {...defaultProps} />);
    expect(screen.getByRole('button', { name: '離群值管理' })).toBeDisabled();
});
```

（`baseStatsData`/`defaultProps` 需依照該測試檔既有的資料結構補齊，至少包含 `ids`、`dates`、`labels`、`avgs`、`ranges`、`x_cl`/`x_ucl`/`x_lcl`/`r_cl`/`r_ucl`/`r_lcl` 等 `SpcChartData` 必要欄位。）

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run src/components/patrol/PatrolCharts.test.tsx`
Expected: FAIL（找不到「管制界限已凍結」等文字，或「離群值管理」按鈕不存在）

- [ ] **Step 4: 修改 `PatrolCharts.tsx`**

`src_frontend/src/components/patrol/PatrolCharts.tsx` 現況的 import 區塊與元件開頭：

```tsx
import { useMemo, useState } from 'react';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import { buildSpcChartModel } from '../../utils/spcChartModel';
import SpcDashboardPanel from '../spc/SpcDashboardPanel';
import { Button, Form } from 'react-bootstrap';
import { useExportPatrolSpcReport, usePatrolStats } from '../../hooks/usePatrol';
import type { SpcChartData } from '../../types';
```

改為：

```tsx
import { useMemo, useState } from 'react';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import { buildSpcChartModel } from '../../utils/spcChartModel';
import SpcDashboardPanel from '../spc/SpcDashboardPanel';
import PatrolOutlierManagerModal from '../spc/PatrolOutlierManagerModal';
import { Badge, Button, Form } from 'react-bootstrap';
import {
    useExportPatrolSpcReport, usePatrolStats,
    useFreezePatrolLimits, useUnfreezePatrolLimits,
} from '../../hooks/usePatrol';
import type { SpcChartData } from '../../types';
```

元件本體（`PatrolCharts` 函式）現況：

```tsx
const PatrolCharts = ({ machine, operator, customer, material, spec, startDate, endDate, onEditPoint, statsItem, statsPos, onItemChange, onPosChange }: PatrolChartsProps) => {
    const exportSpcReport = useExportPatrolSpcReport();
    const [showSpecLimits, setShowSpecLimits] = useState(false);

    // 匯出 SPC 報告（含原始數據 + SPC 統計與圖表）
    const handleExportSpc = () => {
        exportSpcReport.mutate({
            s_date: startDate,
            e_date: endDate,
            m_id: machine,
            op_id: operator,
            cust_id: customer,
            mat: material,
            spec,
            item: statsItem,
            pos: statsPos
        });
    };

    const { data: statsData } = usePatrolStats({
        item: statsItem,
        pos: statsPos,
        m_id: machine,
        op_id: operator,
        cust_id: customer,
        mat: material,
        spec: spec,
        s_date: startDate,
        e_date: endDate
    });

    const spcModel = useMemo(
        () => buildSpcChartModel(statsData as SpcChartData | null | undefined, { showSpecLimits }),
        [statsData, showSpecLimits]
    );
```

改為：

```tsx
const PatrolCharts = ({ machine, operator, customer, material, spec, startDate, endDate, onEditPoint, statsItem, statsPos, onItemChange, onPosChange }: PatrolChartsProps) => {
    const exportSpcReport = useExportPatrolSpcReport();
    const [showSpecLimits, setShowSpecLimits] = useState(false);
    const [outlierTargetId, setOutlierTargetId] = useState<number | null>(null);
    const [selectedRecordId, setSelectedRecordId] = useState('');

    // 匯出 SPC 報告（含原始數據 + SPC 統計與圖表）
    const handleExportSpc = () => {
        exportSpcReport.mutate({
            s_date: startDate,
            e_date: endDate,
            m_id: machine,
            op_id: operator,
            cust_id: customer,
            mat: material,
            spec,
            item: statsItem,
            pos: statsPos
        });
    };

    const { data: statsData } = usePatrolStats({
        item: statsItem,
        pos: statsPos,
        m_id: machine,
        op_id: operator,
        cust_id: customer,
        mat: material,
        spec: spec,
        s_date: startDate,
        e_date: endDate
    });

    const typedStatsData = statsData as SpcChartData | null | undefined;
    const controlLimitsKey = { material, spec, item: statsItem, position: statsPos };
    const freezeLimits = useFreezePatrolLimits();
    const unfreezeLimits = useUnfreezePatrolLimits();

    const spcModel = useMemo(
        () => buildSpcChartModel(typedStatsData, { showSpecLimits }),
        [typedStatsData, showSpecLimits]
    );

    // 記錄選單需去重：同一巡檢主檔可能對應多個組別，ids 陣列會重複同一 main_id
    const recordOptions = useMemo(() => {
        const seen = new Set<string>();
        const opts: { id: string; date?: string }[] = [];
        spcModel.ids.forEach((id, i) => {
            if (seen.has(id)) return;
            seen.add(id);
            opts.push({ id, date: typedStatsData?.dates?.[i] });
        });
        return opts;
    }, [spcModel.ids, typedStatsData]);
```

`return` 區塊現況：

```tsx
    return (
        <div className="mt-4">
            <div className="d-flex align-items-center justify-content-between mb-3">
                <div className="d-flex align-items-center">
                    <h4 className="mb-0 me-3">SPC 監控與分析</h4>
                    <Form.Select
                        className="me-2"
                        style={{ width: 'auto' }}
                        value={statsPos}
                        onChange={e => onPosChange(e.target.value)}
                    >
                        <option value="">全段</option>
                        {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                    </Form.Select>
                    <Form.Select
                        style={{ width: 'auto' }}
                        value={statsItem}
                        onChange={e => onItemChange(e.target.value)}
                    >
                        {ITEMS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}
                    </Form.Select>
                    <Form.Check
                        type="switch"
                        id="show-spec-limits"
                        className="ms-3"
                        label="疊加規格界限（分析模式）"
                        checked={showSpecLimits}
                        onChange={e => setShowSpecLimits(e.target.checked)}
                    />
                </div>
                <Button variant="outline-success" onClick={handleExportSpc} disabled={exportSpcReport.isPending}>
                    <i className="bi bi-file-earmark-bar-graph"></i> {exportSpcReport.isPending ? '匯出中...' : '匯出 SPC 報告'}
                </Button>
            </div>

            <SpcDashboardPanel
                model={spcModel}
                statsItem={statsItem}
                emptyMessage={`選擇的檢驗項目「${statsItem}」沒有足夠的數據來產生 SPC 圖表，請嘗試其他檢驗項目或區段。`}
                sampleCount={statsData?.all_values?.length ?? 0}
                onEditPoint={onEditPoint}
                filterXBarLegendLabels
            />
        </div>
    );
};
```

改為：

```tsx
    return (
        <div className="mt-4">
            <div className="d-flex align-items-center justify-content-between mb-3">
                <div className="d-flex align-items-center">
                    <h4 className="mb-0 me-3">SPC 監控與分析</h4>
                    <Form.Select
                        className="me-2"
                        style={{ width: 'auto' }}
                        value={statsPos}
                        onChange={e => onPosChange(e.target.value)}
                    >
                        <option value="">全段</option>
                        {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                    </Form.Select>
                    <Form.Select
                        style={{ width: 'auto' }}
                        value={statsItem}
                        onChange={e => onItemChange(e.target.value)}
                    >
                        {ITEMS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}
                    </Form.Select>
                    <Form.Check
                        type="switch"
                        id="show-spec-limits"
                        className="ms-3"
                        label="疊加規格界限（分析模式）"
                        checked={showSpecLimits}
                        onChange={e => setShowSpecLimits(e.target.checked)}
                    />
                </div>
                <div className="d-flex align-items-center gap-2">
                    <Form.Select
                        size="sm"
                        style={{ width: 'auto' }}
                        value={selectedRecordId}
                        onChange={e => setSelectedRecordId(e.target.value)}
                        disabled={recordOptions.length === 0}
                    >
                        <option value="">選擇記錄以管理離群值…</option>
                        {recordOptions.map(o => (
                            <option key={o.id} value={o.id}>#{o.id}{o.date ? ` · ${o.date}` : ''}</option>
                        ))}
                    </Form.Select>
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        disabled={!selectedRecordId}
                        onClick={() => setOutlierTargetId(Number(selectedRecordId))}
                    >
                        離群值管理
                    </Button>
                    {typedStatsData?.limits_frozen
                        ? <Badge bg="info">管制界限已凍結</Badge>
                        : <Badge bg="light" text="dark">界限逐次重算中</Badge>}
                    <Button size="sm" variant="outline-primary"
                        disabled={freezeLimits.isPending || !spcModel.chartData}
                        onClick={() => freezeLimits.mutate(controlLimitsKey)}>
                        凍結目前界限
                    </Button>
                    <Button size="sm" variant="outline-secondary"
                        disabled={unfreezeLimits.isPending || !typedStatsData?.limits_frozen}
                        onClick={() => unfreezeLimits.mutate(controlLimitsKey)}>
                        解除凍結
                    </Button>
                    <Button variant="outline-success" onClick={handleExportSpc} disabled={exportSpcReport.isPending}>
                        <i className="bi bi-file-earmark-bar-graph"></i> {exportSpcReport.isPending ? '匯出中...' : '匯出 SPC 報告'}
                    </Button>
                </div>
            </div>

            <SpcDashboardPanel
                model={spcModel}
                statsItem={statsItem}
                emptyMessage={`選擇的檢驗項目「${statsItem}」沒有足夠的數據來產生 SPC 圖表，請嘗試其他檢驗項目或區段。`}
                sampleCount={statsData?.all_values?.length ?? 0}
                onEditPoint={onEditPoint}
                filterXBarLegendLabels
            />

            <PatrolOutlierManagerModal
                mainId={outlierTargetId}
                show={outlierTargetId != null}
                onHide={() => setOutlierTargetId(null)}
            />
        </div>
    );
};
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd src_frontend && npx vitest run src/components/patrol/PatrolCharts.test.tsx`
Expected: 全 PASS

- [ ] **Step 6: 執行全部前端測試確認無回歸**

Run: `cd src_frontend && npx tsc -b --noEmit && npx vitest run`
Expected: tsc 無錯誤，所有測試 PASS

- [ ] **Step 7: Commit**

```bash
git add src_frontend/src/components/patrol/PatrolCharts.tsx src_frontend/src/components/patrol/PatrolCharts.test.tsx
git commit -m "巡檢SPC:PatrolCharts整合離群值管理與管制界限凍結UI"
```

---

## Task 9: 全面驗證

- [ ] **Step 1: 後端全量測試**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests -q`
Expected: 全 PASS

- [ ] **Step 2: 前端全量**

Run: `cd src_frontend && npm run build && npm run lint && npm test`
Expected: build/lint/test 全過

- [ ] **Step 3: 端對端手動驗證（開發環境）**

1. 啟動後端（venv）`cd backend && venv/Scripts/python.exe -m flask --app backend.app:app run --port 5001`、前端 `cd src_frontend && node node_modules/vite/bin/vite.js`（vite dev proxy 預設指向 :80 生產後端，驗證時需暫改 `src_frontend/vite.config.ts` 的 proxy target 為 `http://127.0.0.1:5001`，驗證後改回）。
2. 巡檢頁面選擇材質/規格與檢驗項目（如「外徑」）：確認 SPC 卡片正常顯示（與先前出貨驗證一致的能力指標卡片）。
3. 從「選擇記錄以管理離群值…」下拉選單選一筆記錄 → 點擊「離群值管理」→ 標示一筆量測明細為離群（需填原因）→ 關閉 Modal → 確認統計數字改變（樣本數/直方圖樣本數減少）→ 恢復計入 → 確認數字復原。
4. 點擊「凍結目前界限」→ 確認徽章顯示「管制界限已凍結」→ 點擊「解除凍結」→ 確認恢復「界限逐次重算中」。
5. 匯出 SPC Excel：確認研究資訊區塊正常產生（沿用 Task 18 已完成的 `SpcReportService`，此步驟僅驗證巡檢資料路徑無例外）。
6. 驗證完畢後將 `vite.config.ts` 的 proxy target 改回 `http://127.0.0.1:80`。

- [ ] **Step 4: 最終 commit**

```bash
git add -A
git commit -m "巡檢SPC擴充完成:離群值排除與管制界限凍結全面驗證通過(§6.6,§9.4)"
```

---

## Self-Review 紀錄

- **規格覆蓋**：離群值標示/排除（§6.6，Task 1/2/4/5/6/7/8）、管制界限凍結/解除凍結（§9.4，Task 1/3/4/5/6/8）、巡檢特有的「位置」維度處理（Task 1 新增欄位、Task 3/4 凍結鍵含 position）——全數對應使用者要求的「兩項都做」。
- **已知設計決策**：
  - 凍結鍵刻意不含廠商/客戶維度，因為 `get_spc` 既有的公差查詢本來就不使用 `customer_id`（`vendor_id` 固定傳空字串），維持與現有行為一致，不引入新的隱含語意。
  - `PatrolOutlierManagerModal` 未與出貨的 `OutlierManagerModal` 共用元件，因兩者的資料形狀不同（巡檢恆為 min/max 配對，無單一量測值欄位）且比對現有程式庫慣例（各領域各自一個 Modal，如公差表單與擠壓公差表單分開），維持一致性。
  - `shipping_service.py` 不需修改：`SpcControlLimit.source` 欄位已完全區隔 shipping/patrol 兩邊資料，新增的 `position` 欄位對既有 shipping 資料僅是恆為空字串的欄位，不影響其唯一性語意（Task 3 已加測試驗證兩者互不干擾）。
- **型別一致性**：`excluded_count`/`limits_frozen` 沿用 Task 5/19（出貨模組）已泛用化的 `SpcChartData` 型別（`src_frontend/src/types/spc.ts`），前端無需新增型別即可讀取；`PatrolControlLimitsKey`（Task 6）與後端路由參數鍵（`material`/`spec`/`item`/`position`）命名一致。
