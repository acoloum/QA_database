# CQI-9 每季爐溫測試模組 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 QMS 新增「爐溫測試（Pyrometry）」模組，記錄並管理 5 台爐的 TUS/SAT 定期測試，含自動判定、上傳資料自動繪圖、到期提醒、總覽看板、報告匯出與歷年趨勢。

**Architecture:** 沿用既有 Blueprint + Service + `models.py`（中文欄位名）後端模式與 React Query + 列表/彈窗表單前端模式。新增 4 張資料表（設備主檔、測試主檔、TUS/SAT 明細），附件沿用既有 `Attachment` 表並擴充「用途」分類。資料檔解析在後端用 pandas，繪圖在前端用 chart.js。

**Tech Stack:** Flask 3.1 / SQLAlchemy / PostgreSQL（測試用 SQLite in-memory）/ pandas / React 19 + TypeScript / TanStack React Query / chart.js + react-chartjs-2 / Bootstrap。

**參考規格：** `docs/superpowers/specs/2026-06-16-cqi9-pyrometry-quarterly-furnace-test-design.md`

---

## 慣例（每個 Task 都適用）

- 後端 service 一律 `@staticmethod`，輸入/輸出用中文 key 的 dict，DB 例外時 `db.session.rollback()` 後 `raise`（照抄 `backend/services/extrusion_tolerance_service.py`）。
- 路由用 `@auth_required`，例外回 `jsonify({"error": handle_db_error(e)}), 500`，找不到資料 `raise ValueError` → route 回 404（照抄 `backend/routes/extrusion_tolerance.py`）。
- 測試放 `backend/tests/test_services/`，用 `app` / `db_session` fixture（見 `backend/tests/conftest.py`），DB 為 SQLite in-memory，每測試 `db.create_all()` / `db.drop_all()`。
- 跑後端測試指令（在 repo 根目錄、venv 已啟動）：`python -m pytest backend/tests/test_services/test_pyrometry.py -v`
- 前端頁面放 `src_frontend/src/pages/pyrometry/`，API 呼叫用 `src_frontend/src/services/api.ts` 的 `api` 實例；型別加在 `src_frontend/src/types/index.ts`。
- migration 為 raw SQL，置於 `backend/migration/`，下一個編號為 `21`。
- commit 訊息用繁體中文，結尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## File Structure

**後端（新增）**
- `backend/models.py`（修改）— 新增 4 個模型 + `Attachment` 加 `用途` 欄位
- `backend/migration/21_add_pyrometry.sql`（新增）— 建 4 表 + Attachment 加欄位
- `backend/services/pyrometry_service.py`（新增）— 設備主檔/測試 CRUD、判定、到期、趨勢
- `backend/services/pyrometry_parser.py`（新增）— CSV/Excel 時間序列解析 + 摘要計算
- `backend/routes/pyrometry.py`（新增）— HTTP 路由
- `backend/services/attachment_service.py`（修改）— `VALID_ENTITY_TYPES` 加 `'pyrometry'`、upload 接受 `用途`
- `backend/app.py`（修改）— 註冊 blueprint
- `backend/tests/test_services/test_pyrometry.py`（新增）— service/parser 測試

**前端（新增）**
- `src_frontend/src/types/index.ts`（修改）— 新增型別
- `src_frontend/src/pages/pyrometry/PyrometryDashboardPage.tsx`（新增）— 總覽看板
- `src_frontend/src/pages/pyrometry/PyrometryTestListPage.tsx`（新增）— 測試紀錄列表
- `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`（新增）— 新增/編輯彈窗（含明細表、上傳、曲線圖）
- `src_frontend/src/pages/pyrometry/FurnaceMasterPage.tsx`（新增）— 設備主檔 CRUD + 趨勢
- `src_frontend/src/components/pyrometry/TusChart.tsx`（新增）— chart.js 多通道曲線
- `src_frontend/src/App.tsx`（修改）— 4 條路由
- `src_frontend/src/components/Sidebar.tsx`（修改）— 選單群組

---

# 階段一：設備主檔（Furnace Master）

完成後可運作：5 台爐的 CRUD，後端有測試覆蓋。

## Task 1: 設備主檔 Model

**Files:**
- Modify: `backend/models.py`（檔尾新增）

- [ ] **Step 1: 在 `backend/models.py` 檔尾新增模型**

```python
# ============================================================
# CQI-9 爐溫測試模組
# ============================================================
class Furnace(db.Model):
    """爐子設備主檔 — CQI-9 納管的熱處理爐"""
    __tablename__ = '爐子設備'

    id              = db.Column('識別碼',   db.Integer, primary_key=True)
    code            = db.Column('爐號',     db.String(50), unique=True, nullable=False)
    name            = db.Column('名稱',     db.String(100), nullable=False)
    process_type    = db.Column('製程類型', db.String(20), nullable=True)   # T6時效/T4/退火
    tus_points      = db.Column('TUS點數',  db.Integer, default=12)
    sat_points      = db.Column('SAT點數',  db.Integer, default=2)
    tus_freq_months = db.Column('TUS頻率_月', db.Integer, default=3)        # 每季=3
    sat_freq_months = db.Column('SAT頻率_月', db.Integer, default=3)
    tus_tolerance   = db.Column('TUS允許公差', db.Numeric(6, 2), nullable=True)  # ±°C
    sat_tolerance   = db.Column('SAT允許誤差', db.Numeric(6, 2), nullable=True)  # ±°C
    work_zone       = db.Column('有效加熱區尺寸', db.String(100), nullable=True)
    instrument_type = db.Column('儀器型式', db.String(10), nullable=True)   # CQI-9 A~E
    cqi9_class      = db.Column('CQI9等級', db.String(10), nullable=True)   # 1~6
    is_active       = db.Column('啟用狀態', db.Boolean, default=True, nullable=False)
    note            = db.Column('備註',     db.Text, nullable=True)
    created_at      = db.Column('建立時間', db.DateTime, default=utc_now)
    updated_at      = db.Column('更新時間', db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f'<Furnace {self.code}>'
```

- [ ] **Step 2: 跑既有測試確認沒破壞 import**

Run: `python -m pytest backend/tests/test_services/test_vendor_performance.py -v`
Expected: PASS（確認 models.py 仍可 import）

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "feat(pyrometry): 新增爐子設備主檔 Furnace model"
```

## Task 2: 設備主檔 migration

**Files:**
- Create: `backend/migration/21_add_pyrometry.sql`

- [ ] **Step 1: 建立 migration（本 Task 先建設備主檔，其餘表在 Task 6 補同檔）**

於 `backend/migration/21_add_pyrometry.sql` 寫入：

```sql
-- 21_add_pyrometry.sql — CQI-9 爐溫測試模組
-- 執行：psql -U postgres -d qa_database -f backend/migration/21_add_pyrometry.sql

BEGIN;

-- ① 爐子設備主檔
CREATE TABLE IF NOT EXISTS "爐子設備" (
    "識別碼"      SERIAL PRIMARY KEY,
    "爐號"        VARCHAR(50)  NOT NULL UNIQUE,
    "名稱"        VARCHAR(100) NOT NULL,
    "製程類型"    VARCHAR(20),
    "TUS點數"     INTEGER DEFAULT 12,
    "SAT點數"     INTEGER DEFAULT 2,
    "TUS頻率_月"  INTEGER DEFAULT 3,
    "SAT頻率_月"  INTEGER DEFAULT 3,
    "TUS允許公差" NUMERIC(6,2),
    "SAT允許誤差" NUMERIC(6,2),
    "有效加熱區尺寸" VARCHAR(100),
    "儀器型式"    VARCHAR(10),
    "CQI9等級"    VARCHAR(10),
    "啟用狀態"    BOOLEAN NOT NULL DEFAULT TRUE,
    "備註"        TEXT,
    "建立時間"    TIMESTAMP DEFAULT now(),
    "更新時間"    TIMESTAMP DEFAULT now()
);

COMMIT;
```

- [ ] **Step 2: Commit**（migration 套用由使用者於部署時執行；測試環境用 `db.create_all()`）

```bash
git add backend/migration/21_add_pyrometry.sql
git commit -m "feat(pyrometry): 新增爐子設備主檔 migration"
```

## Task 3: 設備主檔 Service（CRUD）

**Files:**
- Create: `backend/services/pyrometry_service.py`
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫失敗測試**

於 `backend/tests/test_services/test_pyrometry.py` 寫入：

```python
"""CQI-9 爐溫測試模組測試"""
import pytest
from datetime import date
from backend.models import Furnace
from backend.services.pyrometry_service import PyrometryService


