@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   QA Database - Stop Servers
echo ========================================
taskkill /F /IM python.exe >nul 2>&1
echo   Backend stopped
taskkill /F /IM node.exe >nul 2>&1
echo   Frontend stopped
echo ========================================
echo   All servers stopped
echo ========================================
pause
