@echo off
rem Stops the local EduZone system: the admin app, web app, API and database (whatever listens on their ports).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\stop-eduzone.ps1"
echo.
pause
