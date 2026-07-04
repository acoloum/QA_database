# 爐溫測試量測點排除功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 TUS/SAT 爐溫測試能逐頻道（逐量測點）標記「排除，不列入計算」，被排除點不計入均勻度與判定、但保留資料並於報表標註「已排除」、TUS 曲線灰色化，且強制填寫排除原因。

**Architecture:** 在 `TusPoint`/`SatPoint` 各加 `已排除`(bool)、`排除原因`(text) 兩欄。判定層 (`pyrometry_calculations.py`) 對已排除點跳過均勻度/偏差/整體判定；服務層負責驗證原因非空、持久化與序列化；報表層灰底標註並排除於彙總；前端明細表加勾選＋原因欄，並把已排除點位名傳給曲線圖做灰色化。

**Tech Stack:** Flask + SQLAlchemy + PostgreSQL（後端）；pytest（後端測試）；React + TypeScript + react-bootstrap + chart.js（前端）；Vitest + Testing Library（前端測試）。

**慣例：**後端在 venv 啟動；測試由 `db.create_all()` 依 `models.py` 建表，故新增欄位只需改 `models.py` 即可讓測試看見；正式 DB 另用編號 SQL migration。commit 訊息用繁體中文。

---

## File Structure

| 檔案 | 動作 | 責任 |
|------|------|------|
| `backend/migration/31_add_point_exclusion.sql` | 建立 | 正式 DB 加欄位 |
| `backend/models.py` | 修改 | `TusPoint`/`SatPoint` 加 `excluded`/`exclude_reason` |
| `backend/services/pyrometry_calculations.py` | 修改 | `evaluate_tus`/`evaluate_sat` 排除邏輯 + `_is_excluded` helper |
| `backend/services/pyrometry_persistence.py` | 修改 | `build_point_model_kwargs` 帶入排除欄位 |
| `backend/services/pyrometry_service.py` | 修改 | 序列化帶出排除欄位 |
| `backend/services/pyrometry_report.py` | 修改 | 報表灰底標註 + 曲線灰色化 |
| `backend/tests/test_services/test_pyrometry.py` | 修改 | 後端測試 |
| `src_frontend/src/types/pyrometry.ts` | 修改 | 型別加排除欄位 |
| `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts` | 修改 | empty factory 補預設 |
| `src_frontend/src/components/pyrometry/TusChart.tsx` | 修改 | `excludedChannels` prop + 顏色 helper |
| `src_frontend/src/pages/pyrometry/TusSection.tsx` | 修改 | 排除勾選＋原因欄 |
| `src_frontend/src/pages/pyrometry/SatSection.tsx` | 修改 | 排除勾選＋原因欄 |
| `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx` | 修改 | 排除 handler + 存檔擋原因 |
| 對應 `*.test.tsx` | 修改 | 前端測試 |

---

## Task 1: 資料模型（migration + models）

**Files:**
- Create: `backend/migration/31_add_point_exclusion.sql`
- Modify: `backend/models.py`（`TusPoint` 約 790-803、`SatPoint` 約 806-820）

- [ ] **Step 1: 建立 migration SQL**

Create `backend/migration/31_add_point_exclusion.sql`:

```sql
-- 量測點排除（不列入計算）：TUS/SAT 各加「已排除」旗標與原因
ALTER TABLE "TUS量測點明細"
    ADD COLUMN IF NOT EXISTS "已排除" BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS "排除原因" TEXT;

ALTER TABLE "SAT量測點明細"
    ADD COLUMN IF NOT EXISTS "已排除" BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS "排除原因" TEXT;
```

- [ ] **Step 2: 在 `models.py` 的 `TusPoint` 加欄位**

在 `is_pass = db.Column('是否合格', db.Boolean, default=True)` 之後新增：

```python
    excluded       = db.Column('已排除',   db.Boolean, nullable=False, default=False)
    exclude_reason = db.Column('排除原因', db.Text, nullable=True)
```

- [ ] **Step 3: 在 `models.py` 的 `SatPoint` 加相同欄位**

在 `is_pass = db.Column('是否合格', db.Boolean, default=True)` 之後新增：

```python
    excluded       = db.Column('已排除',   db.Boolean, nullable=False, default=False)
    exclude_reason = db.Column('排除原因', db.Text, nullable=True)
```

