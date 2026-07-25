# DataFlow Inspector

**DWS 数仓数据加工链路血缘分析工具** — 导入 DDL、ETL SQL 和作业清单，自动解析表结构、字段血缘、指标口径和风险，不连接生产数据库。

```
ODS ──→ DWD ──→ DWS ──→ ADS
  │       │       │       │
  └── 表级血缘 ──→ 字段级血缘 ──→ 指标识别 ──→ 影响分析
```

## 做什么

| 能力 | 说明 |
|------|------|
| **导入解析** | 上传 ZIP 项目包（DDL + SQL + manifest + jobs.csv + 脱敏样例），自动解析并生成完整数据字典 |
| **表级血缘** | 自动识别 INSERT/CTAS 的读写关系，支持 CTE 穿透和 JOIN 跨表追溯 |
| **字段级血缘** | 基于 SQLGlot AST 逐列追溯来源，区分直接映射 / 表达式转换 / 聚合 |
| **指标识别** | 自动识别 COUNT/SUM/AVG/PERCENTILE_CONT 等聚合指标及其分组维度和过滤条件 |
| **作业 DAG** | 从 jobs.csv 或 SQL 依赖推断构建作业调度拓扑 |
| **风险检测** | `SELECT *` / 时间口径不一致 / 指标过滤漂移 → 自动标记 |
| **影响分析** | 输入 "改某个字段类型"，输出所有受影响的下游表和脚本 |
| **版本对比** | 两次导入之间：表/字段/血缘/指标/风险的变化一目了然 |
| **单表导入** | 不上传 ZIP，直接粘贴一段 CREATE TABLE + ETL SQL，精准入库 |
| **DWS 方言** | 识别 DISTRIBUTE BY / PARTITION BY / WITH 存储参数 / 分布键等 GaussDB(DWS) 专有语法 |

## 不做

- 不连接生产数据库
- 不执行你上传的 SQL
- 推断结果明确标记，不冒充精确事实

---

## 项目结构

```
dataflow-inspector/
│
├── backend/                       ← Python 后端 (FastAPI + SQLite)
│   ├── run.py                     ←  启动入口
│   ├── requirements.txt           ←  fastapi / uvicorn / sqlglot / pytest
│   ├── app/
│   │   ├── main.py                ←  所有 API 路由（项目/导入/血缘/影响分析/单表导入）
│   │   └── parser/                ←  解析引擎（核心）
│   │       ├── ddl_parser.py      ←    DDL → 表/字段/类型/分层
│   │       ├── sql_parser.py      ←    SQL → 表血缘 + 字段血缘（CTE 穿透）
│   │       ├── analyzer.py        ←    整合 DDL+SQL+指标+风险
│   │       ├── dialect_dws.py     ←    DWS 方言适配（分布键/分区/存储参数）
│   │       ├── single_table.py    ←    单表导入 + 冲突检测
│   │       ├── evidence.py        ←    置信度 & 证据链
│   │       └── regex_fallback.py  ←    正则降级兜底
│   └── tests/                     ←  pytest 测试（19 个）
│
├── frontend/                      ← 纯静态前端（零构建、零框架）
│   └── src/
│       ├── index.html             ←  9 个标签页 + 全部样式
│       ├── product-app.js         ←  业务逻辑：API 调用 / 渲染 / 交互
│       └── mock-data.js           ←  演示模式数据（需手动切换）
│
├── examples/                      ← 演示项目包
│   ├── token-traffic-demo.zip     ←  内置演示：5 表 RDS→ADS 链路
│   ├── llm-demo/ & llm-api-demo.zip ← LLM API 实战演示：5 表 + DWS 方言
│   ├── import-template/ & .zip    ←  空白导入模板
│   └── llm_dws_dw_architecture.md ←  架构文档
│
├── docs/                          ← 说明文档
│   ├── architecture.md / input-format.md / user-guide.md
│   └── operations-manual.md       ←  内网部署运维手册
│
├── scripts/                       ← Linux/Mac 启停脚本
├── start-dev.ps1 / stop-dev.ps1   ← Windows 启停脚本
├── Makefile / docker-compose.yml  ← 一键启动 / Docker 部署
└── CLAUDE.md                      ← 工程约束文档
```

