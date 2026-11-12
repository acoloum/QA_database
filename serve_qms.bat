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
REM Read-only schema preflight: models.py vs DB + migration ledger.
REM Warns only; the server still starts so a boot-time check never causes an outage.
set PYTHONIOENCODING=utf-8
"C:\QC_Database\venv\Scripts\python.exe" -m backend.migration.preflight >> logs\qms_server.log 2>&1
if errorlevel 1 echo [%date% %time%] WARNING: schema preflight failed - see lines above, apply pending migrations >> logs\qms_server.log
"C:\QC_Database\venv\Scripts\waitress-serve.exe" --listen=*:80 --threads=8 backend.app:app >> logs\qms_server.log 2>&1
