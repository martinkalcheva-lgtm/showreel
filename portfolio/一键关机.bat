@echo off
chcp 65001 >nul
title 一键关机
echo ================================================
echo    G 的一键关机
echo ================================================
echo.
echo  确认后 30 秒电脑将关闭，期间可随时双击
echo  同目录的「一键取消关机.bat」反悔。
echo.
choice /C YN /M "确定要关机吗 [Y=关机 / N=算了]"
if errorlevel 2 (
  echo 已取消，电脑不会关。
  timeout /t 2 >nul
  exit
)
shutdown /s /t 30
echo.
echo 已安排 30 秒后关机。反悔请立刻双击「一键取消关机.bat」。
timeout /t 5 >nul
