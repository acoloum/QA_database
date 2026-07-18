# 出貨檢驗與巡檢 SPC 2026 現有資料實作計畫

> **給 Codex：** 執行本計畫時必須使用 `superpowers:executing-plans`，每個功能修正使用 `superpowers:test-driven-development`，宣告完成前使用 `superpowers:verification-before-completion`。

**目標：** 以出貨檢驗與巡檢目前已有的連續量測資料，完成 2026 AIAG & VDA SPC 手冊適用範圍內的共用研究引擎、正確穩定性與能力判定、不可變基準版本、核准稽核、OCAP、頁面與報表整合。

**架構：** 出貨與巡檢各自負責資料轉接，統計公式集中於共用 SPC 引擎。回溯分析產生不可變研究版本；持續 SPC 只能使用已核准的界限版本。前端與報表只呈現後端保存結果，不再自行重算判異規則或能力指標。

**技術：** Flask 3.1、SQLAlchemy、PostgreSQL 16／SQLite 測試變體、NumPy、SciPy、React 19、TypeScript、TanStack Query、Chart.js、Vitest、openpyxl。

**核准設計：** `docs/superpowers/specs/2026-07-18-shipping-patrol-spc-2026-current-data-design.md`

**測試基線：** 後端一律使用 `venv\Scripts\python.exe -m pytest`。前端指令從 `src_frontend` 執行。

---

## Task 1：確認測試基線與缺陷重現

**Files:** None（此工作只建立執行證據，不修改檔案）

- [ ] **Step 1：執行目前 SPC 測試基線**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_stability.py backend/tests/test_services/test_spc_distribution.py backend/tests/test_services/test_spc_control_limits.py backend/tests/test_services/test_spc_analysis_service.py backend/tests/test_services/test_spc_golden.py -q`

Expected: 既有測試全部 PASS，記錄通過數與 warning；這只代表舊契約沒有回歸，不代表新手冊差距已修正。

- [ ] **Step 2：以最小腳本重現四個已知缺陷**

依序重現：變異圖失控但仍有 Cp/Cpk、平均 `n` 產生單一界限、兩項判異規則錯誤、常態拒絕後仍保留常態模型。每項保存輸入與實際輸出於執行紀錄，不修改正式檔案。

- [ ] **Step 3：確認工作樹沒有因基線重現產生檔案**

Run: `git status --short`

Expected: 除執行前已知項目外沒有新檔。紅燈測試不得單獨提交；每個缺陷的失敗測試必須在後續對應 Task 中先寫、確認失敗、實作、確認通過，再一起提交。

---

## Task 2：建立統一資料契約與管制圖引擎

**Files:**

- Create: `backend/services/spc_contracts.py`
- Create: `backend/services/spc_chart_engine.py`
- Modify: `backend/services/spc_analysis_service.py`
- Modify: `backend/services/spc_constants.py`
- Create: `backend/tests/test_services/test_spc_2026_regressions.py`
- Create: `backend/tests/test_services/test_spc_chart_engine.py`
- Modify: `backend/tests/test_services/test_spc_analysis_service.py`

- [ ] **Step 1：為輸入與輸出契約寫失敗測試**

契約至少包含 `SpcSubgroup`、`SpcStudyInput`、`SpcChartSeries`、`SpcReason`。子組保留 `key`、`timestamp`、`values`、`record_ids`、`measurement_ids` 及實際 `n`。

```python
def test_subgroup_rejects_empty_values():
    with pytest.raises(ValueError, match="子組不可為空"):
        SpcSubgroup(key="G1", timestamp=None, values=[])
```

- [ ] **Step 2：先寫 X̄-S 選型測試**

- `n >= 3` 且標準差可計算：`chart_type == "xbar_s"`。
- `n == 2`：`chart_type == "xbar_r"`。
- 單值且時間順序成立：`chart_type == "i_mr"`。
- 混合結構無法合理解釋：回傳 `INVALID_SUBGROUP_STRUCTURE`，不回傳零界限。

在 `test_spc_2026_regressions.py` 加入不等子組測試，先執行並確認因缺少逐點界限而 FAIL，再開始實作：

```python
def test_unequal_subgroups_have_point_specific_limits():
    result = analyze_subgroups(SUBGROUPS_WITH_N_3_4_5)
    assert len(result["location_chart"]["ucl"]) == 3
    assert len(set(result["location_chart"]["ucl"])) == 3
    assert result["subgroup_sizes"] == [3, 4, 5]