def test_furnace_add_and_get(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({
            "爐號": "F-01", "名稱": "1號時效爐", "製程類型": "T6時效",
            "TUS點數": 12, "SAT點數": 2, "TUS允許公差": 10, "SAT允許誤差": 5,
        })
        assert fid is not None
        detail = PyrometryService.get_furnace(fid)
        assert detail["爐號"] == "F-01"
        assert detail["TUS點數"] == 12


def test_furnace_list_only_active_by_default(app, db_session):
    with app.app_context():
        a = PyrometryService.add_furnace({"爐號": "F-A", "名稱": "啟用爐"})
        b = PyrometryService.add_furnace({"爐號": "F-B", "名稱": "停用爐"})
        PyrometryService.update_furnace(b, {"爐號": "F-B", "名稱": "停用爐", "啟用狀態": False})
        rows = PyrometryService.list_furnaces(active_only=True)
        codes = [r["爐號"] for r in rows]
        assert "F-A" in codes and "F-B" not in codes
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: FAIL（`ModuleNotFoundError: pyrometry_service`）

- [ ] **Step 3: 建立 service**

於 `backend/services/pyrometry_service.py` 寫入：

```python
"""CQI-9 爐溫測試服務 — 設備主檔、測試紀錄、判定、到期、趨勢"""
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from ..extensions import db
from ..models import Furnace
from ..utils import format_value


def _furnace_to_dict(f: Furnace) -> Dict[str, Any]:
    return {
        "識別碼": f.id, "爐號": f.code, "名稱": f.name,
        "製程類型": f.process_type or "",
        "TUS點數": f.tus_points, "SAT點數": f.sat_points,
        "TUS頻率_月": f.tus_freq_months, "SAT頻率_月": f.sat_freq_months,
        "TUS允許公差": format_value(f.tus_tolerance),
        "SAT允許誤差": format_value(f.sat_tolerance),
        "有效加熱區尺寸": f.work_zone or "",
        "儀器型式": f.instrument_type or "", "CQI9等級": f.cqi9_class or "",
        "啟用狀態": f.is_active, "備註": f.note or "",
    }


class PyrometryService:

    # ---------- 設備主檔 ----------
    @staticmethod
    def list_furnaces(active_only: bool = False) -> List[Dict[str, Any]]:
        q = Furnace.query
        if active_only:
            q = q.filter(Furnace.is_active.is_(True))
        return [_furnace_to_dict(f) for f in q.order_by(Furnace.code).all()]

    @staticmethod
    def get_furnace(furnace_id: int) -> Dict[str, Any]:
        f = db.session.get(Furnace, furnace_id)
        if not f:
            raise ValueError("找不到該爐子設備")
        return _furnace_to_dict(f)

    @staticmethod
    def add_furnace(data: Dict[str, Any]) -> int:
        try:
            f = Furnace(
                code=data.get("爐號"), name=data.get("名稱"),
                process_type=data.get("製程類型") or None,
                tus_points=int(data.get("TUS點數", 12) or 12),
                sat_points=int(data.get("SAT點數", 2) or 2),
                tus_freq_months=int(data.get("TUS頻率_月", 3) or 3),
                sat_freq_months=int(data.get("SAT頻率_月", 3) or 3),
                tus_tolerance=data.get("TUS允許公差") or None,
                sat_tolerance=data.get("SAT允許誤差") or None,
                work_zone=data.get("有效加熱區尺寸") or None,
                instrument_type=data.get("儀器型式") or None,
                cqi9_class=data.get("CQI9等級") or None,
                is_active=bool(data.get("啟用狀態", True)),
                note=data.get("備註") or None,
            )
            db.session.add(f)
            db.session.commit()
            return f.id
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_furnace(furnace_id: int, data: Dict[str, Any]) -> bool:
        try:
            f = db.session.get(Furnace, furnace_id)
            if not f:
                raise ValueError("找不到該爐子設備")
            f.code = data.get("爐號")
            f.name = data.get("名稱")
            f.process_type = data.get("製程類型") or None
            f.tus_points = int(data.get("TUS點數", 12) or 12)
            f.sat_points = int(data.get("SAT點數", 2) or 2)
            f.tus_freq_months = int(data.get("TUS頻率_月", 3) or 3)
            f.sat_freq_months = int(data.get("SAT頻率_月", 3) or 3)
            f.tus_tolerance = data.get("TUS允許公差") or None
            f.sat_tolerance = data.get("SAT允許誤差") or None
            f.work_zone = data.get("有效加熱區尺寸") or None
            f.instrument_type = data.get("儀器型式") or None
            f.cqi9_class = data.get("CQI9等級") or None
            f.is_active = bool(data.get("啟用狀態", True))
            f.note = data.get("備註") or None
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_furnace(furnace_id: int) -> bool:
        try:
            f = db.session.get(Furnace, furnace_id)
            if not f:
                raise ValueError("找不到該爐子設備")
            db.session.delete(f)
            db.session.commit()
            return True
        except ValueError:
            raise
        except Exception as e:
            db.session.rollback()
            raise e
```

> 註：`add_furnace` 用到 `dateutil.relativedelta`（Task 9 到期計算才會用到），此處 import 先保留。若 `python-dateutil` 未安裝，於 `backend/requirements.txt` 加入 `python-dateutil` 並 `pip install python-dateutil`。

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS（3 個測試）

- [ ] **Step 5: Commit**

```bash
git add backend/services/pyrometry_service.py backend/tests/test_services/test_pyrometry.py backend/requirements.txt
git commit -m "feat(pyrometry): 設備主檔 CRUD 服務與測試"
```

## Task 4: 設備主檔 路由 + 註冊 blueprint

**Files:**
- Create: `backend/routes/pyrometry.py`
- Modify: `backend/app.py:23`（import）、`backend/app.py:75`（register）

- [ ] **Step 1: 建立路由**

於 `backend/routes/pyrometry.py` 寫入：

```python
from flask import Blueprint, jsonify, request
from ..services.pyrometry_service import PyrometryService
from ..utils import auth_required, handle_db_error

pyrometry_bp = Blueprint('pyrometry', __name__)


# ---------- 設備主檔 ----------
@pyrometry_bp.route('/api/pyrometry/furnaces', methods=['GET'])
@auth_required
def list_furnaces():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_furnaces(active_only)})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['GET'])
@auth_required
def get_furnace(fid):
    try:
        return jsonify({"success": True, "data": PyrometryService.get_furnace(fid)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@pyrometry_bp.route('/api/pyrometry/furnaces', methods=['POST'])
@auth_required
def add_furnace():
    try:
        new_id = PyrometryService.add_furnace(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['PUT'])
@auth_required
def update_furnace(fid):
    try:
        PyrometryService.update_furnace(fid, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['DELETE'])
@auth_required
def delete_furnace(fid):
    try:
        PyrometryService.delete_furnace(fid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
```

- [ ] **Step 2: 在 `backend/app.py` 註冊**

在 import 區（約 `backend/app.py:23` 之後）加：
```python
from .routes.pyrometry import pyrometry_bp
```
在 register 區（約 `backend/app.py:75` 之後）加：
```python
app.register_blueprint(pyrometry_bp)
```

- [ ] **Step 3: 寫路由整合測試（附加到 test_pyrometry.py）**

```python
def _auth_header(client, db_session):
    """建立測試使用者並回傳 Authorization header"""
    from backend.models import User
    from backend.utils import hash_password, generate_token
    u = User(username="pyro_tester", password=hash_password("pw"), role="admin")
    db_session.add(u)
    db_session.commit()
    token = generate_token(u.id, u.username, u.role)
    return {"Authorization": f"Bearer {token}"}


def test_furnace_api_crud(client, db_session):
    headers = _auth_header(client, db_session)
    r = client.post("/api/pyrometry/furnaces", json={"爐號": "F-09", "名稱": "退火爐"}, headers=headers)
    assert r.status_code == 200
    fid = r.get_json()["id"]
    r = client.get("/api/pyrometry/furnaces", headers=headers)
    assert any(x["爐號"] == "F-09" for x in r.get_json()["data"])
```

> 確認 `generate_token` / `hash_password` 簽名：先看 `backend/utils.py` 對應函式定義，若參數不同（如 `generate_token(user)`）依實際簽名調整本段。

- [ ] **Step 4: 跑測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/pyrometry.py backend/app.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): 設備主檔 API 路由與整合測試"
```

## Task 5: 設備主檔前端頁面

**Files:**
- Modify: `src_frontend/src/types/index.ts`（檔尾新增）
- Create: `src_frontend/src/pages/pyrometry/FurnaceMasterPage.tsx`
- Modify: `src_frontend/src/App.tsx`、`src_frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: 新增型別（`src_frontend/src/types/index.ts` 檔尾）**

```typescript
// CQI-9 爐溫測試
export interface Furnace {
  識別碼: number;
  爐號: string;
  名稱: string;
  製程類型: string;
  TUS點數: number;
  SAT點數: number;
  TUS頻率_月: number;
  SAT頻率_月: number;
  TUS允許公差: string;
  SAT允許誤差: string;
  有效加熱區尺寸: string;
  儀器型式: string;
  CQI9等級: string;
  啟用狀態: boolean;
  備註: string;
}
```

- [ ] **Step 2: 建立設備主檔頁面**

