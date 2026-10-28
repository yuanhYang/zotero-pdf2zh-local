@echo off
chcp 65001 >nul
REM Windows 批处理脚本：被右键菜单调用，用于翻译选定的 PDF 文件。

REM =================================================================
REM === 配置区 (在这里修改你的常用翻译参数)
REM =================================================================

REM ---1.你的Python 拟环境的名称(通常无需修改)---
set "VENV_NAME=.venv"

REM 你可以从下面的示例中选择一个并取消注释 (删掉前面的 REM)，或者自己组合。留空则不添加任何额外参数。
set "PDF2ZH_OPTIONS="

REM --- 示例：使用指定的配置文件 ---
REM set "PDF2ZH_OPTIONS=--config-file "./config.toml""


REM =================================================================
REM === 自动配置 (以下部分通常无需修改)
REM =================================================================
set "PROJECT_PATH=%~dp0"
set "PYTHON_CLIENT_SCRIPT=%PROJECT_PATH%translate_pdf_client.py"
set "PYTHON_PATH="

REM --- Python 环境查找逻辑 ---
if exist "%PROJECT_PATH%%VENV_NAME%\Scripts\python.exe" (
    set "PYTHON_PATH=%PROJECT_PATH%%VENV_NAME%\Scripts\python.exe"
    goto :FoundPython
)
if exist "%USERPROFILE%\miniconda3\envs\%VENV_NAME%\python.exe" (
    set "PYTHON_PATH=%USERPROFILE%\miniconda3\envs\%VENV_NAME%\python.exe"
    goto :FoundPython
)
if exist "%USERPROFILE%\anaconda3\envs\%VENV_NAME%\python.exe" (
    set "PYTHON_PATH=%USERPROFILE%\anaconda3\envs\%VENV_NAME%\python.exe"
    goto :FoundPython
)

:FoundPython
if "%PYTHON_PATH%"=="" (
    echo. & echo [错误] 找不到名为 "%VENV_NAME%" 的 Python 环境。
    timeout /t 30 >nul & exit /b 1
)
if "%~1"=="" (
    echo [错误] 未提供 PDF 文件路径。
    timeout /t 10 >nul & exit /b 1
)

REM =================================================================
REM === 调用 Python 翻译客户端
REM =================================================================
echo.
echo --------------------------------------------------
echo   PDF 翻译任务已启动 (可按 Ctrl+C 中断)
echo --------------------------------------------------
echo.
echo   - Python 环境: %PYTHON_PATH%
echo   - 正在处理文件: %~1
echo   - 使用的额外参数: %PDF2ZH_OPTIONS%
echo.
echo   --- pdf2zh 实时输出如下 ---
echo.

REM --- 执行翻译 (直接调用以显示实时进度) ---
"%PYTHON_PATH%" "%PYTHON_CLIENT_SCRIPT%" "%~1" %PDF2ZH_OPTIONS%
set "EXIT_CODE=%ERRORLEVEL%"

REM =================================================================
REM === 任务结束反馈
REM =================================================================
echo.
echo --------------------------------------------------
if %EXIT_CODE% equ 0 (
    echo [成功] 任务已顺利完成！
) else (
    echo [提示] 任务被中断或出现错误 (退出代码: %EXIT_CODE%)
)
echo --------------------------------------------------
echo.
echo 按任意键关闭此窗口...
pause >nul
exit /b %EXIT_CODE%