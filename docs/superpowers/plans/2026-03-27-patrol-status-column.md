# 現場巡檢歷史清單狀態欄位 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在現場巡檢歷史清單的每筆記錄中新增「狀態」欄位，依押出公差比對量測明細，顯示合格（✓）、超差（⚠️）或無公差資料（-）。

**Architecture:** 後端 `PatrolService.get_history()` 批次查詢押出公差（`ExtrusionToleranceService.check()`），搭配 eager load 的 `PatrolDetail` 明細，計算每筆記錄的 `is_ng` / `tol_found`，附加至回傳 JSON。前端 `PatrolPage` 新增狀態欄，依這兩個欄位顯示 badge，邏輯與 ShippingPage 完全一致。

**Tech Stack:** Flask 3.1 + SQLAlchemy `selectinload`（後端）、React 19 + TypeScript + React Bootstrap `Badge`（前端）、pytest + SQLite in-memory（測試）

---

## File Structure

| 操作 | 檔案 | 說明 |
|------|------|------|
| 新增 | `backend/tests/test_services/test_patrol.py` | 後端 NG 計算的單元測試 |
| 修改 | `backend/services/patrol_service.py` | `get_history()` 加入 NG 計算邏輯 |
| 修改 | `src_frontend/src/types/index.ts` | `PatrolInspection` 新增兩個欄位 |
| 修改 | `src_frontend/src/pages/patrol/PatrolPage.tsx` | 表格新增狀態欄 |

---

## Task 1：後端 NG 計算（TDD）

**Files:**
- Create: `backend/tests/test_services/test_patrol.py`
- Modify: `backend/services/patrol_service.py`

### Step 1.1：撰寫失敗的測試

- [ ] 建立測試檔案 `backend/tests/test_services/test_patrol.py`，內容如下：

```python
import pytest
from datetime import date
from backend.services.patrol_service import PatrolService
from backend.models import (
    PatrolMain, PatrolDetail,
    ExtrusionToleranceMain, ExtrusionToleranceDetail
)


def test_get_history_is_ng_true(app, db_session):
    """量測值超出押出公差時，is_ng 應為 True"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*10*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            tolerance_min=0.5, tolerance_max=1.5
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=0.8, max_val=2.0  # 2.0 超出上限 1.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        assert len(result['data']) == 1
        row = result['data'][0]
        assert row['is_ng'] is True
        assert row['tol_found'] is True


def test_get_history_is_ng_false(app, db_session):
    """量測值在公差範圍內時，is_ng 應為 False"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*10*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            tolerance_min=0.5, tolerance_max=1.5
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=0.8, max_val=1.2  # 在範圍內
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['is_ng'] is False
        assert row['tol_found'] is True


def test_get_history_tol_not_found(app, db_session):
    """查無押出公差資料時，tol_found 應為 False，is_ng 應為 False"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='UNKNOWN_MAT', spec='99*99')
        db_session.add(patrol)
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['tol_found'] is False
        assert row['is_ng'] is False


def test_get_history_concentricity_ng(app, db_session):
    """同心度（厚度 max_val - min_val）超差時，is_ng 應為 True"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*10*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='同心度',
            tolerance_min=0.0, tolerance_max=0.3
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
        db_session.add(patrol)
        db_session.flush()
        # 同心度 = 1.5 - 0.8 = 0.7，超出上限 0.3
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='厚度', position='前段',
            min_val=0.8, max_val=1.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['is_ng'] is True
        assert row['tol_found'] is True


def test_get_history_tol_cache_called_once_per_combo(app, db_session, monkeypatch):
    """相同 (material, spec) 的多筆記錄，公差只查詢一次"""
    with app.app_context():
        call_count = {'n': 0}
        from backend.services import extrusion_tolerance_service as ets_mod
        original_check = ets_mod.ExtrusionToleranceService.check

        def counting_check(args):
            call_count['n'] += 1
            return original_check(args)

        monkeypatch.setattr(ets_mod.ExtrusionToleranceService, 'check', staticmethod(counting_check))

        for _ in range(3):
            patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
            db_session.add(patrol)
        db_session.commit()

        PatrolService.get_history({'page': 1, 'per_page': 20})
        # 3 筆記錄，相同 combo，只應呼叫 1 次
        assert call_count['n'] == 1
```

### Step 1.2：確認測試目前失敗

- [ ] 在 repo 根目錄執行：

