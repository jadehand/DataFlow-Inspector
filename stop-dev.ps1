# DataFlow Inspector Windows 停止脚本
Write-Host "停止 DataFlow Inspector 开发服务..."

$stopped = $false

# 停止后端
$backendJob = Get-Job -Name "dfi-backend" -ErrorAction SilentlyContinue
if ($backendJob) {
    Stop-Job -Name "dfi-backend"
    Remove-Job -Name "dfi-backend" -Force
    $stopped = $true
    Write-Host "  后端已停止"
}

# 停止前端
$frontJob = Get-Job -Name "dfi-frontend" -ErrorAction SilentlyContinue
if ($frontJob) {
    Stop-Job -Name "dfi-frontend"
    Remove-Job -Name "dfi-frontend" -Force
    $stopped = $true
    Write-Host "  前端已停止"
}

if (-not $stopped) {
    Write-Host "  没有运行中的服务"

    # 兜底：按端口杀进程
    foreach ($port in @(18080, 15173)) {
        $conn = netstat -ano 2>$null | Select-String "127.0.0.1:$port"
        if ($conn) {
            $pid = ($conn -split '\s+')[-1]
            if ($pid -match '^\d+$') {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "  端口 $port (PID $pid) 已释放"
            }
        }
    }
}

Write-Host "服务已停止"
