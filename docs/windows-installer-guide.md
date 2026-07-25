# Windows 10/11 本地安装器

## 用户安装

1. 完整解压安装包。
2. 双击安装包根目录的 `安装.bat`。
3. 安装完成后，从桌面或开始菜单启动。

默认安装目录：

```text
%LOCALAPPDATA%\DataFlow Inspector
```

不需要管理员权限、不需要 Docker，也不会监听局域网地址。运行时只监听
`127.0.0.1` 的 `17600-17699` 空闲端口。

## 快捷方式

安装器会在桌面和开始菜单创建：

- 启动 DataFlow Inspector
- 停止 DataFlow Inspector
- 备份 DataFlow Inspector
- 恢复 DataFlow Inspector
- 卸载 DataFlow Inspector（保留数据）

备份默认保存在“文档\DataFlow Inspector Backups”。恢复数据需要输入
`RESTORE`，以防误覆盖。

## 卸载和数据

普通卸载只删除程序，保留：

```text
%LOCALAPPDATA%\DataFlow Inspector\data
```

需要永久删除全部数据时，在 PowerShell 中执行：

```powershell
& "$env:LOCALAPPDATA\DataFlow Inspector\windows\installer\Uninstall.ps1" -DeleteData
```

并按提示输入 `DELETE-DATA`。此操作不可恢复，建议先创建备份。

## 安装包接口

安装包根目录应包含：

```text
app\
runtime\python\
安装.bat
windows\runtime\dfi_launcher.py
```

本版直接使用安装包自带的嵌入式 Python，不会调用系统 Python；如果后续
提供经过签名的 `windows\DataFlowInspector.exe`，安装器会自动优先使用。
