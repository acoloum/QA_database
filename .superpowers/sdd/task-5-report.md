# Task 5：巡檢機器績效研究完成報告

## 交付範圍

- 新增固定機台巡檢研究的 Pm、Pmk、Pmu、Pml G 法分位數引擎。
- 僅允許 `source=patrol`，並要求單一機台、材質、規格、項目與位置；研究條件選項採嚴格 canonical contract 且納入資料雜湊。
- 巡檢 `min_val`、`max_val` 分別保留為觀測值，保存操作者、日期跨度、來源紀錄與量測明細識別碼。
- 新增研究核准 API；機器及已確認 B/C/D 研究使用不建立生產界限的 `approve_research` 流程。
- 機器研究報表使用專用摘要，不產生 Xbar/R、持續監控或 OCAP 語意。

## TDD 證據

1. 引擎測試首次執行因 `spc_machine_performance` 模組不存在而 RED。
2. 研究流程測試首次執行因既有服務拒絕 `machine` 分析族別而 RED。
3. API 測試首次執行回傳 405，新增路由後 GREEN。
4. 報表測試首次執行只有一般 SPC 工作表，新增機器專用報表後 GREEN。
5. B/C/D 研究核准測試首次執行遭 `RESEARCH_APPROVAL_NOT_APPLICABLE` 拒絕，擴充核准條件後 GREEN。

## 驗證

- `backend/tests/test_services/test_spc_machine_performance.py`：3 passed
- `backend/tests/test_services/test_spc_machine_study.py`：4 passed
- 完整 SPC 服務與路由回歸：179 passed
- `git diff --check`：通過

## 已知界線

- 此交付不建立 `SpcLimitVersion`、不提供 ongoing chart，也不為機器研究建立 OCAP。
- 機器研究規格一致性透過固定材質、規格、項目、位置及不可變規格快照／資料雜湊驗證；來源改變時送審或核准會被拒絕。
