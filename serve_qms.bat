@echo off
REM ============================================================
REM QMS PRODUCTION server (no Docker)
REM waitress, port 80, serves built frontend (dist) + /api in one process.
REM LAN PCs connect via  http://<this-machine-ip>  (no port needed).
REM
REM Prereq: build frontend once ->  cd src_frontend  ^&  npm run build
REM         and keep port 80 free (stop "npm run dev" if it uses :80).
REM Uses venv waitress-serve.exe directly (works under Task Scheduler / SYSTEM).
REM ============================================================
cd /d C:\QC_Database
if not exist logs mkdir logs
echo [%date% %time%] QMS starting on http://0.0.0.0:80 >> logs\qms_server.log
"C:\QC_Database\venv\Scripts\waitress-serve.exe" --listen=*:80 --threads=8 backend.app:app >> logs\qms_server.log 2>&1
