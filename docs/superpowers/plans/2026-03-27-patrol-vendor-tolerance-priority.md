# 巡檢歷史清單廠商公差優先 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 `get_history` 公差查詢，使巡檢紀錄有廠商時優先套用廠商公差管理系統資料。

**Architecture:** 只修改 `patrol_service.py` 的 `get_history` 方法：將批次公差查詢的 cache key 由二元 `(material, spec)` 改為三元 `(material, spec, vendor_id)`，並在呼叫 `ExtrusionToleranceService.check` 時傳入 `vendor_id=patrol.customer_id`。下游的 `ExtrusionToleranceService.check` 和 `ToleranceService.check_tolerance` 已正確實作廠商公差優先邏輯，無需修改。

**Tech Stack:** Python 3.14、Flask-SQLAlchemy、pytest（SQLite in-memory）

---

## 注意：現有失敗測試

執行 `pytest backend/tests/test_services/test_patrol.py` 時，`test_get_history_is_ng_true` 和 `test_get_history_concentricity_ng` 兩個測試目前已失敗（pre-existing，與本次修改無關）。原因是測試資料的 `ExtrusionToleranceDetail` 未設定 `std_val`，導致無法計算絕對公差界限。**本計畫不修正這兩個測試，不能讓它們的失敗誤判為本次改動造成的問題。**

---

## 修改的檔案

| 動作 | 路徑 | 說明 |
|---|---|---|
| Modify | `backend/services/patrol_service.py` | `get_history` 公差快取區塊，約第 565–586 行 |
| Modify | `backend/tests/test_services/test_patrol.py` | 新增廠商公差優先的測試案例 |

---

## Task 1：新增失敗測試

**Files:**
- Modify: `backend/tests/test_services/test_patrol.py`

- [ ] **Step 1：在 `test_patrol.py` 新增三個測試**

  在檔案末尾加入以下測試（需在檔案頂部 import 中補上 `VendorToleranceMain, VendorToleranceDetail`）：

  ```python
  from backend.models import (
      PatrolMain, PatrolDetail,
      ExtrusionToleranceMain, ExtrusionToleranceDetail,
      VendorToleranceMain, VendorToleranceDetail, Vendor,
  )


  def test_get_history_prefers_vendor_tolerance(app, db_session):
      """廠商+材質+規格三者相近時，優先套用廠商公差，而非押出公差"""
      with app.app_context():
          vendor = Vendor(name='廠商甲')
          db_session.add(vendor)
          db_session.flush()

          # 廠商公差：外徑標準值 10.0，公差 ±0.1（允許 9.9–10.1）
          vt_main = VendorToleranceMain(
              vendor_id=vendor.id, material='6061', spec='10*2'
          )
          db_session.add(vt_main)
          db_session.flush()
          db_session.add(VendorToleranceDetail(
              main_id=vt_main.id, item='外徑',
              std_val=10.0, tolerance_min=0.1, tolerance_max=0.1
          ))

          # 押出公差：外徑標準值 10.0，公差 ±1.0（允許 9.0–11.0，更寬鬆）
          et_main = ExtrusionToleranceMain(material='6061', spec='10*2*100')
          db_session.add(et_main)
          db_session.flush()
          db_session.add(ExtrusionToleranceDetail(
              main_id=et_main.id, item='外徑',
              std_val=10.0, tolerance_min=1.0, tolerance_max=1.0
          ))

          # 巡檢紀錄：外徑 = 10.5（超出廠商公差 ±0.1，但在押出公差 ±1.0 內）
          patrol = PatrolMain(
              date=date(2026, 1, 1),
              material='6061', spec='10*2*100',
              customer_id=vendor.id
          )
          db_session.add(patrol)
          db_session.flush()
          db_session.add(PatrolDetail(
              main_id=patrol.id, group=1, item='外徑', position='前段',
              min_val=10.5, max_val=10.5
          ))
          db_session.commit()

          result = PatrolService.get_history({'page': 1, 'per_page': 20})
          row = result['data'][0]
          # 若正確套用廠商公差（±0.1），10.5 超差 → is_ng=True
          assert row['is_ng'] is True
          assert row['tol_found'] is True


  def test_get_history_vendor_tolerance_cache_isolation(app, db_session):
      """相同 material+spec 但不同廠商時，各自套用各自的廠商公差，不互相污染"""
      with app.app_context():
          vendor_a = Vendor(name='廠商甲')
          vendor_b = Vendor(name='廠商乙')
          db_session.add_all([vendor_a, vendor_b])
          db_session.flush()

          # 廠商甲公差：外徑 ±0.1（嚴）
          vt_a = VendorToleranceMain(vendor_id=vendor_a.id, material='6061', spec='10*2')
          db_session.add(vt_a)
          db_session.flush()
          db_session.add(VendorToleranceDetail(
              main_id=vt_a.id, item='外徑',
              std_val=10.0, tolerance_min=0.1, tolerance_max=0.1
          ))

          # 廠商乙公差：外徑 ±2.0（寬）
          vt_b = VendorToleranceMain(vendor_id=vendor_b.id, material='6061', spec='10*2')
          db_session.add(vt_b)
          db_session.flush()
          db_session.add(VendorToleranceDetail(
              main_id=vt_b.id, item='外徑',
              std_val=10.0, tolerance_min=2.0, tolerance_max=2.0
          ))

          # 廠商甲巡檢：外徑 10.5 → 超出甲的 ±0.1 → NG
          patrol_a = PatrolMain(
              date=date(2026, 1, 1), material='6061', spec='10*2*100',
              customer_id=vendor_a.id
          )
          db_session.add(patrol_a)
          db_session.flush()
          db_session.add(PatrolDetail(
              main_id=patrol_a.id, group=1, item='外徑', position='前段',
              min_val=10.5, max_val=10.5
          ))

          # 廠商乙巡檢：外徑 10.5 → 在乙的 ±2.0 內 → OK
          patrol_b = PatrolMain(
              date=date(2026, 1, 2), material='6061', spec='10*2*100',
              customer_id=vendor_b.id
          )
          db_session.add(patrol_b)
          db_session.flush()
          db_session.add(PatrolDetail(
              main_id=patrol_b.id, group=1, item='外徑', position='前段',
              min_val=10.5, max_val=10.5
          ))
          db_session.commit()

          result = PatrolService.get_history({'page': 1, 'per_page': 20})
          rows = {r['cust_name']: r for r in result['data']}

          assert rows['廠商甲']['is_ng'] is True
          assert rows['廠商乙']['is_ng'] is False


  def test_get_history_no_customer_id_unchanged(app, db_session):
      """無廠商（customer_id=None）時，行為與修改前相同（fallback 到押出公差）"""
      with app.app_context():
          et_main = ExtrusionToleranceMain(material='6061', spec='10*2*100')
          db_session.add(et_main)
          db_session.flush()
          db_session.add(ExtrusionToleranceDetail(
              main_id=et_main.id, item='外徑',
              std_val=10.0, tolerance_min=1.0, tolerance_max=1.0
          ))

          # 無廠商巡檢：外徑 10.5（在押出公差 ±1.0 內）
          patrol = PatrolMain(
              date=date(2026, 1, 1), material='6061', spec='10*2*100',
              customer_id=None
          )
          db_session.add(patrol)
          db_session.flush()
          db_session.add(PatrolDetail(
              main_id=patrol.id, group=1, item='外徑', position='前段',
              min_val=10.5, max_val=10.5
          ))
          db_session.commit()

          result = PatrolService.get_history({'page': 1, 'per_page': 20})
          row = result['data'][0]
          assert row['tol_found'] is True
          assert row['is_ng'] is False
  ```

