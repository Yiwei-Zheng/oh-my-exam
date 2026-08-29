@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python environment not found.
  echo Run: python scripts\setup_env.py --group all
  pause
  exit /b 1
)

".venv\Scripts\python.exe" "scripts\start_dev.py" %*
set "OME_START_EXIT=%ERRORLEVEL%"

if not "%OME_START_EXIT%"=="0" pause
exit /b %OME_START_EXIT%