```

- [ ] **Step 3：實作逐組界限**

核心介面：

```python
def calculate_chart_set(
    subgroups: list[SpcSubgroup],
    *,
    alpha: float = 0.0027,
) -> SpcChartSet:
    """依每組實際 n 計算位置圖與變異圖，電腦計算優先 X̄-S。"""
```

位置圖及變異圖的 `cl`、`ucl`、`lcl` 都輸出與資料點等長的陣列；固定 `n` 仍輸出重複陣列，避免前端分支。X̄-S 使用卡方精確界限；X̄-R 使用實際 `n` 的 R 分布／常數；I-MR 保存移動全距配對來源。

- [ ] **Step 4：保留舊函式相容包裝**

`calculate_control_limits()` 暫時呼叫新引擎，只在所有界限完全相同時回傳舊純量；不等 `n` 時另回傳 `x_ucls/x_lcls/r_ucls/r_lcls`，不得再以平均 `n` 計算。

- [ ] **Step 5：執行窄測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_chart_engine.py backend/tests/test_services/test_spc_analysis_service.py backend/tests/test_services/test_spc_2026_regressions.py -q`

Expected: PASS。

- [ ] **Step 6：提交**

```text
SPC：新增 X̄-S 優先與逐組界限計算引擎
```

---

## Task 3：位置圖與變異圖共同穩定性判定

**Files:**

- Modify: `backend/services/spc_stability.py`
- Modify: `backend/tests/test_services/test_spc_stability.py`
- Modify: `backend/tests/test_services/test_spc_2026_regressions.py`

- [ ] **Step 1：將八項規則改為通用序列測試**

介面接受逐點界限：

```python
def evaluate_chart_stability(
    values: list[float],
    cl: list[float],
    ucl: list[float],
    lcl: list[float],
    *,
    chart_kind: str,
    enabled_rules: list[str] | None = None,
) -> dict[str, Any]: ...
```

每筆違規包含 `index`、`window_start`、`window_end`、`rule`、`label`、`chart_kind`。以 `(index, rule, chart_kind)` 去重。

先在 `test_spc_2026_regressions.py` 加入位置穩定、變異失控案例，確認舊程式仍錯誤輸出 Cp/Cpk：

```python
def test_variation_chart_out_of_control_blocks_capability():
    result = analyze_subgroups(VARIATION_OUT_OF_CONTROL, specs={"USL": 11, "LSL": 9})
    assert result["stability"]["location"]["stable"] is True
    assert result["stability"]["variation"]["stable"] is False
    assert result["stability"]["stable"] is False
    assert result["capability"]["cpk"] is None
```

- [ ] **Step 2：修正交替與中心線兩側規則**

- `alternating_14` 以相鄰差值正負號交替判定，不依固定奇偶相位。
- `eight_beyond_1s_both` 除了沒有 Zone C 點，還必須 `any(v > cl)` 且 `any(v < cl)`。

- [ ] **Step 3：新增整體研究穩定性**

```python
def evaluate_study_stability(chart_set, enabled_rules=None):
    return {
        "evaluated": location["evaluated"] and variation["evaluated"],
        "stable": location["stable"] is True and variation["stable"] is True,
        "location": location,
        "variation": variation,
        "rules_used": rules,
    }
```

- [ ] **Step 4：移除前端作為真實來源的假設測試準備**

後端輸出必須包含所有圖表的違規點；前端之後只做映射，不再呼叫另一套規則。

