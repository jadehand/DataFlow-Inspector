# MVP 验收说明

## 验收输入

使用 `examples/token-traffic-demo.zip` 创建新项目。包内包含 6 个 DDL 文件、8 个加工 SQL、作业清单和脱敏样例。

## 功能验收

### 导入与解析

- 所有受支持文件成功登记且哈希非空。
- 每条 SQL 可定位到源文件。
- `${biz_date}` 能用 manifest 示例值完成静态解析。
- 单文件失败不影响其他文件。

### 资产

- 至少识别 1 个 RDS 源表、1 个 ODS 表、2 个 DWD 表、2 个 DWS 表、3 个 ADS 表和 3 个维表。
- 识别 `event_time`、`ingestion_time`、`stat_minute`、`stat_hour` 和 `stat_date` 的时间角色。
- 识别请求量、成功量、Token 数、成功率及延迟指标。

### 血缘

应形成主链路：

```text
rds.token_request
→ ods.ods_token_request
→ dwd.dwd_token_request
→ dwd.dwd_token_request_wide
→ dws.dws_token_minute
→ ads.ads_token_realtime
```

并形成 DWD 宽表到 DWS 小时、ADS 日报，再到区域报表的分支；维表字段应关联到宽表或区域报表。

### 作业 DAG

- 识别 8 个作业。
- `ads_daily` 关系标记为推断，其余按照 CSV 标记。
- DAG 无环，且可从迁移作业追踪到最终 ADS。

### 风险发现

必须检出：

1. **时间口径不一致**：`04_dws_minute.sql` 使用 `event_time`，`05_dws_hour.sql` 使用 `ingestion_time`。
2. **SELECT 星号**：`06_ads_realtime.sql` 含 `SELECT *`。
3. **指标过滤漂移**：`07_ads_daily.sql` 排除 `TEST`，其他请求量口径未排除。

建议同时提示 `08_ads_region.sql` 对 `region_code` 固定转换为 `VARCHAR(16)`。

### 影响分析

模拟将 `dwd.dwd_token_request.region_code` 扩为 `VARCHAR(32)`：

- 列出宽表、分钟/小时表和三个 ADS 的传递影响。
- 提示区域报表固定 CAST。
- 提示实时报表 `SELECT *` 的结构风险。
- 给出按 DDL、加工脚本、报表和回刷验证排列的建议顺序。

## 非功能验收

- 解析错误不泄露样例原始值。
- 核心分析无需模型配置。
- 不连接或修改生产 DWS。
- 所有推断均展示置信度和证据边界。
- 同一项目可比较两个导入版本。

## 建议质量指标

以人工标注的演示链路为黄金集：DDL 解析成功率 100%，表级血缘准确率不低于 95%，字段级血缘准确率不低于 85%，所有失败均能定位文件和语句。
