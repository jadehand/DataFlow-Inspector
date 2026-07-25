@echo off
chcp 65001 >nul
setlocal
set "INSTALLER=%~dp0windows\installer\Install.ps1"

if not exist "%INSTALLER%" (
  echo [错误] 安装包不完整，请重新下载并完整解压。
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER%"
if errorlevel 1 (
  echo.
  echo 安装未完成，请查看上方错误信息。
  pause
  exit /b 1
)

echo.
echo 安装完成。请从桌面或开始菜单启动 DataFlow Inspector。
pause
