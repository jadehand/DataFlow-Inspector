# 项目包输入格式

DataFlow Inspector 接收 ZIP 项目包并进行只读静态分析，不连接或执行生产 DWS。可以从 `examples/import-template.zip` 下载空白模板。

## 输入要求速览

| 内容 | 级别 | 用途 |
|---|---|---|
| `sql/*.sql` | **必需** | 识别读写表、加工逻辑、指标、过滤和上下游 |
| `ddl/*.sql` | **强烈推荐** | 补全表字段、类型、`SELECT *` 和字段级血缘 |
| `manifest.yaml` | 推荐 | 声明 SQL 方言、时区、分层规则和平台宏示例 |
| `metadata/jobs.csv` | 可选 | 补充真实作业顺序、调度信息和人工确认关系 |
| `samples/*.csv` | 可选 | 辅助判断类型、基数、空值率及时间范围 |

仅有 SQL 也可导入，但缺失 DDL 时字段级血缘和类型影响分析可能不完整。产品不需要数据库连接地址、账号、密码或全量生产数据。

## 推荐结构

```text
project/
├── manifest.yaml
├── ddl/
│   ├── 01_ods.sql
│   ├── 02_dwd.sql
│   ├── 03_dimensions.sql
│   ├── 04_dws.sql
│   └── 05_ads.sql
├── sql/
│   ├── 01_source_to_ods.sql
│   ├── 02_ods_to_dwd.sql
│   ├── 03_dwd_enrichment.sql
│   ├── 04_dws_aggregation.sql
│   └── 05_ads_report.sql
├── metadata/
│   └── jobs.csv
└── samples/
    ├── ods_example.csv
    └── dwd_example.csv
```

最小可用结构：

```text
project/
├── ddl/
│   └── all_tables.sql
└── sql/
    └── processing_jobs.sql
```

## manifest.yaml

`manifest.yaml` 推荐提供。`project`、`sql_dialect`、`timezone` 是文件内的核心项；`layer_rules` 用正则识别表层级，`variables` 为静态解析平台宏提供示例值。产品保存原 SQL，不会用示例值覆盖源文件。

```yaml
project: token-traffic
sql_dialect: gaussdb_dws
timezone: Asia/Shanghai
variables:
  biz_date: "2026-07-22"
layer_rules:
  ods: "^ods_"
  dwd: "^dwd_"
  dws: "^dws_"
  ads: "^ads_"
```

## SQL 与 DDL

- 文件编码推荐 UTF-8。
- 每个文件可包含多条以分号结尾的语句。
- 表名尽量写成 `schema.table`。
- 尽量上传链路涉及的全部 DDL，包括维度表和外部配置表。
- 推荐一个作业对应一个 SQL 文件，文件名可带顺序编号，但编号不等同于真实调度依赖。
- 保留显式目标字段列表；大量 `SELECT *` 会降低字段级血缘的稳定性。
- 支持 `${name}` 宏；请在 `variables` 中给出可解析的示例值。
- 动态 SQL、存储过程和外部程序依赖会标记为“未完全解析”。

## jobs.csv

```csv
job_name,script_path,schedule,upstream_jobs,owner,relation_status
ods_to_dwd,sql/02_ods_to_dwd.sql,5 * * * *,migration,data-team,confirmed
```

`upstream_jobs` 多值时以分号分隔；`relation_status` 可为 `confirmed` 或 `inferred`。SQL 只能证明数据依赖，不能证明真实调度关系。

## samples

支持 CSV。首版仅将样例用于类型、基数、空值率和时间范围剖析。上传前必须脱敏；建议每表 20～100 行，不上传手机号、证件号、密钥、完整用户文本等敏感值。

## 导入校验

导入器应拒绝绝对路径、`../`、软链接和不支持的扩展名；对每个文件记录 SHA-256、编码、大小和解析诊断。解析失败不能中断其他文件，且必须显示文件和语句位置。

## 正确压缩层级

ZIP 解压后应直接看到一个项目根目录及其内容：

```text
project.zip
└── project/
    ├── manifest.yaml
    ├── ddl/
    ├── sql/
    ├── metadata/
    └── samples/
```

在项目根目录的上一级执行：

```bash
zip -r project.zip project/
```

不要将多个互不相关的项目根目录塞进同一个 ZIP；也不要压缩成多层重复目录，例如 `project/project/project/...`。

## 常见错误

### 错误：只上传数据样例

```text
project/samples/example.csv
```

没有加工 SQL 时无法建立血缘。至少需要 `sql/*.sql`。

### 错误：SQL 只剩省略号或伪代码

```sql
INSERT INTO target_table
SELECT ...
FROM source_table;
```

系统只能识别有限的表级关系，无法还原字段映射和指标公式。请上传脱敏后的完整表达式。

### 错误：DDL 与实际 Schema 不一致

```sql
CREATE TABLE table_a (...);
-- 加工 SQL 实际引用 prod_schema.table_a
```

这可能被识别为两个对象。DDL 和 SQL 应尽量统一使用 `schema.table`。

### 错误：将密码写入 SQL 或 manifest

不要上传数据库密码、密钥、连接串或 Cookie。产品进行静态分析，不需要这些信息。

### 错误：`jobs.csv` 路径与 ZIP 不一致

`script_path` 必须是相对项目根目录的实际路径，例如 `sql/02_ods_to_dwd.sql`，不能填写本机绝对路径。

## 可用示例

- `examples/import-template.zip`：不含真实业务内容的空白导入模板。
- `examples/token-traffic-demo.zip`：用于体验完整链路的演示项目包。
