# MSA 第四版完整模組實作總計畫

**規格來源：** [MSA 第四版完整模組設計](../specs/2026-07-27-msa-fourth-edition-module-design.md)

**目標：** 依 AIAG MSA 第四版與已核准產品決策，分三個可審查、可驗證的交付段落，完成量測設備治理、MSA 研究與統計、前端工作台、核准及正式報告。

**遷移拆分說明：** 核准規格以單一 `44_create_msa_and_measurement_equipment.sql` 表示整體模型；實作計畫將它細分為 migration 44（設備、校驗、匯入、準則）與 migration 45（研究、觀測、結果、決策、再研究、確效），以便分階段部署與回歸。資料語意與不可變要求不變。

## 執行順序

### 第一階段：資料治理基礎

[MSA 設備與準則基礎實作計畫](2026-07-27-msa-equipment-criteria-foundation.md)

交付：

- `msa.view`、`msa.execute`、`msa.manage`、`msa.approve` 四層權限。
- 通用量測設備、校驗、補正點、狀態事件及專用設備連結。
- `measurements (1).csv` 的預覽／確認受控匯入。
- 版本化、核准後不可變的 MSA 判定準則。
- 設備、匯入與準則前端頁面。

Gate：

- migration 44 成功。
- 正式來源預覽重現 108/97/9/2/68/32/1/31 盤點結果。
- 不合格設備被後端資格服務阻擋。
- 基礎前後端測試、lint、build 通過。

### 第二階段：研究與統計核心

[MSA 研究、統計與核准核心實作計畫](2026-07-27-msa-study-statistics-workflow.md)

交付：

- 研究、設備關聯、凍結 plan、盲碼、評價人、append-only 觀測。
- Range、Xbar-R、crossed ANOVA、bias、linearity、stability、attribute、nonrepeatable。
- 不可變結果版本、資料 hash、準則 snapshot、三層判定。
- 送審、核准、退回、作廢與職責分離。
- 週期／事件型再研究。
- golden validation runner 與持久化 PASS/FAIL 證據。

Gate：

- migration 45 成功。
- 每個方法的 reference、edge、not-applicable 測試通過。
- golden validation 全部 PASS。
- admin 自己核准仍回 `MSA_SELF_APPROVAL_FORBIDDEN`。
- 完整後端回歸通過。

### 第三階段：使用體驗、報告與正式確效

[MSA 工作台、報告與完整確效實作計畫](2026-07-27-msa-frontend-report-validation.md)

交付：

- 風險導向工作台。
- 方法導向研究精靈。
- 逐筆盲測、管理矩陣及 Excel 匯入。
- 分層證據結果頁與可存取圖表。
- PDF／Excel 不可變報告。
- 正式資料庫、authenticated API、報告與瀏覽器 smoke。

Gate：

- 報告來源改變後仍可由 saved result 重建相同內容。
- approved PDF 無浮水印，其他狀態有未核准浮水印。
- PDF 全頁 render 與 Excel reopen 驗證通過。
- 前後端全測試、lint、build、golden validation、DB constraint 與 authenticated smoke 全部通過。

## 跨階段不變規則

- 後端維持 route → service → model；統計與商業邏輯不得放 route。
- 正式結果只由後端產生，使用受控 method code/version。
- 第四版正式研究使用 `6σ`；legacy `5.15σ` 必須清楚隔離。
- 非平衡、不完整、不適用、NaN、Infinity 與奇異模型不得產生偽正式結果。
- plan、observation、result、decision、approved calibration 與 approved criteria 均有不可變或 append-only 保護。
- 人工工程判斷不得改寫統計結果。
- 管理員不得繞過自己核准限制。
- 報告只讀保存版本，不重新分析。
- 所有介面狀態不得只靠顏色；圖表必須有文字摘要或資料表。
- 所有正式完成宣告必須附實際驗證證據。

## Commit 與工作目錄界線

- 每個子計畫已列出 review-sized commit；依順序執行，避免把資料模型、統計、UI 與報告混成單一提交。
- 提交訊息使用繁體中文。
- 不納入使用者現有的 `src_frontend/vite.config.ts` 變更。
- 正式來源 PDF 與 CSV 不提交；只提交去識別、最小化的測試 fixtures。
- `.superpowers/` 與 `tmp/` 只作工作產物，不提交。

## 最終驗收證據清單

- Git commits 與 clean/expected dirty status。
- migration 44/45 套用紀錄。
- 設備 CSV preview/confirm batch hash 與統計。
- 各統計方法 golden validation run IDs。
- MSA 後端與前端完整測試輸出。
- lint/build 輸出。
- 資料庫不可變與唯一限制測試。
- authenticated create → collect → analyze → submit → approve smoke。
- self-approval 403。
- PDF/Excel hash、文字抽取、逐頁 render/reopen 證據。
- 1440×900、1024×768、390×844 瀏覽器 smoke 與無 console error。