- [ ] **Step 4: 驗證模型可匯入、測試建表未壞**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py -q`
Expected: PASS（既有測試全過，代表新欄位不影響建表）

- [ ] **Step 5: Commit**

```bash
git add backend/migration/31_add_point_exclusion.sql backend/models.py
git commit -m "新增量測點排除欄位（migration 與模型）"
```

---

## Task 2: `evaluate_tus` 排除邏輯（TDD）

**Files:**
- Modify: `backend/services/pyrometry_calculations.py`（`evaluate_tus` 約 69-101）
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 寫失敗測試**

在 `test_pyrometry.py` 的 `test_evaluate_tus_applies_correction` 之後新增：

```python
def test_evaluate_tus_excludes_flagged_point():
    """已排除點不計入均勻度/偏差/整體判定，但仍回傳且標記已排除"""
    points = [
        {"點位": "TUS-1", "最高溫": 183, "最低溫": 179},
        {"點位": "TUS-2", "最高溫": 999, "最低溫": 999, "已排除": True},  # 異常值，應被排除
    ]
    result = PyrometryService.evaluate_tus(setpoint=180, tolerance=10, points=points)
    assert result["是否合格"] is True                 # 異常點被排除，不拖累判定
    assert result["TUS均勻度極差"] == 4               # 183-179，只算 TUS-1
    assert result["TUS最大正偏差"] == 3               # 183-180
    assert len(result["points"]) == 2                 # 排除點仍保留
    excluded = result["points"][1]
    assert excluded["已排除"] is True
    assert excluded["最大偏差"] is None
    assert excluded["是否合格"] is None
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_evaluate_tus_excludes_flagged_point -v`
Expected: FAIL（目前 999 會被納入，均勻度/判定錯誤）

- [ ] **Step 3: 實作排除邏輯**

在 `pyrometry_calculations.py`，於 `evaluate_tus` 之前新增 helper：

```python
def _is_excluded(p) -> bool:
    """判斷量測點是否被標記排除；接受 bool / 1 / "true" 等表示法。"""
    v = p.get("已排除")
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)
```

將 `evaluate_tus` 迴圈改為（在 `for p in points:` 之後最前面插入排除分支）：

```python
    for p in points:
        excluded = _is_excluded(p)
        if excluded:
            np_point = dict(p)
            np_point["已排除"] = True
            np_point["最大偏差"] = None
            np_point["是否合格"] = None
            out_points.append(np_point)
            continue
        tmax = to_float(p.get("最高溫"))
        tmin = to_float(p.get("最低溫"))
        corr = to_float(p.get("修正值")) or 0.0
        tmax = tmax + corr if tmax is not None else None
        tmin = tmin + corr if tmin is not None else None
        dev_candidates = []
        if tmax is not None:
            dev_candidates.append(tmax - sp)
            all_max.append(tmax)
        if tmin is not None:
            dev_candidates.append(tmin - sp)
            all_min.append(tmin)
        max_dev = max(dev_candidates, key=abs) if dev_candidates else None
        pt_pass = max_dev is None or abs(max_dev) <= tol
        overall_pass = overall_pass and pt_pass
        np_point = dict(p)
        np_point["已排除"] = False
        np_point["最大偏差"] = round(max_dev, 2) if max_dev is not None else None
        np_point["是否合格"] = pt_pass
        out_points.append(np_point)
```

- [ ] **Step 4: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_evaluate_tus_excludes_flagged_point -v`
Expected: PASS

- [ ] **Step 5: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py tests/test_services/test_pyrometry_calculations.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/pyrometry_calculations.py backend/tests/test_services/test_pyrometry.py
git commit -m "evaluate_tus 支援排除點不列入計算"
```

---

## Task 3: `evaluate_sat` 排除邏輯（TDD）

**Files:**
- Modify: `backend/services/pyrometry_calculations.py`（`evaluate_sat` 約 104-143）
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 寫失敗測試**

在 `test_evaluate_sat_pass_and_fail` 之後新增：

```python
def test_evaluate_sat_excludes_flagged_zone():
    """已排除控溫區不計入整體判定，仍回傳並標記已排除"""
    points = [
        {"控溫區": "Z1", "修正值": 0, "readings": [
            {"控制儀表讀值": 180, "校正測試讀值": 182}]},          # 偏差 +2，合格
        {"控溫區": "Z2", "修正值": 0, "已排除": True, "readings": [
            {"控制儀表讀值": 180, "校正測試讀值": 999}]},          # 異常，應被排除
    ]
    result = PyrometryService.evaluate_sat(tolerance=5, points=points)
    assert result["是否合格"] is True
    assert len(result["points"]) == 2
    assert result["points"][1]["已排除"] is True
    assert result["points"][1]["偏差"] is None
    assert result["points"][1]["是否合格"] is None
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_evaluate_sat_excludes_flagged_zone -v`
Expected: FAIL（999 讀值使整體判定為不合格）

- [ ] **Step 3: 實作排除邏輯**

將 `evaluate_sat` 迴圈 `for p in points:` 之後最前面插入排除分支：

```python
    for p in points:
        if _is_excluded(p):
            np_point = {k: v for k, v in p.items() if k not in ("readings", "差值", "偏差", "是否合格")}
            np_point["readings"] = p.get("readings") or []
            np_point["已排除"] = True
            np_point["差值"] = None
            np_point["偏差"] = None
            np_point["是否合格"] = None
            out_points.append(np_point)
            continue
        corr = to_float(p.get("修正值")) or 0.0
        # ...（以下維持原本邏輯不變）
```

並在原本組 `np_point` 的地方（迴圈尾端）補上 `np_point["已排除"] = False`：

找到：
```python
        np_point = {k: v for k, v in p.items() if k not in ("readings", "差值", "偏差", "是否合格")}
        np_point["readings"] = computed_readings
        np_point["差值"] = worst_diff
        np_point["偏差"] = worst_dev
        np_point["是否合格"] = zone_pass
        out_points.append(np_point)
