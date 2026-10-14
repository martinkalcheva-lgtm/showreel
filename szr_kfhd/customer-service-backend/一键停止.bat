@echo off
chcp 65001 >nul
setlocal
title 电商小二 - 一键停止
cd /d "%~dp0"

echo ============================================================
echo   电商小二  一键停止
echo ============================================================
echo.

echo [1/2] 关闭服务窗口 ...
for %%T in (szr-backend-18082 szr-commerce-18081 szr-frontend-5173) do (
    taskkill /FI "WINDOWTITLE eq %%T*" /T /F >nul 2>nul
)

echo [2/2] 按端口清理残留进程 ...
for %%P in (18081 18082 5173) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        echo    结束占用端口 %%P 的进程 PID=%%A
        taskkill /F /PID %%A >nul 2>nul
    )
)

echo.
echo 服务已停止。MySQL 容器默认保留，未停止。
echo  如需一并停止 MySQL：进入 external\docker 执行  docker compose stop
echo.
pause
exit /b 0
