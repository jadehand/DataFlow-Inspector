# 脱敏 SQL 加工样例分析报告

> 分析对象：`uploads/desensitized_data_pipeline.md`  
> 分析原则：只依据文档中可见的 DDL、SQL 片段和文字说明。文档以 `...` 省略的字段、关联条件和逻辑不作确定性结论。

## 1. 结论摘要

该样例展示了一条从双站点原始请求数据，经 DWD 标准化与配置维度构建，再到 DWS 事实富化和分钟聚合的链路：

```text
ods_source_a ─┐
              ├─→ dwd_fact_request ───────────────┐
ods_source_b ─┘                                    │
                                                   ├─→ dws_fact_enriched ─→ dws_agg_minute
配置表、计费规格 ─→ dwd_dim_model ──────────────────┤
服务、模板、资源池、运行状态 ─→ dwd_dim_service ───┘
```

核心业务时间同时包含采集时间、消息队列时间、调度数据时间和配置生效/更新时间。当前加工主要按 `${data_time}` 小时分区幂等重跑，而分钟聚合使用 `ts_collect_std` 截断到分钟。因此，**作业分区时间与业务采集时间并非同一概念**。

样例的主要复杂点是：

- 双站点合并、去重和字段标准化；
- 配置多源合并、自关联及最新版本选择；
- 多维 LEFT JOIN 富化与字段优先级；
- 特殊计费模式下按图片面积重算用量；
- 18/21 个维度口径下的分钟汇总和多组分位数计算。

文档也暴露出多处需要在真实脚本中核验的问题，包括省略字段导致的投影不闭合、聚合字段引用不完整、分组维度数量描述矛盾、`val_input_avg` 实际取 SUM、状态码类型比较不一致，以及价格表可能一对多放大数据。

## 2. 表清单与层级

### 2.1 核心目标表

| 表 | 层级 | 表类型/粒度 | 直接来源 | 主要用途 |
|---|---|---|---|---|
| `ods_source_a` | ODS | 主站请求级原始表 | 外部迁移，文档未给出源表 | 保存请求、计数、用量、延迟及 MQ 元数据 |
| `ods_source_b` | ODS | 副站请求级原始表 | 外部迁移，文档未给出源表 | 与主站结构基本一致；缺少 `err_detail` |
| `dwd_fact_request` | DWD | 请求明细；按小时作业分区 | 两张 ODS 表 | 双站点合并、去重、命名标准化和派生字段 |
| `dwd_dim_model` | DWD | 实体/模型配置小时快照 | 配置表 A/B、计费规格 | 实体层级、计费、限流及资源名称 |
| `dwd_dim_service` | DWD | 服务配置小时快照 | 服务规格、平台服务、模板、资源池、运行状态 | 服务名称、状态、技术参数和区域信息 |
| `dws_fact_enriched` | DWS | 富化事实；文档附录标为小时粒度 | DWD 事实及两个 DWD 维度，另有用户/客户表 | 排除特定租户、补充实体和服务维度、重算特殊用量 |
| `dws_agg_minute` | DWS | 多维分钟聚合 | `dws_fact_enriched`、价格字典 | 吞吐、错误、费用、延迟及分位数指标 |

### 2.2 SQL 中出现的辅助来源

下列对象参与加工，但文档未提供完整 DDL，不能确认其所属层级、唯一键和时间语义：

- 实体配置：`config_table_a`、`config_table_a_hk`、`config_table_b`、`config_table_b_hk`
- 计费规格：`dwd_billing_spec`
- 服务配置：`service_spec_table`、`platform_service_table`、`template_config_table`
- 运行资源：`pool_detail_daily`、`engine_running_summary`
- 排除名单和用户客户：`excluded_tenant_list`、`user_base_table`、`meta_customer_table`
- 价格字典：`sku_price_dict`

文字说明还提到“专属模型表”和“理论指标表”，但展示 SQL 中没有出现对应 JOIN，暂不能建立其血缘。

## 3. 时间字段及其关系

### 3.1 各表时间字段

