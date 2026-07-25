# Windows 本地运行器

`dfi_launcher.py` 是 Windows 10/11 本地安装版的运行入口。正式安装包会
携带 Python、后端依赖和前端资源，用户不需要安装 Python 或 Docker。

## 命令

```powershell
python dfi_launcher.py start
python dfi_launcher.py start --no-browser
python dfi_launcher.py health
python dfi_launcher.py stop
```

未指定命令时等同于 `start`。`serve --port` 是启动器创建后台进程时使用的
内部命令，不应制作用户快捷方式。

## 本机数据

默认只监听 `127.0.0.1`，并从 `17600-17699` 自动选择空闲端口。运行数据
保存在 `%LOCALAPPDATA%\DataFlowInspector`：

```text
DataFlowInspector/
├── data/
│   ├── dataflow.db
│   └── imports/
├── logs/
│   └── app.log
└── run/
    ├── pid
    ├── port
    └── runtime.json
```

开发和自动化测试可使用 `DFI_INSTALL_ROOT` 指定产品根目录，使用
`DFI_LOCAL_APPDATA` 重定向本地数据目录。