- [ ] **Step 5：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_stability.py backend/tests/test_services/test_spc_2026_regressions.py -q`

Expected: PASS。

- [ ] **Step 6：提交**

```text
SPC：位置與變異圖共同判定穩定性並修正八項規則
```

---

## Task 4：分布、時間模型與指標適用性

**Files:**

- Modify: `backend/services/spc_distribution.py`
- Create: `backend/services/spc_time_model.py`
- Modify: `backend/services/spc_analysis_service.py`
- Create: `backend/tests/test_services/test_spc_time_model.py`
- Modify: `backend/tests/test_services/test_spc_distribution.py`
- Modify: `backend/tests/test_services/test_spc_analysis_service.py`
- Modify: `backend/tests/test_services/test_spc_golden.py`

- [ ] **Step 1：先定義「已接受／未確認」分布契約測試**

結果新增 `accepted`、`reason_code`、`candidates`、`fit_method`、`alpha`。常態檢定拒絕且替代模型未被接受時，`model=None`，不得再用常態分位數或常態 PPM。

```python
def test_rejected_normal_without_accepted_alternative_is_unconfirmed():
    dist = assess_distribution(BIMODAL_VALUES)
    assert dist["accepted"] is False
    assert dist["model"] is None
    assert dist_quantiles(dist) == (None, None, None)
```

先執行此案例，確認舊程式因保留常態模型而 FAIL，再開始實作。

- [ ] **Step 2：將分布擬合改為策略登錄表**

第一階段保留常態、非負形狀特性模型、對數常態；每個策略都回傳參數、適合度與拒絕理由。候選選擇必須先通過接受門檻，再比較適合度；只比較 likelihood 不足以宣告模型成立。

- [ ] **Step 3：建立保守的時間模型候選器**

```python
def classify_time_model(chart_set, stability, distribution) -> dict[str, Any]:
    """只產生候選模型與證據，不自動視為已核准。"""
```

- 位置、變異均穩定且常態已接受：候選 A1。
- 位置、變異均穩定且已接受非正態單峰：候選 A2。
- 位置穩定、變異不穩定：候選 B。
- 變異穩定、位置不穩定：依趨勢／階躍等證據列出 C 候選，不自動確認細分類。
- 位置與變異均不穩定或多峰：候選 D。
- 證據不足：`TIME_MODEL_UNCONFIRMED`。

- [ ] **Step 4：封鎖不適用的 Cp/Cpk**

`calculate_process_capability()` 改收 `time_model` 與整體 `stability`：只有已確認 A1/A2 且兩圖穩定才輸出 Cp/Cpk。B/C/D、未確認分布或未確認時間模型回傳 Pp/Ppk 或結構化不適用原因。

- [ ] **Step 5：移除小樣本常態 PPM 回退**

樣本或模型不足時 PPM 為 `None` 並附原因，不得以未驗證常態 Z 法補值。

- [ ] **Step 6：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_distribution.py backend/tests/test_services/test_spc_time_model.py backend/tests/test_services/test_spc_analysis_service.py backend/tests/test_services/test_spc_golden.py -q`

Expected: PASS。

- [ ] **Step 7：提交**

```text
SPC：新增時間模型與分布確認門檻
```

---

## Task 5：建立不可變研究、界限、事件與確效資料模型

**Files:**

- Modify: `backend/models.py`
- Create: `backend/migration/36_create_spc_study_versioning.sql`
- Modify: `backend/seeds/seed_roles.py`
- Create: `backend/tests/test_services/test_spc_models.py`
- Modify: `backend/tests/test_permission_gating.py`

- [ ] **Step 1：先寫模型關聯與唯一性失敗測試**

測試以下模型可由 SQLite `db.create_all()` 建立，研究版本不可覆寫式更新，同一研究版本號唯一，同一製程流／特性只能有一個生效界限版本：

- `SpcStudy` → `SPC研究`
- `SpcStudyVersion` → `SPC研究版本`
- `SpcStudySample` → `SPC研究樣本`
- `SpcLimitVersion` → `SPC界限版本`
- `SpcEvent` → `SPC事件`
- `SpcOcap` → `SPC異常處置`
- `SpcValidationRun` → `SPC軟體確效執行`

- [ ] **Step 2：新增 migration 36**

Migration 必須：

- 建立上述表、外鍵、查詢索引及 PostgreSQL 部分唯一索引；
- 所有 JSON 使用 JSONB；ORM 透過 `JsonType` 支援 SQLite；
- `created_by/approved_by/retired_by` 關聯 `使用者.識別碼`；
- 時間欄位使用 timezone-aware timestamp；
- 在 `出貨巡檢量測明細` 與 `巡檢子檔` 補目前排除者與排除時間欄位；歷史操作另寫 `操作日誌`，避免恢復時覆蓋稽核軌跡。