| 表 | 时间字段 | 可确认语义 | 加工/分区关系 |
|---|---|---|---|
| `ods_source_a/b` | `ts_collect` | 毫秒级采集时间 | 后续转换为 `ts_collect_std` |
|  | `mq_timestamp` | MQ 消息时间 | ODS→DWD 以 `[data_time, data_time+1h)` 过滤；ODS 按其分区 |
|  | `etl_time` | ETL 时间 | 示例中未继续使用 |
| `dwd_fact_request` | `ts_collect` | 原始采集时间 | ODS 直接传递 |
|  | `ts_collect_std` | 标准化采集时间 | `TO_TIMESTAMP(ts_collect / 1000)` |
|  | `ts_event` | 作业数据小时 | 由 `${data_time}` 格式化为整点；用于删除、分区和下游快照关联 |
| `dwd_dim_model` | `created_at/updated_at/deleted_at` | 配置生命周期时间 | 从配置源传递 |
|  | `ts_event` | 维度快照时间 | 固定为 `${data_time}` |
| `dwd_dim_service` | `created_at/updated_at/deleted_at` | 服务配置生命周期时间 | 来源主要是平台服务；最新规格按 `updated_at` 排序 |
|  | `ts_event` | 维度快照时间 | 固定为 `${data_time}` |
| `dws_fact_enriched` | `ts_collect/ts_collect_std` | 原始及标准采集时间 | 从 DWD 事实传递 |
|  | `created_at/updated_at` | 服务配置时间 | 从服务维度传递 |
|  | `ts_event` | 小时作业时间 | 事实及维度均按相同 `${data_time}` 取数 |
| `dws_agg_minute` | `ts_collect` | DDL 声明但展示 SELECT 来源不完整 | 不能从片段确认最终赋值 |
|  | `ts_collect_std` | DDL 声明但展示汇总 CTE未投影 | 不能从片段确认最终赋值 |
|  | `ts_event` | 小时作业/分区时间 | 来自汇总结果，文档片段未完整投影 |
|  | `ts_data_date` | 日期字符串 | `DATE_FORMAT(ts_event, '%Y-%m-%d')` |
| 聚合内部 | `ts_minute` | 分钟统计窗口 | `DATE_FORMAT(ts_collect_std, '%Y-%m-%d %H:%i:00')` |

### 3.2 时间传播关系

```text
ODS.ts_collect（毫秒）
    └─ TO_TIMESTAMP(ts_collect / 1000)
       → DWD.ts_collect_std
       → DWS富化.ts_collect_std
       └─ DATE_FORMAT(..., 分钟)
          → 分钟统计窗口 ts_minute

调度参数 ${data_time}
    ├─ 控制 ODS.mq_timestamp 的小时读取窗口
    ├─ 生成 DWD事实.ts_event
    ├─ 生成两个DWD维度.ts_event
    ├─ 控制 DWS富化事实快照
    └─ 控制分钟聚合作业分区并派生 ts_data_date
```

这说明至少存在三种不同时间：

1. **采集时间**：`ts_collect/ts_collect_std`，决定分钟指标落在哪一分钟；
2. **消息到达时间**：`mq_timestamp`，决定原始记录被哪个小时作业读取；
3. **处理/快照时间**：`ts_event=${data_time}`，决定幂等删除、表分区和维度快照。

若消息迟到，记录可能按 `mq_timestamp` 进入当前小时作业，但其 `ts_collect_std` 属于更早分钟；当前文档没有说明迟到回刷、水位线或跨小时补数策略。

## 4. 维度分类

