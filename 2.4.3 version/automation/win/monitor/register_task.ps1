param(
    # 计划任务名称可自定义
    [string]$TaskName = "ZoteroPdf2ZhMonitor"
)

# --- 自动配置 ---
$ProjectRoot       = $PSScriptRoot          # 当前脚本目录
$MonitorScriptPath = Join-Path $ProjectRoot "zotero_monitor.ps1"
# -------------------

if (-not (Test-Path $MonitorScriptPath)) {
    Write-Error "错误: 监控脚本不存在于: $MonitorScriptPath"
    Start-Sleep -Seconds 20
    exit 1
}

try {
    Write-Host "正在配置计划任务 '$TaskName'..."

    # 获取当前用户的标识
    $User = "$env:USERDOMAIN\$env:USERNAME"

    # 1️⃣ 使用最稳定的 COM 接口与任务计划程序交互
    $scheduler = New-Object -ComObject "Schedule.Service"
    $scheduler.Connect()
    $rootFolder = $scheduler.GetFolder("\")

    # 2️⃣ 定义任务动作 (采用双层隐藏技巧，实现终极静默启动)
    $taskDefinition = $scheduler.NewTask(0)
    $action = $taskDefinition.Actions.Create(0) # 0 = Execute
    $action.Path = "powershell.exe"

    # 构造一个复杂的参数，它会启动一个隐藏的PowerShell，这个PowerShell再用Start-Process启动另一个真正运行脚本的、隐藏的PowerShell。
    # 这是目前已知的、最可靠的防止窗口闪烁的方法。
    $finalArgs = "-NoProfile -ExecutionPolicy Bypass -File \`"$MonitorScriptPath\`""
    $action.Arguments = "-WindowStyle Hidden -Command `"Start-Process powershell.exe -ArgumentList '$finalArgs' -WindowStyle Hidden`""

    # 3️⃣ 定义触发器 (登录时)
    $trigger = $taskDefinition.Triggers.Create(9) # 9 = Logon Trigger

    # [!!] 已移除重复执行的设置，脚本只会在用户登录时启动一次
    # $trigger.Repetition.Interval  = "PT1M"
    # $trigger.Repetition.Duration  = "P1D"

    # 4️⃣ 定义负责人 (Principal)
    $taskDefinition.Principal.UserId     = $User
    $taskDefinition.Principal.LogonType  = 3   # Interactive
    # 若需要最高权限请取消下一行注释
    # $taskDefinition.Principal.RunLevel = 1    # Highest available

    # 5️⃣ 定义任务设置
    $settings = $taskDefinition.Settings
    $settings.DisallowStartIfOnBatteries = $false
    $settings.StopIfGoingOnBatteries     = $false
    $settings.ExecutionTimeLimit         = "PT0S" # Unlimited
    $settings.StartWhenAvailable         = $true

    # 远程会话限制（向后兼容）
    if ($settings.PSObject.Properties.Name -contains 'DisallowStartOnRemoteAppSession') {
        $settings.DisallowStartOnRemoteAppSession = $false
    }

    # 6️⃣ 如已存在同名任务先删除
    try {
        $rootFolder.DeleteTask($TaskName, 0)
    } catch {
        # ignore if not exist
    }

    # 7️⃣ 注册任务
    $rootFolder.RegisterTaskDefinition(
        $TaskName,
        $taskDefinition,
        6,       # CreateOrUpdate
        $User,
        $null,
        3        # Interactive logon
    ) | Out-Null

    Write-Host ""
    Write-Host "=================================================================" -ForegroundColor Green
    Write-Host "✅ 计划任务 '$TaskName' 已成功创建。" -ForegroundColor Green
    Write-Host "   它将在您每次登录 Windows 时自动在后台启动一次监控脚本。" -ForegroundColor Yellow
    Write-Host "=================================================================" -ForegroundColor Green

} catch {
    Write-Error "❌ 注册计划任务失败。请检查错误详情并确保有相应权限。"
    Write-Error "   详情: $($_.Exception.Message)"
}
