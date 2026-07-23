# 機械性質檢驗模組 — Phase 1（核心 CRUD）實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 QC 系統新增「機械性質檢驗」模組的核心 CRUD：資料表、登錄/編輯表單、清單查詢，並依廠商公差下限自動判定 NG。

**Architecture:** 沿用全站三層架構（routes → services → models）。新增 2 張表（主檔 `機械性質檢驗` + 子檔 `機械性質量測明細`）。規格採單邊下限，存檔時依（材質 + 產品尺寸）到既有「廠商公差」撈下限並快照到量測明細，`是否超差 = 量測值 < 下限`。前端沿用 pyrometry 模式（清單 + 表單），EC 區塊與「異常加測（第2取樣）」預設收合。

**Tech Stack:** Flask 3.1 + SQLAlchemy + PostgreSQL（測試用 SQLite in-memory）；React 19 + TypeScript + React Query + Axios + Vitest。

**參考 spec：** `docs/superpowers/specs/2026-07-23-mechanical-properties-inspection-design.md`

**設計常數（全計畫共用）**

- 判定性質與對應廠商公差項目（映射表）：
  - `硬度` → `洛氏硬度`
  - `抗拉強度` → `抗拉強度`
  - `降伏強度` → `降伏強度`
  - `伸長率` → `伸長率`
- 無規格性質：`EC值`（不撈規格、不判定）。
- 量測位置：`爐門`、`爐頂`；取樣序：`1`（常態）、`2`（異常加測）。

---

## Task 1: 資料模型與 migration

**Files:**
- Modify: `backend/models.py`（檔尾新增 2 個模型）
- Create: `backend/migration/40_create_mechanical_tests.sql`
- Test: `backend/tests/test_services/test_mechanical_models.py`

- [ ] **Step 1: 寫失敗測試**

Create `backend/tests/test_services/test_mechanical_models.py`：

```python
from backend.models import MechanicalTest, MechanicalMeasurement


def test_create_mechanical_test_with_measurements(db_session):
    """主檔可帶量測明細，關聯與級聯刪除正常。"""
    test = MechanicalTest(
        product_size="36x25.2",
        material="6061-T651",
        extrusion_lot="010761 D35",
        t4_temp_time="530/40MIN",
        t6_temp_time="175/6HR",
    )
    test.measurements.append(
        MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=73.3)
    )
    db_session.add(test)
    db_session.commit()

    loaded = db_session.get(MechanicalTest, test.id)
    assert loaded.product_size == "36x25.2"
    assert len(loaded.measurements) == 1
    assert loaded.measurements[0].item == "硬度"

    # 級聯刪除
    db_session.delete(loaded)
    db_session.commit()
    assert db_session.query(MechanicalMeasurement).count() == 0


def test_measurement_unique_constraint(db_session):
    """同一測試中（項目+位置+取樣序）不可重複。"""
    import pytest
    from sqlalchemy.exc import IntegrityError

    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.measurements.append(MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=70))
    test.measurements.append(MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=71))
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_mechanical_models.py -v`
Expected: FAIL，`ImportError: cannot import name 'MechanicalTest'`

- [ ] **Step 3: 在 models.py 檔尾新增模型**

先確認 `backend/models.py` 檔首已 import：`from datetime import date`（既有）。在檔案最後新增：

```python
class MechanicalTest(db.Model):
    """機械性質檢驗 — 一筆對應原 Excel 一欄測試紀錄"""
    __tablename__ = '機械性質檢驗'

    id            = db.Column('識別碼',      db.Integer, primary_key=True)
    product_size  = db.Column('產品尺寸',    db.String(50), nullable=False, index=True)
    material      = db.Column('材質',        db.String(50), nullable=False, index=True)
    vendor_id     = db.Column('廠商ID',      db.Integer, db.ForeignKey('廠商資料.識別碼'), nullable=True)
    test_date     = db.Column('測試日期',    db.Date, nullable=True, index=True)
    extrusion_lot = db.Column('擠製日期批號', db.String, nullable=True)
    t4_furnace_no = db.Column('T4爐具編號',  db.String, nullable=True)
    t4_temp_time  = db.Column('T4溫度時間',  db.String, nullable=True)
    t6_temp_time  = db.Column('T6溫度時間',  db.String, nullable=True)
    note          = db.Column('備註',        db.String, nullable=True)
    is_ng         = db.Column('是否NG',      db.Boolean, default=False, nullable=False)
    created_at    = db.Column('建立日期',    db.DateTime(timezone=True), default=datetime.utcnow)
    created_by    = db.Column('建立者ID',    db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    updated_at    = db.Column('更新日期',    db.DateTime(timezone=True), onupdate=datetime.utcnow)

    measurements = db.relationship(
        'MechanicalMeasurement', backref='test', cascade="all, delete-orphan"
    )
    vendor = db.relationship('Vendor')


class MechanicalMeasurement(db.Model):
    """機械性質量測明細 — 一列對應一個（項目×位置×取樣序）量測值"""
    __tablename__ = '機械性質量測明細'
    __table_args__ = (
        db.UniqueConstraint('機械性質檢驗_ID', '量測項目', '測量位置', '取樣序',
                            name='uq_mech_group_item'),
        db.Index('idx_mech_meas_test_id', '機械性質檢驗_ID'),
    )

    id          = db.Column('識別碼',        db.Integer, primary_key=True)
    test_id     = db.Column('機械性質檢驗_ID', db.Integer,
                            db.ForeignKey('機械性質檢驗.識別碼'), nullable=False)
    item        = db.Column('量測項目',      db.String(20), nullable=False)
    location    = db.Column('測量位置',      db.String(10), nullable=False)
    sample_no   = db.Column('取樣序',        db.Integer, nullable=False)
    value       = db.Column('量測值',        db.Numeric(12, 4), nullable=True)
    lower_limit = db.Column('下限',          db.Numeric(12, 4), nullable=True)
    is_ng       = db.Column('是否超差',      db.Boolean, default=False, nullable=False)
    # §6.6 離群值：標示無效並保留追溯，不得刪除；排除於統計計算之外
    excluded          = db.Column('排除統計', db.Boolean, default=False, nullable=False)
    exclusion_reason  = db.Column('排除原因', db.String(200), nullable=True)
    exclusion_user_id = db.Column('排除者ID', db.Integer,
                                  db.ForeignKey('使用者.識別碼'), nullable=True)
    excluded_at       = db.Column('排除時間', db.DateTime(timezone=True), nullable=True)
```

> 注意：若 `backend/models.py` 尚未 import `datetime`，於檔首既有 import 區塊加 `from datetime import datetime, date`（若已有 `date`，改為同時匯入 `datetime`）。實作時先 grep 確認：`grep -n "^from datetime" backend/models.py`。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_mechanical_models.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 建立 migration SQL**