```
改為在 `np_point["readings"] = computed_readings` 之前加入：
```python
        np_point["已排除"] = False
```

- [ ] **Step 4: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_evaluate_sat_excludes_flagged_zone -v`
Expected: PASS

- [ ] **Step 5: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/pyrometry_calculations.py backend/tests/test_services/test_pyrometry.py
git commit -m "evaluate_sat 支援排除控溫區不列入計算"
```

---

## Task 4: 持久化與序列化帶入排除欄位（TDD）

**Files:**
- Modify: `backend/services/pyrometry_persistence.py`（`build_point_model_kwargs`）
- Modify: `backend/services/pyrometry_service.py`（`get_test` 的 `tus_points`/`sat_points` 序列化，約 436-460）
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 寫失敗測試**

在 `test_create_test_persists_report_meta` 之後新增：

```python
def test_create_test_persists_exclusion(app, db_session):
    """排除旗標與原因存檔後可重現，且不列入判定"""
    with app.app_context():
        fid = _make_furnace(tol=10)
        tid = PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "TUS", "測試日期": "2026-04-15",
            "設定溫度": 180, "允許公差": 10,
            "points": [
                {"點位": "TUS-1", "最高溫": 183, "最低溫": 179},
                {"點位": "TUS-2", "最高溫": 999, "最低溫": 999,
                 "已排除": True, "排除原因": "熱電偶斷線"},
            ],
        })
        detail = PyrometryService.get_test(tid)
        assert detail["main"]["是否合格"] is True
        p2 = detail["tus_points"][1]
        assert p2["已排除"] is True
        assert p2["排除原因"] == "熱電偶斷線"
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_create_test_persists_exclusion -v`
Expected: FAIL（`build_point_model_kwargs` 未帶入欄位 / 序列化無此 key → KeyError 或 assert 失敗）

- [ ] **Step 3: 修改 `build_point_model_kwargs`**

在 `pyrometry_persistence.py`，TUS 的 return dict 內、`"is_pass": ...` 之後加入：

```python
            "excluded": bool(point.get("已排除")),
            "exclude_reason": (point.get("排除原因") or None),
```

SAT 的 return dict 內、`"is_pass": ...` 之後加入相同兩行：

```python
        "excluded": bool(point.get("已排除")),
        "exclude_reason": (point.get("排除原因") or None),
```

- [ ] **Step 4: 修改 `get_test` 序列化**

`pyrometry_service.py` 的 `tus_points` 清單，在 `"是否合格": p.is_pass,` 之後加入：

```python
            "已排除": bool(p.excluded),
            "排除原因": p.exclude_reason or "",
```

`sat_points` 清單，在 `"是否合格": p.is_pass,` 之後加入相同兩行：

```python
            "已排除": bool(p.excluded),
            "排除原因": p.exclude_reason or "",
```

- [ ] **Step 5: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_create_test_persists_exclusion -v`
Expected: PASS

- [ ] **Step 6: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py tests/test_services/test_pyrometry_persistence_utils.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/pyrometry_persistence.py backend/services/pyrometry_service.py backend/tests/test_services/test_pyrometry.py
git commit -m "排除欄位持久化與序列化"
```

---

## Task 5: 強制填寫排除原因（後端驗證，TDD）

**Files:**
- Modify: `backend/services/pyrometry_calculations.py`（`validate_test_payload` 約 29-49）
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 寫失敗測試**

新增：

```python
def test_create_test_requires_exclude_reason(app, db_session):
    """已排除但未填原因 → 丟出驗證錯誤"""
    import pytest
    from backend.services.pyrometry_calculations import PyrometryValidationError
    with app.app_context():
        fid = _make_furnace(tol=10)
        with pytest.raises(PyrometryValidationError):
            PyrometryService.create_test({
                "爐子ID": fid, "測試類型": "TUS", "測試日期": "2026-04-15",
                "設定溫度": 180, "允許公差": 10,
                "points": [{"點位": "TUS-1", "最高溫": 999, "最低溫": 999,
                            "已排除": True}],   # 缺原因
            })
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_create_test_requires_exclude_reason -v`
Expected: FAIL（未擋，反而建立成功）

- [ ] **Step 3: 在 `validate_test_payload` 尾端加驗證**

在 `pyrometry_calculations.py` 的 `validate_test_payload`，於 `return {**data, "測試類型": test_type}` 之前插入：

```python
    for pt in data.get("points", []) or []:
        if _is_excluded(pt) and not str(pt.get("排除原因") or "").strip():
            raise PyrometryValidationError("排除的量測點必須填寫排除原因")
```

（`_is_excluded` 於 Task 2 已定義於同檔案。）

- [ ] **Step 4: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_create_test_requires_exclude_reason -v`
Expected: PASS

