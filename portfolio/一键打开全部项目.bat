@echo off
chcp 65001 >nul
title ALL-in-one launcher
echo ==============================================
echo  ALL modules one-click launcher
echo  ----------------------------------------
echo  1) BOSS wenshu-zhiku -> http://localhost:5173
echo  2) EC ecommerce      -> http://localhost:3000
echo  ----------------------------------------
echo  Requirement: Docker Desktop must be running.
echo ==============================================
echo.
echo [1/4] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] Docker Desktop is NOT running.
  echo Please open Docker Desktop first, wait until the
  echo whale icon in the taskbar stops animating,
  echo then double-click this file again.
  echo.
  pause
  exit /b 1
)
echo       Docker OK.
echo.
echo [2/4] Launching BOSS module (mongo/minio/qdrant/es/
echo       milvus + kb services + portal)...
start "boss-launcher" cmd /c "call C:\Users\gbb\Desktop\stady_all\xm\b_w\start_boss.bat"
echo.
echo [3/4] Launching EC module (mysql/redis/checkpoints
echo       + api + web)...
start "ec-launcher" cmd /c "call D:\python_student\ecommerce-operation-assistant\start_ec.bat"
echo.
echo [4/4] Waiting 35s for pages to warm up...
echo       (browsers will open by themselves)
timeout /t 35 /nobreak >nul
echo.
echo ==============================================
echo  ALL modules started.
echo  - wenshu-zhiku : http://localhost:5173
echo  - ecommerce    : http://localhost:3000
echo  Close the black service windows to stop them.
echo ==============================================
timeout /t 15 /nobreak >nul
