@echo off
setlocal EnableExtensions
title GuDing Asset System - One-Click Start

set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"
set "BACKEND_PORT=5200"
set "FRONTEND_PORT=5201"

echo ==============================================
echo    GuDing Asset System - One-Click Start
echo    Frontend :%FRONTEND_PORT%   Backend :%BACKEND_PORT%
echo ==============================================
echo.

rem ========== [1/6] Docker ==========
echo [1/6] Checking Docker ...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo       Docker not running, trying to start Docker Desktop ...
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
)
set /a n=0
:wait_docker
docker info >nul 2>&1
if %errorlevel% equ 0 goto :docker_ok
set /a n+=1
if %n% geq 30 (
    echo [ERROR] Docker not ready within 90s. Please start it manually and retry.
    pause
    exit /b 1
)
timeout /t 3 /nobreak >nul
goto :wait_docker
:docker_ok
echo       Docker ready

rem ========== [2/6] MySQL ==========
echo [2/6] Starting MySQL container ...
docker ps -a --format "{{.Names}}" | findstr /i "guding-mysql" >nul
if %errorlevel% neq 0 (
    echo [ERROR] MySQL container guding-mysql not found. Please create it first.
    pause
    exit /b 1
)
docker start guding-mysql >nul
set /a n=0
:wait_mysql
docker exec guding-mysql mysqladmin ping -uroot -pguding@2026 >nul 2>&1
if %errorlevel% equ 0 goto :mysql_ok
set /a n+=1
if %n% geq 30 (
    echo [ERROR] MySQL not ready within 60s. Please check Docker logs.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto :wait_mysql
:mysql_ok
echo       MySQL ready

rem ========== [3/6] Dependencies ==========
echo [3/6] Checking dependencies ...
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] uv not found. Please install it first: pip install uv
    pause
    exit /b 1
)
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node 18+ first.
    pause
    exit /b 1
)
pushd "%BACKEND%" >nul
uv sync
popd >nul
if not exist "%FRONTEND%\node_modules" (
    echo       First run, installing frontend dependencies ...
    pushd "%FRONTEND%" >nul
    call npm install
    popd >nul
)
echo       Dependencies ready

rem ========== [4/6] Init database ==========
echo [4/6] Initializing database (idempotent: create tables + seed) ...
pushd "%BACKEND%" >nul
uv run python init_db.py
popd >nul

rem ========== [5/6] Start services ==========
echo [5/6] Starting services ...
netstat -ano | findstr "LISTENING" | findstr ":%BACKEND_PORT% " >nul
if %errorlevel% neq 0 (
    start "GuDing-Backend :%BACKEND_PORT%" /D "%BACKEND%" cmd /k uv run uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%
    echo       Backend window started
) else (
    echo       Port %BACKEND_PORT% already in use, reusing existing service
)
netstat -ano | findstr "LISTENING" | findstr ":%FRONTEND_PORT% " >nul
if %errorlevel% neq 0 (
    start "GuDing-Frontend :%FRONTEND_PORT%" /D "%FRONTEND%" cmd /k npm run dev
    echo       Frontend window started
) else (
    echo       Port %FRONTEND_PORT% already in use, reusing existing service
)

rem ========== [6/6] Backend self-check ==========
echo [6/6] Waiting for backend to be ready ...
set /a n=0
:wait_api
curl -s -o nul -m 2 http://127.0.0.1:%BACKEND_PORT%/docs >nul 2>&1
if %errorlevel% equ 0 goto :api_ok
set /a n+=1
if %n% geq 45 (
    echo [ERROR] Backend self-check failed within 90s. Please check the backend window log.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto :wait_api
:api_ok

echo.
echo ==============================================
echo    Startup complete
echo      Frontend  http://localhost:%FRONTEND_PORT%
echo      Backend   http://localhost:%BACKEND_PORT%/docs
echo      Default   admin / admin123
echo    You may close this window; stop services by closing the two service windows
echo ==============================================
if "%~1"=="" pause
exit /b 0