Create `backend/migration/40_create_mechanical_tests.sql`：

```sql
-- 機械性質檢驗模組 Phase 1：主檔 + 量測明細
CREATE TABLE IF NOT EXISTS "機械性質檢驗" (
    "識別碼"       SERIAL PRIMARY KEY,
    "產品尺寸"     VARCHAR(50) NOT NULL,
    "材質"         VARCHAR(50) NOT NULL,
    "廠商ID"       INTEGER REFERENCES "廠商資料"("識別碼"),
    "測試日期"     DATE,
    "擠製日期批號" VARCHAR,
    "T4爐具編號"   VARCHAR,
    "T4溫度時間"   VARCHAR,
    "T6溫度時間"   VARCHAR,
    "備註"         VARCHAR,
    "是否NG"       BOOLEAN NOT NULL DEFAULT FALSE,
    "建立日期"     TIMESTAMPTZ DEFAULT NOW(),
    "建立者ID"     INTEGER REFERENCES "使用者"("識別碼"),
    "更新日期"     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mech_test_size     ON "機械性質檢驗" ("產品尺寸");
CREATE INDEX IF NOT EXISTS idx_mech_test_material ON "機械性質檢驗" ("材質");
CREATE INDEX IF NOT EXISTS idx_mech_test_date     ON "機械性質檢驗" ("測試日期");

CREATE TABLE IF NOT EXISTS "機械性質量測明細" (
    "識別碼"          SERIAL PRIMARY KEY,
    "機械性質檢驗_ID" INTEGER NOT NULL REFERENCES "機械性質檢驗"("識別碼") ON DELETE CASCADE,
    "量測項目"        VARCHAR(20) NOT NULL,
    "測量位置"        VARCHAR(10) NOT NULL,
    "取樣序"          INTEGER NOT NULL,
    "量測值"          NUMERIC(12,4),
    "下限"            NUMERIC(12,4),
    "是否超差"        BOOLEAN NOT NULL DEFAULT FALSE,
    "排除統計"        BOOLEAN NOT NULL DEFAULT FALSE,
    "排除原因"        VARCHAR(200),
    "排除者ID"        INTEGER REFERENCES "使用者"("識別碼"),
    "排除時間"        TIMESTAMPTZ,
    CONSTRAINT uq_mech_group_item UNIQUE ("機械性質檢驗_ID", "量測項目", "測量位置", "取樣序")
);
CREATE INDEX IF NOT EXISTS idx_mech_meas_test_id ON "機械性質量測明細" ("機械性質檢驗_ID");
```

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/migration/40_create_mechanical_tests.sql backend/tests/test_services/test_mechanical_models.py
git commit -m "feat(機械性質): 新增機械性質檢驗主檔與量測明細資料表"
```

---

## Task 2: 規格撈取與 NG 判定（純函式，TDD 核心）

依（材質 + 產品尺寸）到廠商公差撈下限；`是否超差 = 量測值 < 下限`。重用既有 `ExtrusionToleranceService` 的材質/規格比對輔助函式。

**Files:**
- Create: `backend/services/mechanical_spec.py`
- Test: `backend/tests/test_services/test_mechanical_spec.py`

- [ ] **Step 1: 寫失敗測試**

Create `backend/tests/test_services/test_mechanical_spec.py`：

```python
from backend.models import Vendor, VendorToleranceMain, VendorToleranceDetail
from backend.services.mechanical_spec import (
    MECH_ITEM_TO_TOLERANCE,
    lookup_lower_limits,
    compute_measurement_ng,
)


def test_mapping_covers_four_judged_items():
    assert MECH_ITEM_TO_TOLERANCE == {
        "硬度": "洛氏硬度",
        "抗拉強度": "抗拉強度",
        "降伏強度": "降伏強度",
        "伸長率": "伸長率",
    }


def _seed_spec(db_session):
    v = Vendor(name="安泰")
    db_session.add(v)
    db_session.flush()
    main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2")
    db_session.add(main)
    db_session.flush()
    for item, low in [("洛氏硬度", 60), ("抗拉強度", 380), ("降伏強度", 350), ("伸長率", 8)]:
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item=item, tolerance_min=low, unit=""
        ))
    db_session.commit()
    return v.id


def test_lookup_lower_limits_matches_material_and_size(db_session):
    _seed_spec(db_session)
    limits = lookup_lower_limits("6061-T651", "36x25.2")
    # 以機械性質項目名回傳（非廠商公差項目名）
    assert float(limits["硬度"]) == 60
    assert float(limits["抗拉強度"]) == 380
    assert float(limits["降伏強度"]) == 350
    assert float(limits["伸長率"]) == 8
    assert "EC值" not in limits


def test_lookup_returns_empty_when_no_spec(db_session):
    limits = lookup_lower_limits("6061-T651", "99x99")
    assert limits == {}


def test_compute_measurement_ng_lower_bound_only():
    # 值 < 下限 → NG
    assert compute_measurement_ng(59, 60) is True
    # 值 == 下限 → 合格（單邊，含界限）
    assert compute_measurement_ng(60, 60) is False
    # 值 > 下限 → 合格（無上限）
    assert compute_measurement_ng(500, 60) is False
    # 無下限或無值 → 不判定
    assert compute_measurement_ng(50, None) is False
    assert compute_measurement_ng(None, 60) is False
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_mechanical_spec.py -v`
Expected: FAIL，`ModuleNotFoundError: backend.services.mechanical_spec`

- [ ] **Step 3: 實作 mechanical_spec.py**

Create `backend/services/mechanical_spec.py`：

```python
"""機械性質規格撈取與 NG 判定。

規格為單邊下限（只有下限、沒有上限）：量測值 < 下限 → NG。
規格值直接讀取既有「廠商公差」，依（材質 + 產品尺寸）比對，
量測項目對應廠商公差項目採 MECH_ITEM_TO_TOLERANCE 映射。EC 無規格。
"""
from decimal import Decimal
from typing import Dict, Optional

from ..models import VendorToleranceMain, VendorToleranceDetail
from .extrusion_tolerance_service import ExtrusionToleranceService

# 機械性質判定項目 → 廠商公差「測量項目」
MECH_ITEM_TO_TOLERANCE: Dict[str, str] = {
    "硬度": "洛氏硬度",
    "抗拉強度": "抗拉強度",
    "降伏強度": "降伏強度",
    "伸長率": "伸長率",
}


