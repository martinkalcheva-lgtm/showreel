@echo off
chcp 65001 >nul
title 一键关闭全部项目服务
echo ================================================
echo    一键关闭所有项目服务（不关电脑）
echo ================================================
echo.
echo [1/4] 结束本地端口进程（18777 代理 / 18082 客服后端 / 3000 电商前端 / 5173 问数前端）...
for %%P in (18777 18082 3000 5173) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P .*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
  )
)

echo [2/4] 停止客服 MySQL 容器...
docker stop customer-service-mysql >nul 2>&1

echo [3/4] 调用电商运营助手的 stop_ec.bat...
if exist "D:\python_student\ecommerce-operation-assistant\stop_ec.bat" (
  call "D:\python_student\ecommerce-operation-assistant\stop_ec.bat"
) else (
  echo   未找到 stop_ec.bat，跳过。
)

echo [4/4] 调用问数与智库的 stop_boss.bat...
if exist "C:\Users\gbb\Desktop\stady_all\xm\b_w\stop_boss.bat" (
  call "C:\Users\gbb\Desktop\stady_all\xm\b_w\stop_boss.bat"
) else (
  echo   未找到 stop_boss.bat，跳过。
)

echo.
echo 全部服务已关闭。
timeout /t 4 >nul