| 分类 | 代表字段 | 主要来源/说明 |
|---|---|---|
| 请求标识 | `pk_id`、`trace_id` | ODS 有原始标识；DWD/DWS重新生成 UUID，文档未展示 `trace_id` 的继续传播 |
| 实体维度 | `entity_id`、`entity_name`、`parent_entity_id/name`、`source_type`、`entity_type`、`business_type` | 事实与 `dwd_dim_model` 富化，存在多源 COALESCE |
| 服务维度 | `service_id`、`service_name`、`service_status`、`service_desc`、`service_full_name` | 事实与 `dwd_dim_service` 富化 |
| 技术维度 | `data_type`、`max_length`、`model_name`、`engine_type`、`flag_moderation`、`flag_dispatcher` | 服务、模板和运行配置 |
| 租户/用户维度 | `tenant_id`；用户、公司、部门字段仅出现在 CTE | 富化 SQL连接用户表，但展示 SELECT 未输出用户属性 |
| 地域/来源维度 | `region`、`region_source` | 服务维度及双站点来源标识 |
| 计费维度 | `is_billing`、`billing_mode`、`resource_name` | 实体配置与计费规格 |
| 请求分类 | `api_path`、`service_type`、`status_code`、`is_streaming` | 事实字段与派生标记 |
| 扩展维度 | `ext_attr_1` 等，聚合表另有 `auth_channel`、`ext_resolution`、`ext_audio` | 多数字段在片段中省略，具体来源不确定 |
| 时间维度 | `ts_minute`、`ts_event`、`ts_data_date` | 分钟窗口、小时快照、日期 |

分钟表文字称有 18 个或 21 个分组维度，但展示的 `t_minute_summary` 仅明确列出 14 个维度字段，`GROUP BY` 却引用位置 1–18。准确粒度必须以完整 SQL 为准，不能由片段可靠恢复。

## 5. 指标与公式

### 5.1 明细基础指标

`dwd_fact_request` 从 ODS 直接传递：

- 请求计数：`cnt_total`、`cnt_success`、`cnt_client_err`、`cnt_server_err`
- 用量：`val_total`、`val_input`、`val_output`
- 性能：`val_metric_a`、`val_metric_b`、`val_latency`

派生标记：

```sql
is_streaming =
  CASE WHEN val_metric_a = 0 OR val_metric_b = 0
       THEN FALSE ELSE TRUE END
```

它是启发式规则，不是流式协议的直接字段；NULL 输入会落入 `ELSE TRUE`，需确认是否符合业务预期。

### 5.2 富化阶段特殊用量

当 `billing_mode = '7'`、扩展字段不含 `None` 且状态成功时：

```text
image_input = width × height / 64 / 1000
val_input   = image_input
val_total   = image_input + val_output
```

其他情况：

```text
val_input = 原 val_input
val_total = COALESCE(NULLIF(val_input + val_output, 0), 原 val_total)
```

这里 `billing_mode` DDL 为 INTEGER，而 SQL 与字符串 `'7'` 比较；`status_code` DDL 为 VARCHAR，却与数值 `200` 比较。数据库可能隐式转换，但应统一类型。

### 5.3 分钟聚合指标

| 指标 | 文档公式 | 备注 |
|---|---|---|
| `rpm` | `SUM(cnt_total)` | 名称隐含“每分钟”，成立依赖实际分组包含 `ts_minute` |
| `tpm` | `SUM(val_total) * 1000` | 乘 1000 的单位依据未说明 |
| `tpm_input/output` | `SUM(val_input/output) * 1000` | 同上 |
| `metric_a_avg` | `AVG(CASE WHEN val_metric_a > 0 THEN val_metric_a END)` | 排除 0 与非正数 |
| `metric_b_avg` | 同上 | 排除 0 与非正数 |
| `latency_avg` | `AVG(CASE WHEN val_latency > 0 THEN val_latency END)` | 排除 0 与非正数 |
| `cnt_total/success` | 对应字段求和 | 明细中字段本身可能已是计数 |
| `cnt_error` | `cnt_client_err + cnt_server_err` | 客户端与服务端错误之和 |
| `err_rate` | `(cnt_client_err + cnt_server_err) / NULLIF(cnt_total, 0)` | 需确认数据库是否发生整数除法 |
| `val_total/input/output` | 对应字段求和 | 聚合后总量 |
| `price_input` | `val_input * price_input` | 依赖价格表唯一且同单位 |
| `price_output` | `val_output * price_output` | 同上 |
| `price_total` | `price_input金额 + price_output金额` | NULL 价格会令结果为 NULL |
| `tps_input/output/total` | 对应 `tpm / 60.0` | 如果 TPM 已被乘 1000，TPS继承该换算 |
| `ext_cache_token` | `SUM(ext_cache_token)` | 字段在富化表 DDL/SELECT 中未展示，来源不闭合 |
| `real_cached_tokens` | `SUM(real_cached_tokens)` | 同上 |

