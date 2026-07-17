# AIAG-VDA SPC 2026 合規改造實作計畫（P0～P2 全部）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使系統的 SPC 計算、介面與報告符合 AIAG-VDA SPC 手冊 2026 第一版（ISO 22514/3534 體系）。

**Architecture:** 後端新增三個獨立統計模組（穩定性判定 `spc_stability.py`、目標值 `spc_targets.py`、分布評估 `spc_distribution.py`），重構 `spc_analysis_service.py` 的能力指數計算（一律整體變異、穩定性決定 Cp/Cpk vs Pp/Ppk 命名），`shipping_service`/`patrol_service` 只做整合。資料模型加「特性重要度」「排除統計」欄位與「SPC管制界限」凍結表。前端擴充型別後改版 `ProcessCapabilityCard`，管制圖預設不顯示規格界限。

**Tech Stack:** Flask 3.1 + SQLAlchemy + scipy/numpy（後端）、React 19 + TypeScript + Chart.js + vitest（前端）、PostgreSQL 16（raw SQL migration）。

**測試指令：**
- 後端：repo 根目錄執行 `python -m pytest backend/tests/test_services/<檔案>.py -v`（venv 環境）
- 前端：`cd src_frontend && npx vitest run <檔案>`
- 全量驗證：`python -m pytest backend/tests -x -q` 與 `cd src_frontend && npm run build && npm run lint && npm test`

**手冊依據速查（讀者不需重讀手冊）：**
- §6.2/表 6-1：P（績效）用於未證明穩定；C（能力）僅限已證明穩定（統計受控）。兩者公式相同、皆用整體變異。
- §6.8.2.1：G 法（分位數法）：`Cp.G=(U−L)/(X99.865%−X0.135%)`、`Cpk.G=min((U−X50%)/(X99.865%−X50%), (X50%−L)/(X50%−X0.135%))`；常態時退化為 `(U−L)/6s` 與 `min((U−x̄)/3s,(x̄−L)/3s)`（s 為整體樣本標準差）。
- §6.8.2.2：單側規格只計算對應側的 Ppk/Cpk；Cp 可另列為補充。
- §6.6：離群值不得刪除，須標示為無效、保留追溯、排除於參數計算，並記錄原因。
- §9.2.2.1：每多套用一條失控準則誤警率約 +10%，應避免同時套用多項；預設精簡集。
- §9.3.1：現場管制圖不應顯示規格界限；管制界限與規格界限須不同顏色。
- 表 6-4/8-3：目標值依特性重要度（關鍵/主要/次要/其他）。持續監控 Pp/Ppk 或 Cp/Cpk：關鍵 1.67、主要 1.33、次要/其他 1.00。
- 表 8-4/8-5：樣本數 N<125 時依信賴水準上修目標值。
- §10.2：分析軟體須 V&V，計算參數（最小樣本、離群值處理、估計方法、單側算法）必須透明。

---

## Phase 1 — 後端統計引擎（P0）

### Task 1: 穩定性判定模組 `spc_stability.py`

**Files:**
- Create: `backend/services/spc_stability.py`
- Test: `backend/tests/test_services/test_spc_stability.py`

- [ ] **Step 1: 寫失敗測試**

```python
# backend/tests/test_services/test_spc_stability.py
from backend.services.spc_stability import (
    DEFAULT_STABILITY_RULES,
    evaluate_stability,
)


def test_stable_process_returns_stable_true():
    # 交替繞中心線的資料，不觸發任何準則
    avgs = [10.0, 10.2, 9.8, 10.1, 9.9, 10.2, 9.8, 10.1, 9.9, 10.0]
    result = evaluate_stability(avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["evaluated"] is True
    assert result["stable"] is True
    assert result["violations"] == []
    assert result["rules_used"] == DEFAULT_STABILITY_RULES


def test_point_beyond_limits_marks_unstable():
    avgs = [10.0, 10.2, 9.8, 10.1, 12.0, 10.2, 9.8, 10.1, 9.9, 10.0]
    result = evaluate_stability(avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["stable"] is False
    assert result["violations"][0]["index"] == 4
    assert result["violations"][0]["rule"] == "beyond_limits"


def test_run_9_same_side_marks_unstable():
    avgs = [10.1] * 9 + [9.9]
    result = evaluate_stability(avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["stable"] is False
    assert any(v["rule"] == "run_9_same_side" for v in result["violations"])


def test_disabled_rule_is_not_applied():
    avgs = [10.1] * 9 + [9.9]
    result = evaluate_stability(
        avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1,
        enabled_rules=["beyond_limits"],
    )
    assert result["stable"] is True
    assert result["rules_used"] == ["beyond_limits"]


def test_insufficient_data_returns_not_evaluated():
    result = evaluate_stability([10.0, 10.1], x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["evaluated"] is False
    assert result["stable"] is None
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_spc_stability.py -v`
Expected: FAIL（`ModuleNotFoundError: backend.services.spc_stability`）

- [ ] **Step 3: 實作模組**

```python
# backend/services/spc_stability.py
"""穩定性準則（失控準則）判定 — AIAG-VDA SPC 2026 §9.2.2

每增加一條準則會提高誤警率約 10%（§9.2.2.1），
因此預設僅啟用精簡集，其餘準則以參數啟用。
"""
from typing import Any, Dict, List, Optional

# 預設精簡準則集（§9.2.2.1：避免同時套用多項準則）
DEFAULT_STABILITY_RULES = ["beyond_limits", "run_9_same_side", "trend_6"]

# 手冊 §9.2.2 列舉的完整準則（Western Electric / Nelson 子集）
ALL_STABILITY_RULES = [
    "beyond_limits",           # 單點超出管制界限（±3σ）
    "two_of_three_beyond_2s",  # 連續3點中2點位於同側且超出2σ
    "four_of_five_beyond_1s",  # 連續5點中4點位於同側且超出1σ
    "run_9_same_side",         # 連續9點位於中心線同側
    "trend_6",                 # 連續6點持續上升或下降
    "fifteen_within_1s",       # 連續15點皆在中心線±1σ內
]

RULE_LABELS = {
    "beyond_limits": "單點超出管制界限",
    "two_of_three_beyond_2s": "3點中2點超出同側2σ",
    "four_of_five_beyond_1s": "5點中4點超出同側1σ",
    "run_9_same_side": "連續9點同側",
    "trend_6": "連續6點趨勢",
    "fifteen_within_1s": "連續15點在1σ內",
}


def evaluate_stability(
    avgs: List[float],
    x_cl: float,
    x_ucl: float,
    x_lcl: float,
    enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """依啟用的穩定性準則評估製程是否統計受控。

    回傳 evaluated=False 表示資料不足無法評估（此時只能報 Pp/Ppk，§6.2）。
    """
    rules = enabled_rules if enabled_rules is not None else DEFAULT_STABILITY_RULES
    result: Dict[str, Any] = {
        "evaluated": False,
        "stable": None,
        "violations": [],
        "rules_used": rules,
    }
    if len(avgs) < 5 or x_ucl <= x_cl:
        return result

    sigma = (x_ucl - x_cl) / 3
    violations: List[Dict[str, Any]] = []

    def add(idx: int, rule: str) -> None:
        violations.append({"index": idx, "rule": rule, "label": RULE_LABELS[rule]})

    for i, v in enumerate(avgs):
        if "beyond_limits" in rules and (v > x_ucl or v < x_lcl):
            add(i, "beyond_limits")
        if "two_of_three_beyond_2s" in rules and i >= 2:
            w = avgs[i - 2:i + 1]
            above = sum(1 for x in w if x > x_cl + 2 * sigma)
            below = sum(1 for x in w if x < x_cl - 2 * sigma)
            if above >= 2 or below >= 2:
                add(i, "two_of_three_beyond_2s")
        if "four_of_five_beyond_1s" in rules and i >= 4:
            w = avgs[i - 4:i + 1]
            above = sum(1 for x in w if x > x_cl + sigma)
            below = sum(1 for x in w if x < x_cl - sigma)
            if above >= 4 or below >= 4:
                add(i, "four_of_five_beyond_1s")
        if "run_9_same_side" in rules and i >= 8:
            w = avgs[i - 8:i + 1]
            if all(x > x_cl for x in w) or all(x < x_cl for x in w):
                add(i, "run_9_same_side")
        if "trend_6" in rules and i >= 5:
            w = avgs[i - 5:i + 1]
            inc = all(w[j] > w[j - 1] for j in range(1, 6))
            dec = all(w[j] < w[j - 1] for j in range(1, 6))
            if inc or dec:
                add(i, "trend_6")
        if "fifteen_within_1s" in rules and i >= 14:
            w = avgs[i - 14:i + 1]
            if all(abs(x - x_cl) <= sigma for x in w):
                add(i, "fifteen_within_1s")

    result["evaluated"] = True
    result["stable"] = len(violations) == 0
    result["violations"] = violations
    return result
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_spc_stability.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/spc_stability.py backend/tests/test_services/test_spc_stability.py
git commit -m "SPC:新增穩定性準則判定模組(AIAG-VDA 2026 §9.2.2)"
```

---

### Task 2: 目標值模組 `spc_targets.py`

**Files:**
- Create: `backend/services/spc_targets.py`
- Test: `backend/tests/test_services/test_spc_targets.py`

- [ ] **Step 1: 寫失敗測試**

```python
# backend/tests/test_services/test_spc_targets.py
from backend.services.spc_targets import resolve_targets


def test_critical_class_full_sample_uses_base_targets():
    t = resolve_targets("關鍵", n_values=200)
    assert t["class"] == "關鍵"
    assert t["p_target"] == 1.67
    assert t["pk_target"] == 1.67
    assert t["adjusted"] is False
    assert t["insufficient_sample"] is False


def test_major_class_small_sample_adjusts_upward():
    # 表 8-5，95% 信賴水準，N=100，基準 1.33 → 1.35
    t = resolve_targets("主要", n_values=100)
    assert t["pk_target"] > 1.33
    assert t["adjusted"] is True


def test_sample_between_rows_uses_lower_row():
    # N=105 介於 100 與 110 → 保守採 100 列
    t100 = resolve_targets("主要", n_values=100)
    t105 = resolve_targets("主要", n_values=105)
    assert t105["pk_target"] == t100["pk_target"]


def test_below_75_flags_insufficient():
    t = resolve_targets("次要", n_values=40)
    assert t["insufficient_sample"] is True
    assert t["pk_target"] >= 1.00


def test_unknown_class_falls_back_to_other():
    t = resolve_targets(None, n_values=200)
    assert t["class"] == "其他"
    assert t["pk_target"] == 1.00
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_spc_targets.py -v`
Expected: FAIL（module not found）

- [ ] **Step 3: 實作模組**

> 注意：`TARGET_ADJUST_P`/`TARGET_ADJUST_PK` 數值轉錄自手冊表 8-4/8-5（掃描版），
> 實作時若使用者可提供 PDF，建議以 `表 8-4/8-5`（PDF 第 188 頁渲染圖）人工複核一次。

