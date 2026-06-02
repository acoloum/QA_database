@echo off
REM ============================================================
REM Stop the QMS production server (the process listening on TCP port 80).
REM Double-click this file; click "Yes" on the UAC prompt.
REM Note: if auto-start (Task Scheduler "QMS") is enabled, this stops it now,
REM       but it will start again on next boot. To stop permanently, also run:
REM       schtasks /Delete /TN "QMS" /F
REM ============================================================

REM --- self-elevate to administrator if not already ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue; if($c){ $c.OwningProcess | Select-Object -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force; Write-Host ('Stopped QMS server (PID ' + $_ + ')') } catch { Write-Host ('Could not stop PID ' + $_) } } } else { Write-Host 'No server is running on port 80.' }"
echo.
pause
