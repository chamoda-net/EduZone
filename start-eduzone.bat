@echo off
rem Starts the local EduZone system (database, API, web app, admin app) and opens it in Chrome.
rem Each part opens in its own window; stop-eduzone.bat closes them all.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-eduzone.ps1"
echo.
pause
