@echo off
setlocal
cd /d "%~dp0\.."
if exist "tools\.venv\Scripts\python.exe" (
  "tools\.venv\Scripts\python.exe" "tools\sync_web_databases.py"
) else (
  python "tools\sync_web_databases.py"
)
if errorlevel 1 (
  echo.
  echo Database sync failed.
  pause
  exit /b 1
)
echo.
pause