於 `src_frontend/src/pages/pyrometry/FurnaceMasterPage.tsx` 建立一個 React Query 驅動的列表 + 新增/編輯彈窗頁面。**結構照抄 `src_frontend/src/pages/extrusion-tolerance/ExtrusionTolerancePage.tsx`**（同樣的 useQuery 列表 + Bootstrap modal 表單 + toast），欄位改為 Furnace 介面所列。API 端點：
  - 列表：`GET /api/pyrometry/furnaces` → `data: Furnace[]`
  - 新增：`POST /api/pyrometry/furnaces`（body 為中文 key）
  - 更新：`PUT /api/pyrometry/furnaces/{id}`
  - 刪除：`DELETE /api/pyrometry/furnaces/{id}`

表單欄位：爐號、名稱、製程類型（下拉：T6時效/T4/退火）、TUS點數（number, 預設12）、SAT點數（number）、TUS頻率_月（number, 預設3）、SAT頻率_月、TUS允許公差、SAT允許誤差、有效加熱區尺寸、儀器型式、CQI9等級、啟用狀態（checkbox）、備註。

- [ ] **Step 3: 註冊路由（`src_frontend/src/App.tsx`）**

在 lazy import 區加：
```typescript
const FurnaceMasterPage = lazy(() => import('./pages/pyrometry/FurnaceMasterPage'));
```
在受保護路由 `<Route element={<MainLayout />}>` 內加：
```tsx
<Route path="/pyrometry/furnaces" element={<FurnaceMasterPage />} />
```

- [ ] **Step 4: 加選單（`src_frontend/src/components/Sidebar.tsx`）**

在 `menuGroups` 陣列「功能選單」群組後，新增一個群組：
```typescript
{
    title: '爐溫測試 (CQI-9)',
    items: [
        { title: '設備主檔', path: '/pyrometry/furnaces', icon: 'fa-fire' },
    ]
},
```

- [ ] **Step 5: 驗證 build + lint**