- [ ] **Step 5: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/pyrometry_calculations.py backend/tests/test_services/test_pyrometry.py
git commit -m "後端強制填寫排除原因"
```

---

## Task 6: 報表 TUS 已排除列灰底標註（TDD）

**Files:**
- Modify: `backend/services/pyrometry_report.py`（頂部樣式常數區、`build_tus_sheet` 約 162-185）
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 寫失敗測試**

新增：

```python
def test_export_tus_marks_excluded_row(app, db_session):
    """TUS 匯出：已排除列判定欄顯示「已排除：<原因>」"""
    import io as _io
    from openpyxl import load_workbook
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-EXC", "名稱": "排除爐", "TUS允許公差": 10})
        tid = PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "TUS", "測試日期": "2026-04-15",
            "設定溫度": 180, "允許公差": 10,
            "points": [
                {"點位": "TUS-1", "最高溫": 183, "最低溫": 179},
                {"點位": "TUS-2", "最高溫": 999, "最低溫": 999,
                 "已排除": True, "排除原因": "熱電偶斷線"},
            ],
        })
        content = PyrometryService.export_test_xlsx(tid)
        wb = load_workbook(_io.BytesIO(content))
        ws = wb["QRA073-TUS均勻性"]
        assert any(c.value == "已排除：熱電偶斷線" for row in ws.iter_rows() for c in row)
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_export_tus_marks_excluded_row -v`
Expected: FAIL（判定欄仍寫「合格/不合格」）

- [ ] **Step 3: 加灰底樣式常數**

`pyrometry_report.py` 頂部樣式區（`_RED_FILL`/`_BLUE_FILL` 附近）新增：

```python
_EXCLUDED_FILL = PatternFill('solid', fgColor='E2E3E5')   # 已排除：灰底
```

- [ ] **Step 4: 修改 `build_tus_sheet` 迴圈**

將 `for p in detail["tus_points"]:` 的迴圈本體改為：

```python
    for p in detail["tus_points"]:
        excluded = bool(p.get("已排除"))
        reason = p.get("排除原因") or ""
        raw_min = _num(p.get("最低溫"))
        raw_max = _num(p.get("最高溫"))
        total = _num(p.get("修正值")) or 0
        c_tc = tc_corr or 0
        b_rec = round(total - c_tc, 2)
        g_min = round(raw_min + total, 2) if raw_min is not None else None
        g_max = round(raw_max + total, 2) if raw_max is not None else None
        e_min = round(g_min - setpoint, 2) if g_min is not None else None
        e_max = round(g_max - setpoint, 2) if g_max is not None else None
        if not excluded:
            for v in (e_min, e_max):
                if v is not None and (worst is None or abs(v) > abs(worst)):
                    worst = v
        ok = p.get("是否合格", True)
        judge = f"已排除：{reason}" if excluded else ("合格" if ok else "不合格")
        vals = [p.get("點位", ""), raw_min, raw_max, "°C", b_rec, c_tc,
                g_min, g_max, e_min, e_max, judge]
        for i, v in enumerate(vals, start=1):
            cell = _set(ws, f"{chr(64 + i)}{r}", v)
            if excluded:
                cell.fill = _EXCLUDED_FILL
            elif not ok and i == 11:
                cell.fill = _RED_FILL
        r += 1
```

- [ ] **Step 5: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_export_tus_marks_excluded_row -v`
Expected: PASS

- [ ] **Step 6: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/pyrometry_report.py backend/tests/test_services/test_pyrometry.py
git commit -m "TUS 報表標註已排除列並排除於彙總"
```

---

## Task 7: 報表 SAT 已排除列灰底標註（TDD）

**Files:**
- Modify: `backend/services/pyrometry_report.py`（`build_sat_sheet` 約 273-302）
- Test: `backend/tests/test_services/test_pyrometry.py`

- [ ] **Step 1: 寫失敗測試**

新增：

```python
def test_export_sat_marks_excluded_row(app, db_session):
    import io as _io
    from openpyxl import load_workbook
    with app.app_context():
        fid = PyrometryService.add_furnace({"爐號": "F-SEXC", "名稱": "SAT排除爐", "SAT允許誤差": 5})
        tid = PyrometryService.create_test({
            "爐子ID": fid, "測試類型": "SAT", "測試日期": "2026-04-15",
            "設定溫度": 180, "允許公差": 5,
            "points": [
                {"控溫區": "Z1", "修正值": 0, "readings": [
                    {"控制儀表讀值": 180, "校正測試讀值": 182}]},
                {"控溫區": "Z2", "修正值": 0, "已排除": True, "排除原因": "感測器故障",
                 "readings": [{"控制儀表讀值": 180, "校正測試讀值": 999}]},
            ]})
        content = PyrometryService.export_test_xlsx(tid)
        wb = load_workbook(_io.BytesIO(content))
        ws = wb["QRA074-SAT準確度"]
        assert any(c.value == "已排除：感測器故障" for row in ws.iter_rows() for c in row)
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_export_sat_marks_excluded_row -v`
Expected: FAIL

- [ ] **Step 3: 修改 `build_sat_sheet` 迴圈**

將 `for p in detail["sat_points"]:` 迴圈改為（在計算 `worst`/`vals` 處加排除分支）：

```python
    for p in detail["sat_points"]:
        excluded = bool(p.get("已排除"))
        reason = p.get("排除原因") or ""
        corr = _num(p.get("修正值")) or 0
        c_tc = tc_corr or 0
        b_rec = round(corr - c_tc, 2)
        readings = p.get("readings") or []
        if readings:
            worst_r = max(readings, key=lambda rd: abs(_num(rd.get("偏差")) or 0))
            ctrl = _num(worst_r.get("控制儀表讀值"))
            test = _num(worst_r.get("校正測試讀值"))
            diff = _num(worst_r.get("差值"))
            dev  = _num(worst_r.get("偏差"))
        else:
            ctrl = _num(p.get("控制儀表讀值"))
            test = _num(p.get("校正測試讀值"))
            diff = _num(p.get("差值"))
            dev  = _num(p.get("偏差"))
        corrected = round(test + corr, 2) if test is not None else None
        if not excluded and dev is not None and (worst is None or abs(dev) > abs(worst)):
            worst = dev
        ok = p.get("是否合格", True)
        judge = f"已排除：{reason}" if excluded else ("合格" if ok else "不合格")
        vals = [p.get("控溫區", ""), ctrl, test, diff, "°C", b_rec, c_tc, corrected, dev, judge]
        for col, v in zip(cols, vals):
            cell = _set(ws, f"{col}{r}", v)
            if excluded:
                cell.fill = _EXCLUDED_FILL
            elif not ok and col == "J":
                cell.fill = _RED_FILL
        r += 1