### 5.4 分位数

对 `val_input`、`val_output`、`val_metric_a`、`val_metric_b` 分别计算：

```text
PERCENTILE_DISC(0.5 / 0.8 / 0.9 / 0.99)
MAX(...)
```

每类分位数只纳入对应字段 `> 0` 的记录。它们与主汇总通过分钟和完整分组维度连接；片段仅展示部分 JOIN 条件，因此无法确认是否存在错配或一对多。

值得注意的是：

- `val_input_avg` 在最终 SELECT 中取 `t_summary.val_input`，该值是 `SUM(val_input)`，并非平均值；
- `val_output_avg` 同样取汇总值而不是 AVG；
- DDL 有 `metric_a_avg/metric_b_avg`，但无 `val_input/output` 真正均值的可见计算。

## 6. 表级主血缘

### 6.1 核心链路

```text
ods_source_a ─┐
              ├─ UNION ALL → dwd_fact_request
ods_source_b ─┘

config_table_a / config_table_a_hk ─┐
config_table_b / config_table_b_hk ─┼→ dwd_dim_model
dwd_billing_spec ────────────────────┘

service_spec_table ───────────┐
platform_service_table ───────┤
template_config_table ────────┼→ dwd_dim_service
pool_detail_daily ─────────────┤
engine_running_summary ────────┘

dwd_fact_request ──────────────┐
dwd_dim_model ─────────────────┤
dwd_dim_service ───────────────┤
excluded_tenant_list ──────────┼→ dws_fact_enriched
user_base_table ────────────────┤
meta_customer_table ────────────┘

dws_fact_enriched ──────────────┐
sku_price_dict ─────────────────┴→ dws_agg_minute
```

### 6.2 血缘置信度说明

- 核心 7 张表的表级边有明确 SQL 证据，置信度高。
- `user_base_table` 和 `meta_customer_table` 虽参与 JOIN，但展示 SELECT 未使用其字段；它们是执行依赖，却未必产生输出字段血缘。
- `t_service_props`、`t_pool_detail` 被 JOIN，但展示 SELECT 未直接使用其字段；可能影响行数，也可能是脱敏省略造成的不可见字段。
- “专属模型表”和“理论指标表”仅在文字说明中出现，没有可见 SQL 边，不能纳入确定血缘。

## 7. 推断的加工顺序

在不考虑调度平台外部依赖时，数据依赖给出的最小拓扑顺序为：

1. CDM/外部流程将主站、副站请求写入 `ods_source_a/b`；
2. 配置、服务、计费和运行状态等辅助表准备完成；
3. 可并行执行：
   - `ods_source_a/b → dwd_fact_request`
   - 配置表与计费规格 → `dwd_dim_model`
   - 服务与运行配置 → `dwd_dim_service`
4. 三张 DWD 表同一 `${data_time}` 快照齐备后，生成 `dws_fact_enriched`；
5. 富化事实完成后，生成 `dws_agg_minute`。

每个目标表采用：

```sql
DELETE WHERE ts_event = '${data_time}';
INSERT ...
```

因此设计意图是小时分区幂等重跑。但这两条语句若不在事务中，DELETE 成功而 INSERT 失败会留下空分区。真实调度顺序、事务边界、失败重试和 CDM 完成标志未在文档中给出。

## 8. 复杂加工逻辑

1. **双站点合并**：每站点先 `SELECT DISTINCT`，再 `UNION ALL`。这只能消除站点内部完全重复，不能消除跨站点重复。
2. **实体配置统一**：系统实体和两类自定义实体使用不同投影合并；父 ID 为空时回退自身，并自关联获取父名称。
3. **最新计费资源**：限定 `${data_time}` 前 2 天到后 1 天，再按实体取最大 `start_time`；同一实体同一开始时间多行时仍可能重复。
4. **服务配置拼装**：驱动表配合平台服务、JSON 模板、最新规格、近 3 天资源池和近 5 小时运行状态进行多路 LEFT JOIN。
5. **维度快照富化**：事实和两个维度使用相同 `${data_time}`，通过 COALESCE 明确事实优先或配置优先。
6. **租户排除**：先 LEFT JOIN 名单再筛选 NULL，属于 anti-join；分钟层又以常量执行一次排除，形成双重规则。
7. **特殊计费公式**：从字符串分辨率解析宽高并按面积折算，依赖字符串格式严格合法。
8. **分位数计算**：四个独立 CTE按同一细粒度分组后再回连主汇总，计算开销和连接正确性均较敏感。

