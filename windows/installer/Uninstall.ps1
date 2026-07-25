param([switch]$DeleteData)

. "$PSScriptRoot\Common.ps1"
$installRoot = Get-DfiInstallRoot

try {
    if ($DeleteData) {
        $confirmation = Read-Host "这会永久删除全部项目和分析结果。请输入 DELETE-DATA 确认"
        if ($confirmation -ne "DELETE-DATA") {
            Write-Host "已取消卸载。"
            exit 0
        }
    }

    try { Invoke-DfiLauncher -Arguments @("stop") | Out-Null } catch {}

    $desktop = [Environment]::GetFolderPath("Desktop")
    $startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "DataFlow Inspector"
    Get-ChildItem -LiteralPath $desktop -Filter "*DataFlow Inspector*.lnk" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $startMenu -Recurse -Force -ErrorAction SilentlyContinue

    Set-Location $env:TEMP
    foreach ($folder in @("app", "runtime", "windows", "run", "logs")) {
        Remove-Item -LiteralPath (Join-Path $installRoot $folder) -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($DeleteData) {
        Remove-Item -LiteralPath (Join-Path $installRoot "data") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "DataFlow Inspector 及全部本地数据已删除。" -ForegroundColor Green
    } else {
        $notice = Join-Path $installRoot "数据已保留.txt"
        "DataFlow Inspector 已卸载。项目数据仍保存在本目录的 data 文件夹中。重新安装即可继续使用。" |
            Set-Content -LiteralPath $notice -Encoding UTF8
        Write-Host "程序已卸载，项目数据仍保存在：$(Join-Path $installRoot 'data')" -ForegroundColor Green
        Write-Host "重新安装即可继续使用。"
    }
} catch {
    Pause-OnError $_.Exception.Message
    exit 1
}