```

- [ ] **Step 4: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_export_sat_marks_excluded_row -v`
Expected: PASS

- [ ] **Step 5: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/pyrometry_report.py backend/tests/test_services/test_pyrometry.py
git commit -m "SAT 報表標註已排除列並排除於彙總"
```

---

## Task 8: 報表原始曲線灰色化已排除頻道（TDD）

**Files:**
- Modify: `backend/services/pyrometry_report.py`（`build_raw_chart_sheet` 約 327-378）
- Modify: `backend/services/pyrometry_service.py`（`export_test_xlsx` 約 664-670）
- Test: `backend/tests/test_services/test_pyrometry.py`

> 注意：`openpyxl.load_workbook` **不會**讀回圖表物件，故本測試直接對 `build_raw_chart_sheet`
> 產生的記憶體內 workbook 檢查數列（不經存檔/重載）。

- [ ] **Step 1: 寫失敗測試**

新增（直接單元測試 `build_raw_chart_sheet`，驗證已排除頻道數列線條為灰色）：

```python
def test_raw_chart_greys_excluded_channel():
    from openpyxl import Workbook
    from backend.services.pyrometry_report import build_raw_chart_sheet
    wb = Workbook()
    wb.remove(wb.active)
    build_raw_chart_sheet(
        wb, ["11:36", "11:38"],
        {"TUS-1": [179, 183], "TUS-2": [999, 999]},
        180, 10, sheet_name="原始數據", s_start=0, s_end=1,
        excluded_channels={"TUS-2"})
    ws = wb["原始數據"]
    chart = ws._charts[0]
    greys = [
        s for s in chart.series
        if s.graphicalProperties is not None
        and s.graphicalProperties.line is not None
        and "BFBFBF" in str(s.graphicalProperties.line.solidFill)
    ]
    assert greys, "已排除頻道應有灰色數列"
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_raw_chart_greys_excluded_channel -v`
Expected: FAIL（`build_raw_chart_sheet` 尚無 `excluded_channels` 參數 → TypeError）

- [ ] **Step 3: `build_raw_chart_sheet` 增加 `excluded_channels` 參數**

修改函式簽章（新增最後一個參數）：

```python
def build_raw_chart_sheet(wb, times, values: Dict[str, Any], setpoint: float, tol: float,
                          sheet_name: str = "原始數據", title: str = "TUS 溫度曲線",
                          s_start: Optional[int] = None, s_end: Optional[int] = None,
                          excluded_channels: Optional[set] = None):
```

在函式內 `highlight = ...` 之後加入：

```python
    excluded_channels = excluded_channels or set()
```

將儲存格超限標色的條件排除已排除頻道——把：
```python
            if highlight and (s_start <= j <= s_end) and (v is not None):
```
改為：
```python
            if highlight and (s_start <= j <= s_end) and (v is not None) and (ch not in excluded_channels):
```

在檔案頂部 import 區加入（若尚未匯入）：

```python
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
```

在 `chart.set_categories(cats)` 之後、`anchor_col = ...` 之前加入數列灰色化
（數列順序與 `channels` 相同；明確建立 `GraphicalProperties`/`LineProperties` 以免為 None）：

```python
    for idx, ch in enumerate(channels):
        if ch in excluded_channels:
            gp = GraphicalProperties()
            gp.line = LineProperties(solidFill="BFBFBF")
            chart.series[idx].graphicalProperties = gp
