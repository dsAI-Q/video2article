@echo off
chcp 65001 >nul
title v2a - 视频转公众号文章
cd /d "%~dp0"
echo.
echo  ============================================
echo   v2a 视频转公众号文章 - 本地服务启动中...
echo   浏览器将自动打开 http://127.0.0.1:8765
echo   关闭此窗口即停止服务
echo  ============================================
echo.
where python >nul 2>nul
if %errorlevel%==0 (
    python -m v2a webui
) else (
    "%~dp0python\python.exe" -m v2a webui
)
pause