```python
# backend/services/spc_targets.py
"""能力/績效指數目標值 — AIAG-VDA SPC 2026 表 6-4/8-3（特性重要度）與表 8-4/8-5（樣本數調整）"""
from typing import Any, Dict, Optional

VALID_CLASSES = ["關鍵", "主要", "次要", "其他"]

# 表 8-3：持續監控之 Pp/Cp 與 Ppk/Cpk 目標值（N≥125 基準）
CLASS_TARGETS = {
    "關鍵": {"p": 1.67, "pk": 1.67, "initial_pp": 2.00, "initial_ppk": 1.67},
    "主要": {"p": 1.33, "pk": 1.33, "initial_pp": 1.67, "initial_ppk": 1.33},
    "次要": {"p": 1.00, "pk": 1.00, "initial_pp": 1.33, "initial_ppk": 1.00},
    "其他": {"p": 1.00, "pk": 1.00, "initial_pp": 1.00, "initial_ppk": 1.00},
}

# 表 8-4/8-5 的欄（基準目標值）與列（樣本數，遞減）
BASE_COLUMNS = [2.33, 2.00, 1.67, 1.33, 1.00]
TABLE_NS = [125, 120, 110, 100, 90, 80, 75]

# 表 8-4：依樣本數調整 Cp/Pp 目標值（列 = N，欄對應 BASE_COLUMNS）
TARGET_ADJUST_P = {
    "95%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.00, 1.67, 1.33, 1.00],
        110: [2.35, 2.02, 1.68, 1.34, 1.01],
        100: [2.36, 2.03, 1.69, 1.35, 1.01],
        90:  [2.38, 2.04, 1.71, 1.36, 1.02],
        80:  [2.40, 2.06, 1.72, 1.37, 1.03],
        75:  [2.41, 2.07, 1.73, 1.38, 1.04],
    },
    "99%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.68, 1.33, 1.00],
        110: [2.36, 2.02, 1.69, 1.35, 1.01],
        100: [2.38, 2.04, 1.70, 1.36, 1.02],
        90:  [2.40, 2.06, 1.72, 1.37, 1.03],
        80:  [2.43, 2.09, 1.74, 1.39, 1.04],
        75:  [2.45, 2.10, 1.76, 1.40, 1.05],
    },
    "99.90%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.68, 1.34, 1.00],
        110: [2.37, 2.03, 1.70, 1.35, 1.02],
        100: [2.40, 2.06, 1.72, 1.37, 1.03],
        90:  [2.43, 2.09, 1.74, 1.39, 1.04],
        80:  [2.47, 2.12, 1.77, 1.41, 1.06],
        75:  [2.50, 2.14, 1.79, 1.43, 1.07],
    },
    "99.99%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.68, 1.34, 1.01],
        110: [2.38, 2.04, 1.70, 1.36, 1.02],
        100: [2.41, 2.07, 1.73, 1.38, 1.04],
        90:  [2.46, 2.11, 1.76, 1.40, 1.05],
        80:  [2.51, 2.15, 1.80, 1.43, 1.08],
        75:  [2.54, 2.18, 1.82, 1.45, 1.09],
    },
}

# 表 8-5：依樣本數調整 Cpk/Ppk 目標值
TARGET_ADJUST_PK = {
    "95%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.67, 1.33, 1.00],
        110: [2.35, 2.02, 1.68, 1.34, 1.01],
        100: [2.37, 2.03, 1.70, 1.35, 1.02],
        90:  [2.38, 2.05, 1.71, 1.36, 1.02],
        80:  [2.41, 2.07, 1.73, 1.37, 1.03],
        75:  [2.42, 2.08, 1.73, 1.38, 1.04],
    },
    "99%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.68, 1.33, 1.00],
        110: [2.36, 2.02, 1.69, 1.35, 1.01],
        100: [2.38, 2.04, 1.71, 1.36, 1.02],
        90:  [2.41, 2.07, 1.73, 1.37, 1.03],
        80:  [2.44, 2.09, 1.75, 1.39, 1.05],
        75:  [2.46, 2.11, 1.76, 1.40, 1.06],
    },
    "99.90%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.68, 1.34, 1.01],
        110: [2.37, 2.03, 1.70, 1.35, 1.02],
        100: [2.40, 2.06, 1.72, 1.37, 1.03],
        90:  [2.43, 2.09, 1.75, 1.39, 1.04],
        80:  [2.48, 2.13, 1.78, 1.42, 1.06],
        75:  [2.51, 2.15, 1.80, 1.43, 1.08],
    },
    "99.99%": {
        125: [2.33, 2.00, 1.67, 1.33, 1.00],
        120: [2.34, 2.01, 1.68, 1.34, 1.01],
        110: [2.38, 2.04, 1.70, 1.36, 1.02],
        100: [2.41, 2.07, 1.73, 1.38, 1.04],
        90:  [2.46, 2.11, 1.76, 1.40, 1.06],
        80:  [2.51, 2.16, 1.80, 1.44, 1.08],
        75:  [2.55, 2.19, 1.83, 1.45, 1.09],
    },
}


def _adjust(table: Dict[str, Dict[int, list]], base: float, n: int, confidence: str) -> float:
    """依表 8-4/8-5 查調整後目標值；N 介於列之間時保守取較小的 N 列。"""
    if base not in BASE_COLUMNS or n >= 125:
        return base
    rows = table[confidence]
    # 由大到小找第一個 <= n 的列；n < 75 一律用 75 列（另以 insufficient_sample 旗標警示）
    row_n = next((t for t in TABLE_NS if t <= n), 75)
    col = BASE_COLUMNS.index(base)
    return rows[row_n][col]


def resolve_targets(
    characteristic_class: Optional[str],
    n_values: int,
    confidence: str = "95%",
) -> Dict[str, Any]:
    """依特性重要度與樣本數解析目標值（表 8-3 + 表 8-4/8-5）。"""
    cls = characteristic_class if characteristic_class in VALID_CLASSES else "其他"
    base = CLASS_TARGETS[cls]
    p_target = _adjust(TARGET_ADJUST_P, base["p"], n_values, confidence)
    pk_target = _adjust(TARGET_ADJUST_PK, base["pk"], n_values, confidence)
    return {
        "class": cls,
        "confidence": confidence,
        "base_p_target": base["p"],
        "base_pk_target": base["pk"],
        "p_target": p_target,
        "pk_target": pk_target,
        "adjusted": p_target != base["p"] or pk_target != base["pk"],
        "insufficient_sample": n_values < 75,
    }
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_spc_targets.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/spc_targets.py backend/tests/test_services/test_spc_targets.py
git commit -m "SPC:新增特性重要度目標值模組(表8-3/8-4/8-5,含樣本數調整)"
```

---

### Task 3: `calculate_control_limits` 移除 X̄ 圖 LCL 箝制

**Files:**
- Modify: `backend/services/spc_analysis_service.py:42`
- Test: `backend/tests/test_services/test_spc_analysis_service.py`

- [ ] **Step 1: 寫失敗測試（追加到既有測試檔）**

```python
def test_control_limits_lcl_can_be_negative():
    # 中心線接近 0 時 LCL 不得被箝制為 0（真圓度等特性統計上允許負 LCL）
    result = calculate_control_limits(
        avgs=[0.01, 0.02, 0.015, 0.01, 0.02],
        ranges=[0.03, 0.04, 0.03, 0.04, 0.03],
        subgroup_sizes=[5, 5, 5, 5, 5],
    )
    assert result["x_lcl"] < 0
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_spc_analysis_service.py::test_control_limits_lcl_can_be_negative -v`
Expected: FAIL（x_lcl == 0）

- [ ] **Step 3: 修改實作**

`backend/services/spc_analysis_service.py` 第 42 行：

```python
# 修改前
    x_lcl = max(x_cl - A2 * r_cl, 0)
# 修改後
    x_lcl = x_cl - A2 * r_cl
```

- [ ] **Step 4: 執行整個測試檔確認全部通過**

Run: `python -m pytest backend/tests/test_services/test_spc_analysis_service.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/spc_analysis_service.py backend/tests/test_services/test_spc_analysis_service.py
git commit -m "SPC:X-bar圖LCL不再箝制為0"
```

---

### Task 4: `calculate_process_capability` 全面改造

**Files:**
- Modify: `backend/services/spc_analysis_service.py:57-155`（整個函式重寫）
- Test: `backend/tests/test_services/test_spc_analysis_service.py`（更新既有 + 新增）

- [ ] **Step 1: 更新/新增測試**

在 `backend/tests/test_services/test_spc_analysis_service.py` 頂部 import 加入：

```python
from backend.services.spc_stability import evaluate_stability
```

**修改既有測試** `test_process_capability_supports_two_sided_and_ppm`：加入穩定性參數並改斷言（cp/cpk 僅穩定時有值、pp/ppk 一律有值）：

```python
def test_process_capability_supports_two_sided_and_ppm():
    avgs = [10, 10.1, 9.9, 10.2, 9.8]
    stability = {"evaluated": True, "stable": True, "violations": [], "rules_used": []}
    result = calculate_process_capability(
        avgs=avgs,
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        include_reason=True,
        stability=stability,
    )
    assert result["available"] is True
    assert result["applicable"] == "capability"   # 穩定 → 報 Cp/Cpk
    assert result["cp"] is not None
    assert result["cpk"] is not None
    assert result["cp"] == result["pp"]           # §6.2：C 與 P 公式相同（整體變異）
    assert result["cpk"] == result["ppk"]
    assert result["cw"] is not None               # 組內指數另列 Cw/Cwk 參考
    assert result["method"] == "G"
    assert result["ppm"]["total"] >= 0
```

**新增測試：**

```python
def test_unstable_process_reports_performance_only():
    stability = {"evaluated": True, "stable": False,
                 "violations": [{"index": 0, "rule": "beyond_limits", "label": "x"}],
                 "rules_used": ["beyond_limits"]}
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=stability,
    )
    assert result["applicable"] == "performance"
    assert result["cp"] is None and result["cpk"] is None
    assert result["pp"] is not None and result["ppk"] is not None


def test_no_stability_info_reports_performance_only():
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=None,
    )
    assert result["applicable"] == "performance"
    assert result["cp"] is None


def test_upper_one_sided_limits():
    # 同心度等單側上限特性：只計算 PPU/CPU 側（§6.8.2.2）
    result = calculate_process_capability(
        avgs=[0.02, 0.03, 0.025, 0.02, 0.03],
        all_values=[0.02, 0.03, 0.025, 0.02, 0.03, 0.024],
        r_cl=0.01, d2=2.326,
        tolerance_limits={"USL": 0.05, "LSL": 0, "one_sided": "upper"},
    )
    assert result["one_sided"] == "upper"
    assert result["ppk"] is not None
    assert result["ppk"] == result["ppu"]
    assert result["pp"] is None


def test_targets_and_preliminary_flags():
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        characteristic_class="主要",
    )
    assert result["targets"]["class"] == "主要"
    assert result["targets"]["insufficient_sample"] is True  # 只有 10 筆
    assert result["preliminary"] is True                     # n<125 或子組<25
    assert isinstance(result["achieved"], bool)
```

同時更新既有單側下限測試 `test_process_capability_supports_lower_one_sided_limits` 的斷言：`cpk` → 檢查 `ppk`（原本 `cpk` 在無穩定性證明下應為 None）。保留其結構，把 `assert result["cpk"] ...` 類斷言改為 `assert result["ppk"] is not None` 與 `assert result["cpk"] is None`。

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_spc_analysis_service.py -v`
Expected: 新測試 FAIL（TypeError: unexpected keyword 'stability' 等）

- [ ] **Step 3: 重寫 `calculate_process_capability`**

以下取代 `backend/services/spc_analysis_service.py` 原 57-155 行整個函式；檔案頂部 import 加入 `from .spc_targets import resolve_targets`：

```python
def calculate_process_capability(
    avgs: List[float],
    all_values: List[float],
    r_cl: float,
    d2: float,
    tolerance_limits: Dict[str, Any],
    include_reason: bool = True,
    stability: Optional[Dict[str, Any]] = None,
    characteristic_class: str = "其他",
    confidence: str = "95%",
) -> Dict[str, Any]:
    """計算能力/績效指數 — AIAG-VDA SPC 2026。

    - Pp/Ppk 與 Cp/Cpk 公式相同，皆採整體變異（§6.2、§6.8.2.1 常態 G 法）
    - 僅在穩定性已證明（stability.stable=True）時回報 Cp/Cpk，否則只報 Pp/Ppk
    - 組內變異（R̄/d2）之指數另列為 Cw/Cwk 參考值，不再命名為 Cp/Cpk
    - 單側規格只計算對應側指數（§6.8.2.2）
    """
    process_capability: Dict[str, Any] = {"available": False}
    if include_reason:
        process_capability["reason"] = "no_tolerance"

    usl = tolerance_limits.get("USL")
    lsl = tolerance_limits.get("LSL")
    one_sided = tolerance_limits.get("one_sided")

    has_spec = (
        (one_sided == "lower" and lsl is not None)
        or (one_sided == "upper" and usl is not None)
        or (one_sided is None and usl is not None and lsl is not None)
    )
    if len(avgs) < 5:
        if has_spec:
            if include_reason:
                process_capability["reason"] = "insufficient_data"
            process_capability["valid_count"] = len(avgs)
        return process_capability
    if not has_spec:
        return process_capability

    x_bar = float(np.mean(all_values)) if all_values else float(np.mean(avgs))
    sigma_overall = float(np.std(all_values, ddof=1)) if len(all_values) >= 2 else 0.0
    sigma_within = r_cl / d2 if r_cl > 0 else 0.0
    is_stable = bool(stability and stability.get("stable"))

    def _r3(v):
        return round(v, 3) if v is not None else None

    # --- 整體變異指數（G 法常態公式，§6.8.2.1）---
    p_val = pu = pl = pk = None
    if sigma_overall > 0:
        if one_sided == "lower":
            pl = (x_bar - float(lsl)) / (3 * sigma_overall)
            pk = pl
        elif one_sided == "upper":
            pu = (float(usl) - x_bar) / (3 * sigma_overall)
            pk = pu
        else:
            p_val = (float(usl) - float(lsl)) / (6 * sigma_overall)
            pu = (float(usl) - x_bar) / (3 * sigma_overall)
            pl = (x_bar - float(lsl)) / (3 * sigma_overall)
            pk = min(pu, pl)

    # --- 組內參考指數 Cw/Cwk ---
    cw = cwk = None
    if sigma_within > 0:
        if one_sided == "lower":
            cwk = (x_bar - float(lsl)) / (3 * sigma_within)
        elif one_sided == "upper":
            cwk = (float(usl) - x_bar) / (3 * sigma_within)
        else:
            cw = (float(usl) - float(lsl)) / (6 * sigma_within)
            cwk = min(
                (float(usl) - x_bar) / (3 * sigma_within),
                (x_bar - float(lsl)) / (3 * sigma_within),
            )

    # --- PPM（Z 法概念；Phase 4 改依擬合分布）---
    ppm = {"upper": 0.0, "lower": 0.0, "total": 0.0}
    if sigma_overall > 0:
        ppm_upper = ppm_lower = 0.0
        if usl is not None:
            ppm_upper = round(float(scipy_stats.norm.sf((float(usl) - x_bar) / sigma_overall) * 1_000_000), 1)
        if lsl is not None and one_sided != "upper":
            ppm_lower = round(float(scipy_stats.norm.sf((x_bar - float(lsl)) / sigma_overall) * 1_000_000), 1)
        ppm = {"upper": ppm_upper, "lower": ppm_lower, "total": round(ppm_upper + ppm_lower, 1)}

    # --- 目標值（表 8-3～8-5）與達標判定 ---
    targets = resolve_targets(characteristic_class, n_values=len(all_values), confidence=confidence)
    achieved = pk is not None and pk >= targets["pk_target"]

    process_capability.update({
        "available": True,
        "usl": float(usl) if usl is not None else None,
        "lsl": float(lsl) if lsl is not None else None,
        "one_sided": one_sided,
        "method": "G",  # §6.8.2：G 法（常態情形之公式）
        # 績效指數（一律計算）
        "pp": _r3(p_val), "ppk": _r3(pk), "ppu": _r3(pu), "ppl": _r3(pl),
        # 能力指數（僅穩定時回報；數值同績效指數，§6.2）
        "cp": _r3(p_val) if is_stable else None,
        "cpk": _r3(pk) if is_stable else None,
        "cpu": _r3(pu) if is_stable else None,
        "cpl": _r3(pl) if is_stable else None,
        # 組內參考指數
        "cw": _r3(cw), "cwk": _r3(cwk),
        "applicable": "capability" if is_stable else "performance",
        "stability_stable": stability.get("stable") if stability else None,
        "sigma_within": round(sigma_within, 6),
        "sigma_overall": round(sigma_overall, 6),
        "ppm": ppm,
        "targets": targets,
        "achieved": achieved,
        # 手冊建議 n≥125、k≥25 子組（表 6-4）；不足時標示為初步值
        "preliminary": len(all_values) < 125 or len(avgs) < 25,
    })
    return process_capability
