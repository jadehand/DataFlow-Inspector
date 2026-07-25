param([string]$BackupPath)

. "$PSScriptRoot\Common.ps1"
$installRoot = Get-DfiInstallRoot

try {
    if ([string]::IsNullOrWhiteSpace($BackupPath)) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = "选择 DataFlow Inspector 备份"
        $dialog.Filter = "ZIP 备份 (*.zip)|*.zip"
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
        $BackupPath = $dialog.FileName
    }
    if (-not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) {
        throw "找不到备份文件：$BackupPath"
    }
    $confirmation = Read-Host "恢复会替换当前数据。请输入 RESTORE 确认"
    if ($confirmation -ne "RESTORE") {
        Write-Host "已取消恢复。"
        exit 0
    }

    $stage = Join-Path $env:TEMP "dfi-restore-$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Expand-Archive -LiteralPath $BackupPath -DestinationPath $stage
    $restoredData = Join-Path $stage "data"
    if (-not (Test-Path -LiteralPath $restoredData -PathType Container)) {
        throw "这不是有效的 DataFlow Inspector 备份：缺少 data 目录。"
    }

    Invoke-DfiLauncher -Arguments @("stop") | Out-Null
    $currentData = Join-Path $installRoot "data"
    $rollback = Join-Path $installRoot "data.before-restore"
    Remove-Item -LiteralPath $rollback -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $currentData) {
        Move-Item -LiteralPath $currentData -Destination $rollback
    }
    try {
        Move-Item -LiteralPath $restoredData -Destination $currentData
        Remove-Item -LiteralPath $rollback -Recurse -Force -ErrorAction SilentlyContinue
    } catch {
        Remove-Item -LiteralPath $currentData -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $rollback) {
            Move-Item -LiteralPath $rollback -Destination $currentData
        }
        throw
    } finally {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
    Invoke-DfiLauncher -Arguments @("start") | Out-Null
    Write-Host "数据恢复完成。" -ForegroundColor Green
} catch {
    Pause-OnError $_.Exception.Message
    exit 1
}

