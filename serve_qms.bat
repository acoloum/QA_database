@echo off
REM ============================================================
REM QMS 生產啟動腳本（免 Docker）
REM waitress 單一程序，在 80 埠同時服務前端(dist) 與 /api。
REM 內網電腦輸入 http://<本機IP>  即可連線（80 埠免加埠號）。
REM
REM 前置：前端需先建置一次 ->  cd src_frontend ^&^& npm run build
REM 並確認 80 埠未被佔用（例如先關閉開發用的 npm run dev）。
REM ============================================================
cd /d C:\QC_Database
call venv\Scripts\activate.bat
if not exist logs mkdir logs
echo [%date% %time%] QMS 啟動於 http://0.0.0.0:80  >> logs\qms_server.log
waitress-serve --listen=*:80 --threads=8 backend.app:app >> logs\qms_server.log 2>&1