```

同檔頂部 import 區塊改為：

```python
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from .spc_constants import SPC_CONSTANTS
from .spc_targets import resolve_targets
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_spc_analysis_service.py backend/tests/test_services/test_spc_targets.py -v`
Expected: 全 PASS

- [ ] **Step 5: 跑受影響的整合測試**

Run: `python -m pytest backend/tests/test_services/test_shipping_cache.py backend/tests/test_services/test_patrol.py -q`
Expected: PASS（若有測試斷言 `cpk` 非 None，改斷言 `ppk`，因為未傳 stability 時 cpk 應為 None）

- [ ] **Step 6: Commit**

```bash
git add backend/services/spc_analysis_service.py backend/tests/test_services/
git commit -m "SPC:能力指數改採整體變異,穩定性決定Cp/Cpk與Pp/Ppk命名(§6.2/§6.8.2)"
```

---

### Task 5: `shipping_service.get_stats` 整合

**Files:**
- Modify: `backend/services/shipping_service.py:143-392`
- Test: `backend/tests/test_services/test_shipping_cache.py`（既有，驗證不破壞）

- [ ] **Step 1: 加入單側上限特性與特性重要度**

`shipping_service.py` 檔案內（`get_stats` 之前，class 層級或模組層級）新增常數：

```python
# 形狀公差特性：自然下界為 0，屬單側上限規格（§6.8.2.2、§6.8.1 摺疊分布特性）
SHAPE_UPPER_FIELDS = {"同心度", "真圓度", "真直度"}
```

修改 `get_stats` 內公差解析（原 209-238 行）：兩處 `LSL 視為 0` 的分支各加一行 one_sided 標記，並擷取特性重要度。修改後該段：

```python
                    char_class = "其他"
                    for t in tol_result.get('tolerances', []):
                        if t.get('項目') in field_match_set:
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
                            elif dim_min is None and dim_max is not None:
                                # 單側上限尺寸規格（同心度、真圓度等）：自然下界 0
                                tolerance_limits["LSL"] = 0
                                tolerance_limits["USL"] = dim_max
                                if field in SHAPE_UPPER_FIELDS:
                                    tolerance_limits["one_sided"] = "upper"
                            elif dim_min is not None and dim_max is None:
                                tolerance_limits["LSL"] = dim_min
                                tolerance_limits["one_sided"] = "lower"
                            else:
                                tol_min = t.get('公差下限')
                                tol_max = t.get('公差上限')
                                std = t.get('標準值')
                                if std is None and field in nominal_from_spec:
                                    std = nominal_from_spec[field]
                                if tol_min is not None and tol_max is not None and std is not None:
                                    tolerance_limits["LSL"] = std - abs(tol_min)
                                    tolerance_limits["USL"] = std + abs(tol_max)
                                elif tol_min is None and tol_max is not None:
                                    tolerance_limits["LSL"] = 0
                                    tolerance_limits["USL"] = abs(tol_max)
                                    if field in SHAPE_UPPER_FIELDS:
                                        tolerance_limits["one_sided"] = "upper"
                            break
```

注意：`char_class` 需在 `if material:` 區塊外先初始化 `char_class = "其他"`（材質未指定時使用預設）。

- [ ] **Step 2: 穩定性判定與能力計算整合**

檔案頂部 import 加入：

```python
from .spc_stability import evaluate_stability
```

原 355-367 行改為：

```python
            # --- SPC 統計計算 ---
            control_limits = calculate_control_limits(avgs, ranges, subgroup_sizes)
            usl = tolerance_limits.get("USL")
            lsl = tolerance_limits.get("LSL")
            # 穩定性判定（§9.2.2）— 決定回報能力(C)或績效(P)指數
            stability = evaluate_stability(
                avgs,
                control_limits["x_cl"],
                control_limits["x_ucl"],
                control_limits["x_lcl"],
            )
            process_capability = calculate_process_capability(
                avgs,
                all_values,
                control_limits["r_cl"],
                control_limits["d2"],
                tolerance_limits,
                stability=stability,
                characteristic_class=char_class,
            )
            distribution_stats = calculate_distribution_stats(all_values)
            cpk_trend = calculate_cpk_trend(all_values, dates_valid, subgroup_sizes, usl, lsl, is_minmax=is_minmax)
```

`_result` dict（369-392 行）追加兩個 key（放在 `"cpk_trend": cpk_trend` 之後）：

```python
                "stability": stability,
                "characteristic_class": char_class,
```

- [ ] **Step 3: 快取鍵改版（讓舊快取失效）**

原 156-159 行快取鍵前綴 `spc|` 改為 `spc2|`：

```python
        _cache_key = (
            f"spc2|{field}|{vendor or ''}|{material or ''}|"
            f"{spec or ''}|{start_date or ''}|{end_date or ''}"
        )
```

- [ ] **Step 4: 執行相關測試**

Run: `python -m pytest backend/tests/test_services/test_shipping_cache.py backend/tests/test_services/test_spc_analysis_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/shipping_service.py
git commit -m "出貨SPC:整合穩定性判定/特性重要度/單側上限規格"
```

---

### Task 6: `patrol_service.get_stats` 整合

**Files:**
- Modify: `backend/services/patrol_service.py:12-17, 101-122, 200-215`
- Test: `backend/tests/test_services/test_patrol.py`（既有）

- [ ] **Step 1: import 與特性重要度擷取**

`patrol_service.py` 第 12-17 行 import 區塊加入：

```python
from .spc_stability import evaluate_stability
```

第 101 行迴圈前初始化與擷取（比照 shipping）：

```python
                    char_class = "其他"
                    for t in tol_result.get('tolerances', []):
                        if t.get('項目') == item:
                            char_class = t.get('特性重要度') or "其他"
```

（其餘公差解析程式不變；`char_class = "其他"` 也要在 `if material:` 區塊外先宣告。）

- [ ] **Step 2: 呼叫端更新**

原 200-207 行改為：

```python
        stability = evaluate_stability(
            avgs,
            control_limits["x_cl"],
            control_limits["x_ucl"],
            control_limits["x_lcl"],
        )
        process_capability = calculate_process_capability(
            avgs,
            all_values,
            control_limits["r_cl"],
            control_limits["d2"],
            tolerance_limits,
            include_reason=False,
            stability=stability,
            characteristic_class=char_class,
        )
```

並在 get_stats 回傳 dict 中（`cpk_trend` 之後）加入：

```python
            "stability": stability,
            "characteristic_class": char_class,
```

（實際回傳 dict 位置：搜尋 `"cpk_trend"` 於 patrol_service.py，加在同一個 dict。）

- [ ] **Step 3: 執行測試**

Run: `python -m pytest backend/tests/test_services/test_patrol.py -q`
Expected: PASS（若有 cpk 非 None 斷言依 Task 4 Step 5 原則改為 ppk）

- [ ] **Step 4: Commit**

```bash
git add backend/services/patrol_service.py backend/tests/test_services/test_patrol.py
git commit -m "巡檢SPC:整合穩定性判定與特性重要度"
```

---

## Phase 2 — 資料模型與離群值（P0）

### Task 7: Migration 33 + models 欄位

**Files:**
- Create: `backend/migration/33_add_spc_compliance_columns.sql`
- Modify: `backend/models.py:230-236, 265-279, 293-303`

- [ ] **Step 1: 建立 migration SQL**

```sql
-- backend/migration/33_add_spc_compliance_columns.sql
-- AIAG-VDA SPC 2026 合規欄位：
--   特性重要度（表 8-3 目標值分級）、量測值離群排除（§6.6）

ALTER TABLE "廠商公差明細檔" ADD COLUMN IF NOT EXISTS "特性重要度" VARCHAR(10) NOT NULL DEFAULT '其他';
ALTER TABLE "擠壓公差明細檔" ADD COLUMN IF NOT EXISTS "特性重要度" VARCHAR(10) NOT NULL DEFAULT '其他';

-- §6.6：離群值不得刪除，須標示無效並保留追溯、排除於統計計算
ALTER TABLE "出貨巡檢量測明細" ADD COLUMN IF NOT EXISTS "排除統計" BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "出貨巡檢量測明細" ADD COLUMN IF NOT EXISTS "排除原因" VARCHAR(200);
```

- [ ] **Step 2: 套用 migration**

Run: `psql -U postgres -d qa_database -f backend/migration/33_add_spc_compliance_columns.sql`
Expected: `ALTER TABLE` ×4（開發 DB 密碼見專案 .env）

- [ ] **Step 3: models.py 同步**

`ShippingMeasurement`（第 236 行 `is_ng` 之後）加入：

```python
    # §6.6 離群值：標示無效並保留追溯，不得刪除；排除於統計計算之外
    excluded         = db.Column('排除統計', db.Boolean, default=False, nullable=False)
    exclusion_reason = db.Column('排除原因', db.String(200), nullable=True)
```

`VendorToleranceDetail`（第 278 行 `note` 之後）與 `ExtrusionToleranceDetail`（第 303 行 `unit` 之後）各加入：

```python
    # AIAG-VDA SPC 2026 表 8-3：特性重要度（關鍵/主要/次要/其他）決定能力指數目標值
    characteristic_class = db.Column('特性重要度', db.String(10), default='其他')
```

- [ ] **Step 4: 驗證 app 可啟動**

Run: `python -c "from backend.models import ShippingMeasurement, VendorToleranceDetail; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/migration/33_add_spc_compliance_columns.sql backend/models.py
git commit -m "資料模型:新增特性重要度與量測離群排除欄位(migration 33)"
```

---

### Task 8: `tolerance_service` 特性重要度讀寫

**Files:**
- Modify: `backend/services/tolerance_service.py:81-92, 112-125, 148-161, 359-367`
- Test: `backend/tests/test_services/test_tolerance.py`（既有測試檔追加）

- [ ] **Step 1: 寫失敗測試（追加到 test_tolerance.py）**

先看該檔既有 fixture 寫法（頂部 50 行），沿用其建立公差的方式。新增測試（依既有測試的 client/session pattern 調整呼叫方式）：

```python
def test_tolerance_detail_roundtrips_characteristic_class(app_ctx):
    from backend.services.tolerance_service import ToleranceService
    payload = {
        "材質": "TEST-CLS", "規格": "1*2*3", "廠商ID": None, "備註": "",
        "details": [{
            "測量項目": "外徑", "測量位置": "",
            "尺寸下限": 1.0, "尺寸上限": 2.0,
            "公差下限": None, "公差上限": None,
            "標準值": None, "單位": "mm", "備註": "",
            "特性重要度": "關鍵",
        }],
    }
    created = ToleranceService.create(payload)
    got = ToleranceService.get_by_id(created["id"] if isinstance(created, dict) else created)
    assert got["details"][0]["特性重要度"] == "關鍵"
```

（實作時對照 test_tolerance.py 既有的 create/get 呼叫慣例修正函式名稱；重點斷言是「特性重要度可存可取」。）

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_tolerance.py -k characteristic -v`
Expected: FAIL（KeyError 或欄位遺失）

- [ ] **Step 3: 實作四處修改**

1. 序列化（81-92 行 item dict）加入：

```python
                    "特性重要度": d.characteristic_class or '其他',
```

2. create（113-124 行 `VendorToleranceDetail(...)`）與 update（149-160 行）建構子各加入：

```python
                    characteristic_class=d.get('特性重要度', '其他'),
```

3. `check_tolerance` 明細 dict（359-367 行）加入：

```python
                    "特性重要度": d.characteristic_class or '其他',
```

4. 擠壓公差同步：在 `backend/services/extrusion_tolerance_service.py` 中以 `grep -n "公差下限" backend/services/extrusion_tolerance_service.py` 找到對應的序列化與建構子位置，做完全相同的三處修改（序列化輸出 `特性重要度`、create/update 寫入 `characteristic_class`）。

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_tolerance.py backend/tests/test_services/test_extrusion_tolerance.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/tolerance_service.py backend/services/extrusion_tolerance_service.py backend/tests/test_services/
git commit -m "公差服務:特性重要度欄位讀寫與check_tolerance輸出"
```

---

### Task 9: 離群值 API 與統計排除

**Files:**
- Modify: `backend/routes/shipping.py`（新增兩個端點）
- Modify: `backend/services/shipping_service.py`（get_stats 排除 + 兩個服務方法）
- Test: `backend/tests/test_services/test_shipping_measurement_keys.py`（追加）

- [ ] **Step 1: 寫失敗測試（追加）**

對照 `test_shipping_measurement_keys.py` 既有 fixture（建立 ShippingData + ShippingMeasurement 的方式），追加：

```python
def test_set_measurement_exclusion_and_stats_skip(session):
    # 依該檔既有 helper 建立一筆出貨記錄與量測明細後：
    from backend.services.shipping_service import ShippingService
    m_id = <既有helper建立的量測明細id>
    ShippingService.set_measurement_exclusion(m_id, excluded=True, reason="校正量測誤植")
    from backend.models import ShippingMeasurement
    m = ShippingMeasurement.query.get(m_id)
    assert m.excluded is True
    assert m.exclusion_reason == "校正量測誤植"

    # 解除
    ShippingService.set_measurement_exclusion(m_id, excluded=False, reason=None)
    assert ShippingMeasurement.query.get(m_id).excluded is False
```

（`<既有helper建立的量測明細id>` 於實作時以該測試檔的實際 fixture 取得——此檔已有建立量測明細的測試可複製。）

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_shipping_measurement_keys.py -k exclusion -v`
Expected: FAIL（AttributeError: set_measurement_exclusion）

- [ ] **Step 3: 服務方法**

`shipping_service.py` 的 `ShippingService` class 內新增：