## 9. 潜在数据质量与口径风险

### 9.1 可从片段直接确认的结构问题

| 风险 | 证据 | 影响 |
|---|---|---|
| ODS 双表结构不完全一致却使用 `SELECT * UNION ALL` | 文档说明副站缺 `err_detail` | 如果 CTE未显式补 NULL 并对齐列，SQL 可能失败或错位 |
| DWD 事实投影不闭合 | ODS DDL是 `err_detail`，DWD 使用 `status_code`；片段省略字段 | 无法证明状态码来源和字段顺序正确 |
| 实体维度 CTE字段不闭合 | `t_all_entities` 展示投影没有 `source_type/limit_rpm/limit_tpm`，最终却引用 | 完整 SQL 若同样缺失会编译失败 |
| 聚合 CTE字段不闭合 | 最终引用 `ts_collect`、`ts_collect_std`、`ts_event`、`source_type` 等，展示汇总 CTE未投影 | 当前片段无法复现运行 |
| 分组数量矛盾 | 代码注释称18个，文末称21个，展示明确字段更少 | 粒度和分位数 JOIN 键不确定 |
| 平均值命名错误 | `val_input_avg = t_summary.val_input`，后者是 SUM | 报表会把总量误解为均值 |
| 类型比较不一致 | INTEGER `billing_mode` 对 `'7'`；VARCHAR `status_code` 对 `200` | 依赖隐式转换，兼容性和结果有风险 |

### 9.2 业务口径风险

- `DISTINCT` 不等于按业务键去重；DWD 又生成新 UUID，可能掩盖重复请求。
- `UNION ALL` 可能把跨站点同步或重放的同一请求重复计数；`trace_id` 未在 DWD 展示保留。
- 分钟归属按采集时间，小时读取按 MQ 时间；迟到消息会产生跨分区分钟，若只重跑当前小时可能漏补历史分钟。
- `is_streaming` 将 NULL 指标判断为 TRUE，且规则仅由两个性能值是否为 0 决定。
- `is_billing` 除 `business_type='free'` 外全部 TRUE，包括 NULL 或未知类型。
- 服务名称存在事实、配置和特殊引擎回退逻辑，不同报表若使用 `service_name` 与 `service_full_name` 可能口径不同。
- 特定租户既在富化层用名单排除，又在分钟层用硬编码 ID 排除；两套规则可能漂移。
- `err_rate` 未显式转浮点；应验证 DWS 方言中整数除法行为。
- `tpm = SUM(val_total) * 1000` 的 1000 倍换算没有单位说明；需确认 `val_*` 原始单位。
- 价格表只按 `service_id` 连接，未见时间、生效版本、区域或币种条件；若多行会放大聚合结果。
- 特殊图片计费使用字符串拆分并强转 BIGINT，脏格式、空值、非整数、额外分隔符会导致失败或错误计费。
- 多路 LEFT JOIN 的维度源若键不唯一，会复制事实行并放大所有后续指标。
- 分位数排除 0 值，而总量与均值的过滤策略不同；二者样本总体不一致。

### 9.3 工程与性能风险

- `DELETE + INSERT` 非原子时可能产生空分区；
- 多处 `SELECT *` 会在上游加字段或调整列顺序时引发隐式变更；
- 四次扫描富化事实计算分位数，且按高维粒度分组，可能消耗较大；
- `PERCENTILE_DISC` 返回离散观测值，是否符合报表期望需确认；
- 大量高基数维度参与分组可能使分钟表接近明细规模；
- DWS 表分布键与主要 JOIN/GROUP BY 键是否匹配，文档不足以评估。

## 10. 变更影响示例

### 示例 A：在 ODS 新增字段

变更：`ods_source_a/b` 新增 `auth_channel`。

直接影响：

