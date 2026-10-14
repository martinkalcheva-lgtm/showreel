@echo off
chcp 65001 >nul
setlocal
title 电商小二 - 一键启动
cd /d "%~dp0"

echo ============================================================
echo   电商小二  一键启动
echo   项目目录: %CD%
echo ============================================================
echo.

REM ---------- 1/4 MySQL (Docker) ----------
echo [1/4] 启动 MySQL 容器 (端口 3306) ...
where docker >nul 2>nul
if errorlevel 1 (
    echo    [警告] 未找到 docker 命令，跳过 MySQL。请确认已安装并启动 Docker Desktop。
) else (
    pushd "external\docker"
    docker compose up -d
    if errorlevel 1 (
        echo    [警告] MySQL 启动失败，请检查 Docker Desktop 是否在运行。
    ) else (
        echo    等待 3306 端口就绪 ...
        call :wait_port 3306 60
    )
    popd
)
echo.

REM ---------- 2/4 主后端 18082 ----------
echo [2/4] 启动主后端 FastAPI (端口 18082) ...
if not exist ".venv\Scripts\python.exe" (
    echo    [警告] 未找到 .venv\Scripts\python.exe，主后端可能起不来。请先执行: uv sync
) else (
    start "szr-backend-18082" cmd /k ".venv\Scripts\python.exe main.py"
)
echo.

REM ---------- 3/4 电商业务后端 18081 ----------
echo [3/4] 启动电商业务后端 FastAPI (端口 18081) ...
if not exist "external\ecommerce-service-backend\.venv\Scripts\python.exe" (
    echo    [警告] 未找到电商后端的 .venv，可能起不来。请先在其目录执行: uv sync
) else (
    start "szr-commerce-18081" cmd /k "cd /d ""%~dp0external\ecommerce-service-backend"" && .venv\Scripts\python.exe main.py"
)
echo.

REM ---------- 4/4 前端 5173 ----------
echo [4/4] 启动前端 Vite (端口 5173) ...
start "szr-frontend-5173" cmd /k "cd /d ""%~dp0external\customer-service-frontend"" && npm run dev"
echo.

echo 等待前端就绪后自动打开浏览器 ...
call :wait_port 5173 60
start "" "http://127.0.0.1:5173"

echo.
echo ------------------------------------------------------------
echo  启动指令已全部下发，各服务在独立窗口运行。
echo   - 主后端   : http://127.0.0.1:18082/docs
echo   - 电商后端 : http://127.0.0.1:18081/docs
echo   - 前端     : http://127.0.0.1:5173
echo  关闭单个服务：直接关掉它自己的窗口。
echo  全部关闭    ：双击「一键停止.bat」。
echo ------------------------------------------------------------
echo.
pause
exit /b 0

REM ---------- 子过程：等待指定端口就绪 ----------
:wait_port
setlocal enabledelayedexpansion
set "PORT=%~1"
set /a MAX=%~2
set /a N=0
:wait_loop
set /a N+=1
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo    端口 %PORT% 已就绪，用时约 %N% 秒。
    endlocal
    exit /b 0
)
if %N% GEQ %MAX% (
    echo    [警告] 等待端口 %PORT% 超时 %MAX% 秒，继续执行后续步骤。
    endlocal
    exit /b 0
)
timeout /t 1 /nobreak >nul
goto wait_loop