```python
    @staticmethod
    def set_measurement_exclusion(measurement_id: int, excluded: bool, reason: Optional[str]) -> Dict[str, Any]:
        """標示/解除量測值離群排除（§6.6：不刪除、保留追溯、排除統計）"""
        m = ShippingMeasurement.query.get(measurement_id)
        if m is None:
            raise ValueError("量測明細不存在")
        if excluded and not (reason or "").strip():
            raise ValueError("標示離群值必須填寫原因（§6.6）")
        m.excluded = excluded
        m.exclusion_reason = (reason or "").strip() or None if excluded else None
        db.session.commit()
        ShippingService._invalidate_spc_cache()
        return {"id": m.id, "排除統計": m.excluded, "排除原因": m.exclusion_reason}

    @staticmethod
    def get_measurements(shipping_id: int) -> List[Dict[str, Any]]:
        """取得單筆出貨記錄的全部量測明細（供離群值管理 UI）"""
        rows = ShippingMeasurement.query.filter_by(shipping_id=shipping_id).order_by(
            ShippingMeasurement.item, ShippingMeasurement.group_num, ShippingMeasurement.position
        ).all()
        return [{
            "識別碼": m.id, "組別": m.group_num, "量測項目": m.item, "測量位置": m.position,
            "量測值": float(m.value_single) if m.value_single is not None else None,
            "量測最小值": float(m.value_min) if m.value_min is not None else None,
            "量測最大值": float(m.value_max) if m.value_max is not None else None,
            "排除統計": m.excluded, "排除原因": m.exclusion_reason,
        } for m in rows]
```

`_invalidate_spc_cache`：若 `shipping_service.py` 尚無快取清除 helper（以 `grep -n "SPCCache" backend/services/shipping_service.py` 確認），新增：

```python
    @staticmethod
    def _invalidate_spc_cache() -> None:
        from ..models import SPCCache
        try:
            SPCCache.query.filter(SPCCache.cache_key.like('spc2|%')).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
```

- [ ] **Step 4: get_stats 排除離群值**

`get_stats` 量測值迴圈（原 313 行 `for m in group_meas.get(i) or []:`）第一行加入：

```python
                    for m in group_meas.get(i) or []:
                        if m.excluded:
                            excluded_count += 1
                            continue
```

迴圈外（`avgs = []` 區塊，原 294 行附近）初始化 `excluded_count = 0`，並在 `_result` 加入 `"excluded_count": excluded_count,`。

- [ ] **Step 5: 路由**

`backend/routes/shipping.py`（`get_shipping_stats` 之後）新增：

```python
@shipping_bp.route('/api/data/<int:data_id>/measurements', methods=['GET'])
@auth_required
def get_shipping_measurements(data_id):
    """取得單筆出貨記錄的量測明細（含離群標記）"""
    try:
        return jsonify(ShippingService.get_measurements(data_id))
    except Exception as e:
        return api_error(str(e), 500)


@shipping_bp.route('/api/measurements/<int:measurement_id>/exclusion', methods=['PATCH'])
@auth_required
def set_measurement_exclusion(measurement_id):
    """標示/解除量測值離群排除（AIAG-VDA SPC 2026 §6.6）"""
    try:
        body = request.get_json(silent=True) or {}
        result = ShippingService.set_measurement_exclusion(
            measurement_id,
            excluded=bool(body.get('排除統計')),
            reason=body.get('排除原因'),
        )
        return jsonify(result)
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception as e:
        return api_error(str(e), 500)
```

- [ ] **Step 6: 執行測試**

Run: `python -m pytest backend/tests/test_services/test_shipping_measurement_keys.py backend/tests/test_services/test_shipping_cache.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/routes/shipping.py backend/services/shipping_service.py backend/tests/test_services/
git commit -m "離群值管理:量測明細排除API與統計排除(§6.6)"
```

---

## Phase 3 — 前端（P0）

### Task 10: 型別擴充與 chart model 傳遞

**Files:**
- Modify: `src_frontend/src/types/spc.ts`
- Modify: `src_frontend/src/utils/spcChartModel.ts`
- Test: `src_frontend/src/utils/spcChartModel.test.ts`（既有，跑通即可）

- [ ] **Step 1: types/spc.ts 擴充**

`ProcessCapability` 介面追加欄位（原欄位保留）：

```typescript
export interface SpcTargets {
  class: string;
  confidence: string;
  base_p_target: number;
  base_pk_target: number;
  p_target: number;
  pk_target: number;
  adjusted: boolean;
  insufficient_sample: boolean;
}

export interface SpcStabilityViolation {
  index: number;
  rule: string;
  label: string;
}

export interface SpcStability {
  evaluated: boolean;
  stable: boolean | null;
  violations: SpcStabilityViolation[];
  rules_used: string[];
}
```

`ProcessCapability` 內追加：

```typescript
  applicable?: 'capability' | 'performance';
  method?: 'G' | 'Z';
  cw?: number | null;
  cwk?: number | null;
  stability_stable?: boolean | null;
  targets?: SpcTargets;
  achieved?: boolean;
  preliminary?: boolean;
```

`SpcChartData` 內追加：

```typescript
  stability?: SpcStability;
  characteristic_class?: string;
  excluded_count?: number;
```

`DistributionStats` 內追加（Phase 4 使用，先定型別）：

```typescript
  model?: string;
  model_label?: string;
```

- [ ] **Step 2: spcChartModel 傳遞 stability**

`SpcChartModel` 介面（spcChartModel.ts:38-51）加入 `stability: SpcStability | null;`，`emptySpcChartModel` 加 `stability: null,`，`buildSpcChartModel` 回傳物件（197-229 行）加：

```typescript
    stability: data.stability || null,
```

import 區塊補 `SpcStability` 型別。

- [ ] **Step 3: 驗證**

Run: `cd src_frontend && npx tsc -b --noEmit 2>&1 | head -20 && npx vitest run src/utils/spcChartModel.test.ts`
Expected: 無型別錯誤、測試 PASS

- [ ] **Step 4: Commit**

```bash
git add src_frontend/src/types/spc.ts src_frontend/src/utils/spcChartModel.ts
git commit -m "前端型別:SPC穩定性/目標值/適用指數欄位"
```

---

### Task 11: `ProcessCapabilityCard` 改版

**Files:**
- Modify: `src_frontend/src/components/patrol/ProcessCapabilityCard.tsx`（全檔改寫）
- Modify: `src_frontend/src/components/spc/SpcDashboardPanel.tsx:108`（傳入 stability）
- Create: `src_frontend/src/components/patrol/ProcessCapabilityCard.test.tsx`

- [ ] **Step 1: 寫失敗測試**

```tsx
// src_frontend/src/components/patrol/ProcessCapabilityCard.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ProcessCapabilityCard from './ProcessCapabilityCard';

const targets = {
  class: '主要', confidence: '95%',
  base_p_target: 1.33, base_pk_target: 1.33,
  p_target: 1.35, pk_target: 1.35,
  adjusted: true, insufficient_sample: false,
};

describe('ProcessCapabilityCard (AIAG-VDA 2026)', () => {
  it('穩定製程顯示 Cp/Cpk 為適用指數', () => {
    render(<ProcessCapabilityCard statsItem="外徑" processCapability={{
      available: true, applicable: 'capability', method: 'G',
      cp: 1.5, cpk: 1.4, pp: 1.5, ppk: 1.4, usl: 11, lsl: 9,
      targets, achieved: true, preliminary: false, stability_stable: true,
    }} />);
    expect(screen.getByText('Cpk.G')).toBeInTheDocument();
    expect(screen.getByText(/穩定.*能力/)).toBeInTheDocument();
    expect(screen.getByText(/達標/)).toBeInTheDocument();
  });

  it('不穩定製程只顯示 Pp/Ppk 並標示不穩定', () => {
    render(<ProcessCapabilityCard statsItem="外徑" processCapability={{
      available: true, applicable: 'performance', method: 'G',
      cp: null, cpk: null, pp: 1.2, ppk: 1.1, usl: 11, lsl: 9,
      targets, achieved: false, preliminary: true, stability_stable: false,
    }} />);
    expect(screen.getByText('Ppk.G')).toBeInTheDocument();
    expect(screen.queryByText('Cpk.G')).not.toBeInTheDocument();
    expect(screen.getByText(/未達標/)).toBeInTheDocument();
    expect(screen.getByText(/初步值/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run src/components/patrol/ProcessCapabilityCard.test.tsx`
Expected: FAIL

- [ ] **Step 3: 改寫元件**

以下為完整新版 `ProcessCapabilityCard.tsx`（介面 props 不變，新欄位皆 optional，patrol/shipping 兩處呼叫端不需改）：

```tsx
import { Alert, Badge, Card, Col, Row } from 'react-bootstrap';
import { formatPPM, getPpmGrade } from '../../utils/spcAnalysis';
import type { ProcessCapability } from '../../types';

interface ProcessCapabilityCardProps {
    processCapability?: ProcessCapability | null;
    statsItem: string;
}

/** 四象限狀態（AIAG-VDA 2026 圖 9-26）：穩定性 × 指數達標 */
const quadrantBadge = (pc: ProcessCapability) => {
    const stable = pc.stability_stable;
    const ok = pc.achieved;
    if (stable === true && ok) return { text: 'I：具能力且穩定', bg: '#d4edda', color: '#155724' };
    if (stable === true && !ok) return { text: 'III：無能力但穩定', bg: '#fff3cd', color: '#856404' };
    if (stable === false && ok) return { text: 'II：具績效但不穩定', bg: '#fff3cd', color: '#856404' };
    if (stable === false && !ok) return { text: 'IV：無績效且不穩定', bg: '#f8d7da', color: '#721c24' };
    return { text: '穩定性無法驗證', bg: '#e9ecef', color: '#6c757d' };
};

const ProcessCapabilityCard = ({ processCapability, statsItem }: ProcessCapabilityCardProps) => {
    const pc = processCapability;
    if (!pc?.available) {
        return (
            <Card className="mb-4" style={{ border: '2px solid #dee2e6' }}>
                <Card.Body>
                    <h5 className="mb-3">製程能力指標</h5>
                    {pc?.reason === 'insufficient_data' ? (
                        <Alert variant="warning" className="mb-0">
                            <i className="bi bi-exclamation-triangle me-2"></i>
                            資料筆數不足 — 「<strong>{statsItem}</strong>」僅有 <strong>{pc.valid_count ?? 0}</strong> 筆有效數據，
                            需要至少 <strong>5 筆</strong>才能進行分析。
                        </Alert>
                    ) : (
                        <Alert variant="info" className="mb-0">
                            <i className="bi bi-info-circle me-2"></i>
                            無法計算指數 — 需要在<strong>公差管理</strong>中設定「<strong>{statsItem}</strong>」的規格界限。
                        </Alert>
                    )}
                </Card.Body>
            </Card>
        );
    }

    const isCapability = pc.applicable === 'capability';
    const method = pc.method ?? 'G';
    const oneSided = pc.one_sided;
    // 依適用族取值：能力(C) 或 績效(P)
    const pkValue = isCapability ? pc.cpk : pc.ppk;
    const pValue = isCapability ? pc.cp : pc.pp;
    const pkLabel = `${isCapability ? 'Cpk' : 'Ppk'}.${method}`;
    const pLabel = `${isCapability ? 'Cp' : 'Pp'}.${method}`;
    const targets = pc.targets;
    const ppmData = pc.ppm || null;
    const ppmGrade = ppmData ? getPpmGrade(ppmData.total) : null;
    const quad = quadrantBadge(pc);

    return (
        <Card className="mb-4" style={{ border: '2px solid #dee2e6' }}>
            <Card.Body>
                <div className="d-flex align-items-center gap-2 mb-3 flex-wrap">
                    <h5 className="mb-0">製程{isCapability ? '能力' : '績效'}指標</h5>
                    <Badge style={{ backgroundColor: quad.bg, color: quad.color }}>{quad.text}</Badge>
                    {pc.stability_stable === true && <Badge bg="success">穩定（統計受控）→ 能力指數</Badge>}
                    {pc.stability_stable === false && <Badge bg="warning" text="dark">不穩定 → 僅報告績效指數</Badge>}
                    {pc.preliminary && <Badge bg="secondary">初步值（樣本數未達 n≥125 / k≥25）</Badge>}
                </div>
                {oneSided && (
                    <Alert variant="info" className="py-1 px-2 mb-2 small">
                        單側{oneSided === 'lower' ? '下限' : '上限'}規格：僅計算對應側指數（AIAG-VDA §6.8.2.2）
                    </Alert>
                )}
                <Row className="text-center">
                    {!oneSided && (
                        <Col>
                            <div className="text-muted small">{pLabel}</div>
                            <div className="h4">{pValue?.toFixed(3) ?? 'N/A'}</div>
                            <div className="text-muted small">目標 ≥ {targets?.p_target?.toFixed(2) ?? '—'}</div>
                        </Col>
                    )}
                    <Col>
                        <div className="text-muted small">{pkLabel}</div>
                        <div className="h3 mb-1">{pkValue?.toFixed(3) ?? 'N/A'}</div>
                        {targets && pkValue != null && (
                            <Badge bg={pc.achieved ? 'success' : 'danger'}>
                                {pc.achieved ? '達標' : '未達標'}（目標 ≥ {targets.pk_target.toFixed(2)}）
                            </Badge>
                        )}
                    </Col>
                    <Col>
                        <div className="text-muted small">特性重要度</div>
                        <div className="h5">{targets?.class ?? '其他'}</div>
                        {targets?.adjusted && (
                            <div className="text-muted small">目標值已依樣本數上修（{targets.confidence}）</div>
                        )}
                        {targets?.insufficient_sample && (
                            <div className="text-danger small">樣本 &lt; 75，結果僅供參考</div>
                        )}
                    </Col>
                    <Col>
                        <div className="text-muted small">Cwk（組內參考）</div>
                        <div className="h5">{pc.cwk?.toFixed(3) ?? '—'}</div>
                    </Col>
                    <Col>
                        <div className="text-muted small">USL</div>
                        <div className="h5" style={{ color: '#e83e8c' }}>{pc.usl != null ? pc.usl.toFixed(3) : '—'}</div>
                    </Col>
                    <Col>
                        <div className="text-muted small">LSL</div>
                        <div className="h5" style={{ color: '#e83e8c' }}>{pc.lsl != null ? pc.lsl.toFixed(3) : '—'}</div>
                    </Col>
                </Row>

                {ppmData && (
                    <div className="mt-3 pt-3 border-top">
                        <Row className="text-center align-items-center">
                            <Col xs="auto"><strong>PPM 不良率估算</strong></Col>
                            <Col><span className="text-muted small me-1">超上限</span><strong>{formatPPM(ppmData.upper)}</strong></Col>
                            <Col><span className="text-muted small me-1">超下限</span><strong>{formatPPM(ppmData.lower)}</strong></Col>
                            <Col>
                                <span className="text-muted small me-1">總計</span>
                                <strong className="h5 mb-0">{formatPPM(ppmData.total)}</strong>
                                <span className="text-muted small ms-1">PPM</span>
                            </Col>
                            {ppmGrade && (
                                <Col xs="auto">
                                    <Badge style={{ backgroundColor: ppmGrade.bgColor, color: ppmGrade.color, fontSize: '0.8rem' }}>
                                        {ppmGrade.label}
                                    </Badge>
                                </Col>
                            )}
                        </Row>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
};

export default ProcessCapabilityCard;
```