- 两个 ODS DDL；
- `t_source_a/t_source_b` 的列对齐；
- `SELECT * UNION ALL` 的兼容性；
- `dwd_fact_request` DDL和 INSERT 投影。

如需传播到分钟报表，还需依次修改：

```text
dwd_fact_request
→ dws_fact_enriched
→ dws_agg_minute（若作为维度则加入所有汇总与分位数 GROUP BY/JOIN 键）
```

风险：把字段加入分钟分组会提高粒度、增加行数，并改变全部现有指标的聚合口径；只作为展示字段又无法在同一聚合行中唯一取值。

### 示例 B：修改采集时间语义

变更：分钟归属由 `ts_collect_std` 改为 `mq_timestamp`。

影响：

- ODS→DWD 必须保留 `mq_timestamp`；
- DWD、富化事实 DDL和字段血缘需要增加该字段；
- `t_minute_summary` 和四个分位数 CTE的 `ts_minute` 表达式都要同步；
- 历史分钟分区需重算，迟到数据归属会改变；
- 与原指标做同比/环比时会出现不可直接比较的口径断点。

### 示例 C：调整特殊计费公式

变更：`width × height / 64 / 1000` 的除数或成功条件发生改变。

影响路径：

```text
dws_fact_enriched.val_input / val_total
→ dws_agg_minute.val_*、tpm_*、tps_*、price_*
→ 所有消费分钟表的下游报表（文档未提供）
```

还会影响 input/total 的分位数。需要明确生效时间、价格版本，并确定历史数据是否回刷。

### 示例 D：服务维度增加区域版本条件

变更：`dwd_dim_service` 从仅按 `service_id` 关联，改为 `service_id + region`。

可能修复跨区域错配，但会影响：

- 服务维度主键定义和唯一性；
- 富化事实的 JOIN 条件；
- `service_name/status/data_type/engine_type/region` 等字段；
- 分钟表分组及按服务、区域统计的所有指标。

发布前应比较变更前后的事实行数、未匹配率和每个请求键的重复倍数。

## 11. 文档省略导致的不确定项

以下内容不能从当前附件可靠确定，产品分析结果应显示为“待补充/低置信度”：

1. `...` 省略的完整列清单、列顺序和 `UNION ALL` 对齐方式；
2. `status_code`、`region`、聚合扩展字段等的精确来源；
3. 分钟表完整的 18 或 21 个分组维度及所有分位数 JOIN 条件；
4. `trace_id` 是否在真实 DWD 中保留，以及真正的业务去重键；
5. 辅助表的 DDL、唯一键、数据层级、分区和生效时间；
6. `t_service_props`、`t_pool_detail`、用户表、客户表的实际输出用途；
7. 文字提到但 SQL 未展示的专属模型表、理论指标表；
8. 价格表的唯一性、币种、单位、版本和生效区间；
9. `${data_time}` 的类型、时区、调度频率和补数规则；
10. 毫秒时间戳转换使用的时区；
11. DWS 方言对 `DATE_FORMAT`、`DATE_ADD`、整数除法和隐式类型转换的具体行为；
12. DELETE 与 INSERT 是否在同一事务内；
13. DWS 之后是否还有小时表、ADS 表、BI 报表或外部程序消费者；
14. 数据样例、字段基数、NULL 比例、维度键重复率和实际数据量。

## 12. 建议的真实脚本验收顺序

在接入产品时，建议按以下顺序核验：

1. 导入所有完整 DDL 和未经截断的 SQL；
2. 先解决解析失败、字段投影不闭合和 `SELECT *` 列对齐；
3. 建立表级血缘并核对上述核心主链；
4. 展开字段级时间血缘，确认采集/MQ/调度时间的区别；
5. 对每个维度 JOIN 检查连接前后行数和键唯一性；
6. 以一小时真实脱敏样例人工复算 RPM、TPM、错误率、费用和分位数；
7. 明确完整分钟粒度，修正“18/21维”矛盾及 `*_avg` 口径；
8. 用新增字段、计费公式调整、时间字段调整三个案例验证传递影响；
9. 最后补充 DWS 下游 ADS/报表脚本，闭合端到端影响范围。

