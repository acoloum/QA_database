@echo off
chcp 65001 >nul
echo ============================================================
echo 驗證 Python 3.11 安裝
echo ============================================================
echo.

python3.11 --version
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [錯誤] Python 3.11 未正確安裝或未加入 PATH
    echo 請重新執行 Python 3.11 安裝程式，並確認勾選 "Add python.exe to PATH"
    pause
    exit /b 1
)

echo.
echo [OK] Python 3.11 安裝成功！
echo.
pause