- [ ] **Step 3：遷移舊界限但不偽造證據**

把 `SPC管制界限` 每列匯入研究／研究版本／界限版本，狀態標示 `legacy_imported`，缺少的資料雜湊、核准人及完整篩選標示 `audit_incomplete=true`。不刪除舊表。

- [ ] **Step 4：新增權限**

角色預設：

- 檢驗員：`spc.view`
- QA 主管：`spc.view`、`spc.manage`
- 品管經理與 admin：`spc.view`、`spc.manage`、`spc.approve`

- [ ] **Step 5：執行模型與權限測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_models.py backend/tests/test_permission_gating.py backend/tests/test_permissions.py -q`

Expected: PASS。

- [ ] **Step 6：提交**

```text
SPC：新增研究版本、核准界限與 OCAP 稽核模型
```

---

## Task 6：建立出貨與巡檢資料轉接器

**Files:**

- Create: `backend/services/spc_adapters/__init__.py`
- Create: `backend/services/spc_adapters/common.py`
- Create: `backend/services/spc_adapters/shipping.py`
- Create: `backend/services/spc_adapters/patrol.py`
- Create: `backend/tests/test_services/test_spc_shipping_adapter.py`
- Create: `backend/tests/test_services/test_spc_patrol_adapter.py`

- [ ] **Step 1：先寫完整篩選正規化測試**

出貨製程流包含 `vendor/material/spec/field/start_date/end_date`；巡檢包含 `m_id/op_id/cust_id/mat/spec/item/pos/s_date/e_date`。空值、數字字串與日期需正規化後再排序序列化。

```python
def test_patrol_process_stream_changes_when_machine_changes():
    a = canonical_process_stream("patrol", {**BASE, "m_id": "1"})
    b = canonical_process_stream("patrol", {**BASE, "m_id": "2"})
    assert a.key != b.key
```

- [ ] **Step 2：寫來源 ID 與子組內容測試**

每個 `SpcSubgroup` 必須保留主檔 ID、量測明細 ID、時間、原始值、排除快照及合理子組鍵。巡檢不得只保留 `main_id`；出貨分段量測不得在 dict 聚合時互相覆蓋。

- [ ] **Step 3：實作穩定雜湊**

雜湊內容至少包含正規化篩選、排序後資料 ID、原始值、排除狀態、規格快照與計算契約版本。相同資料不同查詢順序產生相同 SHA-256；任一值或狀態變更即不同。

- [ ] **Step 4：實作兩個轉接器**

```python
def build_shipping_study_input(args: Mapping[str, Any]) -> SpcStudyInput: ...
def build_patrol_study_input(args: Mapping[str, Any]) -> SpcStudyInput: ...
```

所有查詢使用 SQLAlchemy bind parameters，不以字串拼接值。無資料與子組不足回傳原因碼，不以空界限補值。

- [ ] **Step 5：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_shipping_adapter.py backend/tests/test_services/test_spc_patrol_adapter.py -q`

Expected: PASS。

- [ ] **Step 6：提交**

```text
SPC：新增出貨與巡檢完整製程流資料轉接器
```

---

## Task 7：建立研究分析與基準生命週期服務

**Files:**

- Create: `backend/services/spc_study_service.py`
- Create: `backend/services/spc_errors.py`
- Create: `backend/tests/test_services/test_spc_study_service.py`

- [ ] **Step 1：先寫回溯分析版本測試**

`analyze(source, filters, actor_id)` 建立研究及不可變研究版本，保存樣本、規格快照、圖表、時間模型、分布、穩定性與指標。再次分析只新增版本，不修改舊 JSON。

- [ ] **Step 2：寫送審與資料雜湊衝突測試**

```python
def test_submit_rejects_changed_source_data(...):
    version = service.analyze(...)
    mutate_source_measurement()
    with pytest.raises(SpcConflict) as exc:
        service.submit(version.id, actor_id=manager.id, reason="建立基準")
    assert exc.value.code == "STUDY_DATA_CHANGED"
```

- [ ] **Step 3：寫核准資格測試**

