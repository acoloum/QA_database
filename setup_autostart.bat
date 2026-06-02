@echo off
REM ============================================================
REM One-click: register QMS to auto-start on boot (Task Scheduler).
REM Double-click this file; click "Yes" on the UAC prompt.
REM Creates task "QMS" -> runs serve_qms.bat at system startup (no login needed).
REM ============================================================

REM --- self-elevate to administrator if not already ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo Creating scheduled task "QMS" (auto-start on boot)...
schtasks /Create /TN "QMS" /TR "C:\QC_Database\serve_qms.bat" /SC ONSTART /RU SYSTEM /RL HIGHEST /F

echo.
echo Done. Verify with:  schtasks /Query /TN "QMS"
echo (To remove later:   schtasks /Delete /TN "QMS" /F )
echo.
pause