Run: `cd src_frontend && npm run build`
Expected: TypeScript 編譯通過、無錯誤

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/types/index.ts src_frontend/src/pages/pyrometry/FurnaceMasterPage.tsx src_frontend/src/App.tsx src_frontend/src/components/Sidebar.tsx
git commit -m "feat(pyrometry): 設備主檔前端頁面與選單"
```

---

# 階段二：測試紀錄 + 明細 + 自動判定

完成後可運作：新增/查詢 TUS、SAT 測試紀錄（手動填量測點），系統自動判定合格與否。

## Task 6: 測試主檔 + TUS/SAT 明細 Model 與 migration

**Files:**
- Modify: `backend/models.py`、`backend/migration/21_add_pyrometry.sql`

- [ ] **Step 1: 在 `backend/models.py` 接續 Furnace 後新增 3 個模型**

```python
class PyrometryTest(SoftDeleteMixin, db.Model):
    """爐溫測試主檔 — 每次 TUS 或 SAT 一筆"""
    __tablename__ = '爐溫測試'

    id            = db.Column('識別碼', db.Integer, primary_key=True)
    furnace_id    = db.Column('爐子ID', db.Integer, db.ForeignKey('爐子設備.識別碼'), nullable=False)
    test_type     = db.Column('測試類型', db.String(10), nullable=False)   # TUS / SAT
    quarter       = db.Column('季別', db.String(10), nullable=True)        # 2026Q2
    test_date     = db.Column('測試日期', db.Date, nullable=False, index=True)
    setpoint      = db.Column('設定溫度', db.Numeric(8, 2), nullable=False)
    tolerance     = db.Column('允許公差', db.Numeric(6, 2), nullable=True)
    tester_id     = db.Column('測試人員', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    test_instrument = db.Column('測試儀器編號', db.String(100), nullable=True)
    std_instrument  = db.Column('標準校正儀器編號', db.String(100), nullable=True)
    cal_due_date  = db.Column('儀器校正到期日', db.Date, nullable=True)
    is_pass       = db.Column('是否合格', db.Boolean, default=False, index=True)
    tus_range     = db.Column('TUS均勻度極差', db.Numeric(8, 2), nullable=True)
    tus_max_pos   = db.Column('TUS最大正偏差', db.Numeric(8, 2), nullable=True)
    tus_max_neg   = db.Column('TUS最大負偏差', db.Numeric(8, 2), nullable=True)
    note          = db.Column('備註', db.Text, nullable=True)
    created_by    = db.Column('建立人', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    created_at    = db.Column('建立時間', db.DateTime, default=utc_now)
    updated_at    = db.Column('更新時間', db.DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.Index('idx_pyro_furnace_type_date', '爐子ID', '測試類型', '測試日期'),
    )

    furnace    = db.relationship('Furnace', backref='tests')
    tester     = db.relationship('Inspector', foreign_keys=[tester_id])
    tus_points = db.relationship('TusPoint', backref='test', cascade='all, delete-orphan')
    sat_points = db.relationship('SatPoint', backref='test', cascade='all, delete-orphan')


class TusPoint(db.Model):
    """TUS 量測點明細 — 每筆=一支熱電偶"""
    __tablename__ = 'TUS量測點明細'

    id          = db.Column('識別碼', db.Integer, primary_key=True)
    test_id     = db.Column('測試ID', db.Integer, db.ForeignKey('爐溫測試.識別碼'), nullable=False)
    position    = db.Column('點位', db.String(20), nullable=True)        # P1~P12
    tc_no       = db.Column('熱電偶編號', db.String(50), nullable=True)
    correction  = db.Column('修正值', db.Numeric(8, 2), nullable=True)
    temp_max    = db.Column('最高溫', db.Numeric(8, 2), nullable=True)
    temp_min    = db.Column('最低溫', db.Numeric(8, 2), nullable=True)
    max_dev     = db.Column('最大偏差', db.Numeric(8, 2), nullable=True)
    is_pass     = db.Column('是否合格', db.Boolean, default=True)


class SatPoint(db.Model):
    """SAT 量測點明細 — 每筆=一個控溫區"""
    __tablename__ = 'SAT量測點明細'

    id           = db.Column('識別碼', db.Integer, primary_key=True)
    test_id      = db.Column('測試ID', db.Integer, db.ForeignKey('爐溫測試.識別碼'), nullable=False)
    zone         = db.Column('控溫區', db.String(20), nullable=True)
    control_read = db.Column('控制儀表讀值', db.Numeric(8, 2), nullable=True)
    test_read    = db.Column('校正測試儀表讀值', db.Numeric(8, 2), nullable=True)
    diff         = db.Column('差值', db.Numeric(8, 2), nullable=True)
    correction   = db.Column('修正值', db.Numeric(8, 2), nullable=True)
    deviation    = db.Column('偏差', db.Numeric(8, 2), nullable=True)
    is_pass      = db.Column('是否合格', db.Boolean, default=True)
```

- [ ] **Step 2: 在 `backend/migration/21_add_pyrometry.sql` 的 `COMMIT;` 前插入建表 SQL**

```sql
-- ② 爐溫測試主檔
CREATE TABLE IF NOT EXISTS "爐溫測試" (
    "識別碼" SERIAL PRIMARY KEY,
    "爐子ID" INTEGER NOT NULL REFERENCES "爐子設備"("識別碼"),
    "測試類型" VARCHAR(10) NOT NULL,
    "季別" VARCHAR(10),
    "測試日期" DATE NOT NULL,
    "設定溫度" NUMERIC(8,2) NOT NULL,
    "允許公差" NUMERIC(6,2),
    "測試人員" INTEGER REFERENCES "品管人員"("識別碼"),
    "測試儀器編號" VARCHAR(100),
    "標準校正儀器編號" VARCHAR(100),
    "儀器校正到期日" DATE,
    "是否合格" BOOLEAN DEFAULT FALSE,
    "TUS均勻度極差" NUMERIC(8,2),
    "TUS最大正偏差" NUMERIC(8,2),
    "TUS最大負偏差" NUMERIC(8,2),
    "備註" TEXT,
    "建立人" INTEGER REFERENCES "使用者"("識別碼"),
    "建立時間" TIMESTAMP DEFAULT now(),
    "更新時間" TIMESTAMP DEFAULT now(),
    "刪除時間" TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pyro_furnace_type_date ON "爐溫測試" ("爐子ID","測試類型","測試日期");
CREATE INDEX IF NOT EXISTS idx_pyro_deleted ON "爐溫測試" ("刪除時間");

-- ③ TUS 量測點明細
CREATE TABLE IF NOT EXISTS "TUS量測點明細" (
    "識別碼" SERIAL PRIMARY KEY,
    "測試ID" INTEGER NOT NULL REFERENCES "爐溫測試"("識別碼") ON DELETE CASCADE,
    "點位" VARCHAR(20),
    "熱電偶編號" VARCHAR(50),
    "修正值" NUMERIC(8,2),
    "最高溫" NUMERIC(8,2),
    "最低溫" NUMERIC(8,2),
    "最大偏差" NUMERIC(8,2),
    "是否合格" BOOLEAN DEFAULT TRUE
);

-- ④ SAT 量測點明細
CREATE TABLE IF NOT EXISTS "SAT量測點明細" (
    "識別碼" SERIAL PRIMARY KEY,
    "測試ID" INTEGER NOT NULL REFERENCES "爐溫測試"("識別碼") ON DELETE CASCADE,
    "控溫區" VARCHAR(20),
    "控制儀表讀值" NUMERIC(8,2),
    "校正測試儀表讀值" NUMERIC(8,2),
    "差值" NUMERIC(8,2),
    "修正值" NUMERIC(8,2),
    "偏差" NUMERIC(8,2),
    "是否合格" BOOLEAN DEFAULT TRUE
);
```

- [ ] **Step 3: 跑測試確認 models 可 import**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS（既有測試仍通過）

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/migration/21_add_pyrometry.sql
git commit -m "feat(pyrometry): 新增測試主檔與 TUS/SAT 明細 model 與 migration"
```

## Task 7: 判定邏輯（純函式，先測）

**Files:**
- Modify: `backend/services/pyrometry_service.py`、`backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫失敗測試**

```python
def test_evaluate_tus_pass():
    """設定溫度180、公差±10：各點偏差皆在內 → 合格，並算均勻度極差"""
    points = [
        {"最高溫": 186, "最低溫": 178},
        {"最高溫": 183, "最低溫": 179},
    ]
    result = PyrometryService.evaluate_tus(setpoint=180, tolerance=10, points=points)
    assert result["是否合格"] is True
    assert result["TUS均勻度極差"] == 8        # 186 - 178
    assert result["TUS最大正偏差"] == 6         # 186 - 180
    assert result["TUS最大負偏差"] == -2        # 178 - 180
    assert result["points"][0]["最大偏差"] == 6
    assert result["points"][0]["是否合格"] is True


def test_evaluate_tus_fail():
    """某點最高溫191 → 偏差+11 超過±10 → 不合格"""
    points = [{"最高溫": 191, "最低溫": 175}]
    result = PyrometryService.evaluate_tus(setpoint=180, tolerance=10, points=points)
    assert result["是否合格"] is False
    assert result["points"][0]["是否合格"] is False


def test_evaluate_sat_pass_and_fail():
    """SAT：偏差=測試-控制；公差±5"""
    points = [
        {"控制儀表讀值": 180, "校正測試儀表讀值": 183},   # diff +3 OK
        {"控制儀表讀值": 180, "校正測試儀表讀值": 187},   # diff +7 NG
    ]
    result = PyrometryService.evaluate_sat(tolerance=5, points=points)
    assert result["points"][0]["差值"] == 3
    assert result["points"][0]["是否合格"] is True
    assert result["points"][1]["是否合格"] is False
    assert result["是否合格"] is False
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_evaluate_tus_pass -v`
Expected: FAIL（`AttributeError: evaluate_tus`）

- [ ] **Step 3: 在 `PyrometryService` 加判定方法**

```python
    # ---------- 判定邏輯 ----------
    @staticmethod
    def evaluate_tus(setpoint: float, tolerance: float, points: List[Dict[str, Any]]) -> Dict[str, Any]:
        sp = float(setpoint)
        tol = float(tolerance)
        out_points = []
        all_max, all_min = [], []
        overall_pass = True
        for p in points:
            tmax = p.get("最高溫")
            tmin = p.get("最低溫")
            tmax = float(tmax) if tmax is not None else None
            tmin = float(tmin) if tmin is not None else None
            dev_candidates = []
            if tmax is not None:
                dev_candidates.append(tmax - sp); all_max.append(tmax)
            if tmin is not None:
                dev_candidates.append(tmin - sp); all_min.append(tmin)
            # 最大偏差 = 絕對值最大的偏差（保留正負號）
            max_dev = max(dev_candidates, key=abs) if dev_candidates else None
            pt_pass = max_dev is None or abs(max_dev) <= tol
            overall_pass = overall_pass and pt_pass
            np = dict(p)
            np["最大偏差"] = round(max_dev, 2) if max_dev is not None else None
            np["是否合格"] = pt_pass
            out_points.append(np)
        tus_range = round(max(all_max) - min(all_min), 2) if all_max and all_min else None
        max_pos = round(max(all_max) - sp, 2) if all_max else None
        max_neg = round(min(all_min) - sp, 2) if all_min else None
        return {
            "是否合格": overall_pass, "TUS均勻度極差": tus_range,
            "TUS最大正偏差": max_pos, "TUS最大負偏差": max_neg, "points": out_points,
        }

    @staticmethod
    def evaluate_sat(tolerance: float, points: List[Dict[str, Any]]) -> Dict[str, Any]:
        tol = float(tolerance)
        out_points = []
        overall_pass = True
        for p in points:
            ctrl = p.get("控制儀表讀值")
            test = p.get("校正測試儀表讀值")
            corr = p.get("修正值") or 0
            diff = None
            if ctrl is not None and test is not None:
                diff = round(float(test) - float(ctrl), 2)
            deviation = round(diff + float(corr), 2) if diff is not None else None
            pt_pass = deviation is None or abs(deviation) <= tol
            overall_pass = overall_pass and pt_pass
            np = dict(p)
            np["差值"] = diff
            np["偏差"] = deviation
            np["是否合格"] = pt_pass
            out_points.append(np)
        return {"是否合格": overall_pass, "points": out_points}
```

- [ ] **Step 4: 跑全部判定測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -k evaluate -v`
Expected: PASS（3 個）

- [ ] **Step 5: Commit**

```bash
git add backend/services/pyrometry_service.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): TUS/SAT 自動判定邏輯與測試"
```

## Task 8: 測試紀錄 CRUD Service（含明細與判定整合）

**Files:**
- Modify: `backend/services/pyrometry_service.py`、`backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫失敗測試**

```python
def _make_furnace(tol=10):
    return PyrometryService.add_furnace({"爐號": "F-T", "名稱": "測試爐", "TUS允許公差": tol})


def test_create_tus_test_auto_judges(app, db_session):
    with app.app_context():
        fid = _make_furnace(tol=10)
        tid = PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "TUS", "測試日期": "2026-04-15",
            "設定溫度": 180, "允許公差": 10,
            "points": [{"點位": "P1", "最高溫": 186, "最低溫": 178},
                       {"點位": "P2", "最高溫": 183, "最低溫": 179}],
        })
        detail = PyrometryService.get_test(tid)
        assert detail["main"]["是否合格"] is True
        assert detail["main"]["季別"] == "2026Q2"          # 由日期自動帶
        assert detail["main"]["TUS均勻度極差"] == 8
        assert len(detail["tus_points"]) == 2


def test_create_sat_test_auto_judges(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-S", "名稱": "退火爐", "SAT允許誤差": 5})
        tid = PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "SAT", "測試日期": "2026-04-15",
            "設定溫度": 180, "允許公差": 5,
            "points": [{"控溫區": "Z1", "控制儀表讀值": 180, "校正測試儀表讀值": 187}],
        })
        detail = PyrometryService.get_test(tid)
        assert detail["main"]["是否合格"] is False
        assert len(detail["sat_points"]) == 1
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -k "create_tus or create_sat" -v`
Expected: FAIL（`AttributeError: create_test`）

- [ ] **Step 3: 加 helper 與 CRUD 方法**

在 `pyrometry_service.py` 頂部 import 區下方加 helper：

```python
def _quarter_of(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def _parse_date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])
```

在 `PyrometryService` 內加：

```python
    # ---------- 測試紀錄 ----------
    @staticmethod
    def create_test(data: Dict[str, Any]) -> int:
        from ..models import PyrometryTest, TusPoint, SatPoint
        try:
            test_date = _parse_date(data.get("測試日期"))
            test_type = data.get("測試類型")
            tolerance = float(data.get("允許公差") or 0)
            setpoint = float(data.get("設定溫度") or 0)
            raw_points = data.get("points", [])

            if test_type == "TUS":
                judged = PyrometryService.evaluate_tus(setpoint, tolerance, raw_points)
            else:
                judged = PyrometryService.evaluate_sat(tolerance, raw_points)

            t = PyrometryTest(
                furnace_id=data.get("爐子ID"), test_type=test_type,
                quarter=data.get("季別") or _quarter_of(test_date),
                test_date=test_date, setpoint=setpoint, tolerance=tolerance,
                tester_id=data.get("測試人員") or None,
                test_instrument=data.get("測試儀器編號") or None,
                std_instrument=data.get("標準校正儀器編號") or None,
                cal_due_date=_parse_date(data.get("儀器校正到期日")),
                is_pass=judged["是否合格"],
                tus_range=judged.get("TUS均勻度極差"),
                tus_max_pos=judged.get("TUS最大正偏差"),
                tus_max_neg=judged.get("TUS最大負偏差"),
                note=data.get("備註") or None,
                created_by=data.get("建立人") or None,
            )
            db.session.add(t)
            db.session.flush()

            for p in judged["points"]:
                if test_type == "TUS":
                    db.session.add(TusPoint(
                        test_id=t.id, position=p.get("點位"), tc_no=p.get("熱電偶編號"),
                        correction=p.get("修正值"), temp_max=p.get("最高溫"),
                        temp_min=p.get("最低溫"), max_dev=p.get("最大偏差"),
                        is_pass=p.get("是否合格", True),
                    ))
                else:
                    db.session.add(SatPoint(
                        test_id=t.id, zone=p.get("控溫區"),
                        control_read=p.get("控制儀表讀值"), test_read=p.get("校正測試儀表讀值"),
                        diff=p.get("差值"), correction=p.get("修正值"),
                        deviation=p.get("偏差"), is_pass=p.get("是否合格", True),
                    ))
            db.session.commit()
            return t.id
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_test(test_id: int) -> Dict[str, Any]:
        from ..models import PyrometryTest
        t = PyrometryTest.query.filter(
            PyrometryTest.id == test_id, PyrometryTest.deleted_at.is_(None)
        ).first()
        if not t:
            raise ValueError("找不到該筆爐溫測試")
        main = {
            "識別碼": t.id, "爐子ID": t.furnace_id,
            "爐號": t.furnace.code if t.furnace else "",
            "測試類型": t.test_type, "季別": t.quarter or "",
            "測試日期": format_value(t.test_date), "設定溫度": format_value(t.setpoint),
            "允許公差": format_value(t.tolerance),
            "測試人員": t.tester_id, "測試人員姓名": t.tester.name if t.tester else "",
            "測試儀器編號": t.test_instrument or "", "標準校正儀器編號": t.std_instrument or "",
            "儀器校正到期日": format_value(t.cal_due_date),
            "是否合格": t.is_pass, "TUS均勻度極差": format_value(t.tus_range),
            "TUS最大正偏差": format_value(t.tus_max_pos), "TUS最大負偏差": format_value(t.tus_max_neg),
            "備註": t.note or "",
        }
        tus_points = [{
            "識別碼": p.id, "點位": p.position or "", "熱電偶編號": p.tc_no or "",
            "修正值": format_value(p.correction), "最高溫": format_value(p.temp_max),
            "最低溫": format_value(p.temp_min), "最大偏差": format_value(p.max_dev),
            "是否合格": p.is_pass,
        } for p in sorted(t.tus_points, key=lambda x: x.id)]
        sat_points = [{
            "識別碼": p.id, "控溫區": p.zone or "", "控制儀表讀值": format_value(p.control_read),
            "校正測試儀表讀值": format_value(p.test_read), "差值": format_value(p.diff),
            "修正值": format_value(p.correction), "偏差": format_value(p.deviation),
            "是否合格": p.is_pass,
        } for p in sorted(t.sat_points, key=lambda x: x.id)]
        return {"success": True, "main": main, "tus_points": tus_points, "sat_points": sat_points}

    @staticmethod
    def update_test(test_id: int, data: Dict[str, Any]) -> bool:
        """更新主檔 + 重建明細（沿用擠壓公差的刪除重建模式）"""
        from ..models import PyrometryTest, TusPoint, SatPoint
        try:
            t = db.session.get(PyrometryTest, test_id)
            if not t or t.deleted_at is not None:
                raise ValueError("找不到該筆爐溫測試")
            test_date = _parse_date(data.get("測試日期"))
            tolerance = float(data.get("允許公差") or 0)
            setpoint = float(data.get("設定溫度") or 0)
            raw_points = data.get("points", [])
            if t.test_type == "TUS":
                judged = PyrometryService.evaluate_tus(setpoint, tolerance, raw_points)
            else:
                judged = PyrometryService.evaluate_sat(tolerance, raw_points)

            t.furnace_id = data.get("爐子ID")
            t.quarter = data.get("季別") or _quarter_of(test_date)
            t.test_date = test_date
            t.setpoint = setpoint
            t.tolerance = tolerance
            t.tester_id = data.get("測試人員") or None
            t.test_instrument = data.get("測試儀器編號") or None
            t.std_instrument = data.get("標準校正儀器編號") or None
            t.cal_due_date = _parse_date(data.get("儀器校正到期日"))
            t.is_pass = judged["是否合格"]
            t.tus_range = judged.get("TUS均勻度極差")
            t.tus_max_pos = judged.get("TUS最大正偏差")
            t.tus_max_neg = judged.get("TUS最大負偏差")
            t.note = data.get("備註") or None

            TusPoint.query.filter_by(test_id=test_id).delete()
            SatPoint.query.filter_by(test_id=test_id).delete()
            for p in judged["points"]:
                if t.test_type == "TUS":
                    db.session.add(TusPoint(
                        test_id=t.id, position=p.get("點位"), tc_no=p.get("熱電偶編號"),
                        correction=p.get("修正值"), temp_max=p.get("最高溫"),
                        temp_min=p.get("最低溫"), max_dev=p.get("最大偏差"),
                        is_pass=p.get("是否合格", True)))
                else:
                    db.session.add(SatPoint(
                        test_id=t.id, zone=p.get("控溫區"),
                        control_read=p.get("控制儀表讀值"), test_read=p.get("校正測試儀表讀值"),
                        diff=p.get("差值"), correction=p.get("修正值"),
                        deviation=p.get("偏差"), is_pass=p.get("是否合格", True)))
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_test(test_id: int) -> bool:
        from ..models import PyrometryTest
        try:
            t = db.session.get(PyrometryTest, test_id)
            if not t or t.deleted_at is not None:
                raise ValueError("找不到該筆爐溫測試")
            t.soft_delete()
            db.session.commit()
            return True
        except ValueError:
            raise
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def search_tests(args: Dict[str, Any]) -> Dict[str, Any]:
        from ..models import PyrometryTest
        q = PyrometryTest.query.filter(PyrometryTest.deleted_at.is_(None))
        if args.get("furnace_id"):
            q = q.filter(PyrometryTest.furnace_id == int(args["furnace_id"]))
        if args.get("test_type"):
            q = q.filter(PyrometryTest.test_type == args["test_type"])
        if args.get("quarter"):
            q = q.filter(PyrometryTest.quarter == args["quarter"])
        if args.get("is_pass") in ("0", "1"):
            q = q.filter(PyrometryTest.is_pass.is_(args["is_pass"] == "1"))
        if args.get("date_from"):
            q = q.filter(PyrometryTest.test_date >= _parse_date(args["date_from"]))
        if args.get("date_to"):
            q = q.filter(PyrometryTest.test_date <= _parse_date(args["date_to"]))
        page = int(args.get("page", 1))
        page_size = int(args.get("page_size", 20))
        total = q.count()
        pg = q.order_by(PyrometryTest.test_date.desc(), PyrometryTest.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False)
        data = [{
            "識別碼": t.id, "爐號": t.furnace.code if t.furnace else "",
            "測試類型": t.test_type, "季別": t.quarter or "",
            "測試日期": format_value(t.test_date), "是否合格": t.is_pass,
            "測試人員姓名": t.tester.name if t.tester else "",
        } for t in pg.items]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": pg.pages}