def lookup_lower_limits(material: str, product_size: str) -> Dict[str, Decimal]:
    """回傳 {機械性質項目: 下限}，查無則不含該項；EC 不查。"""
    if not material or not product_size:
        return {}

    match_material = ExtrusionToleranceService._match_material
    match_spec = ExtrusionToleranceService._match_spec

    mains = VendorToleranceMain.query.filter(
        VendorToleranceMain.material.isnot(None)
    ).all()
    candidate = None
    for m in mains:
        if match_material(material, m.material) and match_spec(product_size, m.spec or ""):
            candidate = m
            break
    if candidate is None:
        return {}

    # 反查：廠商公差項目 → 機械性質項目
    tol_to_mech = {v: k for k, v in MECH_ITEM_TO_TOLERANCE.items()}
    result: Dict[str, Decimal] = {}
    details = VendorToleranceDetail.query.filter_by(main_id=candidate.id).all()
    for d in details:
        mech_item = tol_to_mech.get(d.item)
        if mech_item and d.tolerance_min is not None:
            result[mech_item] = d.tolerance_min
    return result


def compute_measurement_ng(value: Optional[float], lower_limit: Optional[float]) -> bool:
    """單邊下限判定：有值且有下限且值 < 下限 → True，其餘 False。"""
    if value is None or lower_limit is None:
        return False
    return Decimal(str(value)) < Decimal(str(lower_limit))
```

> 註：`_match_material` / `_match_spec` 為既有 `ExtrusionToleranceService` 的 staticmethod，直接重用（材質相近、規格前兩段相符即匹配）。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_mechanical_spec.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/services/mechanical_spec.py backend/tests/test_services/test_mechanical_spec.py
git commit -m "feat(機械性質): 規格下限撈取與單邊 NG 判定"
```

---

## Task 3: CRUD Service

**Files:**
- Create: `backend/services/mechanical_service.py`
- Test: `backend/tests/test_services/test_mechanical_service.py`

- [ ] **Step 1: 寫失敗測試**

Create `backend/tests/test_services/test_mechanical_service.py`：

```python
from backend.models import Vendor, VendorToleranceMain, VendorToleranceDetail, MechanicalTest
from backend.services.mechanical_service import MechanicalService


def _seed_spec(db_session):
    v = Vendor(name="安泰")
    db_session.add(v); db_session.flush()
    main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2")
    db_session.add(main); db_session.flush()
    db_session.add(VendorToleranceDetail(main_id=main.id, item="洛氏硬度", tolerance_min=60, unit=""))
    db_session.commit()


def _payload():
    return {
        "產品尺寸": "36x25.2",
        "材質": "6061-T651",
        "測試日期": "2026-01-20",
        "擠製日期批號": "010761 D35",
        "T4溫度時間": "530/40MIN",
        "T6溫度時間": "175/6HR",
        "measurements": [
            {"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 59},
            {"量測項目": "硬度", "測量位置": "爐頂", "取樣序": 1, "量測值": 73},
        ],
    }


def test_create_computes_ng_from_spec(db_session):
    _seed_spec(db_session)
    new_id = MechanicalService.create(_payload(), user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row is not None
    # 爐門 59 < 下限 60 → 該明細 NG，主檔 NG
    assert row.is_ng is True
    ng_items = [(m.location, m.is_ng) for m in row.measurements if m.item == "硬度"]
    assert ("爐門", True) in ng_items
    assert ("爐頂", False) in ng_items


def test_create_without_spec_is_not_ng(db_session):
    # 無規格 → 不判定
    new_id = MechanicalService.create(_payload(), user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row.is_ng is False
    assert all(m.is_ng is False for m in row.measurements)


def test_list_filters_by_size(db_session):
    MechanicalService.create(_payload(), user_id=None)
    res = MechanicalService.list({"product_size": "36"})
    assert res["total"] == 1
    assert res["data"][0]["產品尺寸"] == "36x25.2"
    res2 = MechanicalService.list({"product_size": "99"})
    assert res2["total"] == 0


def test_update_recomputes_ng(db_session):
    _seed_spec(db_session)
    new_id = MechanicalService.create(_payload(), user_id=None)
    payload = _payload()
    payload["measurements"][0]["量測值"] = 70  # 爐門改為 70 ≥ 60 → 不再 NG
    MechanicalService.update(new_id, payload, user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row.is_ng is False


def test_get_detail_and_delete(db_session):
    new_id = MechanicalService.create(_payload(), user_id=None)
    detail = MechanicalService.get_detail(new_id)
    assert detail["main"]["產品尺寸"] == "36x25.2"
    assert len(detail["measurements"]) == 2
    MechanicalService.delete(new_id)
    assert db_session.get(MechanicalTest, new_id) is None
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_mechanical_service.py -v`
Expected: FAIL，`ModuleNotFoundError: backend.services.mechanical_service`

- [ ] **Step 3: 實作 mechanical_service.py**

Create `backend/services/mechanical_service.py`：

