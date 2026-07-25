# DataFlow Inspector Windows 开发启动脚本
$ErrorActionPreference = "Stop"

$ROOT = "$PSScriptRoot"
$RUN_DIR = "$ROOT\.run"
$BACKEND_PORT = 18080
$FRONTEND_PORT = 15173

# 创建运行时目录
New-Item -ItemType Directory -Force -Path $RUN_DIR | Out-Null
New-Item -ItemType Directory -Force -Path "$ROOT\backend\data" | Out-Null

Write-Host "=== DataFlow Inspector 开发模式 ===" -ForegroundColor Cyan

# 1. 检查依赖
Write-Host "[1/3] 检查 Python 依赖..."
pip install -r "$ROOT\backend\requirements.txt" 2>&1 | Out-Null
python -c "import fastapi, uvicorn, sqlglot" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  依赖安装失败，请手动执行: pip install -r backend\requirements.txt" -ForegroundColor Red
    exit 1
}
Write-Host "  OK" -ForegroundColor Green

# 2. 启动后端
Write-Host "[2/3] 启动后端 (http://127.0.0.1:$BACKEND_PORT)..."
$env:DFI_DATA_DIR = "$ROOT\backend\data"
$env:DFI_DB_PATH = "$ROOT\backend\data\dataflow.db"
$env:DFI_IMPORT_DIR = "$ROOT\backend\data\imports"

$backendJob = Start-Job -Name "dfi-backend" -ScriptBlock {
    Set-Location $using:ROOT
    python -m uvicorn app.main:app --host 127.0.0.1 --port $using:BACKEND_PORT
}
$backendJob | Out-Null

# 等待后端就绪
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BACKEND_PORT/api/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
Write-Host "  后端已就绪" -ForegroundColor Green

# 3. 启动前端
Write-Host "[3/3] 启动前端 (http://127.0.0.1:$FRONTEND_PORT)..."
$frontJob = Start-Job -Name "dfi-frontend" -ScriptBlock {
    Set-Location (Join-Path $using:ROOT "frontend\src")
    python -m http.server $using:FRONTEND_PORT --bind 127.0.0.1
}
$frontJob | Out-Null

# 等待前端就绪
Start-Sleep -Seconds 1
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$FRONTEND_PORT/" -UseBasicParsing -TimeoutSec 3
    Write-Host "  前端已就绪" -ForegroundColor Green
} catch {
    Write-Host "  前端可能未就绪，请手动检查" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 启动完成 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  前端:  http://127.0.0.1:$FRONTEND_PORT/?api=http://127.0.0.1:$BACKEND_PORT/api"
Write-Host "  后端:  http://127.0.0.1:$BACKEND_PORT"
Write-Host "  健康:  http://127.0.0.1:$BACKEND_PORT/api/health"
Write-Host "  日志:  $RUN_DIR"
Write-Host ""
Write-Host "  停止:  .\stop-dev.ps1" -ForegroundColor Yellow
Write-Host ""
