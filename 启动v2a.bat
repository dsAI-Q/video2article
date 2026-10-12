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

REM 1) embedded python (portable bundle)
if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" -m v2a webui
    goto :end
)

REM 2) system python
where python >nul 2>nul
if %errorlevel%==0 (
    python -c "import fastapi" >nul 2>nul
    if %errorlevel%==0 (
        python -m v2a webui
    ) else (
        echo [v2a] 首次运行，正在自动安装依赖...
        python install.py --yes
        python -m v2a webui
    )
    goto :end
)

echo [错误] 未找到 Python。请安装 Python 3.10+ 并勾选 "Add to PATH"。
echo        下载地址: https://www.python.org/downloads/
pause

:end
pause