```python
"""機械性質檢驗 CRUD 服務。"""
from datetime import datetime, date
from typing import Any, Dict, Optional

from ..extensions import db
from ..models import MechanicalTest, MechanicalMeasurement
from ..utils import bounded_int, format_value
from .mechanical_spec import lookup_lower_limits, compute_measurement_ng


def _parse_date(v: Any) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, date):
        return v
    return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class MechanicalService:

    @staticmethod
    def _apply_measurements(test: MechanicalTest, data: Dict[str, Any]) -> None:
        """依 payload 重建量測明細並套規格判定 NG。"""
        # 清除既有明細（更新情境）
        test.measurements.clear()
        limits = lookup_lower_limits(test.material, test.product_size)

        any_ng = False
        for m in data.get("measurements", []):
            item = m.get("量測項目")
            value = _to_float(m.get("量測值"))
            lower = limits.get(item)  # EC 或查無規格 → None
            is_ng = compute_measurement_ng(value, float(lower) if lower is not None else None)
            any_ng = any_ng or is_ng
            test.measurements.append(MechanicalMeasurement(
                item=item,
                location=m.get("測量位置"),
                sample_no=int(m.get("取樣序") or 1),
                value=value,
                lower_limit=lower,
                is_ng=is_ng,
            ))
        test.is_ng = any_ng

    @staticmethod
    def create(data: Dict[str, Any], user_id: Optional[int]) -> int:
        test = MechanicalTest(
            product_size=data.get("產品尺寸"),
            material=data.get("材質"),
            vendor_id=data.get("廠商ID") or None,
            test_date=_parse_date(data.get("測試日期")),
            extrusion_lot=data.get("擠製日期批號") or None,
            t4_furnace_no=data.get("T4爐具編號") or None,
            t4_temp_time=data.get("T4溫度時間") or None,
            t6_temp_time=data.get("T6溫度時間") or None,
            note=data.get("備註") or None,
            created_by=user_id,
        )
        MechanicalService._apply_measurements(test, data)
        db.session.add(test)
        db.session.commit()
        return test.id

    @staticmethod
    def update(test_id: int, data: Dict[str, Any], user_id: Optional[int]) -> None:
        test = db.session.get(MechanicalTest, test_id)
        if not test:
            raise ValueError("找不到該筆機械性質檢驗資料")
        test.product_size = data.get("產品尺寸", test.product_size)
        test.material = data.get("材質", test.material)
        test.vendor_id = data.get("廠商ID") or None
        test.test_date = _parse_date(data.get("測試日期"))
        test.extrusion_lot = data.get("擠製日期批號") or None
        test.t4_furnace_no = data.get("T4爐具編號") or None
        test.t4_temp_time = data.get("T4溫度時間") or None
        test.t6_temp_time = data.get("T6溫度時間") or None
        test.note = data.get("備註") or None
        MechanicalService._apply_measurements(test, data)
        db.session.commit()

    @staticmethod
    def delete(test_id: int) -> None:
        test = db.session.get(MechanicalTest, test_id)
        if not test:
            raise ValueError("找不到該筆機械性質檢驗資料")
        db.session.delete(test)
        db.session.commit()

    @staticmethod
    def list(args: Dict[str, Any]) -> Dict[str, Any]:
        query = MechanicalTest.query
        if args.get("product_size"):
            query = query.filter(MechanicalTest.product_size.like(f"%{args['product_size']}%"))
        if args.get("material"):
            query = query.filter(MechanicalTest.material.like(f"%{args['material']}%"))
        if args.get("date_from"):
            query = query.filter(MechanicalTest.test_date >= _parse_date(args["date_from"]))
        if args.get("date_to"):
            query = query.filter(MechanicalTest.test_date <= _parse_date(args["date_to"]))
        if str(args.get("only_ng", "")).lower() in ("1", "true"):
            query = query.filter(MechanicalTest.is_ng.is_(True))

        page = bounded_int(args.get("page"), 1, 1, 1000000)
        page_size = bounded_int(args.get("page_size"), 20, 1, 100)
        total = query.count()
        # 以識別碼倒序（新→舊），避免 SQLite NULLS LAST 相容性問題（沿用擠壓公差慣例）
        pagination = query.order_by(MechanicalTest.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        data = [{
            "識別碼": t.id,
            "產品尺寸": t.product_size,
            "材質": t.material,
            "測試日期": format_value(t.test_date),
            "擠製日期批號": t.extrusion_lot or "",
            "T4溫度時間": t.t4_temp_time or "",
            "T6溫度時間": t.t6_temp_time or "",
            "是否NG": t.is_ng,
            "備註": t.note or "",
        } for t in pagination.items]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": pagination.pages}

    @staticmethod
    def get_detail(test_id: int) -> Dict[str, Any]:
        t = db.session.get(MechanicalTest, test_id)
        if not t:
            raise ValueError("找不到該筆機械性質檢驗資料")
        main = {
            "識別碼": t.id,
            "產品尺寸": t.product_size,
            "材質": t.material,
            "廠商ID": t.vendor_id,
            "測試日期": format_value(t.test_date),
            "擠製日期批號": t.extrusion_lot or "",
            "T4爐具編號": t.t4_furnace_no or "",
            "T4溫度時間": t.t4_temp_time or "",
            "T6溫度時間": t.t6_temp_time or "",
            "備註": t.note or "",
            "是否NG": t.is_ng,
        }
        measurements = [{
            "識別碼": m.id,
            "量測項目": m.item,
            "測量位置": m.location,
            "取樣序": m.sample_no,
            "量測值": format_value(m.value),
            "下限": format_value(m.lower_limit),
            "是否超差": m.is_ng,
        } for m in sorted(t.measurements, key=lambda x: (x.item, x.location, x.sample_no))]
        return {"success": True, "main": main, "measurements": measurements}
```

> 清理：Step 3 的 `_apply_measurements` 內 `if False else` 是誤植，實作時直接寫 `limits = lookup_lower_limits(test.material, test.product_size)`。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_mechanical_service.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/services/mechanical_service.py backend/tests/test_services/test_mechanical_service.py
git commit -m "feat(機械性質): CRUD 服務與存檔即時 NG 判定"
```

---

## Task 4: Routes 與 Blueprint 註冊

**Files:**
- Create: `backend/routes/mechanical.py`
- Modify: `backend/app.py`（import + register_blueprint）
- Test: `backend/tests/test_mechanical_route.py`

- [ ] **Step 1: 寫失敗測試**

Create `backend/tests/test_mechanical_route.py`：

```python
from backend.models import Role, User
from backend.utils import generate_token, hash_password