```

- [ ] **Step 4: `export_test_xlsx` 傳入已排除頻道**

在 `pyrometry_service.py` 的 `export_test_xlsx`，於 `if main["測試類型"] == "TUS":` 區塊內、呼叫 `build_raw_chart_sheet` 前計算已排除點位名，並帶入參數。將該區塊改為：

```python
        if main["測試類型"] == "TUS":
            rpt.build_tus_sheet(wb, detail, meta, tc_corr)
            excluded_ch = {p.get("點位") for p in detail["tus_points"] if p.get("已排除")}
            cd = detail.get("曲線資料") or {}
            if cd.get("時間"):
                rpt.build_raw_chart_sheet(
                    wb, cd.get("時間"), cd.get("數值"), setpoint, tol,
                    sheet_name="原始數據-記錄器", title="測試儀器（記錄器）溫度曲線",
                    s_start=cd.get("穩定開始", 0), s_end=cd.get("穩定結束", len(cd["時間"]) - 1),
                    excluded_channels=excluded_ch)
            if cd.get("爐體數值"):
                rpt.build_raw_chart_sheet(
                    wb, cd.get("爐體時間") or cd.get("時間"), cd.get("爐體數值"), setpoint, tol,
                    sheet_name="原始數據-爐體", title="爐體記錄溫度曲線",
                    excluded_channels=excluded_ch)
```

- [ ] **Step 5: 執行確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py::test_raw_chart_greys_excluded_channel -v`
Expected: PASS

- [ ] **Step 6: 全套件回歸**

Run: `cd backend && python -m pytest tests/test_services/test_pyrometry.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/pyrometry_report.py backend/services/pyrometry_service.py backend/tests/test_services/test_pyrometry.py
git commit -m "報表原始曲線灰色化已排除頻道"
```

---

## Task 9: 前端型別與 empty factory

**Files:**
- Modify: `src_frontend/src/types/pyrometry.ts`（`TusPoint` 48-58、`SatPoint` 68-77）
- Modify: `src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts`（`emptyTusPoint` 32-39、`emptySatPoint` 40-45）

- [ ] **Step 1: `TusPoint` 加欄位**

在 `是否合格?: boolean;` 之後加入：

```typescript
  已排除?: boolean;
  排除原因?: string;
```

- [ ] **Step 2: `SatPoint` 加欄位**

在其 `是否合格?: boolean;` 之後加入相同兩行：

```typescript
  已排除?: boolean;
  排除原因?: string;
```

- [ ] **Step 3: `emptyTusPoint` / `emptySatPoint` 補預設**

`emptyTusPoint` 物件內加入：
```typescript
  已排除: false,
  排除原因: '',
```
`emptySatPoint` 物件內加入相同兩行。

- [ ] **Step 4: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/types/pyrometry.ts src_frontend/src/pages/pyrometry/pyrometryFormUtils.ts
git commit -m "前端點位型別加入排除欄位"
```

---

## Task 10: TusChart 灰色化 helper 與 prop（TDD）

**Files:**
- Modify: `src_frontend/src/components/pyrometry/TusChart.tsx`
- Create: `src_frontend/src/components/pyrometry/TusChart.test.tsx`

- [ ] **Step 1: 寫失敗測試（純函式 helper）**

Create `src_frontend/src/components/pyrometry/TusChart.test.tsx`:

```typescript
import { describe, expect, it } from 'vitest';
import { channelLineColor, EXCLUDED_COLOR } from './TusChart';

describe('channelLineColor', () => {
  it('returns grey for excluded channels', () => {
    expect(channelLineColor(0, true)).toBe(EXCLUDED_COLOR);
  });
  it('returns a palette colour for normal channels', () => {
    expect(channelLineColor(0, false)).not.toBe(EXCLUDED_COLOR);
  });
});
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/components/pyrometry/TusChart.test.tsx`
Expected: FAIL（`channelLineColor`/`EXCLUDED_COLOR` 未匯出）

- [ ] **Step 3: TusChart 匯出 helper 並套用 prop**

在 `TusChart.tsx` 的 `COLORS` 常數之後加入：

```typescript
export const EXCLUDED_COLOR = '#adb5bd';
export const channelLineColor = (index: number, excluded: boolean): string =>
  excluded ? EXCLUDED_COLOR : COLORS[index % COLORS.length];
```

`TusChartProps` 介面加入：
```typescript
  excludedChannels?: string[];