```

- [ ] **Step 4: 跑測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add backend/services/pyrometry_service.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): 測試紀錄 CRUD 服務（含明細與自動判定整合）"
```

## Task 9: 測試紀錄路由 + 到期計算

**Files:**
- Modify: `backend/routes/pyrometry.py`、`backend/services/pyrometry_service.py`、`backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫到期計算失敗測試**

```python
def test_due_status_overdue(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-D", "名稱": "到期測試爐", "TUS頻率_月": 3})
        # 最近一次 TUS 在 2025-01-01，每季 → 早已逾期（相對 today）
        PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "TUS", "測試日期": "2025-01-01",
            "設定溫度": 180, "允許公差": 10, "points": [{"最高溫": 181, "最低溫": 179}]})
        status = PyrometryService.furnace_due_status(fid)
        assert status["TUS"]["下次應測日"] == "2025-04-01"
        assert status["TUS"]["狀態"] == "逾期"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_due_status_overdue -v`
Expected: FAIL（`AttributeError: furnace_due_status`）

- [ ] **Step 3: 加到期計算方法（用到頂部已 import 的 `relativedelta`、`timedelta`）**

```python
    # ---------- 到期計算 ----------
    @staticmethod
    def _due_for(furnace_id: int, test_type: str, freq_months: int, today: date = None) -> Dict[str, Any]:
        from ..models import PyrometryTest
        today = today or date.today()
        last = PyrometryTest.query.filter(
            PyrometryTest.furnace_id == furnace_id,
            PyrometryTest.test_type == test_type,
            PyrometryTest.deleted_at.is_(None),
        ).order_by(PyrometryTest.test_date.desc()).first()
        if not last:
            return {"最近測試日": None, "下次應測日": None, "狀態": "尚無紀錄"}
        next_due = last.test_date + relativedelta(months=int(freq_months or 3))
        if next_due < today:
            status = "逾期"
        elif next_due - today <= timedelta(days=14):
            status = "即將到期"
        else:
            status = "正常"
        return {"最近測試日": format_value(last.test_date),
                "下次應測日": format_value(next_due), "狀態": status}

    @staticmethod
    def furnace_due_status(furnace_id: int, today: date = None) -> Dict[str, Any]:
        f = db.session.get(Furnace, furnace_id)
        if not f:
            raise ValueError("找不到該爐子設備")
        return {
            "TUS": PyrometryService._due_for(furnace_id, "TUS", f.tus_freq_months, today),
            "SAT": PyrometryService._due_for(furnace_id, "SAT", f.sat_freq_months, today),
        }