def _auth_user(db_session):
    db_session.add(Role(code='qc', name='品管', permissions={
        'mechanical.create': True, 'mechanical.edit': True, 'mechanical.delete': True,
    }))
    user = User(username='qc1', password=hash_password('pw12345678'), role='qc', is_active=True)
    db_session.add(user); db_session.flush()
    token = generate_token(user)
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_via_api(client, db_session):
    headers = _auth_user(db_session)
    payload = {
        "產品尺寸": "36x25.2", "材質": "6061-T651", "測試日期": "2026-01-20",
        "measurements": [{"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 70}],
    }
    r = client.post("/api/mechanical/tests", json=payload, headers=headers)
    assert r.status_code == 200
    new_id = r.get_json()["id"]

    r2 = client.get("/api/mechanical/tests?product_size=36", headers=headers)
    assert r2.status_code == 200
    assert r2.get_json()["total"] == 1

    r3 = client.get(f"/api/mechanical/tests/{new_id}", headers=headers)
    assert r3.status_code == 200
    assert r3.get_json()["main"]["材質"] == "6061-T651"


def test_create_requires_permission(client, db_session):
    db_session.add(Role(code='viewer', name='唯讀', permissions={}))
    user = User(username='v1', password=hash_password('pw12345678'), role='viewer', is_active=True)
    db_session.add(user); db_session.flush()
    headers = {"Authorization": f"Bearer {generate_token(user)}"}
    r = client.post("/api/mechanical/tests", json={"產品尺寸": "x", "材質": "y"}, headers=headers)
    assert r.status_code == 403
```

> 執行前先確認 `generate_token` 簽名：`grep -n "def generate_token" backend/utils.py`。若其參數非 `user` 物件，依既有測試（如 `test_services/test_attachment_validation.py`）的用法調整。

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && python -m pytest tests/test_mechanical_route.py -v`
Expected: FAIL（404，路由未註冊）

- [ ] **Step 3: 實作 routes/mechanical.py**

Create `backend/routes/mechanical.py`：

```python
from flask import Blueprint, jsonify, request, g
from ..services.mechanical_service import MechanicalService
from ..utils import auth_required, require_perm, handle_db_error

mechanical_bp = Blueprint('mechanical', __name__)


def _current_user_id():
    user = getattr(g, 'current_user', None)
    return getattr(user, 'id', None) if user else None


@mechanical_bp.route('/api/mechanical/tests', methods=['GET'])
@auth_required
def list_tests():
    """機械性質檢驗清單查詢"""
    try:
        return jsonify(MechanicalService.list(request.args))
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['GET'])
@auth_required
def get_test(test_id):
    """取得單筆機械性質檢驗明細"""
    try:
        return jsonify(MechanicalService.get_detail(test_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@mechanical_bp.route('/api/mechanical/tests', methods=['POST'])
@auth_required
@require_perm('mechanical.create')
def create_test():
    """新增機械性質檢驗"""
    try:
        new_id = MechanicalService.create(request.json or {}, _current_user_id())
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['PUT'])
@auth_required
@require_perm('mechanical.edit')
def update_test(test_id):
    """更新機械性質檢驗"""
    try:
        MechanicalService.update(test_id, request.json or {}, _current_user_id())
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['DELETE'])
@auth_required
@require_perm('mechanical.delete')
def delete_test(test_id):
    """刪除機械性質檢驗"""
    try:
        MechanicalService.delete(test_id)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/spec', methods=['GET'])
@auth_required
def get_spec():
    """依材質+尺寸查規格下限（供表單即時顯示）"""
    from ..services.mechanical_spec import lookup_lower_limits
    material = request.args.get('material', '')
    size = request.args.get('product_size', '')
    limits = lookup_lower_limits(material, size)
    return jsonify({"success": True, "limits": {k: float(v) for k, v in limits.items()}})
```

> 確認 `auth_required` 如何提供目前使用者：`grep -n "g.current_user\|g.user" backend/utils.py`。若既有慣例是 `g.user` 而非 `g.current_user`，於 `_current_user_id()` 對齊。

- [ ] **Step 4: 在 app.py 註冊 blueprint**

Modify `backend/app.py`：於既有 import 區塊（`from .routes.pyrometry import ...` 附近）加入：

```python
from .routes.mechanical import mechanical_bp
```

於 `app.register_blueprint(spc_studies_bp)`（第 79 行附近）之後加入：

```python
app.register_blueprint(mechanical_bp)
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd backend && python -m pytest tests/test_mechanical_route.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 全後端測試回歸**

Run: `cd backend && python -m pytest -q`
Expected: 全數通過（無新失敗）

- [ ] **Step 7: Commit**

```bash
git add backend/routes/mechanical.py backend/app.py backend/tests/test_mechanical_route.py
git commit -m "feat(機械性質): 新增 REST API 端點與權限控管"
```

---

## Task 5: 前端型別與 API

**Files:**
- Modify: `src_frontend/src/types/index.ts`（檔尾新增介面）
- Create: `src_frontend/src/services/mechanicalApi.ts`

- [ ] **Step 1: 新增型別**

於 `src_frontend/src/types/index.ts` 檔尾新增：

```typescript
// ===== 機械性質檢驗 =====
export type MechItem = 'EC值' | '硬度' | '抗拉強度' | '降伏強度' | '伸長率';
export type MechLocation = '爐門' | '爐頂';

export interface MechanicalMeasurement {
  量測項目: MechItem;
  測量位置: MechLocation;
  取樣序: number;
  量測值: number | null;
  下限?: number | null;
  是否超差?: boolean;
}

export interface MechanicalTestListItem {
  識別碼: number;
  產品尺寸: string;
  材質: string;
  測試日期: string | null;
  擠製日期批號: string;
  T4溫度時間: string;
  T6溫度時間: string;
  是否NG: boolean;
  備註: string;
}

export interface MechanicalTestDetail {
  main: {
    識別碼: number;
    產品尺寸: string;
    材質: string;
    廠商ID: number | null;
    測試日期: string | null;
    擠製日期批號: string;
    T4爐具編號: string;
    T4溫度時間: string;
    T6溫度時間: string;
    備註: string;
    是否NG: boolean;
  };
  measurements: MechanicalMeasurement[];
}

export interface MechanicalTestPayload {
  產品尺寸: string;
  材質: string;
  廠商ID?: number | null;
  測試日期?: string | null;
  擠製日期批號?: string;
  T4爐具編號?: string;
  T4溫度時間?: string;
  T6溫度時間?: string;
  備註?: string;
  measurements: MechanicalMeasurement[];
}
```

- [ ] **Step 2: 建立 API 模組**

Create `src_frontend/src/services/mechanicalApi.ts`：

```typescript
import api from './api';
import type {
  MechanicalTestDetail,
  MechanicalTestListItem,
  MechanicalTestPayload,
} from '../types';

export interface MechanicalListResponse {
  success: boolean;
  data: MechanicalTestListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const mechanicalApi = {
  list: (params: Record<string, string | number | undefined>) =>
    api.get<MechanicalListResponse>('/mechanical/tests', { params }).then((r) => r.data),

  getDetail: (id: number) =>
    api.get<MechanicalTestDetail>(`/mechanical/tests/${id}`).then((r) => r.data),

  create: (payload: MechanicalTestPayload) =>
    api.post<{ success: boolean; id: number }>('/mechanical/tests', payload).then((r) => r.data),

  update: (id: number, payload: MechanicalTestPayload) =>
    api.put<{ success: boolean }>(`/mechanical/tests/${id}`, payload).then((r) => r.data),

  remove: (id: number) =>
    api.delete<{ success: boolean }>(`/mechanical/tests/${id}`).then((r) => r.data),

  getSpec: (material: string, product_size: string) =>
    api
      .get<{ success: boolean; limits: Record<string, number> }>('/mechanical/spec', {
        params: { material, product_size },
      })
      .then((r) => r.data.limits),
};
```

- [ ] **Step 3: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無新錯誤

- [ ] **Step 4: Commit**

```bash
git add src_frontend/src/types/index.ts src_frontend/src/services/mechanicalApi.ts
git commit -m "feat(機械性質): 前端型別定義與 API 模組"
```

---

## Task 6: 表單量測值組裝（純函式，TDD）

把表單狀態轉為送出用的量測陣列，並反向由明細還原表單狀態。純函式，先測試。

**Files:**
- Create: `src_frontend/src/pages/mechanical/mechanicalPayload.ts`
- Test: `src_frontend/src/pages/mechanical/mechanicalPayload.test.ts`

- [ ] **Step 1: 寫失敗測試**

Create `src_frontend/src/pages/mechanical/mechanicalPayload.test.ts`：

```typescript
import { describe, it, expect } from 'vitest';
import {
  JUDGED_ITEMS,
  buildMeasurements,
  emptyGrid,
  hydrateGrid,
  type MechGrid,
} from './mechanicalPayload';

describe('mechanicalPayload', () => {
  it('emptyGrid 常態每項有爐門/爐頂取樣1兩格', () => {
    const grid = emptyGrid();
    expect(grid['硬度']['爐門'][1]).toBe('');
    expect(grid['硬度']['爐頂'][1]).toBe('');
  });

  it('buildMeasurements 僅輸出有值的格子', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][1] = '70';
    grid['硬度']['爐頂'][1] = '73';
    const out = buildMeasurements(grid);
    expect(out).toContainEqual({ 量測項目: '硬度', 測量位置: '爐門', 取樣序: 1, 量測值: 70 });
    expect(out).toContainEqual({ 量測項目: '硬度', 測量位置: '爐頂', 取樣序: 1, 量測值: 73 });
    // 空格不輸出
    expect(out.some((m) => m.量測項目 === '抗拉強度')).toBe(false);
  });

  it('buildMeasurements 含第2取樣（異常加測）', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][2] = '69';
    const out = buildMeasurements(grid);
    expect(out).toContainEqual({ 量測項目: '硬度', 測量位置: '爐門', 取樣序: 2, 量測值: 69 });
  });

  it('hydrateGrid 由明細還原表單', () => {
    const grid = hydrateGrid([
      { 量測項目: '硬度', 測量位置: '爐門', 取樣序: 1, 量測值: 70 },
      { 量測項目: 'EC值', 測量位置: '爐頂', 取樣序: 1, 量測值: 42 },
    ]);
    expect(grid['硬度']['爐門'][1]).toBe('70');
    expect(grid['EC值']['爐頂'][1]).toBe('42');
  });

  it('JUDGED_ITEMS 為四項判定性質（不含 EC）', () => {
    expect(JUDGED_ITEMS).toEqual(['硬度', '抗拉強度', '降伏強度', '伸長率']);
  });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/mechanical/mechanicalPayload.test.ts`
Expected: FAIL（找不到模組）

- [ ] **Step 3: 實作 mechanicalPayload.ts**

Create `src_frontend/src/pages/mechanical/mechanicalPayload.ts`：

```typescript
import type { MechItem, MechLocation, MechanicalMeasurement } from '../../types';

export const JUDGED_ITEMS: MechItem[] = ['硬度', '抗拉強度', '降伏強度', '伸長率'];
export const ALL_ITEMS: MechItem[] = ['硬度', '抗拉強度', '降伏強度', '伸長率', 'EC值'];
export const LOCATIONS: MechLocation[] = ['爐門', '爐頂'];
export const SAMPLES = [1, 2] as const;

// grid[item][location][sampleNo] = 字串輸入值
export type MechGrid = Record<MechItem, Record<MechLocation, Record<number, string>>>;

export function emptyGrid(): MechGrid {
  const grid = {} as MechGrid;
  for (const item of ALL_ITEMS) {
    grid[item] = { 爐門: {}, 爐頂: {} } as Record<MechLocation, Record<number, string>>;
    for (const loc of LOCATIONS) {
      for (const s of SAMPLES) grid[item][loc][s] = '';
    }
  }
  return grid;
}

export function buildMeasurements(grid: MechGrid): MechanicalMeasurement[] {
  const out: MechanicalMeasurement[] = [];
  for (const item of ALL_ITEMS) {
    for (const loc of LOCATIONS) {
      for (const s of SAMPLES) {
        const raw = grid[item]?.[loc]?.[s];
        if (raw !== undefined && raw !== '') {
          const num = Number(raw);
          out.push({
            量測項目: item,
            測量位置: loc,
            取樣序: s,
            量測值: Number.isFinite(num) ? num : null,
          });
        }
      }
    }
  }
  return out;
}

export function hydrateGrid(measurements: MechanicalMeasurement[]): MechGrid {
  const grid = emptyGrid();
  for (const m of measurements) {
    if (grid[m.量測項目]?.[m.測量位置] && m.量測值 !== null && m.量測值 !== undefined) {
      grid[m.量測項目][m.測量位置][m.取樣序] = String(m.量測值);
    }
  }
  return grid;
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd src_frontend && npx vitest run src/pages/mechanical/mechanicalPayload.test.ts`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/pages/mechanical/mechanicalPayload.ts src_frontend/src/pages/mechanical/mechanicalPayload.test.ts
git commit -m "feat(機械性質): 表單量測值組裝與還原工具（含測試）"
```

---

## Task 7: 清單頁 MechanicalTestListPage

**Files:**
- Create: `src_frontend/src/pages/mechanical/MechanicalTestListPage.tsx`

- [ ] **Step 1: 實作清單頁**

Create `src_frontend/src/pages/mechanical/MechanicalTestListPage.tsx`：

```tsx
import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { mechanicalApi } from '../../services/mechanicalApi';
import MechanicalTestForm from './MechanicalTestForm';

export default function MechanicalTestListPage() {
  const qc = useQueryClient();
  const [size, setSize] = useState('');
  const [material, setMaterial] = useState('');
  const [editingId, setEditingId] = useState<number | null | 'new'>(null);

  const params = useMemo(
    () => ({ product_size: size || undefined, material: material || undefined }),
    [size, material],
  );

  const { data, isLoading } = useQuery({
    queryKey: ['mechanical-tests', params],
    queryFn: () => mechanicalApi.list(params),
  });

  const del = useMutation({
    mutationFn: (id: number) => mechanicalApi.remove(id),
    onSuccess: () => {
      toast.success('已刪除');
      qc.invalidateQueries({ queryKey: ['mechanical-tests'] });
    },
  });

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>機械性質檢驗</h1>
        <button className="btn btn-primary" onClick={() => setEditingId('new')}>
          <i className="fa-solid fa-plus" /> 新增檢驗
        </button>
      </div>

      <div className="filter-bar">
        <input placeholder="產品尺寸" value={size} onChange={(e) => setSize(e.target.value)} />
        <input placeholder="材質" value={material} onChange={(e) => setMaterial(e.target.value)} />
      </div>

      {isLoading ? (
        <p>載入中…</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>產品尺寸</th><th>材質</th><th>測試日期</th>
              <th>批號</th><th>T4</th><th>T6</th><th>判定</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {data?.data.map((row) => (
              <tr key={row.識別碼}>
                <td>{row.產品尺寸}</td>
                <td>{row.材質}</td>
                <td>{row.測試日期 ?? ''}</td>
                <td>{row.擠製日期批號}</td>
                <td>{row.T4溫度時間}</td>
                <td>{row.T6溫度時間}</td>
                <td>
                  {row.是否NG ? (
                    <span className="badge badge-danger">NG</span>
                  ) : (
                    <span className="badge badge-success">OK</span>
                  )}
                </td>
                <td>
                  <button className="btn btn-sm" onClick={() => setEditingId(row.識別碼)}>編輯</button>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => {
                      if (confirm('確定刪除這筆檢驗？')) del.mutate(row.識別碼);
                    }}
                  >刪除</button>
                </td>
              </tr>
            ))}
            {data && data.data.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: 'center' }}>查無資料</td></tr>
            )}
          </tbody>
        </table>
      )}

      {editingId !== null && (
        <MechanicalTestForm
          testId={editingId === 'new' ? null : editingId}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            qc.invalidateQueries({ queryKey: ['mechanical-tests'] });
          }}
        />
      )}
    </div>
  );
}
```

> 樣式類名（`page-container`、`data-table`、`badge` 等）沿用既有頁面慣例。實作時開啟一個既有清單頁（如 `pages/extrusion-tolerance/ExtrusionTolerancePage.tsx`）比對實際類名，若不同則對齊。

- [ ] **Step 2: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 僅剩「找不到 MechanicalTestForm」（下一個 Task 建立），其餘無錯

- [ ] **Step 3: Commit**

```bash
git add src_frontend/src/pages/mechanical/MechanicalTestListPage.tsx
git commit -m "feat(機械性質): 檢驗清單頁（篩選/新增/編輯/刪除）"
```

---

## Task 8: 登錄表單 MechanicalTestForm（EC 收合 + 異常加測開關）

**Files:**
- Create: `src_frontend/src/pages/mechanical/MechanicalTestForm.tsx`

- [ ] **Step 1: 實作表單**

Create `src_frontend/src/pages/mechanical/MechanicalTestForm.tsx`：

```tsx
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { mechanicalApi } from '../../services/mechanicalApi';
import type { MechItem, MechanicalTestPayload } from '../../types';
import {
  JUDGED_ITEMS,
  LOCATIONS,
  buildMeasurements,
  emptyGrid,
  hydrateGrid,
  type MechGrid,
} from './mechanicalPayload';

interface Props {
  testId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

interface BasicFields {
  產品尺寸: string;
  材質: string;
  測試日期: string;
  擠製日期批號: string;
  T4爐具編號: string;
  T4溫度時間: string;
  T6溫度時間: string;
  備註: string;
}

const EMPTY_BASIC: BasicFields = {
  產品尺寸: '', 材質: '6061-T651', 測試日期: '', 擠製日期批號: '',
  T4爐具編號: '', T4溫度時間: '', T6溫度時間: '', 備註: '',
};

export default function MechanicalTestForm({ testId, onClose, onSaved }: Props) {
  const [basic, setBasic] = useState<BasicFields>(EMPTY_BASIC);
  const [grid, setGrid] = useState<MechGrid>(emptyGrid());
  const [showSecond, setShowSecond] = useState(false); // 異常加測（第2取樣）
  const [showEc, setShowEc] = useState(false);          // 導電度 EC
  const [saving, setSaving] = useState(false);

  // 編輯：載入既有資料
  const { data: detail } = useQuery({
    queryKey: ['mechanical-test', testId],
    queryFn: () => mechanicalApi.getDetail(testId as number),
    enabled: testId !== null,
  });

  useEffect(() => {
    if (detail) {
      setBasic({
        產品尺寸: detail.main.產品尺寸,
        材質: detail.main.材質,
        測試日期: detail.main.測試日期 ?? '',
        擠製日期批號: detail.main.擠製日期批號,
        T4爐具編號: detail.main.T4爐具編號,
        T4溫度時間: detail.main.T4溫度時間,
        T6溫度時間: detail.main.T6溫度時間,
        備註: detail.main.備註,
      });
      setGrid(hydrateGrid(detail.measurements));
      // 若有第2取樣或 EC 值，預設展開
      if (detail.measurements.some((m) => m.取樣序 === 2)) setShowSecond(true);
      if (detail.measurements.some((m) => m.量測項目 === 'EC值')) setShowEc(true);
    }
  }, [detail]);

  // 規格下限（用於即時 NG 提示）
  const { data: limits } = useQuery({
    queryKey: ['mechanical-spec', basic.材質, basic.產品尺寸],
    queryFn: () => mechanicalApi.getSpec(basic.材質, basic.產品尺寸),
    enabled: !!basic.材質 && !!basic.產品尺寸,
  });

  const setCell = (item: MechItem, loc: string, sample: number, val: string) => {
    setGrid((g) => ({
      ...g,
      [item]: { ...g[item], [loc]: { ...g[item][loc as '爐門'], [sample]: val } },
    }));
  };

  const cellNg = (item: MechItem, val: string): boolean => {
    const low = limits?.[item];
    if (low === undefined || val === '') return false;
    return Number(val) < low;
  };

  const save = async () => {
    if (!basic.產品尺寸 || !basic.材質) {
      toast.error('請填寫產品尺寸與材質');
      return;
    }
    const payload: MechanicalTestPayload = {
      產品尺寸: basic.產品尺寸,
      材質: basic.材質,
      測試日期: basic.測試日期 || null,
      擠製日期批號: basic.擠製日期批號,
      T4爐具編號: basic.T4爐具編號,
      T4溫度時間: basic.T4溫度時間,
      T6溫度時間: basic.T6溫度時間,
      備註: basic.備註,
      measurements: buildMeasurements(grid),
    };
    setSaving(true);
    try {
      if (testId === null) await mechanicalApi.create(payload);
      else await mechanicalApi.update(testId, payload);
      toast.success('已儲存');
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  const samples = showSecond ? [1, 2] : [1];
  const items: MechItem[] = showEc ? [...JUDGED_ITEMS, 'EC值'] : JUDGED_ITEMS;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: 720 }} onClick={(e) => e.stopPropagation()}>
        <h2>{testId === null ? '新增' : '編輯'}機械性質檢驗</h2>

        {/* 基本資料 */}
        <div className="form-grid">
          <label>產品尺寸
            <input value={basic.產品尺寸} onChange={(e) => setBasic({ ...basic, 產品尺寸: e.target.value })} />
          </label>
          <label>材質
            <input value={basic.材質} onChange={(e) => setBasic({ ...basic, 材質: e.target.value })} />
          </label>
          <label>測試日期
            <input type="date" value={basic.測試日期} onChange={(e) => setBasic({ ...basic, 測試日期: e.target.value })} />
          </label>
          <label>擠製日期/批號
            <input value={basic.擠製日期批號} onChange={(e) => setBasic({ ...basic, 擠製日期批號: e.target.value })} />
          </label>
          <label>T4爐具編號
            <input value={basic.T4爐具編號} onChange={(e) => setBasic({ ...basic, T4爐具編號: e.target.value })} />
          </label>
          <label>T4溫度/時間
            <input value={basic.T4溫度時間} onChange={(e) => setBasic({ ...basic, T4溫度時間: e.target.value })} />
          </label>
          <label>T6溫度/時間
            <input value={basic.T6溫度時間} onChange={(e) => setBasic({ ...basic, T6溫度時間: e.target.value })} />
          </label>
        </div>

        {/* 量測開關 */}
        <div className="toggle-bar" style={{ display: 'flex', gap: 16, margin: '12px 0' }}>
          <label><input type="checkbox" checked={showSecond} onChange={(e) => setShowSecond(e.target.checked)} /> 異常加測（第2取樣）</label>
          <label><input type="checkbox" checked={showEc} onChange={(e) => setShowEc(e.target.checked)} /> 顯示導電度 (EC)</label>
        </div>

        {/* 量測表 */}
        <table className="data-table">
          <thead>
            <tr>
              <th>項目</th>
              {LOCATIONS.map((loc) =>
                samples.map((s) => <th key={`${loc}-${s}`}>{loc}{s}</th>),
              )}
              <th>下限</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item}>
                <td>{item}</td>
                {LOCATIONS.map((loc) =>
                  samples.map((s) => {
                    const val = grid[item][loc][s] ?? '';
                    const ng = cellNg(item, val);
                    return (
                      <td key={`${loc}-${s}`}>
                        <input
                          style={{ width: 70, borderColor: ng ? '#e53e3e' : undefined }}
                          value={val}
                          onChange={(e) => setCell(item, loc, s, e.target.value)}
                        />
                      </td>
                    );
                  }),
                )}
                <td>{item === 'EC值' ? '—' : (limits?.[item] ?? '—')}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <label style={{ display: 'block', marginTop: 12 }}>備註
          <textarea value={basic.備註} onChange={(e) => setBasic({ ...basic, 備註: e.target.value })} />
        </label>

        <div className="modal-actions" style={{ marginTop: 16 }}>
          <button className="btn" onClick={onClose}>取消</button>
          <button className="btn btn-primary" disabled={saving} onClick={save}>
            {saving ? '儲存中…' : '儲存'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

> 樣式類名（`modal-overlay`、`form-grid` 等）沿用既有 Modal 慣例；實作時比對一個既有 modal（如 `components/ncmr/NCMRModal.tsx`）對齊實際類名。

- [ ] **Step 2: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 3: Commit**

```bash
git add src_frontend/src/pages/mechanical/MechanicalTestForm.tsx
git commit -m "feat(機械性質): 登錄表單（EC 收合、異常加測開關、即時 NG 提示）"
```

---

## Task 9: 路由、側邊選單與權限目錄

**Files:**
- Modify: `src_frontend/src/App.tsx`（lazy import + Route）
- Modify: `src_frontend/src/components/Sidebar.tsx`（選單項目）
- Modify: `src_frontend/src/pages/admin/adminPermissions.ts`（權限群組）

- [ ] **Step 1: App.tsx 加入路由**

於 lazy import 區塊（`AdvancedSpcPage` 附近）加入：

```typescript
const MechanicalTestListPage = lazy(() => import('./pages/mechanical/MechanicalTestListPage'));
```

於 `ProtectedRoute` → `MainLayout` 內（`/pyrometry/...` 路由之後、`</Route>` 之前）加入：

```tsx
<Route path="/mechanical" element={<MechanicalTestListPage />} />
```

- [ ] **Step 2: Sidebar.tsx 加入選單**

於「功能選單」群組的 items 陣列中（`擠壓公差` 之後）加入：

```tsx
{ title: '機械性質', path: '/mechanical', icon: 'fa-dumbbell' },
```

- [ ] **Step 3: adminPermissions.ts 加入權限群組**

於 `PERMISSION_GROUPS` 陣列末端（或「爐溫測試」群組之後）加入：

```typescript
{
  label: '機械性質',
  perms: [
    { key: 'mechanical.create', label: '建立' },
    { key: 'mechanical.edit', label: '編輯' },
    { key: 'mechanical.delete', label: '刪除' },
  ],
},
```

- [ ] **Step 4: 前端建置驗證**

Run: `cd src_frontend && npm run build`
Expected: TypeScript 檢查 + Vite build 成功，無錯誤

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/App.tsx src_frontend/src/components/Sidebar.tsx src_frontend/src/pages/admin/adminPermissions.ts
git commit -m "feat(機械性質): 前端路由、側邊選單與權限目錄"
```

---

## Task 10: 端到端手動驗證

**Files:** 無（驗證用）

- [ ] **Step 1: 套用 migration 到開發資料庫**

Run（依 CLAUDE.md，後端於 venv 中）：
```bash
# 於 psql 或既有匯入方式套用
psql -U postgres -d qa_database -f backend/migration/40_create_mechanical_tests.sql
```
Expected: 兩張表建立成功

- [ ] **Step 2: 啟動後端 + 前端**

依 memory「啟動方式」：開發用 `backend`（venv，:5001）+ `src_frontend`（`npm run dev`）。

- [ ] **Step 3: 瀏覽器驗證（用 preview 工具）**
  - 側邊選單出現「機械性質」，進入清單頁。
  - 新增一筆：填 36x25.2 / 6061-T651 / 硬度爐門1=59、爐頂1=73。
  - 若廠商公差已填 6061-T651 硬度下限，59 應標紅、儲存後清單顯示 NG；否則顯示 OK（無規格）。
  - 開「異常加測」→ 每項多出第2取樣欄位；開「顯示 EC」→ 出現 EC值 列。
  - 編輯該筆確認資料正確回填；刪除確認消失。

- [ ] **Step 4: 全測試回歸**

Run: `cd backend && python -m pytest -q` 與 `cd src_frontend && npx vitest run`
Expected: 全數通過

- [ ] **Step 5: 標記 Phase 1 完成**

於 spec 或 commit message 註記 Phase 1 完成，準備進入 Phase 2（Excel 匯入/匯出）。

---

## 完成後（Phase 2 / 3 預告）

- **Phase 2**：Excel 匯入（解析多工作表轉置格式）+ 匯出/列印報表。
- **Phase 3**：SPC `mechanical` adapter + 進階 SPC 頁支援 + 儀表板趨勢。

（兩者各自另開 plan。）
