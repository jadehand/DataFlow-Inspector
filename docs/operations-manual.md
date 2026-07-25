# DataFlow Inspector 1.0 内网部署与运维手册

## 1. 部署边界

正式版采用两个容器：

```text
内网浏览器
    │ HTTP
    ▼
Web / Nginx :15173
    ├── 静态前端
    └── /api/* ──► Backend :18080（仅容器网络）
                         │
                         ▼
             dataflow-inspector_data
             ├── dataflow.db
             └── imports/
```

宿主机只暴露一个 Web 端口，后端不直接开放。前后端同源，因此不需要为每个内网 IP 放宽 CORS。

本版本面向可信内网中的个人或小团队，不包含登录、细粒度权限和统一认证。若不同权限人员共用同一网络，建议在前置网关增加认证，或升级到多人企业版。

## 2. 前置条件

- 64 位 Linux。
- Docker Engine 24 或更高版本。
- Docker Compose v2（命令形式为 `docker compose`）。
- 建议 2 核 CPU、4 GB 内存、20 GB 可用磁盘。
- 首次构建镜像时能访问已配置的 Docker 镜像源和 Python 包源。

确认工具：

```bash
command -v docker
docker compose version
docker info
```

不要在生产数据目录中直接解压未知 ZIP。项目导入必须通过产品预检接口完成。

## 3. 首次安装

解压正式版源码后执行：

```bash
cp .env.example .env
make install
```

安装脚本依次执行：

1. 检查 Docker、Compose、配置和端口。
2. 构建固定版本镜像。
3. 创建持久化卷 `dataflow-inspector_data`。
4. 启动后端和 Web 服务。
5. 校验 API、SQLite 数据库与返回 JSON。

默认地址为 `http://127.0.0.1:15173`。

## 4. 内网访问配置

`.env` 中最重要的设置：

```dotenv
DFI_BIND_ADDRESS=127.0.0.1
DFI_HTTP_PORT=15173
DFI_MAX_ZIP_BYTES=52428800
```

绑定策略：

- `127.0.0.1`：默认值，只有服务器本机能访问，最安全。
- 服务器实际内网 IP：推荐的内网共享方式，例如 `10.20.30.40`。
- `0.0.0.0`：监听所有网卡，仅在防火墙已经限制可信内网来源时使用。

修改后执行：

```bash
make restart
make health
```

端口 `8080` 被明确禁止。不要将本产品通过 NAT、端口转发或公网负载均衡器直接暴露到互联网。

## 5. 日常操作

```bash
make start
make stop
make restart
make status
make health
make logs
```

按服务看日志：

```bash
./scripts/logs.sh backend
./scripts/logs.sh web
```

持续跟踪日志：

```bash
./scripts/logs.sh --follow backend
```

Docker 日志默认以单文件 10 MB、最多 5 个文件轮转，可通过 `.env` 调整。日志不记录上传 ZIP 的原始内容；运维人员仍应控制日志文件访问权限。

## 6. 数据持久化

数据卷固定命名为：

```text
dataflow-inspector_data
```

内容：

- `dataflow.db`：项目、导入版本和分析结果。
- `imports/`：已经安全解压的导入文件。

以下操作不会删除数据：

```bash
make stop
docker compose down
```

以下操作会永久删除数据，日常运维禁止使用：

```bash
docker compose down -v
docker volume rm dataflow-inspector_data
```

建议每天备份，备份文件复制到另一台受控服务器或企业备份介质，并按组织要求加密保存。

## 7. 备份

```bash
make backup
```

默认输出到 `backups/dataflow-inspector-<UTC时间>.tar.gz`，并生成同名 `.sha256` 文件。备份过程使用 SQLite 在线备份 API，确保数据库快照一致，同时打包 `imports/`。

指定路径：

```bash
make backup BACKUP=/srv/backup/dfi-nightly.tar.gz
```

校验：

```bash
sha256sum -c /srv/backup/dfi-nightly.tar.gz.sha256
tar -tzf /srv/backup/dfi-nightly.tar.gz
```

备份包含业务 SQL 和元数据，应按敏感内部资料管理。

## 8. 恢复

恢复会覆盖当前数据库和导入文件，必须先确认目标备份和当前业务窗口。

```bash
make restore \
  BACKUP=/srv/backup/dfi-nightly.tar.gz \
  RESTORE_CONFIRM=yes
```

恢复脚本会：

1. 检查压缩包路径、成员类型和数据库 SHA-256。
2. 停止 Web 与后端。
3. 在临时目录解包。
4. 执行 SQLite `PRAGMA integrity_check`。
5. 原子替换数据库和导入目录。
6. 启动服务并执行健康检查。

建议每季度在隔离测试机做一次恢复演练。

## 9. 升级与回滚

升级前：

1. 保存当前版本源码包。
2. 阅读新版本变更说明。
3. 确认磁盘至少能同时容纳新旧镜像和一份完整备份。

在新版本源码目录执行：

```bash
cp /path/old/.env .env
make upgrade
```

脚本会先生成 `backups/pre-upgrade-*.tar.gz`，再构建和启动新镜像。如果健康检查失败：

1. 切回上一版本源码目录。
2. 执行 `make install` 恢复旧镜像。
3. 如涉及数据格式变化，使用升级前备份执行 `make restore ... RESTORE_CONFIRM=yes`。

当前 1.0 使用 SQLite 自动创建缺失表，没有独立迁移工具；未来涉及破坏性数据库迁移时，发布说明必须明确标注。

## 10. 健康检查与监控

手工检查：

```bash
make health
make status
```

存活与就绪接口：

```text
GET /api/health
GET /api/ready
```

监控流量存活可使用 `/api/health`；安装、启动和恢复验收使用 `/api/ready`。就绪响应必须同时包含：

```json
{"status":"ready","database":"ok","storage":"ok"}
```

建议内网监控系统每分钟检查一次 Web 地址 `/api/ready`，连续 3 次失败再告警。另应监控：

- Docker 容器重启次数。
- 宿主机磁盘使用率，80% 预警、90% 严重告警。
- 备份任务最近成功时间。
- HTTP 5xx 数量和导入失败率。

## 11. 故障排查

### 页面打不开

```bash
make status
make health
make logs
```

检查 `.env` 的绑定 IP 是否属于当前服务器，以及防火墙是否允许 `DFI_HTTP_PORT`。

### 后端不健康

```bash
./scripts/logs.sh backend
docker volume inspect dataflow-inspector_data
```

重点检查数据卷权限、磁盘空间和 SQLite 错误。不要直接编辑 `dataflow.db`。

### 导入提示文件过大

默认 ZIP 上限为 50 MiB。确认资料已脱敏、删除无关文件后再考虑调整 `DFI_MAX_ZIP_BYTES`，然后执行 `make restart`。Nginx 请求上限为 64 MiB；正式版建议保持业务限制不超过该值。

### 端口冲突

修改 `.env` 中的 `DFI_HTTP_PORT`，不要停止或接管未知进程。产品拒绝绑定宿主机 `8080`。

### Docker 构建失败

确认镜像源、DNS 和 Python 包源可达。不要反复删除数据卷；镜像构建与持久化数据是独立的。

## 12. 正式版验收

部署前执行：

```bash
make release-check
```

启动后执行：

```bash
make health
DATAFLOW_API_URL=http://127.0.0.1:15173/api make smoke
```

验收通过后保存：

- 当前源码归档和 SHA-256。
- `.env` 的脱敏副本。
- `make status` 输出。
- 最近一次备份和恢复演练记录。