```bash
cd C:/QC_Database && python -m pytest backend/tests/test_services/test_patrol.py -v 2>&1 | head -40
```

預期結果：測試因 `'is_ng'` key 不存在而 **FAILED**（KeyError 或 AssertionError）

### Step 1.3：實作後端 NG 計算

- [ ] 修改 `backend/services/patrol_service.py`：

**Step 1.3a**：在檔案頂部，將 `from sqlalchemy import func, text` 那行改為：

```python
from sqlalchemy import func, text
from sqlalchemy.orm import selectinload
```

**Step 1.3b**：找到 `get_history` 方法中的查詢建立區段（約在第 534 行），將：

```python
query = db.session.query(
    PatrolMain,
    Machine.name.label('m_name'),
    Operator.name.label('op_name'),
    Vendor.name.label('cust_name')
)\
    .outerjoin(Machine, PatrolMain.machine_id == Machine.id)\
    .outerjoin(Operator, PatrolMain.operator_id == Operator.id)\
    .outerjoin(Vendor, PatrolMain.customer_id == Vendor.id)
```

改為（加入 `.options(selectinload(PatrolMain.details))`）：

```python
query = db.session.query(
    PatrolMain,
    Machine.name.label('m_name'),
    Operator.name.label('op_name'),
    Vendor.name.label('cust_name')
)\
    .outerjoin(Machine, PatrolMain.machine_id == Machine.id)\
    .outerjoin(Operator, PatrolMain.operator_id == Operator.id)\
    .outerjoin(Vendor, PatrolMain.customer_id == Vendor.id)\
    .options(selectinload(PatrolMain.details))
```

**Step 1.3c**：找到分頁後建立 `data = []` 的區段（約第 559 行），在 `data = []` 前插入以下批次公差查詢邏輯：

```python
            # --- 批次查詢押出公差（以避免 N+1） ---
            from ..services.extrusion_tolerance_service import ExtrusionToleranceService

            unique_combos = {
                (patrol_item.material or '', patrol_item.spec or '')
                for patrol_item, *_ in pagination.items
                if patrol_item.material
            }

            tol_cache: dict = {}
            for mat, sp in unique_combos:
                result = ExtrusionToleranceService.check({'material': mat, 'spec': sp})
                if result.get('found'):
                    tol_cache[(mat, sp)] = {t['項目']: t for t in result.get('tolerances', [])}
                else:
                    tol_cache[(mat, sp)] = None
```

**Step 1.3d**：將原本 `data = []` 之後的 for 迴圈（建立每筆 `data.append({...})`）改為以下版本（加入 NG 計算）：

```python
            data = []
            for item in pagination.items:
                patrol, m_name, op_name, cust_name = item

                # --- NG 計算 ---
                mat = patrol.material or ''
                sp = patrol.spec or ''
                tol_map = tol_cache.get((mat, sp)) if mat else None
                tol_found = tol_map is not None
                is_ng = False

                if tol_found:
                    for d in patrol.details:
                        tol = tol_map.get(d.item)
                        if tol:
                            for val in [
                                float(d.min_val) if d.min_val is not None else None,
                                float(d.max_val) if d.max_val is not None else None,
                            ]:
                                if val is None:
                                    continue
                                if tol.get('公差下限') is not None and val < tol['公差下限']:
                                    is_ng = True
                                if tol.get('公差上限') is not None and val > tol['公差上限']:
                                    is_ng = True

                        # 同心度：厚度行的 max_val - min_val 與同心度公差比對
                        if not is_ng and d.item == '厚度' and d.min_val is not None and d.max_val is not None:
                            conc_tol = tol_map.get('同心度')
                            if conc_tol:
                                concentricity = float(d.max_val) - float(d.min_val)
                                if conc_tol.get('公差下限') is not None and concentricity < conc_tol['公差下限']:
                                    is_ng = True
                                if conc_tol.get('公差上限') is not None and concentricity > conc_tol['公差上限']:
                                    is_ng = True

                        if is_ng:
                            break

                date_str = patrol.date.strftime('%Y-%m-%d') if patrol.date else ''
                data.append({
                    'id': patrol.id,
                    'date': date_str,
                    'm_name': m_name.strip() if m_name else '',
                    'op_name': op_name.strip() if op_name else '',
                    'cust_name': cust_name.strip() if cust_name else '',
                    'mat': patrol.material,
                    'spec': patrol.spec,
                    'is_ng': is_ng,
                    'tol_found': tol_found,
                })
```