- [ ] **Step 2：確認測試失敗（實作前應 FAIL）**

  ```bash
  cd C:/QC_Database
  python -m pytest backend/tests/test_services/test_patrol.py::test_get_history_prefers_vendor_tolerance backend/tests/test_services/test_patrol.py::test_get_history_vendor_tolerance_cache_isolation backend/tests/test_services/test_patrol.py::test_get_history_no_customer_id_unchanged -v
  ```

  期望：`test_get_history_prefers_vendor_tolerance` FAIL（is_ng=False，因為 vendor_id 沒傳），其他兩個可能 PASS 或 FAIL。

- [ ] **Step 3：Commit 失敗測試**

  ```bash
  git add backend/tests/test_services/test_patrol.py
  git commit -m "test(patrol): 新增廠商公差優先套用的測試案例"
  ```

---

## Task 2：實作三元 cache key 與 vendor_id 傳遞

**Files:**
- Modify: `backend/services/patrol_service.py`（約第 565–586 行）

- [ ] **Step 1：修改 `get_history` 的公差快取區塊**

  找到 `get_history` 方法中的批次查詢公差區塊，將以下舊程式碼：

  ```python
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

  替換為：

  ```python
  unique_combos = {
      (patrol_item.material or '', patrol_item.spec or '', patrol_item.customer_id)
      for patrol_item, *_ in pagination.items
      if patrol_item.material
  }

  tol_cache: dict = {}
  for mat, sp, vid in unique_combos:
      result = ExtrusionToleranceService.check({'material': mat, 'spec': sp, 'vendor_id': vid})
      if result.get('found'):
          tol_cache[(mat, sp, vid)] = {t['項目']: t for t in result.get('tolerances', [])}
      else:
          tol_cache[(mat, sp, vid)] = None
  ```

- [ ] **Step 2：修改 cache lookup 改用三元 key**

  找到同方法中的 cache lookup：

  ```python
  tol_map = tol_cache.get((mat, sp)) if mat else None
  ```

  替換為：

  ```python
  tol_map = tol_cache.get((mat, sp, patrol.customer_id)) if mat else None
  ```

- [ ] **Step 3：執行新增的三個測試，確認全部通過**

  ```bash
  cd C:/QC_Database
  python -m pytest backend/tests/test_services/test_patrol.py::test_get_history_prefers_vendor_tolerance backend/tests/test_services/test_patrol.py::test_get_history_vendor_tolerance_cache_isolation backend/tests/test_services/test_patrol.py::test_get_history_no_customer_id_unchanged -v
  ```

  期望：3 個 PASS

- [ ] **Step 4：執行全部巡檢測試，確認原有測試未回退**

  ```bash
  cd C:/QC_Database
  python -m pytest backend/tests/test_services/test_patrol.py -v
  ```

  期望：新增 3 個 PASS，原有 4 個通過的測試仍 PASS，原有 2 個失敗的測試（`test_get_history_is_ng_true`、`test_get_history_concentricity_ng`）仍是 pre-existing FAIL（本次未修改）。

- [ ] **Step 5：Commit**

  ```bash
  git add backend/services/patrol_service.py
  git commit -m "fix(patrol): 歷史清單公差查詢傳入廠商 ID，優先套用廠商公差"
  ```
