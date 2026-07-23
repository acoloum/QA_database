# Task 5 實作報告：兩個獨立追溯編號面板與新增／編輯表單

## 結果

- 機械性質新增／編輯表單已由舊的成對批次列，切換為「擠製編號」與「T4爐號」兩份完全獨立的清單。
- 兩份清單各自新增、刪除、重排與輸入，不會改變另一份清單。
- 儲存 payload 只送出 `extrusion_numbers` 與 `t4_furnace_numbers`，不再送出 `batches`。
- 空白編號會在建立 payload 時排除，送出前會 trim 並重新編為連續序號。
- 同一份清單內 trim 後的重複值會即時標成錯誤，輸入欄位與錯誤訊息有可存取關聯，並阻擋儲存。
- 編輯 hydrate 僅讀新版兩份清單；fixture 刻意保留 deprecated `batches`，驗證其內容不會出現在新表單。

## Frontend design 如何影響實作

本功能服務 QC 檢驗人員，單一視覺任務是明確表達「兩種追溯編號互不配對」。因此：

- 使用既有 React Bootstrap 與系統字型、主題色、danger 狀態，沒有新增局部 palette、字型或動畫。
- 使用兩個同等權重的 `border rounded p-3 h-100` 面板，各自具有標題與新增按鈕，作為唯一的視覺強調。
- 以 `Row` 搭配兩個 `Col md={6}`：桌面並排，低於 `md` breakpoint 時自然堆疊。
- 每列序號只表示該清單內順序；沒有跨欄對齊、連線、共用新增按鈕或其他暗示配對的視覺。
- 錯誤沿用 Bootstrap invalid feedback，並以唯一 ID 連結 `aria-describedby`，讓視覺與輔助科技使用者取得相同錯誤資訊。

## TDD：RED 證據

先新增 `MechanicalTraceNumberPanel.test.tsx`，並先更新表單測試鎖定獨立新增／刪除、新版 payload、重複阻擋與不讀 deprecated `batches`，正式碼尚未修改時執行：

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx src/pages/mechanical/MechanicalTestForm.test.tsx
```

結果：exit code 1；2 個測試檔失敗。面板測試因 `./MechanicalTraceNumberPanel` 尚不存在而無法解析；表單 25 個測試中 6 個失敗、19 個通過，失敗原因為找不到「新增擠製編號」、新版獨立欄位與新版 hydrate 值。這些均為需求尚未實作的預期失敗，不是測試拼字或環境錯誤。

## TDD：GREEN 證據

完成最小實作後執行 brief 指定命令：

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx src/pages/mechanical/MechanicalTestForm.test.tsx src/pages/mechanical/mechanicalPayload.test.ts
```

結果：exit code 0；3 個測試檔、40 個測試全部通過。

## 驗證

- 指定測試：3 files / 40 tests PASS。
- 全前端回歸：`npm test -- --run`，106 files / 428 tests PASS。
- Lint：`npm run lint -- --max-warnings=0`，exit code 0，0 warnings。
- Build：`npm run build`，TypeScript 與 Vite production build 均通過。
- 格式：`git diff --check`，exit code 0。
- 範圍檢查：表單與面板正式碼已無 `batches`、`MechanicalBatch` 或舊 batch state 操作；`batches` 只保留在 detail 型別的 optional deprecated 相容欄位。

## 變更檔案

- `src_frontend/src/pages/mechanical/MechanicalTraceNumberPanel.tsx`
- `src_frontend/src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx`
- `src_frontend/src/pages/mechanical/MechanicalTestForm.tsx`
- `src_frontend/src/pages/mechanical/MechanicalTestForm.test.tsx`
- `src_frontend/src/types/mechanical.ts`

## 自審

- 獨立性：兩面板使用不同 state、setter、duplicate set 與新增／刪除操作。
- Payload：只組成新版兩清單；既有 helper 統一負責 trim、排除空白與重編序號。
- Hydrate：只讀 `detail.extrusion_numbers` 與 `detail.t4_furnace_numbers`，沒有 fallback 到 `batches`。
- 重複防護：忽略空白值，僅在同一清單內比較 trim 後字串；兩列都標錯並在 save 前阻擋 API。
- 可存取性：面板以 heading 標記 region，輸入有唯一 label，重複錯誤具有唯一 ID 與 `aria-describedby`。
- 響應式：`Col md={6}` 在桌面等寬並排、手機單欄堆疊；沒有新增自訂 CSS breakpoint。
- 範圍：未修改後端、Task 6 清單或附件；未納入工作樹既存的 `task-3-report.md` 修改。

## 疑慮

- 本次以元件測試、完整前端回歸、lint 與 production build 驗證；未啟動服務進行瀏覽器實畫面檢查。響應式行為直接使用專案既有 Bootstrap `md` breakpoint，未新增自訂樣式。