未確認時間模型、變異圖失控、無適用圖表、資料稽核不完整或權限不足都不得核准。A1/A2、兩圖穩定且資料雜湊一致才可核准。

- [ ] **Step 4：實作狀態機**

允許狀態：

```text
draft -> submitted -> approved -> active -> retired
                 \-> rejected
```

所有轉換必填理由並寫 `操作日誌`。核准與啟用在單一交易內完成；使用資料庫唯一索引及鎖定防止同製程流並行雙重啟用。

- [ ] **Step 5：實作舊基準相容讀取**

`legacy_imported` 可查詢及顯示，但 `audit_incomplete` 不得直接視為新手冊正式核准基準；必須重新建立研究版本。

- [ ] **Step 6：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_study_service.py -q`

Expected: PASS。

- [ ] **Step 7：提交**

```text
SPC：實作不可變研究與基準核准生命週期
```

---

## Task 8：建立失控事件、OCAP 與排除稽核

**Files:**

- Create: `backend/services/spc_ocap_service.py`
- Modify: `backend/services/shipping_service.py`
- Modify: `backend/services/patrol_service.py`
- Create: `backend/tests/test_services/test_spc_ocap_service.py`
- Modify: `backend/tests/test_services/test_spc_control_limits.py`
- Modify: `backend/tests/test_services/test_patrol.py`

- [ ] **Step 1：先寫事件去重與 OCAP 測試**

持續 SPC 同一界限版本、資料點、圖表及規則只建立一筆事件。OCAP 必須保留 6M 調查、重新量測、製程調整、產品處置、責任人及有效性確認。

- [ ] **Step 2：寫排除／恢復稽核測試**

排除與恢復都必填理由；保存操作者、時間、舊值、新值。修改來源資料後，已核准研究版本及其樣本快照完全不變，只有後續分析得到新雜湊。

- [ ] **Step 3：實作事件同步**

只有持續 SPC 對已生效界限產生正式失控事件；回溯分析只回傳診斷違規，不自動開 OCAP。

- [ ] **Step 4：更新目前離群服務**

`set_measurement_exclusion()` 與 `set_patrol_detail_exclusion()` 接收 `actor_id`，更新目前狀態並呼叫 `log_audit()`。恢復時不得刪除先前排除紀錄。

- [ ] **Step 5：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_ocap_service.py backend/tests/test_services/test_spc_control_limits.py backend/tests/test_services/test_patrol.py -q`

Expected: PASS。

- [ ] **Step 6：提交**

```text
SPC：新增失控事件、OCAP 與排除恢復稽核
```

---

## Task 9：新增共用 SPC API 並切換舊統計服務

**Files:**

- Create: `backend/routes/spc_studies.py`
- Modify: `backend/app.py`
- Modify: `backend/routes/shipping.py`
- Modify: `backend/routes/patrol.py`
- Modify: `backend/services/shipping_service.py`
- Modify: `backend/services/patrol_service.py`
- Create: `backend/tests/test_spc_study_routes.py`
- Modify: `backend/tests/test_permission_gating.py`
- Modify: `backend/tests/test_services/test_shipping_cache.py`

- [ ] **Step 1：先寫 API 契約與權限失敗測試**

端點：

```text
POST /api/spc/studies/analyze
GET  /api/spc/studies
GET  /api/spc/studies/<id>
POST /api/spc/study-versions/<id>/submit
POST /api/spc/study-versions/<id>/approve
POST /api/spc/limit-versions/<id>/retire
GET  /api/spc/studies/<id>/history
POST /api/spc/events/<id>/ocap
PATCH /api/spc/ocap/<id>
```

分析需 `spc.view`，送審／OCAP 需 `spc.manage`，核准／停用需 `spc.approve`。資料雜湊衝突回 `409` 與 `STUDY_DATA_CHANGED`。

- [ ] **Step 2：實作統一錯誤回應**

```json
{"success": false, "code": "TIME_MODEL_UNCONFIRMED", "message": "時間模型尚未確認"}
```

不可計算的回溯結果使用 `200` 並在 `applicability.reasons` 說明；輸入錯誤 `400`、權限 `403`、版本衝突 `409`。

- [ ] **Step 3：切換兩個舊統計服務**

