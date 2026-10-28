# Windows PowerShell 脚本：移除“翻译为双语PDF”右键菜单

# --- 参数（无需改动） ---
$KeyPath = "Registry::HKEY_CLASSES_ROOT\SystemFileAssociations\.pdf\shell\TranslateToDualPdf"

# --- 检查管理员权限 ---
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning '错误：此脚本需要以管理员身份运行才能修改注册表。'
    Read-Host  '按 Enter 键退出...'
    exit 1
}

Write-Host '正在移除右键菜单项...'

# --- 主逻辑 ---
if (Test-Path $KeyPath) {
    try {
        Remove-Item -Path $KeyPath -Recurse -Force
        Write-Host "`n✅ 已成功移除。"
        Write-Host '如菜单仍可见，请重启文件资源管理器或注销后重新登录。'
    } catch {
        Write-Error '❌ 删除注册表键时发生错误。'
        Write-Error "错误详情：$($_.Exception.Message)"
    }
} else {
    Write-Host "`n🟡 未找到目标键，可能已被删除。" -ForegroundColor Yellow
}

Write-Host ''
Read-Host '操作完成，按 Enter 键退出...'
