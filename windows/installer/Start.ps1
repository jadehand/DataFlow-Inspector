. "$PSScriptRoot\Common.ps1"
try {
    $code = Invoke-DfiLauncher -Arguments @("start")
    if ($code -ne 0) { throw "启动程序返回错误代码 $code。" }
} catch {
    Pause-OnError $_.Exception.Message
    exit 1
}