`ShippingService.get_stats()` 與 `PatrolService.get_spc()` 改呼叫相同引擎／轉接器。過渡期保留舊頂層欄位，但新增 `schema_version`、巢狀 `charts/stability/distribution/capability/applicability/study_version`；所有舊欄位都從同一結果映射，不再重算。

- [ ] **Step 4：停止舊凍結端點寫入**

GET 暫時提供唯讀 `legacy_imported` 狀態；POST／DELETE 回 `410 LEGACY_SPC_LIMITS_READ_ONLY`，提示使用研究核准流程。前後端同一批切換，避免使用者失去操作入口。

- [ ] **Step 5：調整快取**

回溯分析快取鍵使用規範化完整篩選與資料雜湊；核准、排除、恢復及來源資料異動後只失效相關製程流。正式研究版本本身不可因快取過期而改變。

- [ ] **Step 6：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_spc_study_routes.py backend/tests/test_permission_gating.py backend/tests/test_services/test_shipping_cache.py backend/tests/test_services/test_patrol.py -q`

Expected: PASS。

- [ ] **Step 7：提交**

```text
SPC：新增共用研究 API 並切換出貨與巡檢統計服務
```

---

## Task 10：報表改由保存研究版本重建

**Files:**

- Modify: `backend/services/spc_report.py`
- Modify: `backend/services/patrol_excel_utils.py`
- Modify: `backend/routes/shipping.py`
- Modify: `backend/routes/patrol.py`
- Create: `backend/tests/test_services/test_spc_report_versioning.py`
- Modify: `backend/tests/test_services/test_patrol_excel_utils.py`

- [ ] **Step 1：先寫版本重建測試**

建立研究版本並產生報表，修改來源資料後再次由同一版本產生；兩份 SPC 統計、界限、圖表資料與資料雜湊必須相同。

- [ ] **Step 2：擴充報表內容**

加入研究類型、完整篩選、規格快照、每組 `n`、圖表選型、位置／變異界限、時間模型、分布證據、穩定性、指標適用性、資料雜湊、程式版本、核准資訊及 OCAP 摘要。

- [ ] **Step 3：調整匯出端點**

優先接受 `study_version_id`。未提供時建立並保存一個回溯研究版本後匯出，確保報表永遠有可追溯來源。

- [ ] **Step 4：執行測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_report_versioning.py backend/tests/test_services/test_patrol_excel_utils.py -q`

Expected: PASS。

- [ ] **Step 5：提交**

```text
SPC：報表改由不可變研究版本重建
```

---

## Task 11：前端改用後端統一 SPC 契約

**Files:**

- Modify: `src_frontend/src/types/spc.ts`
- Create: `src_frontend/src/hooks/useSpcStudies.ts`
- Modify: `src_frontend/src/hooks/useShipping.ts`
- Modify: `src_frontend/src/hooks/usePatrol.ts`
- Modify: `src_frontend/src/utils/spcChartModel.ts`
- Modify: `src_frontend/src/utils/spcAnalysis.ts`
- Modify: `src_frontend/src/utils/spcChartModel.test.ts`
- Modify: `src_frontend/src/utils/spcAnalysis.test.ts`

- [ ] **Step 1：先更新型別與契約測試**

新增 `SpcStudyResult`、`SpcChartSeries`、`SpcApplicability`、`SpcTimeModel`、`SpcDistributionAssessment`、`SpcStudyVersionSummary`。界限是陣列，違規包含 `chart_kind` 與視窗。

- [ ] **Step 2：建立共用 Query hooks**

分析、送審、核准、停用、歷程、OCAP 均由 `useSpcStudies.ts` 提供，mutation 成功後依研究 ID 與製程流精準失效查詢。

- [ ] **Step 3：移除前端第二套判異真實來源**

`buildSpcChartModel()` 直接映射後端 `charts` 與 `stability`。`analyzeWECO()`／`analyzeRChartWECO()` 只保留為純展示或測試工具，不再決定頁面狀態、點色或能力卡。

- [ ] **Step 4：支援 X̄-S／X̄-R／I-MR 與逐點界限**

圖例、縱軸名稱及資料集依 `chart_type` 動態顯示；UCL/LCL 使用陣列。變異圖同時判斷上、下界。

