param(
    [string]$OutputDirectory = (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "DataFlow Inspector Backups")
)

. "$PSScriptRoot\Common.ps1"
$installRoot = Get-DfiInstallRoot
$dataDir = Join-Path $installRoot "data"

try {
    if (-not (Test-Path -LiteralPath $dataDir -PathType Container)) {
        throw "尚无可备份的数据。请先启动并使用产品。"
    }
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $OutputDirectory "DataFlowInspector-$stamp.zip"
    $stage = Join-Path $env:TEMP "dfi-backup-$([Guid]::NewGuid().ToString('N'))"

    Invoke-DfiLauncher -Arguments @("stop") | Out-Null
    try {
        New-Item -ItemType Directory -Force -Path $stage | Out-Null
        Copy-Item -LiteralPath $dataDir -Destination (Join-Path $stage "data") -Recurse -Force
        Compress-Archive -LiteralPath (Join-Path $stage "data") -DestinationPath $backup -CompressionLevel Optimal
    } finally {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        Invoke-DfiLauncher -Arguments @("start", "--no-browser") | Out-Null
    }
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        throw "备份文件未生成。"
    }
    Write-Host "备份完成：$backup" -ForegroundColor Green
    Start-Process explorer.exe -ArgumentList "/select,`"$backup`""
} catch {
    Pause-OnError $_.Exception.Message
    exit 1
}

