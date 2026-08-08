# 全庫優化與缺陷修正設計

## 目標

落地上一輪全庫掃描確認的交易原子性、錯誤契約、部署資源限制、查詢效能、migration 可追蹤性與測試可靠性缺口；維持既有路由、資料表名、欄位名及前端公開資料契約。

## 設計原則

- 每個 mutation 只有外層 use case 擁有 `commit`；內部模組只能 `add`、`flush` 或回傳待提交結果。
- 所有 HTTP 錯誤使用 `{success:false,error:{code,message,details}}`；legacy 字串只由共用 Axios 相容層處理。
- 先在介面測試捕捉行為，再修改 implementation；不以改測試期待值消除失敗。
- 查詢先在 PostgreSQL/SQLite 共同可用的 SQL 聚合或條件完成，再做必要的序列化。
- 內部重構保留既有外部 interface；新增 seam 必須讓行為與測試更集中，而非增加 pass-through wrapper。

## 批次範圍

### A. 交易與錯誤契約

`CAPAService.update_step` 將 D7 任務同步改為同一個 session 交易；`TaskService.create` 提供不提交的內部建立路徑。非 MSA 附件刪除採先提交資料庫刪除、再刪實體檔，失敗時恢復資料庫連結。校正 adapter 改用共用 envelope；所有 `handle_db_error` 呼叫攤平 message/details。

### B. 部署與測試可靠性

限流只信任受控 Nginx forwarded address，memory limiter 保留單程序相容性並明確限制部署範圍。Flask 設定全域 body 上限，與 Nginx 及匯入服務一致。子程序測試一律指定 UTF-8；CI 對必要整合測試 skip 直接失敗，並測試 Python 3.12/3.14。前端 debounce 測試改用 fake timers。升級可安全升級的開發依賴並重新產生 lockfile。

### C. 查詢與 migration

品質分析 repeat issues 使用 SQL `GROUP BY/HAVING` 取得 top groups；機械判定篩選先以資料庫可表達的 `is_ng` 或子查詢縮小集合，避免無界 ORM collection。新增 migration ledger/checksum 工具，並把目前編號 SQL 的套用結果寫入台帳；不直接對正式資料庫執行。

### D. 內部 seam 與維護性

移除無效的 route `try/except: raise`。校正服務保留原有公開方法，將 payload normalization、計算輸入、ORM apply 與序列化移到私有模組；大型前端校正頁只抽出純表單 reducer/serializer，不改 React Query 對外 hook interface。模型分檔先以 registry/metadata parity 測試保護，再分批移動，不在本輪一次改寫所有 import。

## 驗收

- CAPA D7 失敗時業務欄位與任務零寫入。
- 所有校正及資料庫錯誤均可由 Axios 取得穩定 code/message/details。
- Docker/Windows 上傳、限流及測試輸出有明確上限與 UTF-8 行為。
- repeat issues 與 mechanical status 不再以無界 Python collection 聚合。
- 必要 migration integration tests 不得靜默 skip。
- 後端 pytest、前端 Vitest、lint、build、`pip check`、production `npm audit` 均通過。
