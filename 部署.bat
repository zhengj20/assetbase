@echo off
setlocal EnableExtensions
title GuDing Asset System - Deploy

set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"
set "BACKEND_PORT=5200"
set "FRONTEND_PORT=5201"

echo ==============================================
echo    GuDing Asset System - Deploy
echo ==============================================
echo.

rem ========== [1/5] Check dependencies ==========
echo [1/5] Checking dependencies ...
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
echo       Dependencies ready

rem ========== [2/5] Install dependencies ==========
echo [2/5] Installing project dependencies ...
pushd "%BACKEND%" >nul
uv sync
popd >nul
if not exist "%FRONTEND%\node_modules" (
    echo       First run, installing frontend dependencies ...
    pushd "%FRONTEND%" >nul
    call npm install
    popd >nul
)
echo       Dependencies installed

rem ========== [3/5] Init database ==========
echo [3/5] Initializing database ...
pushd "%BACKEND%" >nul
uv run python init_db.py
popd >nul
echo       Database initialized

rem ========== [4/5] Build frontend ==========
echo [4/5] Building frontend static files ...
pushd "%FRONTEND%" >nul
call npm run build
popd >nul
echo       Frontend built

rem ========== [5/5] Start service ==========
echo [5/5] Starting backend service ...
netstat -ano | findstr "LISTENING" | findstr ":%BACKEND_PORT% " >nul
if %errorlevel% neq 0 (
    start "GuDing-Backend" /D "%BACKEND%" cmd /k uv run uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --workers 4
    echo       Backend started
) else (
    echo       Port %BACKEND_PORT% already in use, reusing existing service
)

echo.
echo ==============================================
echo    Deploy complete
echo.
echo    Local access:
echo      http://localhost:%BACKEND_PORT%/docs
echo.
echo    External access:
echo      http://YOUR_PUBLIC_IP:%BACKEND_PORT%/docs
echo.
echo    Please make sure:
echo      1. Firewall allows port %BACKEND_PORT%
echo      2. Cloud security group has an inbound rule for %BACKEND_PORT%
echo.
echo    Frontend static files are at:
echo      %FRONTEND%\dist
echo    Host them with Nginx or access the backend API directly
echo ==============================================
echo.
if "%~1"=="" pause
exit /b 0
