@echo off
rem ============================================================
rem  v2a - one-click setup for Windows
rem  Detects Python, then runs install.py in non-interactive mode
rem  to install dependencies + portable ffmpeg + config.yaml.
rem ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === v2a setup (Windows) ===
echo.

rem --- find python ---
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
  where py >nul 2>&1 && set "PY=py"
)
if not defined PY (
  echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo         and check "Add python.exe to PATH", then re-run this file.
  pause
  exit /b 1
)

rem --- check version ---
%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python too old ^(need 3.10+^). Please upgrade Python.
  pause
  exit /b 1
)
echo [OK] Python found: 
%PY% --version

echo.
echo Running install.py --yes ... ^(this installs dependencies, may take a few minutes^)
echo.
%PY% install.py --yes
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo === Setup finished. Next: ===
  echo   set LLM_API_KEY=sk-xxxx
  echo   python -m v2a video your_video.mp4 --style tutorial
) else (
  echo === Setup finished with warnings ^(see messages above^). ===
)
pause
exit /b %RC%
