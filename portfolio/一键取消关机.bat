@echo off
chcp 65001 >nul
title 一键取消关机
shutdown /a >nul 2>&1
if %errorlevel%==0 (
  echo 已取消关机计划，电脑不会关了。
) else (
  echo 当前没有进行中的关机计划。
)
timeout /t 3 >nul
