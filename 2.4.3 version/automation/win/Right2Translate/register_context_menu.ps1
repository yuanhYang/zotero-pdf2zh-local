[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# region === 自动配置 ===
$ProjectRoot   = $PSScriptRoot
$CmdScriptPath = Join-Path $ProjectRoot 'translate_pdf_context.cmd'
$MenuName      = '翻译为双语PDF'
$RegKey        = 'Registry::HKEY_CLASSES_ROOT\SystemFileAssociations\.pdf\shell\TranslateToDualPdf'
# endregion

Write-Verbose "项目根目录: $ProjectRoot"
Write-Verbose "批处理脚本: $CmdScriptPath"

# 检查批处理脚本是否存在
if (-not (Test-Path -LiteralPath $CmdScriptPath)) {
    Write-Error "未在目录中找到 translate_pdf_context.cmd，脚本终止。"
}

# 主流程
try {
    Write-Host '正在创建右键菜单项，请稍候…'

    # 创建主键
    if (-not (Test-Path $RegKey)) {
        New-Item -Path $RegKey -Force | Out-Null
        Write-Verbose "已创建注册表键: $RegKey"
    }

    # 设置显示名称
    Set-ItemProperty -Path $RegKey -Name '(default)' -Value $MenuName -Force
    Write-Verbose "设置菜单显示名称: $MenuName"

    # 可选：设置图标
    # Set-ItemProperty -Path $RegKey -Name 'Icon' -Value 'imageres.dll,70' -Force

    # 创建 command 子键并写入调用
    $CommandKey = Join-Path $RegKey 'command'
    if (-not (Test-Path $CommandKey)) {
        New-Item -Path $CommandKey -Force | Out-Null
    }

    $CommandValue = "`"$CmdScriptPath`" `"%1`""
    Set-ItemProperty -Path $CommandKey -Name '(default)' -Value $CommandValue -Force
    Write-Verbose "写入 command: $CommandValue"

    Write-Host ''
    Write-Host "✅ 成功！右键菜单 “$MenuName” 已创建。" -ForegroundColor Green
    Write-Host '如果菜单暂未出现，可重启文件资源管理器 (explorer) 或注销后重新登录。'

} catch {
    Write-Error "❌ 失败: 创建右键菜单时发生错误。详情: $($_.Exception.Message)"
    exit 1
}