---

## 快速开始

### 前置条件

- Python 3.10+
- 无需 Node.js（前端是纯静态文件）
- 无需 Docker（SQLite 内置于 Python）

### Windows

```powershell
cd D:\Projects\dataflow-inspector

# 安装依赖（首次）
pip install -r backend\requirements.txt

# 启动（两个终端）
# 终端 1: 后端
cd backend
python run.py                         # → http://127.0.0.1:18080

# 终端 2: 前端
cd frontend\src
python -m http.server 15173 --bind 127.0.0.1
                                      # → http://127.0.0.1:15173
```

或一键：

```powershell
.\start-dev.ps1     # 启动
.\stop-dev.ps1      # 停止
```

浏览器打开 **http://127.0.0.1:15173**

### Linux / Mac

```bash
make dev            # 一键启动前后端
make stop           # 停止
make smoke          # 黑盒验收
```

---

## 怎么用

### 方式 1：标准 ZIP 导入

1. 打开 **http://127.0.0.1:15173** → 新建项目
2. 点击 **「＋ 导入新版本」**
3. 拖入 ZIP 包（格式见 `docs/input-format.md`）
4. 先点 **「检查项目包」** 预检 → 确认无误后点 **「上传并分析」**
5. 完成后浏览 6 个视图：资产目录 / 血缘图 / 作业流 / 指标 / 影响分析 / 版本对比

### 方式 2：单表导入

1. 进入项目 → 使用 API 或前端页面粘贴 DDL + ETL SQL
2. 有 ETL SQL：精确解析血缘 → 确认后入库
3. 无 ETL SQL：作为孤立表入库，或根据字段推断返回待确认建议

```bash
curl -X POST http://127.0.0.1:18080/api/projects/1/tables/import \
  -H "Content-Type: application/json" \
  -d '{"ddl": "CREATE TABLE dwd.detail (...)", "etl_sql": "INSERT INTO dwd.detail SELECT ... FROM ods.source"}'
```

### 方式 3：上传演示包体验

导入 `examples/token-traffic-demo.zip` 立刻看到完整的血缘图。

---

## API 速览

| 方法 | 路径 | 用途 |
|------|------|------|
| `POST` | `/api/projects` | 新建项目 |
| `POST` | `/api/projects/{id}/imports` | ZIP 导入分析 |
| `POST` | `/api/imports/preflight` | ZIP 预检 |
| `GET` | `/api/projects/{id}/catalog` | 资产目录 |
| `GET` | `/api/projects/{id}/lineage` | 表级/字段级血缘 |
| `GET` | `/api/projects/{id}/workflows` | 作业 DAG |
| `GET` | `/api/projects/{id}/metrics` | 指标列表 |
| `POST` | `/api/projects/{id}/impact-analysis` | 变更影响分析 |
| `GET` | `/api/projects/{id}/compare` | 版本对比 |
| `POST` | `/api/projects/{id}/tables/import` | 单表导入 |
| `POST` | `/api/projects/{id}/tables/preview` | 单表预览 |
| `POST` | `/api/projects/{id}/assistant/query` | 证据式问答 |

---

## 测试

```bash
cd backend
PYTHONPATH=. pytest tests/ -v        # 19 个测试
python test_llm_demo.py              # LLM 演示项目手工验证
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/input-format.md` | ZIP 导入包格式规范 |
| `docs/architecture.md` | 系统架构 & 解析策略 |
| `docs/user-guide.md` | 用户操作手册 |
| `docs/operations-manual.md` | 内网部署、备份恢复、运维 |
| `docs/acceptance.md` | 验收标准 |
| `CLAUDE.md` | 工程约束 & 开发规范 |