- [ ] **Step 5：執行前端窄測試**

Run: `npx vitest run src/utils/spcChartModel.test.ts src/utils/spcAnalysis.test.ts`

Workdir: `src_frontend`

Expected: PASS。

- [ ] **Step 6：提交**

```text
前端：改用後端 SPC 研究契約與逐點界限
```

---

## Task 12：共用研究面板、核准歷程與 OCAP UI

**Files:**

- Create: `src_frontend/src/components/spc/SpcStudyPanel.tsx`
- Create: `src_frontend/src/components/spc/SpcStudyWorkflowBar.tsx`
- Create: `src_frontend/src/components/spc/SpcBaselineApprovalModal.tsx`
- Create: `src_frontend/src/components/spc/SpcStudyHistoryOffcanvas.tsx`
- Create: `src_frontend/src/components/spc/SpcOcapOffcanvas.tsx`
- Modify: `src_frontend/src/components/spc/SpcDashboardPanel.tsx`
- Modify: `src_frontend/src/components/spc/SpcMethodologyModal.tsx`
- Modify: `src_frontend/src/components/shipping/ShippingCharts.tsx`
- Modify: `src_frontend/src/components/patrol/PatrolCharts.tsx`
- Create: `src_frontend/src/components/spc/SpcStudyPanel.test.tsx`
- Create: `src_frontend/src/components/spc/SpcBaselineApprovalModal.test.tsx`
- Create: `src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx`
- Modify: `src_frontend/src/components/shipping/ShippingCharts.test.tsx`
- Modify: `src_frontend/src/components/patrol/PatrolCharts.test.tsx`

- [ ] **Step 1：先寫模式與適用性 UI 測試**

測試回溯／持續 SPC 標章、A1/A2/B/C/D 候選、分布未確認原因、位置穩定但變異失控時不顯示 Cp/Cpk。

- [ ] **Step 2：建立共用面板**

共用面板顯示研究摘要、方法、樣本充分性、位置圖、變異圖、分布、Pp/Ppk 或 Cp/Cpk、診斷原因及版本。現場持續模式預設不顯示規格界限；回溯模式提供切換。

- [ ] **Step 3：取代凍結／解凍按鈕**

工作流程列改為「建立候選」「送審」「核准生效」「停用／重建」。核准 Modal 顯示完整篩選、資料筆數、來源 ID 摘要、資料雜湊、時間範圍、子組、界限及理由。

- [ ] **Step 4：加入權限閘門**

`spc.view` 可分析，`spc.manage` 可送審與維護 OCAP，`spc.approve` 才顯示核准／停用。前端隱藏按鈕只改善體驗；後端仍是最終權限控制。

- [ ] **Step 5：建立歷程與 OCAP Offcanvas**

歷程顯示不可變研究／界限版本與稽核缺漏。點擊失控點可開 OCAP，輸入 6M、重新量測、製程調整、產品處置、責任人及有效性。

- [ ] **Step 6：切換出貨與巡檢頁面**

兩頁把目前完整篩選傳給共用面板；移除舊 `limits_frozen` 操作及前端自行組合不完整 key。保留既有離群管理入口，但補理由及稽核資訊。

- [ ] **Step 7：執行元件測試**

Run: `npx vitest run src/components/spc src/components/shipping/ShippingCharts.test.tsx src/components/patrol/PatrolCharts.test.tsx`

Workdir: `src_frontend`

Expected: PASS。

- [ ] **Step 8：提交**

```text
前端：新增 SPC 研究核准、歷程與 OCAP 共用介面
```

---

## Task 13：更新確效文件、黃金資料與舊功能清理

**Files:**

- Modify: `backend/tests/test_services/test_spc_golden.py`
- Modify: `backend/scripts/spc_regression.py`
- Modify: `docs/spc_validation.md`
- Modify: `docs/superpowers/plans/2026-07-17-aiag-vda-spc-2026-compliance.md`
- Create: `docs/spc_migration_36_runbook.md`

- [ ] **Step 1：擴充黃金資料集**

固定輸入與期望值涵蓋 A1、A2、B、C、D，X̄-S、X̄-R、I-MR，不等 `n`，單／雙邊規格，位置穩定但變異失控，以及無可接受分布。

