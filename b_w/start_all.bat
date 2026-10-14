@echo off
title B_W Portal Launcher
echo ==============================================
echo  Boss Workbench launcher - 4 services
echo  1) kb import   -^> http://localhost:8000
echo  2) kb query    -^> http://localhost:8001
echo  3) data-agent  -^> http://localhost:8002
echo  4) portal web  -^> http://localhost:5173
echo.
echo  Close a window to stop that service.
echo  If a port is already in use, that service
echo  is probably running already - ignore it.
echo ==============================================
start "1-kb-import-8000" cmd /k "cd /d C:\Users\gbb\Desktop\stady_all\xm\b_w\knowledge_base && .venv\Scripts\python.exe -m web.api.import_service"
start "2-kb-query-8001" cmd /k "cd /d C:\Users\gbb\Desktop\stady_all\xm\b_w\knowledge_base && .venv\Scripts\python.exe -m web.api.query_service"
start "3-data-agent-8002" cmd /k "cd /d C:\Users\gbb\Desktop\stady_all\xm\b_w\ws\data-agent && .venv\Scripts\python.exe -m uvicorn main:app --port 8002"
start "4-portal-5173" cmd /k "cd /d C:\Users\gbb\Desktop\stady_all\xm\b_w\portal && npm run dev"
timeout /t 8 /nobreak >nul
start http://localhost:5173
