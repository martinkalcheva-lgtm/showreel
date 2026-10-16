@echo off
chcp 65001 >nul
title ALL-in-one launcher

echo ==================================================
echo   ALL MODULES - ONE CLICK LAUNCHER
echo --------------------------------------------------
echo   [BOSS] wenshu-zhiku  -^> http://localhost:5173
echo   [EC]   ecommerce     -^> http://localhost:3000
echo   [KEFU] xiaoer        -^> http://localhost:18082
echo   [KB]   wenshu-zhiku  -^> http://localhost:7954/chat.html
echo --------------------------------------------------
echo   BOSS backend : data-agent  on 8002
echo   EC   backend : api         on 8010
echo   KEFU backend : fastapi     on 18083
echo   Requirement  : Docker Desktop must be running
echo ==================================================
echo.

echo [1/7] Checking Docker Desktop ...
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo   [ERROR] Docker Desktop is NOT running.
  echo   Open Docker Desktop, wait until the whale icon
  echo   stops animating, then double-click this file again.
  echo.
  pause
  exit /b 1
)
echo       Docker OK.
echo.

echo [2/7] Launching BOSS module
echo       ^(docker deps + data-agent:8002 + portal:5173^) ...
if not exist "C:\Users\gbb\Desktop\stady_all\xm\b_w\start_boss.bat" (
  echo       [ERROR] start_boss.bat not found. Skipped.
) else (
  start "boss-launcher" /D "C:\Users\gbb\Desktop\stady_all\xm\b_w" cmd /k start_boss.bat
  echo       Launch command sent.
)
echo.

echo [3/7] Launching EC module
echo       ^(docker deps + api:8010 + web:3000^) ...
if not exist "D:\python_student\ecommerce-operation-assistant\start_ec.bat" (
  echo       [ERROR] start_ec.bat not found. Skipped.
) else (
  start "ec-launcher" /D "D:\python_student\ecommerce-operation-assistant" cmd /k start_ec.bat
  echo       Launch command sent.
)
echo.

echo [4/7] Launching KEFU module
echo       ^(docker mysql:3308 + commerce:18081 + backend:18083 + web:18082^) ...
if not exist "%~dp0..\szr_kfhd\customer-service-backend\main.py" (
  echo       [ERROR] KEFU backend not found. Skipped.
) else (
  start "kefu-mysql" /D "%~dp0..\szr_kfhd\customer-service-backend\external\docker" cmd /k "docker compose up -d"
  start "kefu-backend" /D "%~dp0..\szr_kfhd\customer-service-backend" cmd /k ".venv\Scripts\python.exe main.py"
  start "kefu-commerce" /D "%~dp0..\szr_kfhd\customer-service-backend\external\ecommerce-service-backend" cmd /k ".venv\Scripts\python.exe main.py"
  start "kefu-frontend" /D "%~dp0..\szr_kfhd\customer-service-backend\external\customer-service-frontend" cmd /k npm run dev
  echo       Launch commands sent.
)
echo.

echo [5/7] Launching KB module
echo       ^(kb query:7954 live + kb import:7955^) ...
if not exist "C:\Users\gbb\Desktop\stady_all\xm\b_w\knowledge_base\web\api\query_service.py" (
  echo       [ERROR] knowledge_base not found. Skipped.
) else (
  start "kb-query-7954" /D "C:\Users\gbb\Desktop\stady_all\xm\b_w\knowledge_base" cmd /k ".venv\Scripts\python.exe -m uvicorn web.api.query_service:app --port 7954"
  start "kb-import-7955" /D "C:\Users\gbb\Desktop\stady_all\xm\b_w\knowledge_base" cmd /k ".venv\Scripts\python.exe -m uvicorn web.api.import_service:app --port 7955"
  echo       Launch commands sent.
)
echo.

echo [6/7] Waiting 45s for services to warm up ...
timeout /t 45 /nobreak >nul
echo.

echo [7/7] Port self-check ...
call :CHK 8002 "BOSS backend  data-agent"
call :CHK 5173 "BOSS frontend portal"
call :CHK 8010 "EC   backend  api"
call :CHK 3000 "EC   frontend web"
call :CHK 18083 "KEFU backend  fastapi"
call :CHK 18082 "KEFU frontend web"
call :CHK 7954 "KB   chat     query"
call :CHK 7955 "KB   import   service"
echo.
echo ==================================================
echo   Any [X] line means that service did NOT start.
echo   Check the matching black window for the reason.
echo   A "bind error" is harmless - it only means the
echo   service was already running; just close it.
echo ==================================================
echo.
echo   Opening browsers in 5s ...
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"
start "" "http://localhost:3000"
start "" "http://localhost:18082"
start "" "http://localhost:7954/chat.html"
timeout /t 8 /nobreak >nul
exit /b

:CHK
netstat -ano | findstr ":%~1 " | findstr "LISTENING" >nul
if errorlevel 1 (
  echo   [X]  %~2  ^(port %~1^)
) else (
  echo   [OK] %~2  ^(port %~1^)
)
exit /b
