Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DfiInstallRoot {
    return Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}

function Get-DfiLauncher {
    param([string]$InstallRoot = (Get-DfiInstallRoot))

    $exeCandidates = @(
        (Join-Path $InstallRoot "windows\DataFlowInspector.exe"),
        (Join-Path $InstallRoot "windows\runtime\DataFlowInspector.exe")
    )
    foreach ($candidate in $exeCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return @{ Kind = "exe"; Program = $candidate; Script = $null }
        }
    }

    $python = Join-Path $InstallRoot "runtime\python\python.exe"
    $script = Join-Path $InstallRoot "windows\runtime\dfi_launcher.py"
    if ((Test-Path -LiteralPath $python -PathType Leaf) -and
        (Test-Path -LiteralPath $script -PathType Leaf)) {
        return @{ Kind = "python"; Program = $python; Script = $script }
    }

    throw "本地运行时不完整。请重新安装 DataFlow Inspector。"
}

function Invoke-DfiLauncher {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$InstallRoot = (Get-DfiInstallRoot)
    )

    $launcher = Get-DfiLauncher -InstallRoot $InstallRoot
    $previousLocalData = $env:DFI_LOCAL_APPDATA
    $previousInstallRoot = $env:DFI_INSTALL_ROOT
    $env:DFI_LOCAL_APPDATA = $InstallRoot
    $env:DFI_INSTALL_ROOT = Join-Path $InstallRoot "app"
    Push-Location $InstallRoot
    try {
        if ($launcher.Kind -eq "exe") {
            & $launcher.Program @Arguments | Out-Host
        } else {
            & $launcher.Program $launcher.Script @Arguments | Out-Host
        }
        return $LASTEXITCODE
    } finally {
        Pop-Location
        if ($null -eq $previousLocalData) {
            Remove-Item Env:DFI_LOCAL_APPDATA -ErrorAction SilentlyContinue
        } else {
            $env:DFI_LOCAL_APPDATA = $previousLocalData
        }
        if ($null -eq $previousInstallRoot) {
            Remove-Item Env:DFI_INSTALL_ROOT -ErrorAction SilentlyContinue
        } else {
            $env:DFI_INSTALL_ROOT = $previousInstallRoot
        }
    }
}

function Pause-OnError {
    param([string]$Message)
    Write-Host ""
    Write-Host "[错误] $Message" -ForegroundColor Red
    Read-Host "按回车键关闭"
}
