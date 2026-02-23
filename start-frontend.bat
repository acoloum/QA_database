@echo off
cd /d "%~dp0\src_frontend"
echo ========================================
echo   Starting Frontend Server
echo ========================================
call npm run dev
echo.
echo Exit code: %ERRORLEVEL%
pause
