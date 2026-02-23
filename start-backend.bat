@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ========================================
echo   Starting Backend Server (port 5001)
echo ========================================

call venv\Scripts\activate.bat
python -m backend.app
