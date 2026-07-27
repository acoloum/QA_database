# Task 8 報告：量測設備與受控匯入頁面

## 交付內容

- 完成 `/msa/equipment` 設備風險工作台：搜尋、狀態與校驗篩選、風險排序、分頁、桌面語意表格、行動版設備卡片、載入／錯誤／空狀態，以及具焦點管理的設備證據抽屜。
- 設備抽屜整合主檔、能力、校驗與補正點、狀態事件、CQI-9 關聯及研究入口；建立、狀態異動與匯入僅對 `msa.manage` 開放，校驗核准另要求 `msa.approve`。
- 完成校驗草稿與補正點增刪、核准原因及 optimistic concurrency `expected_status` 契約；停用設備重新啟用時送出後端接受的 `reactivated`。
- 完成 `/msa/imports` 三步受控匯入：上傳與預覽、逐列問題處置、確認匯入，以及匯入歷程／批次明細重新載入；未解決的阻擋問題不可確認，且沒有 bulk ignore。
- 補上 `GET /api/measurement-equipment/imports` 與 `GET /api/measurement-equipment/imports/<id>` 歷程契約，兩者均受 `msa.view` 保護。
- 設備 list/detail 回傳一致的 `calibration_status`、`next_calibration_date` 與 `calibration_block_reason`；狀態依指定 `as_of` 與最近一筆已核准且生效的校驗判斷，list 維持固定兩次 SELECT，沒有 N+1。
- 視覺使用設計規格色票、證據軌、可見 focus、reduced motion 與響應式佈局；匯入問題文字由 React escape，未使用 `dangerouslySetInnerHTML`。

## TDD 證據

1. 設備校驗摘要先出現 5 個失敗，再以有效日期、核准狀態與免校規則完成最小實作，聚焦後端轉綠。
2. 匯入歷程路由先取得 2 個 404，再補 list/detail route 與 service 後轉綠。
3. 前端先因新頁面／元件不存在與路由缺失而 collection RED，再逐步完成頁面、抽屜、校驗表單與匯入審查。
4. `active` 狀態異動先由測試抓到錯誤 payload，修正為 `reactivated` 後轉綠。
5. 設備 detail 摘要一致性測試先因缺少 `calibration_status` 失敗，補齊與 list 相同的序列化後轉綠。
6. 最後一筆補正點移除測試先因找不到按鈕失敗，改為允許零筆後，頁面 11 項測試全數通過。

## 驗證結果

| 項目 | 結果 |
| --- | --- |
| 新鮮後端聚焦測試 | PASS，75 tests |
| 新鮮前端聚焦測試 | PASS，5 files / 31 tests |
| 後端完整測試 | PASS，877 passed / 2 skipped |
| 前端完整測試 | PASS，112 files / 488 tests |
| `npm run lint` | PASS |
| `git diff --check` | PASS（僅 Git 的 LF/CRLF 提示） |
| Task 8 TypeScript diagnostics | 0 |
| `npm run build` | BLOCKED（既有分支 TypeScript 基線錯誤，exit 2） |

完整後端與前端測試在最後兩個針對性回歸案例加入前已通過；加入 detail 摘要修正與補正點刪除修正後，已重新執行涵蓋相關路徑的上述新鮮聚焦測試。完整 build 的既有錯誤不在 `src/components/msa`、`src/pages/msa`、`src/hooks/useMsa*`、`src/types/msa.ts` 或 `src/App.tsx`，篩選後 Task 8 診斷數為 0。

## 範圍確認

- 未修改 `vite.config.ts`。
- 未將盤點用的 68／66 筆統計虛構為頁面 KPI 或 API 資料。
- 自行啟動的唯讀 reviewer 依父任務指示中止；獨立 SDD review 由父任務統一安排。
