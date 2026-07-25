. "$PSScriptRoot\Common.ps1"
try {
    $code = Invoke-DfiLauncher -Arguments @("stop")
    if ($code -ne 0) { throw "停止程序返回错误代码 $code。" }
    Write-Host "DataFlow Inspector 已停止。" -ForegroundColor Green
} catch {
    Pause-OnError $_.Exception.Message
    exit 1
}