- [ ] **Step 2：讓回歸腳本驗證保存版本**

腳本輸出方法版本、資料雜湊、圖表選型、逐組界限、兩圖穩定性、時間模型、分布及指標；遇到模型未確認時驗證原因碼，不期待補值。

- [ ] **Step 3：更新 V&V 文件**

移除「前 25 組直接凍結」「小樣本退回常態」及「固定 X̄-R」描述；加入 X̄-S 優先、完整製程流、時間模型、不可變核准、OCAP、容許誤差及重現步驟。

- [ ] **Step 4：標示舊計畫已被新規格取代部分**

在 7 月 17 日計畫開頭加入 superseded notice，不改寫舊提交歷史內容。Runbook 包含 migration 36 備份、dry-run、筆數核對、legacy audit 缺漏及回復步驟。

- [ ] **Step 5：執行確效測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_services/test_spc_golden.py -q`

Run: `venv\Scripts\python.exe backend/scripts/spc_regression.py`

Expected: PASS 且無 `NaN`、無未說明的常態回退。

- [ ] **Step 6：提交**

```text
文件：更新 SPC 2026 軟體確效與版本遷移說明
```

---

## Task 14：全面驗證與完成審查

**Files:**

- Modify only if verification exposes a scoped defect.

- [ ] **Step 1：後端全量測試**

Run: `venv\Scripts\python.exe -m pytest backend/tests -q`

Expected: 全部 PASS；不得只跑 SPC 窄測試。

- [ ] **Step 2：前端 lint、build 與全量測試**

Run: `npm run lint`

Run: `npm run build`

Run: `npm test`

Workdir: `src_frontend`

Expected: lint 0 errors、build 成功、全部測試 PASS。既有無關 warning 必須明確記錄，不得誤報為本次新增。

- [ ] **Step 3：依賴與差異檢查**

Run: `npm audit`

Workdir: `src_frontend`

Run: `git diff --check`

Expected: 無本次新增的高風險依賴問題；差異檢查乾淨。

- [ ] **Step 4：migration 靜態與資料核對**

在可用 PostgreSQL 測試環境執行 migration 36 dry-run／transaction rollback；確認舊 `SPC管制界限` 筆數與 `legacy_imported` 筆數一致、原表仍存在、沒有偽造核准人。

- [ ] **Step 5：手動情境驗證**

1. 出貨頁套日期與廠商篩選，建立回溯分析；確認研究篩選及雜湊完整。
2. 巡檢頁切換機台、作業員或客戶；確認不會取得另一製程流的基準。
3. 建立變異失控資料；確認兩頁、報表均不顯示 Cp/Cpk。
4. 送審後修改來源資料；確認核准回 `409 STUDY_DATA_CHANGED`。
5. 核准 A1/A2 基準後加入失控點；確認建立事件並可完成 OCAP。
6. 停用基準；確認歷程仍可重建且沒有 DELETE。
7. 修改來源資料後由舊研究版本重匯報表；確認結果不變。

- [ ] **Step 6：最終程式碼審查**

依 `superpowers:requesting-code-review` 檢查：統計公式只有一份、權限在後端、版本不可變、完整篩選進雜湊、無常態補值、無刪除稽核資料、前端不重算。

- [ ] **Step 7：提交驗證後必要修正**

若驗證沒有產生檔案變更，不建立空提交；若有修正：

```text
SPC：修正全面驗證發現的整合問題
```

---

## 完成定義

- 位置與變異圖共同判定穩定性，變異失控時 Cp/Cpk 一律為空。
- 電腦計算預設 X̄-S；小子組或個別值按適用條件選 X̄-R／I-MR。
- 不等子組大小採逐點界限，不再平均 `n`。
- 常態拒絕後不回退；時間模型未確認時不宣告能力。
- 完整頁面篩選、資料 ID、規格快照與雜湊進入研究版本。
- 界限版本不可變，核准、停用、排除、恢復與 OCAP 均可稽核。
- 出貨、巡檢、前端與報表共用同一後端統計結果。
- 舊基準保留為 `legacy_imported`，不刪除、不偽造核准證據。
- 黃金資料、後端全量、前端 lint／build／test、audit 與差異檢查全部完成並有實際輸出證據。
