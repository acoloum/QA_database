@echo off
REM ============================================================
REM QMS DEVELOPMENT server (Vite, port 5173)
REM /api is proxied to the production waitress (:80), so no separate
REM backend is needed. Can run at the same time as production (:80).
REM
REM Usage: just double-click this file.
REM   - Dev URL:  http://localhost:5173   (live HMR on save)
REM   - Keep this window open = server running; Ctrl+C or close = stop.
REM   - To publish changes to LAN: cd src_frontend, npm run build,
REM     then restart production (serve_qms.bat).
REM ============================================================
cd /d C:\QC_Database\src_frontend
echo.
echo  Starting DEV server (Vite :5173) ...
echo  Dev URL:  http://localhost:5173      (press Ctrl+C to stop)
echo.
call "C:\Program Files\nodejs\npm.cmd" run dev
echo.
echo  Dev server stopped. Press any key to close.
pause >nul
