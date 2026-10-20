@echo off
setlocal
set "ROOT=%~dp0"
set "TMP=%ROOT%.tmp"
set "TEMP=%ROOT%.tmp"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%ROOT%"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
"%PYTHON%" -m pytest -q %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%