```

- [ ] **Step 4: 在 `backend/routes/pyrometry.py` 加測試紀錄路由**

```python
# ---------- 測試紀錄 ----------
@pyrometry_bp.route('/api/pyrometry/tests', methods=['GET'])
@auth_required
def search_tests():
    return jsonify(PyrometryService.search_tests(request.args))


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['GET'])
@auth_required
def get_test(tid):
    try:
        return jsonify(PyrometryService.get_test(tid))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@pyrometry_bp.route('/api/pyrometry/tests', methods=['POST'])
@auth_required
def create_test():
    try:
        new_id = PyrometryService.create_test(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['PUT'])
@auth_required
def update_test(tid):
    try:
        PyrometryService.update_test(tid, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['DELETE'])
@auth_required
def delete_test(tid):
    try:
        PyrometryService.delete_test(tid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
```

- [ ] **Step 5: 跑測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/routes/pyrometry.py backend/services/pyrometry_service.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): 測試紀錄路由與到期計算"
```

## Task 10: 測試紀錄列表頁 + 新增/編輯表單（手動填）

**Files:**
- Modify: `src_frontend/src/types/index.ts`、`src_frontend/src/App.tsx`、`src_frontend/src/components/Sidebar.tsx`
- Create: `src_frontend/src/pages/pyrometry/PyrometryTestListPage.tsx`、`src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`

- [ ] **Step 1: 新增型別（`types/index.ts` 檔尾）**

```typescript
export interface PyrometryTestRow {
  識別碼: number;
  爐號: string;
  測試類型: 'TUS' | 'SAT';
  季別: string;
  測試日期: string;
  是否合格: boolean;
  測試人員姓名: string;
}

export interface TusPoint {
  識別碼?: number;
  點位: string;
  熱電偶編號: string;
  修正值: string | number | null;
  最高溫: string | number | null;
  最低溫: string | number | null;
  最大偏差?: string | number | null;
  是否合格?: boolean;
}

export interface SatPoint {
  識別碼?: number;
  控溫區: string;
  控制儀表讀值: string | number | null;
  校正測試儀表讀值: string | number | null;
  差值?: string | number | null;
  修正值: string | number | null;
  偏差?: string | number | null;
  是否合格?: boolean;
}
```

- [ ] **Step 2: 建立列表頁 `PyrometryTestListPage.tsx`**

React Query 列表，篩選列：爐子（下拉，來源 `GET /api/pyrometry/furnaces?active_only=1`）、測試類型（TUS/SAT/全部）、季別（文字）、合格狀態（全部/合格/不合格）、日期區間。表格欄：爐號、類型、季別、日期、判定（合格綠 badge / 不合格紅 badge）、人員、操作（檢視/編輯/刪除）。「新增」按鈕開 `PyrometryTestForm`。資料來源 `GET /api/pyrometry/tests`，刪除 `DELETE /api/pyrometry/tests/{id}`。**列表/篩選/分頁結構照抄 `ExtrusionTolerancePage.tsx`。**

- [ ] **Step 3: 建立表單 `PyrometryTestForm.tsx`（本 Task 先做手動填，上傳在 Task 13 加）**

Bootstrap modal。流程：
  1. 選爐子（下拉）→ 選測試類型（TUS/SAT）→ 依爐子主檔自動帶入：公差（TUS 用 `TUS允許公差` / SAT 用 `SAT允許誤差`）、明細列數（TUS 用 `TUS點數`、SAT 用 `SAT點數`）。
  2. 主檔欄位：測試日期、設定溫度、測試人員（下拉品管人員，沿用既有取得方式）、測試儀器編號、標準校正儀器編號、儀器校正到期日、備註。季別不需手填（後端自動帶）。
  3. 明細表格：TUS 顯示「點位/熱電偶編號/修正值/最高溫/最低溫」可編輯欄；SAT 顯示「控溫區/控制儀表讀值/校正測試儀表讀值/修正值」。列數預設帶主檔點數，可增減列。
  4. 送出：`POST /api/pyrometry/tests`（新增）或 `PUT /api/pyrometry/tests/{id}`（編輯），body 含主檔欄位與 `points: TusPoint[] | SatPoint[]`。
  5. 成功後 `invalidateQueries` 重整列表並 toast 成功。

- [ ] **Step 4: 路由 + 選單**

`App.tsx` 加：
```typescript
const PyrometryTestListPage = lazy(() => import('./pages/pyrometry/PyrometryTestListPage'));
```
```tsx
<Route path="/pyrometry/tests" element={<PyrometryTestListPage />} />
```
`Sidebar.tsx` 在「爐溫測試 (CQI-9)」群組 items 最前面加：
```typescript
{ title: '測試紀錄', path: '/pyrometry/tests', icon: 'fa-temperature-high' },
```

- [ ] **Step 5: 驗證 build**

Run: `cd src_frontend && npm run build`
Expected: 編譯通過

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/types/index.ts src_frontend/src/pages/pyrometry/PyrometryTestListPage.tsx src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx src_frontend/src/App.tsx src_frontend/src/components/Sidebar.tsx
git commit -m "feat(pyrometry): 測試紀錄列表頁與新增/編輯表單"
```

---

# 階段三：附件雙來源 + TUS 自動繪圖

完成後可運作：上傳測試儀器/爐體數據檔，後端解析回填 TUS 摘要並提供繪圖資料，前端畫多通道曲線。

## Task 11: 擴充 Attachment 支援 pyrometry 與「用途」

**Files:**
- Modify: `backend/models.py`（Attachment 加欄位）、`backend/migration/21_add_pyrometry.sql`、`backend/services/attachment_service.py`

- [ ] **Step 1: `Attachment` 加 `用途` 欄位**

在 `backend/models.py` 的 `Attachment` 類別中 `d_step` 欄位後新增：
```python
    purpose = db.Column('用途', db.String(30), nullable=True)  # test_data|furnace_data|scan|cert|other
```

- [ ] **Step 2: migration 加欄位（在 `21_add_pyrometry.sql` 的 `COMMIT;` 前）**

```sql
-- ⑤ 既有附件表加「用途」欄位
ALTER TABLE "附件" ADD COLUMN IF NOT EXISTS "用途" VARCHAR(30);
```

- [ ] **Step 3: 擴充 `attachment_service.py`**

- 將 `VALID_ENTITY_TYPES = {'capa', 'task', 'complaint'}` 改為 `{'capa', 'task', 'complaint', 'pyrometry'}`。
- 在 `AttachmentService.upload(...)` 簽名加參數 `purpose: Optional[str] = None`，建立 `Attachment` 物件時帶入 `purpose=purpose`；查詢回傳的 dict 加 `"用途": a.purpose`。

> 先讀 `backend/services/attachment_service.py` 的 `upload` 與查詢方法完整實作，依其既有參數順序插入 `purpose`，並同步更新 `backend/routes/attachment.py` 對應呼叫（從 `request.form.get('purpose')` 取值傳入）。

- [ ] **Step 4: 寫測試（附加到 test_pyrometry.py）**

```python
def test_attachment_accepts_pyrometry(app, db_session):
    from backend.services.attachment_service import VALID_ENTITY_TYPES
    assert 'pyrometry' in VALID_ENTITY_TYPES
```

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_attachment_accepts_pyrometry -v`
Expected: PASS

- [ ] **Step 5: 跑既有附件測試確認沒破壞**

Run: `python -m pytest backend/tests/test_services/test_attachment_validation.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/migration/21_add_pyrometry.sql backend/services/attachment_service.py backend/routes/attachment.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): 附件支援 pyrometry 實體與用途分類"
```

## Task 12: 溫度資料檔解析器（CSV/Excel → 時間序列 + 摘要）

**Files:**
- Create: `backend/services/pyrometry_parser.py`
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫失敗測試**

```python
def test_parse_timeseries_csv_summary(tmp_path):
    from backend.services.pyrometry_parser import parse_temperature_file
    csv = tmp_path / "tus.csv"
    csv.write_text(
        "時間,TC-01,TC-02\n"
        "0,178,179\n"
        "1,186,183\n"
        "2,182,180\n", encoding="utf-8")
    with open(csv, "rb") as f:
        result = parse_temperature_file(f, filename="tus.csv")
    assert result["時間"] == ["0", "1", "2"]
    channels = {c["名稱"]: c for c in result["通道"]}
    assert channels["TC-01"]["最高溫"] == 186
    assert channels["TC-01"]["最低溫"] == 178
    assert channels["TC-02"]["最高溫"] == 183
    assert result["數值"]["TC-01"] == [178, 186, 182]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_parse_timeseries_csv_summary -v`
Expected: FAIL（`ModuleNotFoundError: pyrometry_parser`）

- [ ] **Step 3: 建立解析器**

於 `backend/services/pyrometry_parser.py` 寫入：

```python
"""溫度記錄器時間序列解析 — 第一欄為時間，其後每欄為一支熱電偶溫度"""
from typing import Dict, Any, BinaryIO
import pandas as pd


def parse_temperature_file(file_obj: BinaryIO, filename: str) -> Dict[str, Any]:
    """解析固定格式的 CSV/Excel：

    回傳 {
      "時間": [str, ...],
      "通道": [{"名稱": str, "最高溫": float, "最低溫": float}, ...],
      "數值": {通道名稱: [float, ...]},
    }
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("僅支援 .csv / .xlsx / .xls 檔")

    if df.shape[1] < 2:
        raise ValueError("檔案需至少包含『時間』欄與一個熱電偶欄")

    time_col = df.columns[0]
    channel_cols = list(df.columns[1:])
    times = [str(v) for v in df[time_col].tolist()]

    channels, values = [], {}
    for col in channel_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        vals = [float(v) for v in df[col].tolist()]
        values[str(col)] = vals
        channels.append({
            "名稱": str(col),
            "最高溫": float(series.max()),
            "最低溫": float(series.min()),
        })
    return {"時間": times, "通道": channels, "數值": values}
```

- [ ] **Step 4: 跑測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_parse_timeseries_csv_summary -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/pyrometry_parser.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): 溫度資料檔解析器（時間序列與摘要）"
```

## Task 13: 上傳解析路由 + 前端繪圖

**Files:**
- Modify: `backend/routes/pyrometry.py`、`backend/tests/test_services/test_pyrometry.py`
- Create: `src_frontend/src/components/pyrometry/TusChart.tsx`
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`