注意：元件內部 `ProcessCapability` 改用 `types` 的共用型別（原本檔內自定義的 interface 刪除）；`getCpkGrade` 不再由本元件使用，但 `spcAnalysis.ts` 中保留（Excel 報告與其他呼叫處 Phase 4 才處理）。

- [ ] **Step 4: 執行測試與既有測試**

Run: `cd src_frontend && npx vitest run src/components/patrol/ProcessCapabilityCard.test.tsx src/components/spc/SpcDashboardPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/patrol/ProcessCapabilityCard.tsx src_frontend/src/components/patrol/ProcessCapabilityCard.test.tsx
git commit -m "前端:能力卡片改版-穩定性決定指數/四象限/目標值達標(2026手冊)"
```

---

### Task 12: 公差表單特性重要度欄位

**Files:**
- Modify: `src_frontend/src/components/tolerance/toleranceFormUtils.ts`
- Modify: `src_frontend/src/components/tolerance/ToleranceDetailTable.tsx`
- Modify: `src_frontend/src/hooks/useTolerance.ts`（ToleranceDetailItem 型別）
- Modify: `src_frontend/src/types/tolerance.ts`（ToleranceCreateInput details 型別）
- Test: `src_frontend/src/components/tolerance/toleranceFormUtils.test.ts`（追加）

- [ ] **Step 1: 寫失敗測試（追加）**

```typescript
// 追加至 toleranceFormUtils.test.ts
import { buildTolerancePayload, createToleranceDetailRow, mapToleranceDetailToRow } from './toleranceFormUtils';

it('特性重要度預設為其他且可往返', () => {
  const row = createToleranceDetailRow('r1');
  expect(row.charClass).toBe('其他');

  const mapped = mapToleranceDetailToRow(
    { 測量項目: '外徑', 特性重要度: '關鍵' } as never, 'r2');
  expect(mapped.charClass).toBe('關鍵');

  const payload = buildTolerancePayload({
    date: '2026-07-17', material: 'M', spec: 'S', vendorId: '', remark: '',
    details: [{ ...row, item: '外徑', charClass: '主要' }],
  });
  expect(payload.details[0].特性重要度).toBe('主要');
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run src/components/tolerance/toleranceFormUtils.test.ts`
Expected: FAIL

- [ ] **Step 3: 實作**

`toleranceFormUtils.ts`：
- `ToleranceDetailRow` 加 `charClass: string;`
- `createToleranceDetailRow` 加 `charClass: '其他',`
- `mapToleranceDetailToRow` 加 `charClass: detail.特性重要度 ?? '其他',`
- `buildTolerancePayload` 的 map 中加 `特性重要度: detail.charClass || '其他',`

`useTolerance.ts` 的 `ToleranceDetailItem` 加 `特性重要度?: string;`；`types/tolerance.ts` 的 `ToleranceCreateInput` details 項目型別加 `特性重要度?: string;`（以 `grep -n "ToleranceCreateInput" src_frontend/src/types/tolerance.ts` 定位）。

`ToleranceDetailTable.tsx`：
- 表頭（第 121 行「標準值」之後）加 `<th style={{ width: '9%' }}>特性重要度</th>`
- `SortableRow`（第 59 行 std 欄之後）加：

```tsx
            <td>
                <Form.Select size="sm" value={detail.charClass}
                    onChange={e => onChange(index, 'charClass', e.target.value)}>
                    <option value="關鍵">關鍵</option>
                    <option value="主要">主要</option>
                    <option value="次要">次要</option>
                    <option value="其他">其他</option>
                </Form.Select>
            </td>
```

- 擠壓公差對應元件：以 `grep -rn "測量項目" src_frontend/src/components/extrusion-tolerance/` 找到明細表格，做相同的欄位新增（select + payload key `特性重要度`）。

- [ ] **Step 4: 執行測試與建置**

Run: `cd src_frontend && npx vitest run src/components/tolerance/ && npx tsc -b --noEmit`
Expected: PASS、無型別錯誤

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/tolerance/ src_frontend/src/components/extrusion-tolerance/ src_frontend/src/hooks/useTolerance.ts src_frontend/src/types/tolerance.ts
git commit -m "前端:公差明細新增特性重要度選單"
```

---

### Task 13: 離群值管理 Modal

**Files:**
- Create: `src_frontend/src/components/spc/OutlierManagerModal.tsx`
- Modify: `src_frontend/src/hooks/useShipping.ts`（新增兩個 hooks）
- Modify: `src_frontend/src/components/shipping/ShippingCharts.tsx`（掛入 modal）

- [ ] **Step 1: hooks**

`useShipping.ts` 追加（對照檔內既有 useQuery/useMutation 寫法與 `api` 實例）：

```typescript
export interface ShippingMeasurementItem {
  識別碼: number;
  組別: number;
  量測項目: string;
  測量位置: string;
  量測值: number | null;
  量測最小值: number | null;
  量測最大值: number | null;
  排除統計: boolean;
  排除原因: string | null;
}

export const useShippingMeasurements = (shippingId: number | null) =>
  useQuery<ShippingMeasurementItem[]>({
    queryKey: ['shipping-measurements', shippingId],
    queryFn: async () => (await api.get(`/data/${shippingId}/measurements`)).data,
    enabled: shippingId != null,
  });

export const useSetMeasurementExclusion = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (p: { id: number; excluded: boolean; reason: string }) =>
      (await api.patch(`/measurements/${p.id}/exclusion`, { 排除統計: p.excluded, 排除原因: p.reason })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shipping-measurements'] });
      queryClient.invalidateQueries({ queryKey: ['shipping-stats'] });
    },
  });
};
```

（`api` 路徑前綴依檔內既有寫法：若既有呼叫是 `api.get('/api/stats', ...)` 形式則同樣加 `/api` 前綴。queryKey `'shipping-stats'` 以檔內 `useShippingStats` 實際 key 為準。）

- [ ] **Step 2: Modal 元件**

```tsx
// src_frontend/src/components/spc/OutlierManagerModal.tsx
import { useState } from 'react';
import { Alert, Badge, Button, Form, Modal, Table } from 'react-bootstrap';
import { useSetMeasurementExclusion, useShippingMeasurements } from '../../hooks/useShipping';

interface OutlierManagerModalProps {
  shippingId: number | null;
  show: boolean;
  onHide: () => void;
}

