# MSA 正式服務 smoke 作業手冊

部署 MSA 模組後，用這份手冊確認「重啟後的服務真的載入了新的 ORM 與
Blueprint」，而不只是程式碼進了版控。

---

## 為什麼要走 HTTP

`backend/scripts/smoke_msa.py` 刻意透過 HTTP 呼叫執行中的服務，而不是
直接呼叫 service 層。直接呼叫 service 只證明程式碼是對的，證明不了
**線上那個 process 已經載入這份程式碼**。

這個選擇實際抓到過一個單元測試漏掉的缺陷：權限轉接器會把服務層的
403 一律改寫成 `MSA_PERMISSION_DENIED`，導致職責分離的
`MSA_SELF_APPROVAL_FORBIDDEN` 被蓋掉。核准者看到「權限不足」會去要
更多權限，而不是知道自己根本不該核准這份研究。

---

## 一、先決條件

### 1. 資料庫選擇（重要）

MSA 的觀測、結果與決策是 append-only，**寫進去就刪不掉**。因此：

> 不要對正式資料庫跑 smoke。

建議做法是複製 schema 到專用 smoke 資料庫：

```powershell
Set-Item -Path Env:PGPASSWORD -Value'<password>'
$pg = "C:\Program Files\PostgreSQL\18\bin"

& "$pg\pg_dump.exe" -U postgres --schema-only --no-owner --no-privileges `
    -f schema.sql qa_database