- [ ] **Step 1: 先寫上傳解析路由測試**

```python
import io

def test_parse_upload_route(client, db_session):
    headers = _auth_header(client, db_session)
    data = {
        "file": (io.BytesIO("時間,TC-01,TC-02\n0,178,179\n1,186,183\n".encode("utf-8")), "tus.csv"),
    }
    r = client.post("/api/pyrometry/parse-data", data=data,
                    headers=headers, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    ch = {c["名稱"]: c for c in body["data"]["通道"]}
    assert ch["TC-01"]["最高溫"] == 186
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_parse_upload_route -v`
Expected: FAIL（404）

- [ ] **Step 3: 加解析路由（`backend/routes/pyrometry.py`）**

```python
from ..services.pyrometry_parser import parse_temperature_file


@pyrometry_bp.route('/api/pyrometry/parse-data', methods=['POST'])
@auth_required
def parse_data():
    """上傳時間序列資料檔，回傳通道摘要與繪圖資料（不落地，僅解析）"""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "缺少檔案"}), 400
    try:
        result = parse_temperature_file(file.stream, filename=file.filename)
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
```

- [ ] **Step 4: 跑測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS（全部）

- [ ] **Step 5: 建立繪圖元件 `TusChart.tsx`**

用 `react-chartjs-2` 的 `Line`。props：`{ 時間: string[]; 數值: Record<string, number[]>; 爐體數值?: Record<string, number[]>; 設定溫度: number; 公差: number }`。
  - 每個測試儀器通道一條實線；若有 `爐體數值`，對應通道畫虛線（`borderDash: [6,4]`）。
  - 加兩條水平參考線（上限 = 設定溫度+公差、下限 = 設定溫度−公差）：用額外 dataset 以常數陣列繪製。
  - **參考既有 chart.js 用法**：先看 `src_frontend/src/pages/` 內已使用 `react-chartjs-2` 的頁面（例如 DashboardPage 或 analytics）確認 `Chart.register(...)` 的既有註冊方式，沿用相同 import。

- [ ] **Step 6: 在 `PyrometryTestForm.tsx` 串接上傳與回填**

當測試類型為 TUS 時，表單顯示兩個上傳欄：「測試儀器數據（基準）」與「爐體記錄數據（對照，選配）」。
  - 選檔後呼叫 `POST /api/pyrometry/parse-data`（multipart）取得 `通道/數值/時間`。
  - 用「測試儀器數據」的各通道 `最高溫/最低溫` **自動回填** TUS 明細表（依通道順序對應 P1..Pn，可手動覆寫）。
  - 將兩組 `數值` 傳入 `<TusChart>` 即時預覽曲線。
  - 實體檔上傳保存沿用既有附件 API（`entity_type=pyrometry`、`entity_id=` 存檔後的測試 id、`purpose=test_data|furnace_data`）——於測試紀錄存檔成功取得 id 後再上傳附件。

- [ ] **Step 7: 驗證 build**

Run: `cd src_frontend && npm run build`
Expected: 編譯通過

- [ ] **Step 8: Commit**

```bash
git add backend/routes/pyrometry.py backend/tests/test_services/test_pyrometry.py src_frontend/src/components/pyrometry/TusChart.tsx src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx
git commit -m "feat(pyrometry): 上傳資料解析路由與 TUS 自動繪圖回填"
```

---

# 階段四：總覽看板 / 到期 / 趨勢 / 匯出

完成後可運作：看板顯示 5 台爐到期狀態、單台爐歷年趨勢、單筆報告匯出。

## Task 14: 看板與趨勢 Service + 路由

**Files:**
- Modify: `backend/services/pyrometry_service.py`、`backend/routes/pyrometry.py`、`backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫測試**

```python
def test_dashboard_lists_all_furnaces_with_due(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-DB", "名稱": "看板爐", "TUS頻率_月": 3})
        PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "TUS", "測試日期": "2025-01-01",
            "設定溫度": 180, "允許公差": 10, "points": [{"最高溫": 181, "最低溫": 179}]})
        board = PyrometryService.dashboard()
        row = next(r for r in board if r["爐號"] == "F-DB")
        assert row["TUS"]["狀態"] == "逾期"
        assert "最近結果" in row