### Step 1.4：確認測試通過

- [ ] 執行：

```bash
cd C:/QC_Database && python -m pytest backend/tests/test_services/test_patrol.py -v
```

預期結果：全部 5 個測試 **PASSED**

### Step 1.5：確認現有測試未破壞

- [ ] 執行：

```bash
cd C:/QC_Database && python -m pytest backend/tests/ -v
```

預期結果：所有測試 PASSED

### Step 1.6：Commit

- [ ] 執行：

```bash
cd C:/QC_Database && git add backend/tests/test_services/test_patrol.py backend/services/patrol_service.py && git commit -m "feat(patrol): 歷史清單 get_history 加入押出公差 NG 計算（is_ng / tol_found）"
```

---

## Task 2：前端型別與 UI

**Files:**
- Modify: `src_frontend/src/types/index.ts:66-85`
- Modify: `src_frontend/src/pages/patrol/PatrolPage.tsx:205-244`

### Step 2.1：更新 TypeScript 型別

- [ ] 修改 `src_frontend/src/types/index.ts`，找到 `PatrolInspection` interface（約第 66 行），在 `details?: PatrolDetail[];` 之後加入：

```typescript
    is_ng?: boolean;
    tol_found?: boolean;
```

結果應如下：

```typescript
export interface PatrolInspection {
    id: number;
    date: string;
    machine_id?: number;
    machine_name?: string;
    m_name?: string;
    operator_id?: number;
    operator_name?: string;
    op_name?: string;
    inspector_id?: number;
    inspector_name?: string;
    customer_id?: number;
    customer_name?: string;
    cust_name?: string;
    material?: string;
    mat?: string;
    batch?: string;
    spec?: string;
    details?: PatrolDetail[];
    is_ng?: boolean;
    tol_found?: boolean;
}
```

### Step 2.2：在表格加入狀態欄（標題）

- [ ] 修改 `src_frontend/src/pages/patrol/PatrolPage.tsx`，找到 `<thead className="table-dark">` 的 `<tr>` 區段（約第 206 行），在 `<th>規格</th>` 之後、`<th>操作</th>` 之前插入：

```tsx
                                <th className="text-center">狀態</th>
```

### Step 2.3：在表格加入狀態欄（資料列）

- [ ] 同檔案，找到資料列的 `data.map(item => (...))` 中，`<td>{item.spec}</td>` 之後、操作按鈕 `<td>` 之前插入：

```tsx
                                        <td className="text-center">
                                            {!item.tol_found ? (
                                                <span className="badge bg-secondary">-</span>
                                            ) : item.is_ng ? (
                                                <span className="badge bg-danger">⚠️ 超差</span>
                                            ) : (
                                                <span className="badge bg-success">✓ 合格</span>
                                            )}
                                        </td>
```

### Step 2.4：更新 colSpan

- [ ] 同檔案，找到載入中的 `<tr><td colSpan={8}` 與無資料的 `<tr><td colSpan={8}`，兩處均改為 `colSpan={9}`：

```tsx
{isLoading ? (
    <tr><td colSpan={9} className="text-center py-4">載入中...</td></tr>
) : data.length === 0 ? (
    <tr><td colSpan={9} className="text-center py-4">無資料</td></tr>
```

### Step 2.5：TypeScript 型別檢查

- [ ] 執行：

```bash
cd C:/QC_Database/src_frontend && npm run build 2>&1 | tail -20
```

預期結果：build 成功，無 TypeScript 錯誤

### Step 2.6：Commit

- [ ] 執行：

```bash
cd C:/QC_Database && git add src_frontend/src/types/index.ts src_frontend/src/pages/patrol/PatrolPage.tsx && git commit -m "feat(patrol): 歷史清單新增狀態欄位，顯示合格 / 超差"
```

---

## 驗收確認

完成後以下行為應符合預期：

| 情境 | 期望顯示 |
|------|---------|
| 押出公差存在且所有量測值合格 | `✓ 合格`（綠色） |
| 押出公差存在且任一值超出公差 | `⚠️ 超差`（紅色） |
| 厚度 max − min 超出同心度公差 | `⚠️ 超差`（紅色） |
| 查無押出公差資料（材質/規格無對應） | `-`（灰色） |
| 記錄無材質資料 | `-`（灰色） |
