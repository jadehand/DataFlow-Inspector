# DataFlow Inspector

面向 DWS 分层加工的 SQL 资产、字段语义、血缘、指标口径、作业顺序与变更影响分析工具。

## 当前能力

- 导入包含 DDL、SQL、作业清单和脱敏样例的项目包。
- 识别 ODS、DWD、DWS、ADS 表与字段。
- 查询表级/字段级血缘、指标口径和作业流。
- 检测时间口径不一致、`SELECT *`、指标过滤漂移等风险。
- 对拟议字段或逻辑变更生成上下游影响说明。
- 前端提供资产、血缘、作业、指标、版本与助手视图。
- 支持表级/字段级元数据集中保存、保存前差异预览和 metadata revision 快照。
- 支持导入版本 compare 与 metadata revision compare 两类差异视图。

内置演示包位于 `examples/token-traffic-demo.zip`，覆盖：

```text
RDS → ODS → DWD → DWS 分钟/小时 → ADS
```

## 快速启动

要求 Python 3；Node/npm 仅在前端包含 `package.json` 时需要。执行：

```bash
cp .env.example .env
make check
make dev
```

默认地址：

- 前端：<http://127.0.0.1:15173/?api=http://127.0.0.1:18080/api>
- 后端：<http://127.0.0.1:18080>

启动脚本会先检查端口。它明确拒绝使用 `8080`，也不会停止或重启该端口上的服务。

停止：

```bash
make stop
```

日志写入 `.run/backend.log` 和 `.run/frontend.log`。

## 黑盒验收

服务启动后执行：

```bash
make smoke
```

验收脚本会：

1. 检查后端健康状态。
2. 创建临时分析项目。
3. 上传 `token-traffic-demo.zip`。
4. 在导入阶段执行 SQL/DDL 解析。
5. 查询资产、血缘、指标和作业流 API。
6. 执行一次字段类型变更影响分析和证据化问答。
7. 校验 HTTP 状态及 JSON 错误字段。

可通过环境变量修改后端地址：

```bash
DATAFLOW_API_URL=http://127.0.0.1:18080 make smoke
```

## Docker Compose

若本机具备 Docker Compose：

```bash
command -v docker
docker compose config
docker compose up --build
```

Compose 只映射 `18080` 和 `15173`，不会映射 `8080`。

## 打包

```bash
make package
```

输出 `dist/dataflow-inspector-source.tar.gz`。归档排除运行日志、数据库、虚拟环境和 `node_modules`。

## 目录

```text
backend/        分析 API 与数据模型
frontend/       Web 产品界面
examples/       Token 流量演示项目
docs/           输入、架构、用户和验收文档
scripts/        启停、检查与打包脚本
tests_e2e/      黑盒验收脚本
```

详细输入格式和验收说明见 `docs/input-format.md` 与 `docs/acceptance.md`。

## Metadata Revision

保存表级或字段级元数据时，系统会生成一条 metadata revision 快照，用于审计和后续比较。

当前支持：

- `GET /api/projects/{pid}/metadata/revisions`
- `GET /api/projects/{pid}/metadata/compare?left=R1&right=R2`
- revision 审计字段：`source`、`operator`、`reason`
- 版本比较页展示最近两次 metadata revision 的差异摘要
- 表详情页展示当前表所在项目的最新 metadata revision
- 从版本比较或 metadata revision 比较可直接带差异证据进入影响分析