```

元件解構參數加入 `excludedChannels = []`，並改資料集組法。將：
```typescript
    ...channels.map((ch, i) => {
      const base = COLORS[i % COLORS.length];
      const ptColor = 數值[ch].map((v, j) => ptStateColor(v, j, base));
      const ptRadius = 數值[ch].map((v, j) => (ptIsOut(v, j) ? 4 : 2));
```
改為：
```typescript
    ...channels.map((ch, i) => {
      const isExcluded = excludedChannels.includes(ch);
      const base = channelLineColor(i, isExcluded);
      const ptColor = 數值[ch].map((v, j) => (isExcluded ? base : ptStateColor(v, j, base)));
      const ptRadius = 數值[ch].map((v, j) => (!isExcluded && ptIsOut(v, j) ? 4 : 2));
```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/components/pyrometry/TusChart.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/pyrometry/TusChart.tsx src_frontend/src/components/pyrometry/TusChart.test.tsx
git commit -m "TusChart 支援已排除頻道灰色化"
```

---

## Task 11: TusSection 排除勾選與原因欄（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/TusSection.tsx`
- Modify: `src_frontend/src/pages/pyrometry/TusSection.test.tsx`

- [ ] **Step 1: 寫失敗測試**

在 `TusSection.test.tsx` 的 `describe` 內新增（並在既有 `render` 呼叫補上兩個新 props，見 Step 3 的 props 定義）：

```typescript
  it('toggles exclusion and requires a reason input', async () => {
    const user = userEvent.setup();
    const onToggleExclude = vi.fn();
    const onReasonChange = vi.fn();
    render(
      <TusSection
        tusPoints={tusPoints}
        setpoint="180" tolerance="10" chartData={null}
        rangeStart={0} rangeEnd={0} showDetail={false} timeLabels={[]}
        onFileUpload={() => undefined}
        onRangeStartChange={() => undefined}
        onRangeEndChange={() => undefined}
        onApplyRangeTus={() => undefined}
        onToggleDetail={() => undefined}
        onUpdateTus={() => undefined}
        onApplyCorrections={() => undefined}
        onToggleExclude={onToggleExclude}
        onReasonChange={onReasonChange}
      />,
    );
    await user.click(screen.getByRole('checkbox', { name: '排除 1' }));
    expect(onToggleExclude).toHaveBeenCalledWith(0, true);
  });
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/TusSection.test.tsx`
Expected: FAIL（無 checkbox / prop 未定義）

- [ ] **Step 3: TusSection 加 props 與欄位**

`Props` 介面加入：
```typescript
  onToggleExclude: (index: number, checked: boolean) => void;
  onReasonChange: (index: number, value: string) => void;
```
元件解構參數加入 `onToggleExclude, onReasonChange`。

表頭 `<tr>` 於「最低溫」之後加入兩欄：
```tsx
              <th style={{ width: 70 }}>排除</th>
              <th>排除原因</th>
```

每列 `<tr>` 於「最低溫」`<td>` 之後加入兩個 `<td>`：
```tsx
                <td className="text-center">
                  <Form.Check
                    type="checkbox"
                    aria-label={`排除 ${index + 1}`}
                    checked={!!point.已排除}
                    onChange={event => onToggleExclude(index, event.target.checked)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={point.排除原因 ?? ''}
                    aria-label={`排除原因 ${index + 1}`}
                    disabled={!point.已排除}
                    placeholder={point.已排除 ? '必填' : ''}
                    isInvalid={!!point.已排除 && !String(point.排除原因 ?? '').trim()}
                    onChange={event => onReasonChange(index, event.target.value)}
                  />
                </td>
```

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/TusSection.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/pages/pyrometry/TusSection.tsx src_frontend/src/pages/pyrometry/TusSection.test.tsx
git commit -m "TusSection 加入排除勾選與原因欄"
```

---

## Task 12: SatSection 排除勾選與原因欄（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/SatSection.tsx`
- Modify: `src_frontend/src/pages/pyrometry/SatSection.test.tsx`

> 注意：先讀 `SatSection.tsx` 現有明細表結構（控溫區列渲染處），比照其 `onUpdate*` 樣式加入新 props 與 UI。以下以與 TusSection 相同的欄位型式實作。

- [ ] **Step 1: 寫失敗測試**

在 `SatSection.test.tsx` 新增（props 名稱比照既有測試中 render 的既有 props，另加下列兩個）：

```typescript
  it('toggles zone exclusion', async () => {
    const user = userEvent.setup();
    const onToggleExclude = vi.fn();
    // ...沿用該檔既有 render helper，補上 onToggleExclude / onReasonChange 兩個 props
    await user.click(screen.getByRole('checkbox', { name: '排除 1' }));
    expect(onToggleExclude).toHaveBeenCalledWith(0, true);
  });
```

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/SatSection.test.tsx`
Expected: FAIL

- [ ] **Step 3: SatSection 加 props 與欄位**

`Props` 介面加入：
```typescript
  onToggleExclude: (index: number, checked: boolean) => void;
  onReasonChange: (index: number, value: string) => void;
```
在控溫區明細表每列（比照 TusSection Step 3）於最後加入「排除」checkbox 與「排除原因」欄，`aria-label` 分別為 `排除 ${index + 1}`、`排除原因 ${index + 1}`，`checked={!!point.已排除}`、原因欄 `disabled={!point.已排除}`。表頭同步加「排除」「排除原因」兩欄。

- [ ] **Step 4: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/SatSection.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/pages/pyrometry/SatSection.tsx src_frontend/src/pages/pyrometry/SatSection.test.tsx
git commit -m "SatSection 加入排除勾選與原因欄"
```

---

## Task 13: 表單 handler、曲線傳參與存檔擋原因（TDD）

**Files:**
- Modify: `src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx`
- Test: `src_frontend/src/pages/pyrometry/PyrometryTestForm.test.tsx`

> 先讀 `PyrometryTestForm.tsx` 的 `setTusPoints`/`setSatPoints` 用法、`TusSection`/`SatSection` 的 JSX 使用處、以及送出 payload 前的流程（約 200-290）。

- [ ] **Step 1: 寫失敗測試**

在 `PyrometryTestForm.test.tsx` 新增（驗證：勾選排除但未填原因時，不會呼叫送出 API）：

```typescript
  it('blocks submit when an excluded point has no reason', async () => {
    // 依該檔既有 render／mock 樣式：建立一個含已排除、無原因的 TUS 點
    // 觸發送出後，斷言送出 mutation/mock 未被呼叫，且顯示錯誤訊息「排除的量測點必須填寫排除原因」
  });
```

（實作時比照該檔既有測試的 render 與 mock 寫法補完。）

- [ ] **Step 2: 執行確認失敗**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/PyrometryTestForm.test.tsx`
Expected: FAIL

- [ ] **Step 3: 新增排除 handler**

在 `PyrometryTestForm.tsx` 內（`setTusPoints` 定義後）加入四個 handler：

```typescript
  const handleToggleTusExclude = (index: number, checked: boolean) =>
    setTusPoints(prev => prev.map((p, i) =>
      i === index ? { ...p, 已排除: checked, 排除原因: checked ? p.排除原因 ?? '' : '' } : p));
  const handleTusReason = (index: number, value: string) =>
    setTusPoints(prev => prev.map((p, i) => (i === index ? { ...p, 排除原因: value } : p)));
  const handleToggleSatExclude = (index: number, checked: boolean) =>
    setSatPoints(prev => prev.map((p, i) =>
      i === index ? { ...p, 已排除: checked, 排除原因: checked ? p.排除原因 ?? '' : '' } : p));
  const handleSatReason = (index: number, value: string) =>
    setSatPoints(prev => prev.map((p, i) => (i === index ? { ...p, 排除原因: value } : p)));
```

- [ ] **Step 4: 接上 Section props 與曲線灰色化**

`<TusSection ... />` 補上：
```tsx
              onToggleExclude={handleToggleTusExclude}
              onReasonChange={handleTusReason}
```
若表單直接使用 `<TusChart>`（或透過 TusSection 傳遞），將已排除點位名傳入其 `excludedChannels`：
```tsx
              excludedChannels={tusPoints.filter(p => p.已排除).map(p => p.點位)}
```
`<SatSection ... />` 補上：
```tsx
              onToggleExclude={handleToggleSatExclude}
              onReasonChange={handleSatReason}
```
（若 `excludedChannels` 需經由 `TusSection` 轉傳，於 `TusSection` 的 `Props` 增加 `excludedChannels?: string[]` 並轉交給內部 `<TusChart>`。）

- [ ] **Step 5: 送出前擋未填原因**

在送出 payload 的函式最前面（建立 payload / 呼叫 mutation 之前）加入：

```typescript
    const activePoints = type === 'TUS' ? tusPoints : satPoints;
    const missingReason = activePoints.some(
      p => p.已排除 && !String(p.排除原因 ?? '').trim(),
    );
    if (missingReason) {
      setError('排除的量測點必須填寫排除原因');
      return;
    }
```

（`setError` 若不存在，改用該檔既有的錯誤顯示機制；實作時對齊現況。）

- [ ] **Step 6: 執行確認通過**

Run: `cd src_frontend && npx vitest run src/pages/pyrometry/PyrometryTestForm.test.tsx`
Expected: PASS

- [ ] **Step 7: 前端全測試 + lint + build**

Run: `cd src_frontend && npx vitest run && npm run lint && npm run build`
Expected: 全數通過

- [ ] **Step 8: Commit**

```bash
git add src_frontend/src/pages/pyrometry/PyrometryTestForm.tsx src_frontend/src/pages/pyrometry/PyrometryTestForm.test.tsx
git commit -m "表單接上排除 handler、曲線灰色化與存檔擋原因"
```

---

## Task 14: 正式 DB 套用 migration 與端到端驗證

**Files:** 無（操作）

- [ ] **Step 1: 套用 migration 到開發 DB**

Run（於 venv、依 `.env` 連線；PowerShell 可用 psql 或既有慣例）：
```bash
psql -U postgres -d qa_database -f backend/migration/31_add_point_exclusion.sql
```
Expected: `ALTER TABLE` ×2 成功

- [ ] **Step 2: 後端全套件最終回歸**

Run: `cd backend && python -m pytest -q`
Expected: PASS

- [ ] **Step 3: 手動端到端（可選，若已啟動前後端）**

於爐溫測試表單勾選某頻道「排除」、填原因、存檔；重開確認狀態保留；匯出報表確認該列灰底標「已排除：原因」、TUS 曲線該頻道為灰線；未填原因時存檔被擋。

- [ ] **Step 4: 收尾 commit（若有微調）**

```bash
git add -A
git commit -m "套用量測點排除 migration 並完成端到端驗證"
```

---

## 備註 / 不在範圍

- 不做 CQI-9 最少有效熱電偶數／有效點數下限驗證。
- 不回溯處理既有已存檔測試（本功能對新建/編輯生效）。
- SAT 無時間序列曲線，排除僅反映於明細表與報表。
