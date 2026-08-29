@echo off
setlocal
chcp 65001 >nul

set "WEB_ROOT=%~dp0"
for %%I in ("%WEB_ROOT%..") do set "PROJECT_ROOT=%%~fI"
set "BACKEND_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "FRONTEND_ROOT=%WEB_ROOT%frontend"

if not exist "%BACKEND_PYTHON%" (
  echo [ERROR] Python environment not found: %BACKEND_PYTHON%
  echo [错误] 未找到 Python 虚拟环境，请先在项目根目录完成环境安装。
  pause
  exit /b 1
)

if not exist "%FRONTEND_ROOT%\package.json" (
  echo [ERROR] Frontend package not found: %FRONTEND_ROOT%
  echo [错误] 未找到前端工程。
  pause
  exit /b 1
)

if not exist "%FRONTEND_ROOT%\node_modules" (
  echo [ERROR] Frontend dependencies are not installed.
  echo [错误] 前端依赖尚未安装，请先在 web\frontend 运行 npm install。
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo [OK] Backend and frontend environments are ready.
  echo [正常] 前后端环境已就绪。
  exit /b 0
)

echo Starting Oh My Exam API and frontend...
echo 正在启动 Oh My Exam 后端和前端...

start "Oh My Exam API" /D "%PROJECT_ROOT%" "%BACKEND_PYTHON%" -m uvicorn oh_my_exam_server.main:app --host 127.0.0.1 --port 8000 --reload
start "Oh My Exam Web" /D "%FRONTEND_ROOT%" cmd /k npm run dev

echo.
echo API: http://127.0.0.1:8000
echo Web: use the address printed in the frontend window, usually http://127.0.0.1:5173
echo 网页：请使用前端窗口显示的地址，通常为 http://127.0.0.1:5173
echo Close both server windows to stop the application.
echo 关闭两个服务器窗口即可停止应用。
pause