/** 離群值管理（AIAG-VDA 2026 §6.6）：標示無效、保留追溯、排除統計，不得刪除 */
const OutlierManagerModal = ({ shippingId, show, onHide }: OutlierManagerModalProps) => {
  const { data: measurements = [], isLoading } = useShippingMeasurements(show ? shippingId : null);
  const setExclusion = useSetMeasurementExclusion();
  const [reasons, setReasons] = useState<Record<number, string>>({});

  const toggle = (id: number, currentlyExcluded: boolean) => {
    const reason = reasons[id] ?? '';
    if (!currentlyExcluded && !reason.trim()) return; // 標示離群必填原因
    setExclusion.mutate({ id, excluded: !currentlyExcluded, reason });
  };

  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>離群值管理（記錄 #{shippingId}）</Modal.Title>
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
              {measurements.map(m => (
                <tr key={m.識別碼} className={m.排除統計 ? 'table-secondary' : ''}>
                  <td>{m.量測項目}</td>
                  <td className="text-center">{m.組別}</td>
                  <td className="text-center">{m.測量位置 || '—'}</td>
                  <td className="text-center">
                    {m.量測值 ?? (m.量測最小值 != null ? `${m.量測最小值} / ${m.量測最大值}` : '—')}
                  </td>
                  <td className="text-center">
                    {m.排除統計
                      ? <Badge bg="secondary">已排除</Badge>
                      : <Badge bg="success">計入統計</Badge>}
                  </td>
                  <td>
                    {m.排除統計 ? (m.排除原因 || '') : (
                      <Form.Control size="sm" placeholder="離群原因（必填）"
                        value={reasons[m.識別碼] ?? ''}
                        onChange={e => setReasons(prev => ({ ...prev, [m.識別碼]: e.target.value }))} />
                    )}
                  </td>
                  <td className="text-center">
                    <Button size="sm"
                      variant={m.排除統計 ? 'outline-success' : 'outline-danger'}
                      disabled={setExclusion.isPending || (!m.排除統計 && !(reasons[m.識別碼] ?? '').trim())}
                      onClick={() => toggle(m.識別碼, m.排除統計)}>
                      {m.排除統計 ? '恢復計入' : '標示離群'}
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

export default OutlierManagerModal;
```

- [ ] **Step 3: 掛入 ShippingCharts**

`ShippingCharts.tsx`：
- 新增 state：`const [outlierTargetId, setOutlierTargetId] = useState<number | null>(null);`
- `SpcDashboardPanel` 的 `onEditPoint` 呼叫處旁（以 `grep -n "onEditPoint" src_frontend/src/components/shipping/ShippingCharts.tsx` 定位其 JSX），在面板下方渲染：

```tsx
            <OutlierManagerModal
                shippingId={outlierTargetId}
                show={outlierTargetId != null}
                onHide={() => setOutlierTargetId(null)}
            />
```

- 在匯出報告按鈕旁新增入口按鈕（點選管制圖點後可開啟）：`SpcDashboardPanel` 傳入的 `onEditPoint` 保持原行為；另加一顆按鈕「離群值管理」開啟 modal，內容輸入框讓使用者輸入記錄 ID，或（較佳）在 `onEditPoint` handler 中同時 `setOutlierTargetId(id)`——實作時擇一，建議：管制圖點擊 → 先開既有編輯，另在 WecoViolationAlert 列表旁提供「管理離群值」按鈕。最簡實作：`onEditPoint={(id) => setOutlierTargetId(id)}` 若既有 onPointClick 已被編輯功能占用，則在圖表工具列加按鈕 + 目前選取點 ID。

- [ ] **Step 4: 驗證**

Run: `cd src_frontend && npx tsc -b --noEmit && npm run lint`
Expected: 通過

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/spc/OutlierManagerModal.tsx src_frontend/src/hooks/useShipping.ts src_frontend/src/components/shipping/ShippingCharts.tsx
git commit -m "前端:離群值管理Modal(標示/恢復/原因必填)"
```

---

## Phase 4 — P1

### Task 14: 分布評估模組 `spc_distribution.py`

**Files:**
- Create: `backend/services/spc_distribution.py`
- Test: `backend/tests/test_services/test_spc_distribution.py`

- [ ] **Step 1: 寫失敗測試**

```python
# backend/tests/test_services/test_spc_distribution.py
import numpy as np
import pytest

from backend.services.spc_distribution import assess_distribution, dist_quantiles, tail_ppm


def test_normal_data_detected_as_normal():
    rng = np.random.default_rng(42)
    values = rng.normal(10, 0.5, 300).tolist()
    d = assess_distribution(values)
    assert d["model"] == "normal"
    assert d["normal_ok"] is True


def test_shape_field_uses_folded_normal():
    rng = np.random.default_rng(42)
    values = np.abs(rng.normal(0, 0.02, 300)).tolist()
    d = assess_distribution(values, field="真圓度")
    assert d["model"] == "folded_normal"


def test_quantiles_are_ordered():
    rng = np.random.default_rng(1)
    values = rng.normal(10, 0.5, 300).tolist()
    d = assess_distribution(values)
    q_lo, q_mid, q_hi = dist_quantiles(d)
    assert q_lo < q_mid < q_hi
    # 常態下位數應接近平均
    assert q_mid == pytest.approx(10, abs=0.2)


def test_tail_ppm_reflects_spec_distance():
    rng = np.random.default_rng(7)
    values = rng.normal(10, 0.5, 500).tolist()
    d = assess_distribution(values)
    near = tail_ppm(d, usl=10.5, lsl=9.5)
    far = tail_ppm(d, usl=13, lsl=7)
    assert near["total"] > far["total"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_spc_distribution.py -v`
Expected: FAIL（module not found）

- [ ] **Step 3: 實作模組**

```python
# backend/services/spc_distribution.py
"""統計分布評估 — AIAG-VDA SPC 2026 §6.8.1

- 形狀公差特性（圓度/同心度/直度等）理論分布為摺疊常態（§6.8.1）
- 其他特性以 Anderson-Darling 檢定常態性；非常態時擇一擬合分布
- 供 G 法（分位數法）指數計算與依分布之 PPM 估算（§6.8.2.1/6.8.2.3）
"""
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

# 自然下界為 0 的形狀公差特性
SHAPE_FIELDS = {"同心度", "真圓度", "真直度", "圓度", "平面度", "直線度"}

MODEL_LABELS = {
    "normal": "常態分布",
    "folded_normal": "摺疊常態分布（形狀公差）",
    "lognormal": "對數常態分布",
}


def assess_distribution(all_values: List[float], field: Optional[str] = None) -> Dict[str, Any]:
    """評估適當的分布模型並擬合參數。"""
    arr = np.asarray(all_values, dtype=float)
    result: Dict[str, Any] = {
        "model": "normal",
        "label": MODEL_LABELS["normal"],
        "params": (float(np.mean(arr)) if arr.size else 0.0,
                   float(np.std(arr, ddof=1)) if arr.size >= 2 else 0.0),
        "ad_stat": None,
        "normal_ok": True,
        "n": int(arr.size),
    }
    if arr.size < 20 or float(np.std(arr, ddof=1)) == 0:
        return result  # 樣本太少：以常態近似，不做檢定

    # 形狀公差：直接採摺疊常態（§6.8.1 理論分布），不看 AD 檢定
    if field in SHAPE_FIELDS:
        c, loc, scale = scipy_stats.foldnorm.fit(arr, floc=0)
        result.update({
            "model": "folded_normal",
            "label": MODEL_LABELS["folded_normal"],
            "params": (float(c), 0.0, float(scale)),
            "normal_ok": False,
        })
        return result

    ad = scipy_stats.anderson(arr, dist="norm")
    result["ad_stat"] = float(ad.statistic)
    # 臨界值索引 2 對應顯著水準 5%
    normal_ok = ad.statistic < ad.critical_values[2]
    result["normal_ok"] = bool(normal_ok)
    if normal_ok:
        return result

    # 非常態：正值資料嘗試對數常態，以對數概似擇優；否則維持常態近似並標示
    if np.all(arr > 0):
        s, loc, scale = scipy_stats.lognorm.fit(arr, floc=0)
        ll_lognorm = float(np.sum(scipy_stats.lognorm.logpdf(arr, s, loc, scale)))
        mu, sd = float(np.mean(arr)), float(np.std(arr, ddof=1))
        ll_norm = float(np.sum(scipy_stats.norm.logpdf(arr, mu, sd)))
        if ll_lognorm > ll_norm:
            result.update({
                "model": "lognormal",
                "label": MODEL_LABELS["lognormal"],
                "params": (float(s), float(loc), float(scale)),
            })
    return result


def _frozen(dist: Dict[str, Any]):
    model = dist["model"]
    p = dist["params"]
    if model == "folded_normal":
        return scipy_stats.foldnorm(p[0], loc=p[1], scale=p[2])
    if model == "lognormal":
        return scipy_stats.lognorm(p[0], loc=p[1], scale=p[2])
    return scipy_stats.norm(p[0], p[1])


def dist_quantiles(dist: Dict[str, Any]):
    """回傳 G 法所需分位數 (X0.135%, X50%, X99.865%)（§6.8.2.1）"""
    f = _frozen(dist)
    return float(f.ppf(0.00135)), float(f.ppf(0.5)), float(f.ppf(0.99865))


def tail_ppm(dist: Dict[str, Any], usl: Optional[float], lsl: Optional[float]) -> Dict[str, float]:
    """依擬合分布估算超規 PPM（§6.8.2.3 Z 法：OOS 比例）"""
    f = _frozen(dist)
    upper = float(f.sf(usl) * 1_000_000) if usl is not None else 0.0
    lower = float(f.cdf(lsl) * 1_000_000) if lsl is not None else 0.0
    return {"upper": round(upper, 1), "lower": round(lower, 1), "total": round(upper + lower, 1)}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_spc_distribution.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/spc_distribution.py backend/tests/test_services/test_spc_distribution.py
git commit -m "SPC:新增分布評估模組(AD檢定/摺疊常態/對數常態,G法分位數)"
```

---

### Task 15: 分布整合進能力計算

**Files:**
- Modify: `backend/services/spc_analysis_service.py`（capability + distribution_stats）
- Modify: `backend/services/shipping_service.py`、`backend/services/patrol_service.py`（傳 field）
- Test: `backend/tests/test_services/test_spc_analysis_service.py`（追加）

- [ ] **Step 1: 寫失敗測試**

```python
def test_capability_uses_percentile_method_for_non_normal():
    import numpy as np
    rng = np.random.default_rng(3)
    values = np.abs(rng.normal(0, 0.01, 300)).tolist()  # 摺疊常態形狀資料
    avgs = [float(np.mean(values[i:i+5])) for i in range(0, 100, 5)]
    result = calculate_process_capability(
        avgs=avgs, all_values=values, r_cl=0.01, d2=2.326,
        tolerance_limits={"USL": 0.05, "LSL": 0, "one_sided": "upper"},
        field="真圓度",
    )
    assert result["distribution"]["model"] == "folded_normal"
    assert result["ppk"] is not None
    # G 法分位數：Ppk = (U − X50%) / (X99.865% − X50%)
    from backend.services.spc_distribution import assess_distribution, dist_quantiles
    d = assess_distribution(values, field="真圓度")
    q_lo, q_mid, q_hi = dist_quantiles(d)
    expected = (0.05 - q_mid) / (q_hi - q_mid)
    assert result["ppk"] == pytest.approx(expected, abs=0.01)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_spc_analysis_service.py -k percentile -v`
Expected: FAIL（unexpected keyword 'field'）

- [ ] **Step 3: 實作整合**

`spc_analysis_service.py`：
1. import 加 `from .spc_distribution import assess_distribution, dist_quantiles, tail_ppm`
2. `calculate_process_capability` 簽名追加 `field: Optional[str] = None`。
3. 在計算 `x_bar` 後加入分布評估，非常態時整體變異指數改用分位數公式：

```python
    dist = assess_distribution(all_values, field=field)
    process_capability_dist = {
        "model": dist["model"], "label": dist["label"],
        "normal_ok": dist["normal_ok"], "ad_stat": dist["ad_stat"],
    }
    use_percentile = dist["model"] != "normal"
    if use_percentile:
        q_lo, q_mid, q_hi = dist_quantiles(dist)
```

4. 整體變異指數區塊改為（取代 Task 4 的 `p_val/pu/pl/pk` 計算）：

```python
    p_val = pu = pl = pk = None
    if use_percentile and (q_hi - q_lo) > 0:
        # G 法分位數公式（§6.8.2.1）
        if one_sided == "lower":
            pl = (x_bar_med := q_mid, (q_mid - float(lsl)) / (q_mid - q_lo))[1] if (q_mid - q_lo) > 0 else None
            pk = pl
        elif one_sided == "upper":
            pu = (float(usl) - q_mid) / (q_hi - q_mid) if (q_hi - q_mid) > 0 else None
            pk = pu
        else:
            p_val = (float(usl) - float(lsl)) / (q_hi - q_lo)
            pu = (float(usl) - q_mid) / (q_hi - q_mid) if (q_hi - q_mid) > 0 else None
            pl = (q_mid - float(lsl)) / (q_mid - q_lo) if (q_mid - q_lo) > 0 else None
            pk = min(v for v in [pu, pl] if v is not None) if (pu or pl) else None
    elif sigma_overall > 0:
        # 常態：G 法退化公式（(U−L)/6s 等）
        ...(維持 Task 4 的常態計算不變)...
```

（實作時把 walrus 寫法展開為一般 if，保持可讀。）

5. PPM 區塊改為依分布：

```python
    ppm = tail_ppm(dist, usl=float(usl) if usl is not None else None,
                   lsl=float(lsl) if (lsl is not None and one_sided != "upper") else None)
```

6. 回傳 dict 加 `"distribution": process_capability_dist,`。
7. `calculate_distribution_stats` 追加 model 資訊：簽名加 `field: Optional[str] = None`，回傳 dict 追加：

```python
    dist = assess_distribution(all_values, field=field)
    return {
        "skewness": skewness, "kurtosis": kurtosis,
        "normality": normality, "normality_label": normality_label,
        "model": dist["model"], "model_label": dist["label"],
    }
```

8. 呼叫端：`shipping_service.py` 的 `calculate_process_capability(...)` 加 `field=field`、`calculate_distribution_stats(all_values)` 改 `calculate_distribution_stats(all_values, field=field)`；`patrol_service.py` 同（其變數名為 `item`）。

- [ ] **Step 4: 執行測試**

Run: `python -m pytest backend/tests/test_services/ -q`
Expected: 全 PASS

- [ ] **Step 5: 前端顯示分布模型**

`SpcDashboardPanel.tsx` 常態性檢查卡（88-106 行）在 Badge 前加一欄：

```tsx
              <Col><span className="text-muted small me-1">分布模型</span><strong>{distributionStats.model_label ?? '常態分布'}</strong></Col>
```

Run: `cd src_frontend && npx vitest run src/components/spc/SpcDashboardPanel.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/ backend/tests/test_services/ src_frontend/src/components/spc/SpcDashboardPanel.tsx
git commit -m "SPC:非常態分布改用G法分位數計算指數與PPM(§6.8.1/6.8.2)"
```

---

### Task 16: 失控準則前後端統一與可配置

**Files:**
- Modify: `src_frontend/src/utils/spcAnalysis.ts`（analyzeWECO 接受規則集）
- Modify: `src_frontend/src/utils/spcChartModel.ts`（使用後端 rules_used）
- Modify: `backend/services/spc_report.py:14-40`（改用 spc_stability）
- Test: `src_frontend/src/utils/spcChartModel.test.ts`（追加）

- [ ] **Step 1: 前端規則對映**

`spcAnalysis.ts` 的 `analyzeWECO` 簽名改為：

```typescript
// 後端規則 id → 前端規則實作對映；預設集與後端 DEFAULT_STABILITY_RULES 一致
export const DEFAULT_RULES = ['beyond_limits', 'run_9_same_side', 'trend_6'];

export function analyzeWECO(
  data: number[], cl: number, ucl: number, lcl: number, labels: string[],
  enabledRules: string[] = DEFAULT_RULES,
): AnalyzedData {
```

函式內每條規則加上開關（規則 id 對映：Rule1=`beyond_limits`、Rule2=`run_9_same_side`、Rule3=`trend_6`、Rule4=`alternating_14`、Rule5=`two_of_three_beyond_2s`、Rule6=`four_of_five_beyond_1s`、Rule7=`fifteen_within_1s`、Rule8=`eight_beyond_1s_both`）：

```typescript
        if (enabledRules.includes('beyond_limits') && (val > ucl || val < lcl)) reasons.push("Rule 1: 超出控制限");
        if (enabledRules.includes('run_9_same_side') && i >= 8) { ...原 Rule 2 內容... }
        if (enabledRules.includes('trend_6') && i >= 5) { ...原 Rule 3 內容... }
        if (enabledRules.includes('alternating_14') && i >= 13) { ...原 Rule 4 內容... }
        if (enabledRules.includes('two_of_three_beyond_2s') && i >= 2) { ...原 Rule 5 內容... }
        if (enabledRules.includes('four_of_five_beyond_1s') && i >= 4) { ...原 Rule 6 內容... }
        if (enabledRules.includes('fifteen_within_1s') && i >= 14) { ...原 Rule 7 內容... }
        if (enabledRules.includes('eight_beyond_1s_both') && i >= 7) { ...原 Rule 8 內容... }
```

`spcChartModel.ts` 第 74 行改為：

```typescript
  const wecoRaw = analyzeWECO(
    data.avgs, data.x_cl, data.x_ucl, data.x_lcl, data.labels,
    data.stability?.rules_used,
  );
```

- [ ] **Step 2: 前端測試（追加至 spcChartModel.test.ts）**

```typescript
it('依後端 rules_used 限縮 WECO 規則', () => {
  const base = {
    labels: Array.from({ length: 9 }, (_, i) => `P${i}`),
    ids: [], dates: [], subgroup_sizes: [], all_values: [],
    avgs: Array(9).fill(10.1),           // 連續9點同側 → run_9_same_side
    ranges: Array(9).fill(0.2),
    x_cl: 10, x_ucl: 10.9, x_lcl: 9.1, r_cl: 0.2, r_ucl: 0.5, r_lcl: 0,
    avg_subgroup_size: 5,
    tolerance: { found: false }, process_capability: { available: false },
    distribution_stats: {}, cpk_trend: [],
  };
  const withRule = buildSpcChartModel({
    ...base,
    stability: { evaluated: true, stable: false, violations: [], rules_used: ['run_9_same_side'] },
  } as never);
  expect(withRule.analysis!.violations.length).toBeGreaterThan(0);

  const withoutRule = buildSpcChartModel({
    ...base,
    stability: { evaluated: true, stable: true, violations: [], rules_used: ['beyond_limits'] },
  } as never);
  expect(withoutRule.analysis!.violations.length).toBe(0);
});
```

Run: `cd src_frontend && npx vitest run src/utils/spcChartModel.test.ts`
Expected: PASS

- [ ] **Step 3: Excel 報告改用後端穩定性模組**

`spc_report.py` 頂部的自帶 3 條規則分析函式（14-40 行左右，`Rule 1/2/3` 那段）刪除，改 import：

```python
from .spc_stability import evaluate_stability, RULE_LABELS
```

原呼叫該函式產生 violations 的位置（以 `grep -n "Rule 1" backend/services/spc_report.py` 定位）改為：

```python
        stability = stats_data.get('stability') or evaluate_stability(
            stats_data.get('avgs', []),
            stats_data.get('x_cl', 0), stats_data.get('x_ucl', 0), stats_data.get('x_lcl', 0),
        )
        violations = [
            {"index": v["index"], "label": v["label"]}
            for v in stability.get("violations", [])
        ]
```

WECO 工作表欄位對應處同步調整（原欄位結構保留，reasons 改用 `v["label"]`）。

- [ ] **Step 4: 後端測試**

Run: `python -m pytest backend/tests -q -k "spc or shipping or patrol"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/utils/ backend/services/spc_report.py
git commit -m "SPC:失控準則前後端統一,依後端rules_used配置(§9.2.2.1)"
```

---

### Task 17: 管制圖規格線預設分離

**Files:**
- Modify: `src_frontend/src/utils/spcChartModel.ts:65, 190-195`
- Modify: `src_frontend/src/components/shipping/ShippingCharts.tsx:69`
- Modify: `src_frontend/src/components/patrol/PatrolCharts.tsx`（同樣呼叫處）
- Test: `src_frontend/src/utils/spcChartModel.test.ts`

- [ ] **Step 1: 寫失敗測試（追加）**

```typescript
it('預設不在管制圖疊規格界限，開啟選項才顯示', () => {
  const statsData = {
    labels: ['A', 'B', 'C', 'D', 'E'], ids: [], dates: [],
    avgs: [10, 10.1, 9.9, 10, 10.1], ranges: [0.2, 0.2, 0.2, 0.2, 0.2],
    subgroup_sizes: [], all_values: [],
    x_cl: 10, x_ucl: 10.9, x_lcl: 9.1, r_cl: 0.2, r_ucl: 0.5, r_lcl: 0,
    avg_subgroup_size: 5, tolerance: { found: true },
    process_capability: { available: true, usl: 11, lsl: 9 },
    distribution_stats: {}, cpk_trend: [],
  } as never;

  const hidden = buildSpcChartModel(statsData);
  expect(hidden.chartData!.xBar.datasets.some(d => d.label === 'USL')).toBe(false);

  const shown = buildSpcChartModel(statsData, { showSpecLimits: true });
  expect(shown.chartData!.xBar.datasets.some(d => d.label === 'USL')).toBe(true);
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run src/utils/spcChartModel.test.ts`
Expected: 新測試 FAIL

- [ ] **Step 3: 實作**

`spcChartModel.ts`：

```typescript
export interface SpcChartModelOptions {
  /** §9.3.1：現場管制圖不應顯示規格界限，預設 false，分析情境可開啟 */
  showSpecLimits?: boolean;
}

export const buildSpcChartModel = (
  statsData: SpcChartData | null | undefined,
  options: SpcChartModelOptions = {},
): SpcChartModel => {
```

第 190 行條件改為：

```typescript
  if (options.showSpecLimits && pc?.available && pc.usl != null && pc.lsl != null) {
```

`ShippingCharts.tsx`：加 state 與切換，並把圖例中「USL/LSL 規格限」項與 SpcDashboardPanel 的顯示連動：

```tsx
    const [showSpecLimits, setShowSpecLimits] = useState(false);
    const spcModel = useMemo(
        () => buildSpcChartModel(statsData as SpcChartData | null | undefined, { showSpecLimits }),
        [statsData, showSpecLimits]
    );
```

在檢驗項目選單旁 JSX 加：

```tsx
                <Form.Check type="switch" id="show-spec-limits" className="ms-3"
                    label="疊加規格界限（分析模式）"
                    checked={showSpecLimits}
                    onChange={e => setShowSpecLimits(e.target.checked)} />
```

`PatrolCharts.tsx`：以 `grep -n "buildSpcChartModel" src_frontend/src/components/patrol/PatrolCharts.tsx` 找到相同呼叫，做同樣修改。

`spcChartModel.test.ts` 既有測試若斷言 USL 資料集存在，改為傳 `{ showSpecLimits: true }`。

- [ ] **Step 4: 執行測試**

Run: `cd src_frontend && npx vitest run && npx tsc -b --noEmit`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/utils/spcChartModel.ts src_frontend/src/components/
git commit -m "前端:管制圖預設不顯示規格界限,新增分析模式切換(§9.3.1)"
```

---

### Task 18: Excel 報告補要素

**Files:**
- Modify: `backend/services/spc_report.py`（統計摘要工作表）
- Test: 手動驗證匯出

- [ ] **Step 1: 新增「研究資訊」區塊**

在統計摘要工作表「管制界限」區塊之前（`spc_report.py` 第 144 行 `ws[f'A{row}'] = "管制界限"` 之前）插入，沿用檔內既有的 row/樣式寫法：

```python
        # --- 研究資訊（AIAG-VDA 2026 §11.2 報告要素）---
        ws[f'A{row}'] = "研究資訊（AIAG-VDA SPC 2026）"
        ws[f'A{row}'].font = Font(bold=True, size=12)
        row += 1
        stability = stats_data.get('stability') or {}
        pc = stats_data.get('process_capability') or {}
        targets = pc.get('targets') or {}
        dist_info = pc.get('distribution') or {}
        applicable = pc.get('applicable')
        study_items = [
            ("研究類型", "持續製程監控（回顧式管制圖）"),
            ("適用指數", "能力 Cp/Cpk（穩定）" if applicable == "capability"
                        else "績效 Pp/Ppk（不穩定或穩定性未證明）"),
            ("計算方法", f"{pc.get('method', 'G')} 法（分位數法；常態時等同 6s 公式）"),
            ("分布模型", dist_info.get('label', '常態分布')),
            ("穩定性判定", "穩定（統計受控）" if stability.get('stable')
                          else ("不穩定" if stability.get('stable') is False else "無法評估")),
            ("使用之穩定性準則", "、".join(stability.get('rules_used', [])) or "—"),
            ("特性重要度", targets.get('class', '其他')),
            ("Ppk/Cpk 目標值", targets.get('pk_target')),
            ("目標值樣本數調整", f"已依樣本數上修（{targets.get('confidence','95%')}）" if targets.get('adjusted') else "無"),
            ("樣本數(個別值)", len(stats_data.get('all_values', []))),
            ("子組數", len(stats_data.get('avgs', []))),
            ("排除之離群值筆數", stats_data.get('excluded_count', 0)),
            ("初步值註記", "是（n<125 或子組<25）" if pc.get('preliminary') else "否"),
        ]
        for name, value in study_items:
            ws[f'A{row}'] = name
            ws[f'B{row}'] = value if value is not None else 'N/A'
            row += 1
        row += 1
```

（`Font` 已在檔內 import；若無則補 `from openpyxl.styles import Font`。）

- [ ] **Step 2: 指標名稱區塊調整**

原 205-212 行的指標清單改為（Cp/Cpk 缺值時顯示說明而非 N/A）：

```python
            capability_items = [
                (f"Pp.{pc.get('method','G')} (製程績效)", pc.get('pp')),
                (f"Ppk.{pc.get('method','G')} (修正製程績效)", pc.get('ppk')),
                (f"Cp.{pc.get('method','G')} (製程能力,僅穩定時)", pc.get('cp') if pc.get('cp') is not None else '不適用(未證明穩定)'),
                (f"Cpk.{pc.get('method','G')} (修正製程能力,僅穩定時)", pc.get('cpk') if pc.get('cpk') is not None else '不適用(未證明穩定)'),
                ("Cw (組內能力參考)", pc.get('cw')),
                ("Cwk (組內能力參考)", pc.get('cwk')),
                ("σ_overall (整體標準差)", pc.get('sigma_overall')),
                ("σ_within (組內標準差)", pc.get('sigma_within')),
            ]
```

分級 `get_cpk_grade`（190-233 行）改為與目標值比較：達標(綠)/未達標(紅)，比較對象 `pc.get('ppk') if applicable=='performance' else pc.get('cpk')` vs `targets.get('pk_target')`。結論區（278-300 行）同樣以目標值取代固定 1.67/1.33/1.0 門檻：

```python
            pk_val = pc.get('cpk') if applicable == 'capability' else pc.get('ppk')
            pk_target = targets.get('pk_target', 1.33)
            if pk_val is not None:
                if pk_val >= pk_target:
                    conclusion_lines.append(f"✅ 指數 {pk_val} 達到特性重要度「{targets.get('class','其他')}」目標值 {pk_target}。")
                    conclusion_lines.append("建議：維持現有製程管控。")
                else:
                    conclusion_lines.append(f"❌ 指數 {pk_val} 未達目標值 {pk_target}，需啟動改善（OCAP/根本原因分析）。")
            if stability.get('stable') is False:
                conclusion_lines.append("⚠️ 製程未通過穩定性準則，僅能報告績效指數 Pp/Ppk；請先消除特殊原因後重新評估能力。")
```

- [ ] **Step 3: 手動驗證**

啟動後端後：

Run: `curl -s -o /tmp/spc.xlsx -w "%{http_code}" "http://localhost:5001/api/spc-report?field=外徑" -H "Authorization: Bearer <dev token>"`
Expected: `200`，開啟 xlsx 確認「研究資訊」區塊存在。（或以既有匯出測試 `python -m pytest backend/tests/test_services/test_shipping_export_utils.py -q` 確認未破壞。）

- [ ] **Step 4: Commit**

```bash
git add backend/services/spc_report.py
git commit -m "Excel報告:補研究資訊/方法標示/目標值結論(§11.2)"
```

---

## Phase 5 — P2

### Task 19: 管制界限凍結與重算

**Files:**
- Create: `backend/migration/34_create_spc_control_limits.sql`
- Modify: `backend/models.py`（新 model）
- Modify: `backend/services/shipping_service.py`（get_stats 套用凍結界限 + 凍結服務）
- Modify: `backend/routes/shipping.py`（3 個端點）
- Modify: `src_frontend/src/components/shipping/ShippingCharts.tsx` + `src_frontend/src/hooks/useShipping.ts`
- Test: `backend/tests/test_services/test_spc_control_limits.py`

- [ ] **Step 1: Migration**

```sql
-- backend/migration/34_create_spc_control_limits.sql
-- §9.4：管制界限經確認後凍結；預期變更或無法歸因時重算並留紀錄
CREATE TABLE IF NOT EXISTS "SPC管制界限" (
    "識別碼"   SERIAL PRIMARY KEY,
    "資料來源" VARCHAR(20)  NOT NULL DEFAULT 'shipping',
    "廠商"     VARCHAR(100) NOT NULL DEFAULT '',
    "材質"     VARCHAR(100) NOT NULL DEFAULT '',
    "規格"     VARCHAR(100) NOT NULL DEFAULT '',
    "量測項目" VARCHAR(30)  NOT NULL,
    "X中心線"  NUMERIC(14,6) NOT NULL,
    "X上限"    NUMERIC(14,6) NOT NULL,
    "X下限"    NUMERIC(14,6) NOT NULL,
    "R中心線"  NUMERIC(14,6) NOT NULL,
    "R上限"    NUMERIC(14,6) NOT NULL,
    "R下限"    NUMERIC(14,6) NOT NULL DEFAULT 0,
    "子組大小" INTEGER NOT NULL DEFAULT 5,
    "備註"     VARCHAR(200),
    "建立時間" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "更新時間" TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_spc_limits UNIQUE ("資料來源","廠商","材質","規格","量測項目")
);
```

Run: `psql -U postgres -d qa_database -f backend/migration/34_create_spc_control_limits.sql`

- [ ] **Step 2: Model（models.py，SPCCache 之後）**

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
    x_ucl      = db.Column('X上限', db.Numeric(14, 6), nullable=False)
    x_lcl      = db.Column('X下限', db.Numeric(14, 6), nullable=False)
    r_cl       = db.Column('R中心線', db.Numeric(14, 6), nullable=False)
    r_ucl      = db.Column('R上限', db.Numeric(14, 6), nullable=False)
    r_lcl      = db.Column('R下限', db.Numeric(14, 6), nullable=False, default=0)
    avg_n      = db.Column('子組大小', db.Integer, nullable=False, default=5)
    note       = db.Column('備註', db.String(200))
    created_at = db.Column('建立時間', db.DateTime, default=utc_now)
    updated_at = db.Column('更新時間', db.DateTime, default=utc_now, onupdate=utc_now)
```

- [ ] **Step 3: 服務（TDD）**

測試 `backend/tests/test_services/test_spc_control_limits.py`（沿用既有 conftest 的 app/session fixture）：

```python
from backend.services.shipping_service import ShippingService


def test_freeze_and_apply_control_limits(session):
    key = {"vendor": "", "material": "MAT-X", "spec": "1*2*3", "field": "外徑"}
    limits = {"x_cl": 10.0, "x_ucl": 10.9, "x_lcl": 9.1,
              "r_cl": 0.4, "r_ucl": 0.85, "r_lcl": 0.0, "avg_n": 5}
    saved = ShippingService.freeze_control_limits(key, limits, note="基準期確認")
    assert saved["X中心線"] == 10.0

    found = ShippingService.get_frozen_limits(key)
    assert found is not None
    assert found["x_ucl"] == 10.9

    ShippingService.unfreeze_control_limits(key)
    assert ShippingService.get_frozen_limits(key) is None
```

實作（ShippingService 內）：

```python
    @staticmethod
    def _limits_key_filter(key: Dict[str, str]):
        from ..models import SpcControlLimit
        return SpcControlLimit.query.filter_by(
            source='shipping',
            vendor=key.get('vendor') or '',
            material=key.get('material') or '',
            spec=key.get('spec') or '',
            field=key['field'],
        )

    @staticmethod
    def get_frozen_limits(key: Dict[str, str]) -> Optional[Dict[str, float]]:
        rec = ShippingService._limits_key_filter(key).first()
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
        from ..models import SpcControlLimit
        rec = ShippingService._limits_key_filter(key).first()
        if rec is None:
            rec = SpcControlLimit(
                source='shipping',
                vendor=key.get('vendor') or '', material=key.get('material') or '',
                spec=key.get('spec') or '', field=key['field'],
            )
            db.session.add(rec)
        rec.x_cl, rec.x_ucl, rec.x_lcl = limits["x_cl"], limits["x_ucl"], limits["x_lcl"]
        rec.r_cl, rec.r_ucl, rec.r_lcl = limits["r_cl"], limits["r_ucl"], limits.get("r_lcl", 0)
        rec.avg_n = limits.get("avg_n", 5)
        rec.note = note
        db.session.commit()
        ShippingService._invalidate_spc_cache()
        return {"X中心線": float(rec.x_cl), "識別碼": rec.id}

    @staticmethod
    def unfreeze_control_limits(key: Dict[str, str]) -> None:
        ShippingService._limits_key_filter(key).delete()
        db.session.commit()
        ShippingService._invalidate_spc_cache()
```

`get_stats` 內套用（Task 5 Step 2 的統計計算段，`calculate_control_limits` 之後）：

```python
            frozen = ShippingService.get_frozen_limits({
                "vendor": vendor, "material": material, "spec": spec, "field": field,
            })
            limits_frozen = frozen is not None
            if limits_frozen:
                control_limits.update({k: frozen[k] for k in
                    ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl", "avg_n")})
```

`_result` 加 `"limits_frozen": limits_frozen,`（穩定性判定要在套用凍結界限「之後」執行，以凍結界限判定）。

路由（shipping.py）：

```python
@shipping_bp.route('/api/control-limits', methods=['GET', 'POST', 'DELETE'])
@auth_required
def spc_control_limits():
    """管制界限凍結管理（§9.4）：GET 查詢 / POST 以目前統計凍結 / DELETE 解除"""
    try:
        key = {
            "vendor": request.args.get('vendor', '') or (request.get_json(silent=True) or {}).get('vendor', ''),
            "material": request.args.get('material', '') or (request.get_json(silent=True) or {}).get('material', ''),
            "spec": request.args.get('spec', '') or (request.get_json(silent=True) or {}).get('spec', ''),
            "field": request.args.get('field') or (request.get_json(silent=True) or {}).get('field', '外徑'),
        }
        if request.method == 'GET':
            return jsonify(ShippingService.get_frozen_limits(key) or {})
        if request.method == 'POST':
            body = request.get_json(silent=True) or {}
            stats = ShippingService.get_stats({**key, "vendor": key["vendor"], "material": key["material"], "spec": key["spec"], "field": key["field"]})
            limits = {k: stats[k] for k in ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl")}
            limits["avg_n"] = stats.get("avg_subgroup_size", 5)
            return jsonify(ShippingService.freeze_control_limits(key, limits, note=body.get('note', '')))
        ShippingService.unfreeze_control_limits(key)
        return jsonify({"ok": True})
    except Exception as e:
        return api_error(str(e), 500)
```

- [ ] **Step 4: 前端**

`useShipping.ts` 加 `useFrozenLimits`（GET）與 `useFreezeLimits`/`useUnfreezeLimits`（mutation，成功後 invalidate `shipping-stats`）。`ShippingCharts.tsx` 工具列加兩顆按鈕與狀態 badge：

```tsx
                {statsData?.limits_frozen
                    ? <Badge bg="info" className="ms-2">管制界限已凍結</Badge>
                    : <Badge bg="light" text="dark" className="ms-2">界限逐次重算中</Badge>}
                <Button size="sm" variant="outline-primary" className="ms-2"
                    onClick={() => freezeLimits.mutate({ vendor, material, spec, field: statsField })}>
                    凍結目前界限
                </Button>
                <Button size="sm" variant="outline-secondary" className="ms-1"
                    onClick={() => unfreezeLimits.mutate({ vendor, material, spec, field: statsField })}>
                    解除凍結
                </Button>
```

`SpcChartData` 型別加 `limits_frozen?: boolean;`。

- [ ] **Step 5: 測試與 commit**

Run: `python -m pytest backend/tests/test_services/test_spc_control_limits.py -v && cd src_frontend && npx tsc -b --noEmit`
Expected: PASS

```bash
git add backend/ src_frontend/
git commit -m "SPC:管制界限凍結/解除與重算機制(§9.4,migration 34)"
```

---

### Task 20: V&V — 黃金資料集、參數透明文件、計算方法說明 UI

**Files:**
- Create: `backend/tests/test_services/test_spc_golden.py`
- Create: `docs/spc_validation.md`
- Create: `src_frontend/src/components/spc/SpcMethodologyModal.tsx`
- Modify: `src_frontend/src/components/spc/SpcDashboardPanel.tsx`（info 按鈕）

- [ ] **Step 1: 黃金資料集測試**

先執行產生腳本取得目前輸出（實作時把印出的數值貼進測試常數）：

```bash
python - <<'EOF'
import numpy as np
from backend.services.spc_analysis_service import (
    calculate_control_limits, calculate_process_capability)
from backend.services.spc_stability import evaluate_stability
rng = np.random.default_rng(2026)
subs = [sorted(rng.normal(10, 0.3, 5).tolist()) for _ in range(30)]
avgs = [float(np.mean(s)) for s in subs]
ranges = [float(max(s) - min(s)) for s in subs]
all_values = [v for s in subs for v in s]
cl = calculate_control_limits(avgs, ranges, [5]*30)
st = evaluate_stability(avgs, cl["x_cl"], cl["x_ucl"], cl["x_lcl"])
pc = calculate_process_capability(avgs, all_values, cl["r_cl"], cl["d2"],
    {"USL": 11, "LSL": 9}, stability=st, characteristic_class="主要")
print({k: cl[k] for k in ("x_cl","x_ucl","x_lcl","r_cl","r_ucl")})
print(st["stable"], pc["ppk"], pc["pp"], pc["cwk"], pc["ppm"]["total"], pc["targets"]["pk_target"])
EOF
```

測試檔（數值以上述輸出貼入）：

```python
# backend/tests/test_services/test_spc_golden.py
"""黃金資料集回歸測試 — §10.2 軟體確效：鎖定統計輸出防止未察覺的行為變更"""
import numpy as np
import pytest

from backend.services.spc_analysis_service import (
    calculate_control_limits, calculate_process_capability)
from backend.services.spc_stability import evaluate_stability


def _golden_dataset():
    rng = np.random.default_rng(2026)
    subs = [sorted(rng.normal(10, 0.3, 5).tolist()) for _ in range(30)]
    avgs = [float(np.mean(s)) for s in subs]
    ranges = [float(max(s) - min(s)) for s in subs]
    all_values = [v for s in subs for v in s]
    return avgs, ranges, all_values


def test_golden_dataset_outputs_are_stable():
    avgs, ranges, all_values = _golden_dataset()
    cl = calculate_control_limits(avgs, ranges, [5] * 30)
    st = evaluate_stability(avgs, cl["x_cl"], cl["x_ucl"], cl["x_lcl"])
    pc = calculate_process_capability(
        avgs, all_values, cl["r_cl"], cl["d2"],
        {"USL": 11, "LSL": 9}, stability=st, characteristic_class="主要")

    # ↓ 實作時以產生腳本的實際輸出取代下列期望值（pytest.approx, rel=1e-6）
    assert cl["x_cl"] == pytest.approx(<貼上>, rel=1e-6)
    assert cl["x_ucl"] == pytest.approx(<貼上>, rel=1e-6)
    assert cl["r_cl"] == pytest.approx(<貼上>, rel=1e-6)
    assert pc["ppk"] == pytest.approx(<貼上>, rel=1e-4)
    assert pc["pp"] == pytest.approx(<貼上>, rel=1e-4)
    assert pc["cwk"] == pytest.approx(<貼上>, rel=1e-4)
    assert pc["targets"]["pk_target"] == <貼上>
```

Run: `python -m pytest backend/tests/test_services/test_spc_golden.py -v` → PASS

- [ ] **Step 2: 參數透明文件**

```markdown
<!-- docs/spc_validation.md -->
# SPC 分析軟體確效文件（AIAG-VDA SPC 2026 §10.2）

本文件揭露系統 SPC 計算所用之全部參數與方法，供查證（verification）與確效（validation）。

## 計算參數
| 參數 | 值 | 依據 |
|---|---|---|
| 指數估計方法 | G 法（分位數法）；常態分布時退化為 (U−L)/6s | §6.8.2.1 |
| 位置/離散估計量 | 個別值算術平均 x̄；整體樣本標準差 s（ddof=1） | ISO 22514-2 |
| 組內變異估計 | R̄/d₂（僅用於 Cw/Cwk 參考值與 R 圖界限） | §6.2 |
| 能力 vs 績效命名 | 穩定性準則全數通過 → Cp/Cpk；否則 Pp/Ppk | §6.2、表 6-1 |
| 穩定性準則（預設） | 超出管制界限、連續9點同側、連續6點趨勢 | §9.2.2 |
| 最低計算門檻 | 5 個子組（不足時不計算，回報 insufficient_data） | 系統定義 |
| 建議樣本 | n≥125 個別值、k≥25 子組；不足時標示「初步值」並依表 8-4/8-5 上修目標值（預設信賴水準 95%） | 表 6-4、8-4/8-5 |
| 離群值處理 | 人工標示（必填原因）、保留追溯、排除於統計計算；系統不自動剔除 | §6.6 |
| 單側公差 | 只計算對應側 Ppk/Cpk；形狀公差（同心度/真圓度/真直度）自然下界 0，採單側上限 | §6.8.2.2 |
| 分布模型 | 形狀公差→摺疊常態；其他→AD 檢定（α=5%），非常態且全正→對數常態擇優 | §6.8.1 |
| PPM 估算 | 依擬合分布之尾端機率（Z 法概念） | §6.8.2.3 |
| 管制界限 | 基準期前 25 個子組；可凍結，凍結後沿用至解除 | §9.4 |

## 確效方式
- 單元測試：`backend/tests/test_services/test_spc_*.py`
- 黃金資料集回歸：`test_spc_golden.py`（鎖定輸出，變更計算需同步審查）
- 回歸腳本：`backend/scripts/spc_regression.py`
```

- [ ] **Step 3: 計算方法說明 Modal**

```tsx
// src_frontend/src/components/spc/SpcMethodologyModal.tsx
import { Modal, Table } from 'react-bootstrap';

interface SpcMethodologyModalProps { show: boolean; onHide: () => void; }

/** §10.2 參數透明化：讓使用者了解指數計算所用的方法與參數 */
const SpcMethodologyModal = ({ show, onHide }: SpcMethodologyModalProps) => (
  <Modal show={show} onHide={onHide} size="lg">
    <Modal.Header closeButton>
      <Modal.Title>SPC 計算方法說明（AIAG-VDA SPC 2026）</Modal.Title>
    </Modal.Header>
    <Modal.Body>
      <Table size="sm" bordered>
        <tbody>
          <tr><td>指數方法</td><td>G 法（分位數法）；常態分布時等同 (U−L)/6s。指數名稱後綴 .G 表示此方法。</td></tr>
          <tr><td>能力 vs 績效</td><td>穩定性準則全數通過 → 報告 Cp/Cpk（能力）；否則報告 Pp/Ppk（績效）。兩者公式相同，皆用整體標準差。</td></tr>
          <tr><td>穩定性準則</td><td>預設：超出管制界限、連續9點同側、連續6點趨勢（避免同時套用過多準則以控制誤警率）。</td></tr>
          <tr><td>目標值</td><td>依公差管理之「特性重要度」查表（關鍵 1.67 / 主要 1.33 / 次要與其他 1.00）；樣本數 &lt;125 時依 95% 信賴水準上修。</td></tr>
          <tr><td>離群值</td><td>僅由人工標示（必填原因），標示後排除於統計但保留於資料庫供追溯，不會刪除。</td></tr>
          <tr><td>單側公差</td><td>僅計算對應側指數；同心度/真圓度/真直度以 0 為自然下界、採單側上限。</td></tr>
          <tr><td>分布模型</td><td>形狀公差採摺疊常態；其他以 Anderson-Darling 檢定，非常態時擬合對數常態並以分位數法計算。</td></tr>
          <tr><td>PPM</td><td>依擬合分布之尾端機率估算（非常態時不再使用常態假設）。</td></tr>
          <tr><td>管制界限</td><td>預設以前 25 個子組為基準期；可於圖表工具列凍結/解除。</td></tr>
        </tbody>
      </Table>
      <div className="text-muted small">完整參數揭露見 docs/spc_validation.md（§10.2 軟體確效）。</div>
    </Modal.Body>
  </Modal>
);

export default SpcMethodologyModal;
```

`SpcDashboardPanel.tsx`：頂部加 state 與按鈕：

```tsx
  const [showMethodology, setShowMethodology] = useState(false);
```

在 `<WecoViolationAlert ...>` 上方（return 開頭）加：

```tsx
      <div className="text-end mb-2">
        <Button variant="outline-secondary" size="sm" onClick={() => setShowMethodology(true)}>
          <i className="bi bi-info-circle me-1"></i>計算方法說明
        </Button>
      </div>
      <SpcMethodologyModal show={showMethodology} onHide={() => setShowMethodology(false)} />
```

（import `useState`、`Button`、`SpcMethodologyModal`。）

- [ ] **Step 4: 驗證與 commit**

Run: `cd src_frontend && npx vitest run src/components/spc/ && npx tsc -b --noEmit`
Expected: PASS

```bash
git add backend/tests/test_services/test_spc_golden.py docs/spc_validation.md src_frontend/src/components/spc/
git commit -m "SPC:V&V黃金資料集/確效文件/計算方法說明UI(§10.2)"
```

---

### Task 21: 全面驗證

- [ ] **Step 1: 後端全量測試**

Run: `python -m pytest backend/tests -q`
Expected: 全 PASS

- [ ] **Step 2: 回歸腳本**

Run: `python backend/scripts/spc_regression.py`
Expected: 正常結束（若腳本斷言舊 Cpk 行為，依新規則更新其期望值並在輸出註明）

- [ ] **Step 3: 前端全量**

Run: `cd src_frontend && npm run build && npm run lint && npm test`
Expected: build/lint/test 全過

- [ ] **Step 4: 端對端手動驗證（開發環境）**

1. 啟動後端（venv）`cd backend && python app.py`、前端 `cd src_frontend && npm run dev`（注意 dev proxy 指向 :80 生產後端的問題——驗證時將 vite proxy 暫指 :5001 或直接以生產模式驗證）。
2. 出貨統計頁選「外徑」：確認卡片顯示 Pp/Ppk 或 Cp/Cpk 其一、四象限 badge、目標值達標、分布模型。
3. 選「真圓度」：確認單側上限提示與摺疊常態。
4. 標示一筆離群值 → 統計數字改變、excluded_count 增加、恢復後復原。
5. 凍結界限 → badge 顯示已凍結；解除 → 恢復。
6. 匯出 SPC Excel：確認研究資訊區塊。

- [ ] **Step 5: 最終 commit**

```bash
git add -A
git commit -m "AIAG-VDA SPC 2026合規改造完成:全面驗證通過"
```

---

## Self-Review 紀錄

- **規格覆蓋**：P0（穩定性→指數命名 Task 1/4/5/6、目標值 Task 2/8/11/12、單側 upper Task 4/5、離群值 Task 7/9/13）、P1（分布 Task 14/15、準則配置 Task 16、規格線 Task 17、報告 Task 18）、P2（界限凍結 Task 19、G/Z 標示 Task 11/18、V&V Task 20）——全數對應。
- **已知妥協**（實作時注意）：
  - 表 8-4/8-5 數值為掃描件轉錄，Task 2 註明需人工複核。
  - Task 8/9/13 有少數步驟依賴既有測試 fixture 與 hooks 慣例，указ明了以 grep 定位的具體位置與要插入的完整程式碼。
  - 巡檢（patrol）資料的離群值標記不在本計畫範圍（其量測儲存結構不同），已於 Task 9 僅實作出貨模組；若需要巡檢版可另開計畫。
- **型別一致性**：`stability`/`targets`/`applicable`/`method`/`cw`/`cwk`/`preliminary`/`limits_frozen` 於後端輸出（Task 4/5/19）、前端型別（Task 10）、卡片（Task 11）、報告（Task 18）命名一致。
