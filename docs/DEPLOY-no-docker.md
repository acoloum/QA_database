# QMS 免 Docker 生產部署（waitress 單一程序，80 埠）

讓內網電腦**只輸入 IP**（`http://<本機IP>`，免加埠號）即可連線。
單一 waitress 程序同時服務前端（build 後的 dist）與 `/api`，與 API 同源 → 不需 proxy、無 CORS 問題。

## 架構
```
瀏覽器 (內網) ──http://192.168.0.144──▶ waitress :80
                                          ├─ /            → src_frontend/dist/index.html（前端 SPA）
                                          ├─ /assets/...  → 靜態檔
                                          ├─ /shipping…   → 回 index.html，交前端路由
                                          └─ /api/...      → Flask 後端（同程序）
                          PostgreSQL (本機 :5432)
```

## 一次性前置
1. **建置前端**（每次改前端程式後都要重跑一次）：
   ```
   cd src_frontend
   npm run build
   ```
2. **釋放 80 埠**：關閉開發用的 `npm run dev`（它佔用 :80）。確認 :80 沒有其他服務（本專案 Apache 在 :8080，不衝突）。

## 手動啟動 / 停止
- 啟動：在專案根目錄雙擊或執行 **`serve_qms.bat`**（會啟用 venv 並以 waitress 在 :80 提供服務）。
- 連線測試（本機）：瀏覽器開 `http://localhost` 或 `http://127.0.0.1`。
- 內網其他電腦：`http://<本機區網IP>`（例如 `http://192.168.0.144`）。
- 停止：在該視窗按 `Ctrl + C`；或結束對應的 python/waitress 程序。
- 日誌：`logs\qms_server.log`。

## 設定開機自動啟動（Task Scheduler）
以**系統管理員**身分開 PowerShell 或命令提示字元，執行：
```
schtasks /Create /TN "QMS" /TR "C:\QC_Database\serve_qms.bat" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
```
- `/SC ONSTART`：開機即啟動（不需登入）。
- `/RU SYSTEM`：以系統帳號執行（可繫結 80 埠、不需有人登入）。
- 立即測試一次：`schtasks /Run /TN "QMS"`
- 查看狀態：`schtasks /Query /TN "QMS" /V /FO LIST`
- 移除：`schtasks /Delete /TN "QMS" /F`

> 注意：設定自動啟動前，請先確認手動執行 `serve_qms.bat` 能正常服務、且 :80 未被佔用。

## 開發 vs 生產
- **開發**：照舊 `npm run dev`（:80，HMR 即時更新）。
- **生產（給內網用）**：`npm run build` 後跑 `serve_qms.bat`。
- 兩者不要同時佔用 :80。改了前端程式 → 重新 `npm run build` → 重啟 `serve_qms.bat`（或重跑排程任務）才會生效。

## 防火牆
若其他電腦連不到，於本機開放輸入規則允許 TCP 80：
```
netsh advfirewall firewall add rule name="QMS HTTP 80" dir=in action=allow protocol=TCP localport=80
```
