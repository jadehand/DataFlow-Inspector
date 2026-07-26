# DataFlow Inspector

面向 DWS 分层加工的 SQL 资产、字段语义、血缘、指标口径、作业顺序与变更影响分析工具。

## 当前状态

当前基线为 **P2 可用版本**，目标使用范围是约 5 人的可信内部小组。P0 功能闭环、P1 前端架构重构和 P2 真实业务验收均已完成；P3 生产治理不属于当前版本的上线前置条件。

推荐在每次交付前执行：

```bash
make check
make dev
make p2-check
```

`make p2-check` 会验证从项目创建、两版 ZIP 导入、异步轮询，到资产、详情、血缘、作业、指标、风险、比较和影响分析的完整链路。

当前版本的使用边界：

- 面向可信内网环境和小规模协作，不提供细粒度用户、角色和项目权限。
- 不连接生产数据库，不执行上传 SQL，只做静态解析和只读分析。
- 适合当前演示包量级及相近规模，不承诺大规模资产下的分页和查询性能。
- 动态 SQL、存储过程、复杂宏和部分 `SELECT *` 字段映射会明确降级。

未来的 P3 条目及启动条件见 [未来演进清单](docs/future-roadmap.md)。

## 已完成功能

- 导入包含 DDL、SQL、作业清单和脱敏样例的项目包。
- ZIP 导入支持预检、异步分析、状态恢复和压缩炸弹防护。
- 识别 ODS、DWD、DWS、ADS 表与字段。
- 查询表级/字段级血缘、指标口径和作业流。
- 检测时间口径不一致、`SELECT *`、指标过滤漂移等风险。
- 比较两个导入版本的表、字段、血缘、指标和风险变化。
- 对字段或逻辑变更生成上下游影响说明，附带证据、影响路径和修改建议。
- 前端提供概览、资产、详情、血缘、作业、指标、导入历史、版本比较、影响分析与助手视图。
- 支持表级/字段级元数据集中保存、保存前差异预览和 metadata revision 快照。
- 支持导入版本 compare 与 metadata revision compare 两类差异视图。
- ZIP 导入和单表导入都会保存可追溯的 DDL / ETL 文件资产，支持查看与导出。

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

启动脚本会检查端口占用，拒绝使用 `8080` 且不会触碰该端口已有服务。
若后端入口不是默认的 `app.main:app`，可通过 `DATAFLOW_BACKEND_APP` 指定：

```bash
DATAFLOW_BACKEND_APP=app.factory:create_app:factory make dev
```

支持的入口格式：

- `模块:属性:app`
- `模块:工厂函数:factory`

停止：

```bash
make stop
```

日志写入 `.run/backend.log` 和 `.run/frontend.log`。

## 验收

服务启动后执行：

```bash
make smoke
```

冒烟测试覆盖以下检查：

1. 后端健康状态。
2. OpenAPI 是否暴露核心路由。
3. `15173` 可访问、`8080` 被 CORS 拒绝。
4. 创建临时项目，验证项目列表和详情接口。
5. 导入接口存在且拒绝非法负载。
6. 错误返回结构包含 `error/detail/status_code/request_id`。

可通过环境变量修改后端地址：

```bash
DATAFLOW_API_URL=http://127.0.0.1:18080 make smoke
```

完整 P2 验收：

```bash
DATAFLOW_API_URL=http://127.0.0.1:18080 make p2-check
```

该命令先跑静态检查、单元测试和架构验证，再用独立测试数据执行两版 ZIP 导入及完整业务 API 验收。人工验收标准见 [验收说明](docs/acceptance.md)。

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

输出 `dist/dataflow-inspector-source.tar.gz`。打包时排除运行日志、数据库、虚拟环境和 `node_modules`。

## 目录

```text
backend/        分析 API 与数据模型
frontend/       Web 产品界面
examples/       Token 流量演示项目
docs/           输入、架构、用户和验收文档
scripts/        启停、检查与打包脚本
tests_e2e/      黑盒验收脚本
```

详细输入格式、验收说明和未来演进清单见：

- [输入格式](docs/input-format.md)
- [验收说明](docs/acceptance.md)
- [未来演进清单](docs/future-roadmap.md)

## Metadata Revision

保存表级或字段级元数据时，系统会生成一份 metadata revision 快照，用于审计和后续比较。

当前支持：

- `GET /api/projects/{pid}/metadata/revisions`
- `GET /api/projects/{pid}/metadata/compare?left=R1&right=R2`
- revision 审计字段：`source`、`operator`、`reason`
- 版本比较页展示最近两次 metadata revision 的差异摘要
- 表详情页展示当前表所在项目的最新 metadata revision
- 从版本比较或 metadata revision 比较可直接带差异证据进入影响分析
