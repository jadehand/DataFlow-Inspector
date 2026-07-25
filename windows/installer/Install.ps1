param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "DataFlow Inspector")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-Shortcut {
    param([string]$Path, [string]$ScriptPath, [string]$WorkingDirectory)
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,14"
    $shortcut.Save()
}

try {
    $packageRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $packageRoot = (Resolve-Path -LiteralPath $packageRoot).Path
    $installFull = [IO.Path]::GetFullPath($InstallDir)
    if ($installFull.TrimEnd("\") -eq $packageRoot.TrimEnd("\")) {
        throw "不能直接在安装包目录内安装，请保留默认安装位置。"
    }

    foreach ($folder in @("app", "runtime", "windows")) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $folder) -PathType Container)) {
            throw "安装包不完整：缺少 $folder 目录。请重新下载并完整解压。"
        }
    }

    Write-Host "正在安装 DataFlow Inspector 到：$installFull"
    New-Item -ItemType Directory -Force -Path $installFull | Out-Null

    # Stop an older installation before replacing program files. User data is never removed here.
    $oldExe = Join-Path $installFull "windows\DataFlowInspector.exe"
    if (Test-Path -LiteralPath $oldExe -PathType Leaf) {
        $env:DFI_LOCAL_APPDATA = $installFull
        $env:DFI_INSTALL_ROOT = Join-Path $installFull "app"
        & $oldExe stop 2>$null
    }

    foreach ($folder in @("app", "runtime", "windows")) {
        $target = Join-Path $installFull $folder
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        Copy-Item -LiteralPath (Join-Path $packageRoot $folder) -Destination $target -Recurse -Force
    }

    foreach ($file in @("README-Windows.md", "版本说明.md")) {
        $source = Join-Path $packageRoot $file
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $installFull $file) -Force
        }
    }

    . (Join-Path $installFull "windows\installer\Common.ps1")
    $null = Get-DfiLauncher -InstallRoot $installFull

    $desktop = [Environment]::GetFolderPath("Desktop")
    $startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "DataFlow Inspector"
    New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
    $items = @(
        @{ Name = "启动 DataFlow Inspector"; Script = "Start.ps1" },
        @{ Name = "停止 DataFlow Inspector"; Script = "Stop.ps1" },
        @{ Name = "备份 DataFlow Inspector"; Script = "Backup.ps1" },
        @{ Name = "恢复 DataFlow Inspector"; Script = "Restore.ps1" },
        @{ Name = "卸载 DataFlow Inspector（保留数据）"; Script = "Uninstall.ps1" }
    )
    foreach ($item in $items) {
        $scriptPath = Join-Path $installFull ("windows\installer\" + $item.Script)
        New-Shortcut -Path (Join-Path $startMenu ($item.Name + ".lnk")) -ScriptPath $scriptPath -WorkingDirectory $installFull
        New-Shortcut -Path (Join-Path $desktop ($item.Name + ".lnk")) -ScriptPath $scriptPath -WorkingDirectory $installFull
    }

    Write-Host ""
    Write-Host "安装完成。无需管理员权限，也不需要 Docker。" -ForegroundColor Green
    Write-Host "业务数据将保存在：$(Join-Path $installFull 'data')"
    exit 0
} catch {
    Write-Host ""
    Write-Host "[安装失败] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
