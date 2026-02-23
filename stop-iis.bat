@echo off
echo Stopping IIS services...
net stop was /y
net stop w3svc /y
echo.
echo Done.
pause
