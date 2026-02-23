@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ========================================
echo   QA Database - Start Servers
echo ========================================

echo [1/2] Starting Backend (port 5001)...
start "Backend" cmd /k venv\Scripts\activate.bat ^&^& python -m backend.app
echo   Backend started

echo [2/2] Starting Frontend (port 5173)...
cd src_frontend
start "Frontend" cmd /k npm run dev
cd ..
echo   Frontend started

echo.
echo ========================================
echo   Servers Started!
echo   Backend:  http://localhost:5001
echo   Frontend: http://localhost:5173
echo ========================================
echo   Close the windows to stop servers
echo ========================================

pause
