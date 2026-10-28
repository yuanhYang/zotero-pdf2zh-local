@echo off
chcp 65001 >nul
REM Windows 批处理脚本：被右键菜单调用，用于翻译选定的 PDF 文件。
REM 脚本会自动检测路径，并优先使用 uv 环境。

REM === 配置区 (通常只需修改这里的环境名称) ===
REM 你的 uv 或 Conda 虚拟环境的名称
set "VENV_NAME=.venv"

REM === 自动配置 (无需修改) ===
REM 自动获取项目根路径 (即此 .cmd 文件所在的目录)
set "PROJECT_PATH=%~dp0"
REM 翻译客户端脚本的完整路径
set "PYTHON_CLIENT_SCRIPT=%PROJECT_PATH%translate_pdf_client.py"


REM === 查找 Python 可执行文件 (智能检测) ===
set "PYTHON_PATH="

REM --- 1. 优先查找项目目录内的 uv 环境 ---
if exist "%PROJECT_PATH%%VENV_NAME%\Scripts\python.exe" (
    set "PYTHON_PATH=%PROJECT_PATH%%VENV_NAME%\Scripts\python.exe"
)

REM --- 2. 如果找不到 uv, 则回退查找 Conda 环境 ---
if "%PYTHON_PATH%"=="" (
    if exist "%USERPROFILE%\miniconda3\envs\%VENV_NAME%\python.exe" set "PYTHON_PATH=%USERPROFILE%\miniconda3\envs\%VENV_NAME%\python.exe"
    if exist "%USERPROFILE%\anaconda3\envs\%VENV_NAME%\python.exe" set "PYTHON_PATH=%USERPROFILE%\anaconda3\envs\%VENV_NAME%\python.exe"
    if exist "C:\ProgramData\Anaconda3\envs\%VENV_NAME%\python.exe" set "PYTHON_PATH=C:\ProgramData\Anaconda3\envs\%VENV_NAME%\python.exe"
    if exist "C:\ProgramData\miniconda3\envs\%VENV_NAME%\python.exe" set "PYTHON_PATH=C:\ProgramData\miniconda3\envs\%VENV_NAME%\python.exe"
)

REM --- 检查最终是否找到 Python ---
if "%PYTHON_PATH%"=="" (
    echo.
    echo [错误] 找不到名为 "%VENV_NAME%" 的 Python 环境。
    echo.
    echo 请检查:
    echo 1. 虚拟环境名称是否正确。
    echo 2. 是否已在项目目录中创建了 uv 环境，或已安装了 Conda 环境。
    echo.
    echo 此窗口将在30秒后自动关闭...
    timeout /t 30 >nul
    exit /b 1
)


REM === 检查输入参数 ===
if "%~1"=="" (
    echo [错误] 未提供 PDF 文件路径。
    timeout /t 10 >nul
    exit /b 1
)


REM === 调用 Python 翻译客户端 ===
echo 正在调用翻译脚本...
"%PYTHON_PATH%" "%PYTHON_CLIENT_SCRIPT%" "%~1"

exit /b %ERRORLEVEL%