def test_trend_returns_tus_history(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-TR", "名稱": "趨勢爐"})
        for d, hi in [("2026-01-10", 185), ("2026-04-10", 188)]:
            PyrometryService.create_test({
                "爐子ID": fid, "測試類型": "TUS", "測試日期": d,
                "設定溫度": 180, "允許公差": 10,
                "points": [{"最高溫": hi, "最低溫": 178}]})
        trend = PyrometryService.tus_trend(fid)
        assert len(trend) == 2
        assert trend[0]["測試日期"] <= trend[1]["測試日期"]
        assert "均勻度極差" in trend[0]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -k "dashboard or trend" -v`
Expected: FAIL

- [ ] **Step 3: 加方法**

```python
    # ---------- 看板與趨勢 ----------
    @staticmethod
    def dashboard(today: date = None) -> List[Dict[str, Any]]:
        from ..models import PyrometryTest
        rows = []
        for f in Furnace.query.filter(Furnace.is_active.is_(True)).order_by(Furnace.code).all():
            due = PyrometryService.furnace_due_status(f.id, today)
            last = PyrometryTest.query.filter(
                PyrometryTest.furnace_id == f.id, PyrometryTest.deleted_at.is_(None)
            ).order_by(PyrometryTest.test_date.desc()).first()
            rows.append({
                "爐子ID": f.id, "爐號": f.code, "名稱": f.name,
                "製程類型": f.process_type or "",
                "TUS": due["TUS"], "SAT": due["SAT"],
                "最近結果": ({"測試類型": last.test_type, "測試日期": format_value(last.test_date),
                            "是否合格": last.is_pass} if last else None),
            })
        return rows

    @staticmethod
    def tus_trend(furnace_id: int) -> List[Dict[str, Any]]:
        from ..models import PyrometryTest
        tests = PyrometryTest.query.filter(
            PyrometryTest.furnace_id == furnace_id,
            PyrometryTest.test_type == "TUS",
            PyrometryTest.deleted_at.is_(None),
        ).order_by(PyrometryTest.test_date.asc()).all()
        return [{
            "測試日期": format_value(t.test_date), "季別": t.quarter or "",
            "均勻度極差": format_value(t.tus_range),
            "最大正偏差": format_value(t.tus_max_pos),
            "最大負偏差": format_value(t.tus_max_neg),
            "是否合格": t.is_pass,
        } for t in tests]
```

- [ ] **Step 4: 加路由（`backend/routes/pyrometry.py`）**

```python
@pyrometry_bp.route('/api/pyrometry/dashboard', methods=['GET'])
@auth_required
def dashboard():
    return jsonify({"success": True, "data": PyrometryService.dashboard()})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>/tus-trend', methods=['GET'])
@auth_required
def tus_trend(fid):
    return jsonify({"success": True, "data": PyrometryService.tus_trend(fid)})
```

- [ ] **Step 5: 跑測試**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS（全部）

- [ ] **Step 6: Commit**

```bash
git add backend/services/pyrometry_service.py backend/routes/pyrometry.py backend/tests/test_services/test_pyrometry.py
git commit -m "feat(pyrometry): 總覽看板與單台爐 TUS 趨勢服務與路由"
```

## Task 15: 總覽看板頁 + 設備趨勢圖

**Files:**
- Create: `src_frontend/src/pages/pyrometry/PyrometryDashboardPage.tsx`
- Modify: `src_frontend/src/pages/pyrometry/FurnaceMasterPage.tsx`、`src_frontend/src/App.tsx`、`src_frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: 建立看板頁 `PyrometryDashboardPage.tsx`**

`GET /api/pyrometry/dashboard` → 5 張爐卡片。每張卡顯示：爐號＋名稱、製程類型、最近結果（合格綠 / 不合格紅 badge）、TUS 與 SAT 的「下次應測日」與狀態徽章（正常🟢 / 即將到期🟡 / 逾期🔴，用 Bootstrap badge 顏色 success/warning/danger）。逾期卡片排最前（前端依狀態排序）。點卡片導向 `/pyrometry/tests?furnace_id={id}`。

- [ ] **Step 2: 設備主檔頁加趨勢圖**

在 `FurnaceMasterPage.tsx` 每列加「趨勢」按鈕 → 開 modal，呼叫 `GET /api/pyrometry/furnaces/{id}/tus-trend`，用 `react-chartjs-2` 的 `Line` 畫「均勻度極差 / 最大正偏差 / 最大負偏差」隨測試日期變化的折線。

- [ ] **Step 3: 路由 + 選單**

`App.tsx` 加：
```typescript
const PyrometryDashboardPage = lazy(() => import('./pages/pyrometry/PyrometryDashboardPage'));
```
```tsx
<Route path="/pyrometry" element={<PyrometryDashboardPage />} />
```
`Sidebar.tsx`「爐溫測試 (CQI-9)」群組 items 最前面加：
```typescript
{ title: '爐溫總覽', path: '/pyrometry', icon: 'fa-gauge' },
```

- [ ] **Step 4: 驗證 build**

Run: `cd src_frontend && npm run build`
Expected: 編譯通過

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/pages/pyrometry/PyrometryDashboardPage.tsx src_frontend/src/pages/pyrometry/FurnaceMasterPage.tsx src_frontend/src/App.tsx src_frontend/src/components/Sidebar.tsx
git commit -m "feat(pyrometry): 總覽看板頁與設備歷年趨勢圖"
```

## Task 16: 單筆報告匯出（Excel）

**Files:**
- Modify: `backend/services/pyrometry_service.py`、`backend/routes/pyrometry.py`、`backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 先寫測試（產出非空 xlsx bytes）**

```python
def test_export_test_xlsx(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-EX", "名稱": "匯出爐", "TUS允許公差": 10})
        tid = PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "TUS", "測試日期": "2026-04-15",
            "設定溫度": 180, "允許公差": 10,
            "points": [{"點位": "P1", "最高溫": 186, "最低溫": 178}]})
        content = PyrometryService.export_test_xlsx(tid)
        assert isinstance(content, (bytes, bytearray))
        assert content[:2] == b"PK"      # xlsx 為 zip 容器
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py::test_export_test_xlsx -v`
Expected: FAIL（`AttributeError: export_test_xlsx`）

- [ ] **Step 3: 加匯出方法（用 openpyxl，沿用既有匯出風格）**

```python
    # ---------- 報告匯出 ----------
    @staticmethod
    def export_test_xlsx(test_id: int) -> bytes:
        import io
        from openpyxl import Workbook
        detail = PyrometryService.get_test(test_id)
        main = detail["main"]
        wb = Workbook()
        ws = wb.active
        ws.title = "爐溫測試報告"
        ws.append(["爐溫測試報告", main["測試類型"]])
        ws.append(["爐號", main["爐號"], "測試日期", main["測試日期"]])
        ws.append(["設定溫度", main["設定溫度"], "允許公差", main["允許公差"]])
        ws.append(["季別", main["季別"], "判定", "合格" if main["是否合格"] else "不合格"])
        ws.append([])
        if main["測試類型"] == "TUS":
            ws.append(["均勻度極差", main["TUS均勻度極差"], "最大正偏差", main["TUS最大正偏差"],
                       "最大負偏差", main["TUS最大負偏差"]])
            ws.append([])
            ws.append(["點位", "熱電偶編號", "修正值", "最高溫", "最低溫", "最大偏差", "判定"])
            for p in detail["tus_points"]:
                ws.append([p["點位"], p["熱電偶編號"], p["修正值"], p["最高溫"],
                           p["最低溫"], p["最大偏差"], "合格" if p["是否合格"] else "不合格"])
        else:
            ws.append(["控溫區", "控制儀表讀值", "校正測試儀表讀值", "差值", "修正值", "偏差", "判定"])
            for p in detail["sat_points"]:
                ws.append([p["控溫區"], p["控制儀表讀值"], p["校正測試儀表讀值"], p["差值"],
                           p["修正值"], p["偏差"], "合格" if p["是否合格"] else "不合格"])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
```

- [ ] **Step 4: 加路由（用 `send_file`）**

```python
import io as _io
from flask import send_file


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>/export', methods=['GET'])
@auth_required
def export_test(tid):
    try:
        content = PyrometryService.export_test_xlsx(tid)
        return send_file(
            _io.BytesIO(content),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, download_name=f'pyrometry_{tid}.xlsx')
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
```

- [ ] **Step 5: 前端在明細/列表加「匯出」按鈕**

在 `PyrometryTestListPage.tsx` 每列加「匯出」按鈕：以帶 token 的方式下載 `GET /api/pyrometry/tests/{id}/export`（用 `api.get(url, { responseType: 'blob' })` 後建立 URL 觸發下載）。

- [ ] **Step 6: 跑測試 + build**

Run: `python -m pytest backend/tests/test_services/test_pyrometry.py -v`
Expected: PASS
Run: `cd src_frontend && npm run build`
Expected: 編譯通過

- [ ] **Step 7: Commit**

```bash
git add backend/services/pyrometry_service.py backend/routes/pyrometry.py backend/tests/test_services/test_pyrometry.py src_frontend/src/pages/pyrometry/PyrometryTestListPage.tsx
git commit -m "feat(pyrometry): 單筆爐溫測試報告 Excel 匯出"
```

## Task 17: 全模組回歸與收尾

**Files:** 無新增

- [ ] **Step 1: 跑後端全測試**

Run: `python -m pytest backend/tests -v`
Expected: 全部 PASS（含既有測試未被破壞）

- [ ] **Step 2: 前端 build + lint**

Run: `cd src_frontend && npm run build && npm run lint`
Expected: build 通過；lint 無新增錯誤

- [ ] **Step 3: 確認 migration 完整**

人工檢視 `backend/migration/21_add_pyrometry.sql`：4 張表 + 附件加欄位皆在同一檔、可重複執行（`IF NOT EXISTS`）。

- [ ] **Step 4: Commit（如有收尾調整）**

```bash
git add -A
git commit -m "chore(pyrometry): 全模組回歸測試與收尾"
```

---

## Self-Review（已執行）

**1. Spec coverage：**
- 設備主檔（5 爐、TUS/SAT 點數/頻率/公差）→ Task 1-5 ✅
- TUS/SAT 測試紀錄 + 明細 + 自動判定 → Task 6-10 ✅
- 附件雙來源（用途分類）→ Task 11、13 ✅
- TUS 上傳資料自動繪圖 + 回填 → Task 12-13 ✅
- 功能 A 到期提醒 → Task 9、14-15 ✅
- 功能 B 總覽看板 → Task 14-15 ✅
- 功能 D 報告匯出 → Task 16 ✅
- 功能 E 歷年趨勢 → Task 14-15 ✅
- 權限（軟刪除、auth）→ 沿用 `@auth_required` + `SoftDeleteMixin`（Task 6、8）✅
- 不做 C（NCMR/CAPA 連動）→ 計畫未含 ✅

**2. Placeholder scan：** 後端核心邏輯（model/migration/service/parser/route/test）皆為完整可執行程式碼。前端頁面以「照抄既有 `ExtrusionTolerancePage.tsx` 結構 + 明確 API 合約與欄位清單」描述（既有 codebase 模式），非 placeholder。

**3. Type consistency：** 後端 dict key（如 `TUS均勻度極差`、`最大偏差`、`差值`、`偏差`）於 model 欄位、judgment 輸出、get/export 之間一致；前端型別 `TusPoint/SatPoint/PyrometryTestRow/Furnace` 與後端 key 對應一致。`evaluate_tus/evaluate_sat/create_test/get_test/update_test/search_tests/furnace_due_status/dashboard/tus_trend/export_test_xlsx` 命名跨 Task 一致。

**待實作期間確認（來自 spec 第 9 節）：** 實際記錄器匯出檔欄位格式、各爐公差數值、SAT 實際頻率、PDF 是否另做（本計畫先做 Excel 匯出）。
