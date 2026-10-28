@echo off
chcp 65001 >nul
title Zotero PDF2zh Server
cd /d "%~dp0"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo ============================================================
echo   Zotero PDF2zh Server
echo ============================================================
echo.
echo   [1] venv mode   - use the existing venv folder (fast start)
echo   [2] uv mode     - uv run, builds its own env on first use
echo.
echo   Press ENTER for [1] venv mode, or 2 for uv mode.
echo.

set "MODE="
set /p "MODE=Select mode [1]: "
if "%MODE%"=="" set "MODE=1"

if "%MODE%"=="1" goto venv_mode
if "%MODE%"=="2" goto uv_mode
echo.
echo [ERROR] Invalid choice "%MODE%". Please enter 1 or 2.
pause
exit /b 2

:venv_mode
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [ERROR] venv not found: %~dp0venv\Scripts\python.exe
    echo.
    echo Create it once with:
    echo     uv venv venv --python 3.12
    echo     uv pip install --python venv\Scripts\python.exe -r requirements.txt
    echo.
    echo Or choose [2] uv mode, which manages its own environment.
    pause
    exit /b 1
)
echo.
echo [venv] Starting server with venv\Scripts\python.exe ...
echo.
"venv\Scripts\python.exe" server.py %*
goto finished

:uv_mode
where uv >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] uv not found on PATH.
    echo.
    echo Install it with:
    echo     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    echo.
    echo Then reopen this window, or choose [1] venv mode instead.
    pause
    exit /b 1
)
echo.
echo [uv] Starting server with uv run ...
echo      The first run downloads dependencies and may take a few minutes.
echo.
uv run --python 3.12 --with-requirements requirements.txt server.py %*
goto finished

:finished
echo.
echo ============================================================
echo Server stopped. Press any key to close this window.
echo ============================================================
pause >nul
