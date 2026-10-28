# --- 脚本启动时，首先会输出自身的 PID，方便手动调试 ---
$MonitorPid = $PID
Write-Output "监控脚本启动，自身 PID 为: $MonitorPid"

# --- 用户配置 (只需修改这里) ---
# 虚拟环境名称 (你的 uv 或 Conda 环境名)
$VenvName = ".venv"
# --------------------------------

# --- 自动配置 (通常无需修改) ---
# 项目根目录 (自动获取脚本所在目录，无需手动设置)
$ProjectPath = $PSScriptRoot
# 日志目录
$LogDir      = Join-Path $ProjectPath "logs"
$MonitorLog  = Join-Path $LogDir "monitor.log"
$ServerLog   = Join-Path $LogDir "server.log"
# Python 服务脚本
$ServerScript = "server.py"
# 监听端口
$ServerPort   = 8888
# --------------------------------

# PowerShell 控制台与管道编码为 UTF-8（防止日志乱码）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8

# 创建日志目录
if (-not (Test-Path $LogDir)) {
    try { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
    catch {}
}

function Log-Message {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line      = "[$timestamp] $Message"
    # [!!] 确保在手动运行时，日志会同时输出到控制台和文件
    Write-Output $line
    try {
        # 始终按 UTF-8 追加监控日志
        Add-Content -Path $MonitorLog -Value $line -Encoding utf8
    } catch {}
}

function Send-Notification {
    param([string]$Title, [string]$Message)
    try {
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $toastXml  = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
                        [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $toastXml.GetElementsByTagName("text")
        $textNodes.Item(0).InnerText = $Title
        $textNodes.Item(1).InnerText = $Message
        $toast    = [Windows.UI.Notifications.ToastNotification]::new($toastXml)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ZoteroPDF2ZH")
        $notifier.Show($toast)
    } catch {
        Log-Message "通知: $Title - $Message"
    }
}

function Is-ServerRunning {
    return (Get-NetTCPConnection -State Listen -LocalPort $ServerPort -ErrorAction SilentlyContinue) -ne $null
}

function Is-ZoteroRunning {
    return (Get-Process -Name "zotero" -ErrorAction SilentlyContinue) -ne $null
}

function Start-Server {
    Log-Message "尝试启动 Python 服务器..."
    $pythonExe = $null

    # 1. 检测 uv 虚拟环境
    $uvPythonPath = Join-Path -Path $ProjectPath -ChildPath "$VenvName\Scripts\python.exe"
    if (Test-Path $uvPythonPath) {
        $pythonExe = $uvPythonPath
        Log-Message "检测到 uv 环境: $pythonExe"
    } else {
        # 2. 回退检测 Conda 环境
        Log-Message "未找到 uv 环境，正在尝试搜索 Conda 环境..."
        $condaPaths = @(
            "$env:USERPROFILE\miniconda3\envs\$VenvName\python.exe",
            "$env:USERPROFILE\anaconda3\envs\$VenvName\python.exe",
            "C:\\ProgramData\\miniconda3\\envs\\$VenvName\\python.exe",
            "C:\\ProgramData\\Anaconda3\\envs\\$VenvName\\python.exe"
        )
        foreach ($path in $condaPaths) {
            if (Test-Path $path) {
                $pythonExe = $path
                Log-Message "检测到 Conda 环境: $pythonExe"
                break
            }
        }
    }

    if (-not $pythonExe) {
        $errorMessage = "错误: 找不到 Python 解释器。请检查虚拟环境 '$VenvName' 是否存在且路径正确。"
        Log-Message $errorMessage
        Send-Notification "Zotero PDF2ZH 错误" $errorMessage
        return
    }

    if (Is-ServerRunning) {
        Log-Message "错误: 端口 $ServerPort 已被占用，无法启动服务。"
        Send-Notification "Zotero PDF2ZH 错误" "❌ 端口 $ServerPort 已被占用"
        return
    }

    $serverScriptPath = Join-Path $ProjectPath $ServerScript

    # 使用 CMD.EXE 替代 PowerShell 包装器来启动服务
    $command = "set PYTHONUTF8=1 && `"$pythonExe`" -X utf8 -u `"$serverScriptPath`" $ServerPort > `"$ServerLog`" 2>&1"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c $command" -WindowStyle Hidden -WorkingDirectory $ProjectPath

    # 等待片刻，让服务器启动
    Start-Sleep -Seconds 4

    # 检查服务是否已在端口上启动
    if (Is-ServerRunning) {
        Log-Message "服务器已在端口 $ServerPort 上成功启动。其输出已被记录到 logs/server.log"
        Send-Notification "Zotero PDF2ZH" "✅ PDF 翻译服务已启动"
    } else {
        Log-Message "错误: 服务器未能成功启动。请检查 logs/server.log 文件获取详细错误信息。"
        Send-Notification "Zotero PDF2ZH 错误" "❌ PDF 翻译服务启动失败"
    }
}

function Stop-Server {
    Log-Message "正在尝试停止占用端口 $ServerPort 的服务..."
    $connection = Get-NetTCPConnection -State Listen -LocalPort $ServerPort -ErrorAction SilentlyContinue

    if ($connection) {
        $pid_to_stop = $connection.OwningProcess
        Log-Message "找到占用端口 $ServerPort 的进程，其 PID 为: $pid_to_stop"

        # 安全锁：检查是否要停止的进程是监控脚本自身
        if ($pid_to_stop -eq $MonitorPid) {
            Log-Message "!!! 致命逻辑错误：要停止的进程 (PID: $pid_to_stop) 正是监控脚本自身！操作已取消。"
            Send-Notification "Zotero PDF2ZH 严重错误" "监控脚本试图自我关闭，操作已被阻止。"
            return
        }

        Log-Message "正在强制停止进程 (PID: $pid_to_stop)..."
        Stop-Process -Id $pid_to_stop -Force -ErrorAction SilentlyContinue

        Start-Sleep -Seconds 1
        if (-not (Get-Process -Id $pid_to_stop -ErrorAction SilentlyContinue)) {
            Log-Message "服务 (PID: $pid_to_stop) 已成功停止。"
            Send-Notification "Zotero PDF2ZH" "🔌 PDF 翻译服务已停止"
        } else {
            Log-Message "警告: 未能停止进程 (PID: $pid_to_stop)。"
        }
    } else {
        Log-Message "端口 $ServerPort 未被占用，无需停止。"
    }
}

function Perform-MonitorCheck {
    Log-Message "--- 开始监控检查 ---"
    if (Is-ZoteroRunning) {
        Log-Message "Zotero 正在运行。"
        if (-not (Is-ServerRunning)) {
            Log-Message "检测到服务器未运行，正在启动..."
            Start-Server
        } else {
            Log-Message "服务器也正在运行，状态正常。"
        }
    } else {
        Log-Message "Zotero 未运行。"
        if (Is-ServerRunning) {
            Log-Message "检测到服务器仍在运行，正在停止..."
            Stop-Server
        } else {
            Log-Message "服务器也未运行，状态正常。"
        }
    }
    Log-Message "--- 监控检查结束 ---"
}

# --- 10 秒级循环监控 ---
while ($true) {
    Perform-MonitorCheck
    Start-Sleep -Seconds 10
}