& "$pg\psql.exe" -U postgres -c "DROP DATABASE IF EXISTS qa_database_smoke WITH (FORCE);"
& "$pg\psql.exe" -U postgres -c "CREATE DATABASE qa_database_smoke;"
& "$pg\psql.exe" -U postgres -d qa_database_smoke -f schema.sql
```

用 `--schema-only` 而不是重跑 migration，可以確保 trigger、partial
unique index 與 CHECK 完全與正式環境一致。

若組織政策要求必須對正式庫驗證，smoke 產生的資料一律以
`SMOKE-MSA-<timestamp>` 前綴標示，且結束時把結果版本標記作廢
（runner 預設行為）。不可變證據**不得**直接 DELETE。

### 2. 帳號

需要四個帳號，涵蓋四種身分：

| 角色 | 權限需求 | 用途 |
|---|---|---|
| manager | `msa.manage` | 建立設備、準則、計畫、輸入讀值 |
| executor | `msa.execute`（**不可**有 `msa.approve`） | 建立研究；驗證權限不足會被擋 |
| approver | `msa.approve`，且**完全不碰**研究資料 | 執行獨立核准 |
| participant_approver | `msa.approve`，但會輸入一筆讀值 | 驗證職責分離真的擋得住 |

第四個帳號常被忽略但不可省略：沒有 `msa.approve` 的人會被權限層先擋
下，**根本走不到職責分離檢查**，那條規則等於沒驗到。

Token 一律由環境變數提供，不寫進腳本、不進版控：

```powershell
$env:MSA_SMOKE_MANAGER_TOKEN = '<token>'
$env:MSA_SMOKE_EXECUTOR_TOKEN = '<token>'
$env:MSA_SMOKE_APPROVER_TOKEN = '<token>'
$env:MSA_SMOKE_PARTICIPANT_APPROVER_TOKEN = '<token>'
```

### 3. 中文字型

PDF 報告需要繁體中文字型；缺少時服務會回 `MSA_REPORT_FONT_MISSING`
而**不會**輸出亂碼。Windows 使用系統內建字型即可；容器與 Linux 需要：

```bash
apt-get install -y fonts-noto-cjk
```

專案的 `Dockerfile` 已包含此套件。

---

## 二、重啟服務

先依正式部署方式重啟，讓新的 ORM 與 Blueprint 生效：

```powershell
.\stop_qms.bat
.\serve_qms.bat
```

確認 listener 存在：

```powershell
Get-NetTCPConnection -LocalPort 5001 -State Listen
```

> **注意**：不要在服務執行中重建資料庫。連線池會留下指向舊資料庫的
> 陳舊連線，產生難以排查的結果。順序永遠是「停服務 → 重建 DB →
> 起服務」。

---

## 三、執行 smoke

```powershell
venv\Scripts\python.exe -m backend.scripts.smoke_msa --base-url http://localhost:5001
```

若正式入口是 Nginx，另外驗一次：

```powershell
venv\Scripts\python.exe -m backend.scripts.smoke_msa --base-url http://localhost:8080
```

`--keep` 只在除錯時使用，它會保留 smoke 資料不標記作廢。

### 涵蓋範圍

1. 建立設備 → 建立校驗 → 核准校驗 → 啟用設備
2. 建立判定準則設定 → 建立版本 → 核准版本
3. 建立研究 → 建立計畫 → 凍結（保存設備／準則／隨機順序快照）
4. 取得盲測任務 → 輸入 18 筆讀值 → 完整性驗證
5. 分析（驗證資料指紋與判定）
6. 送審
7. **無 `msa.approve` 者核准 → 403 `MSA_PERMISSION_DENIED`**
8. **有權限但輸入過資料者核准 → 403 `MSA_SELF_APPROVAL_FORBIDDEN`**
9. 獨立核准 → approved
10. 下載 PDF／Excel，驗證魔術位元組、檔案大小與稽核欄位

### 讀值為什麼要有結構

smoke 的讀值由 `_smoke_reading()` 產生，刻意讓每個變異來源都非零。
若所有評價人讀值相同，交互作用均方會是 0、F 值無定義，引擎會（正確
地）回 `MSA_METHOD_NOT_APPLICABLE / degenerate_model`。這是引擎在保護
結論品質，不是 bug。

---

## 四、資料庫限制驗證

在 smoke 資料庫或測試交易內執行，九項應全部回 `t`：

```sql
BEGIN;
-- 1 設備編號唯一            2 已核准校驗不可修改
-- 3 已核准校驗不可刪除      4 凍結計畫不可修改
-- 5 觀測讀值不可修改        6 觀測不可刪除
-- 7 結果統計不可修改        8 結果不可刪除
-- 9 同研究僅一個送審中結果
ROLLBACK;
```

完整腳本見本手冊 git 歷史或依 `backend/migration/44`–`47` 的
trigger 定義自行編寫。重點是**在交易內嘗試違規並確認被擋下**，
而不是只檢查 trigger 存在。

---

## 五、報告驗證

| 檢查 | 方式 |
|---|---|
| 檔案真實性 | PDF 開頭 `%PDF-`、Excel 開頭 `PK\x03\x04` |
| 中文可抽取 | `pypdf` 抽取文字應含「量測系統分析報告」 |
| 稽核欄位 | Excel「版本稽核」工作表的資料雜湊／方法代碼／程式版本需與 API 回應一致 |
| 浮水印 | 已核准報告**不得**出現「未核准」；未核准報告每頁都要有 |
| 只讀保存版本 | 改動來源設備名稱後重新產生，內容必須逐格／逐字相同 |

---

## 六、清理

runner 預設會把結果版本標記作廢（`void`）。若使用專用 smoke 資料庫，
直接整個刪除最乾淨：

```powershell
& "$pg\psql.exe" -U postgres -c "DROP DATABASE qa_database_smoke WITH (FORCE);"
```

對正式庫執行過的 smoke：

- 結果版本：已由 runner 標記 `voided`
- 觀測與工作流決策：**不可刪除**，依 append-only 設計保留
- 設備與準則：可由具權限者停用，但同樣建議保留 `SMOKE-MSA-` 前綴以利辨識

---

## 七、失敗時怎麼看

runner 失敗會印出實際 HTTP 狀態與完整回應內容。常見情形：

| 症狀 | 通常原因 |
|---|---|
| `MSA_PERMISSION_DENIED` 出現在該是職責分離的步驟 | 用了沒有 `msa.approve` 的帳號，或權限轉接器又把服務層 403 蓋掉了 |
| `MSA_METHOD_NOT_APPLICABLE / degenerate_model` | 讀值缺乏變異結構 |
| `MSA_REPORT_FONT_MISSING` | 伺服器缺中文字型 |
| PDF 檔頭不符 | 下載到的是錯誤頁而不是檔案，檢查認證與路由 |
| 資料庫行為與預期不符 | 服務執行中重建過資料庫，重啟服務再試 |
