@echo off
title Octop Server (port 8088)
cd /d D:\python_student\octop_two
set OCTOP_BIND_HOST=0.0.0.0
".venv\Scripts\octop.exe" run
echo.
echo Server exited. Press any key to close.
pause >nul
