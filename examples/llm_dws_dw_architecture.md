# LLM API 调用数仓分层落地方案（GaussDB (DWS)）

> ⚠️ **声明：本文档中所有表结构、数据、字段、客户 ID、模型名称为 AI 模拟生成，不包含任何真实业务数据。**

## 架构总览

- **架构链路**：ODS → DWD → DIM → DWS → ADS
- **调度模式**：小时增量 ETL，幂等 Delete+Insert
- **分区策略**：统一按天 RANGE 分区，保留 p_default 兜底脏时间数据；不启用 PERIOD/TTL 自动分区，过期分区使用外部定时脚本清理
- **存储规范**：列存 compress=middle；列存聚合表不创建 B 树索引
- **分布键结论**（业务数据验证无严重倾斜）：

| 分层 | 分布策略 |
|------|---------|
| ODS/DWD 明细 | HASH(request_id) |
| DWS 分钟聚合 | HASH(customer_id, model_id) |
| ADS 日汇总 | HASH(customer_id) |
| DIM 维表 | REPLICATION 复制分布 |

---

## 0. 创建分层 Schema

```sql
CREATE SCHEMA IF NOT EXISTS ods;
CREATE SCHEMA IF NOT EXISTS dwd;
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS dws;
CREATE SCHEMA IF NOT EXISTS ads;
```

---

## 1. ODS 原始贴源层 `ods.ods_llm_api_request_log`

原始网关采集 LLM API 请求日志，不清洗、不关联维度；短期留存（1~3 天）

```sql
CREATE TABLE IF NOT EXISTS ods.ods_llm_api_request_log (
    request_id         VARCHAR(64)  COMMENT '单次请求唯一ID(UUID)',
    trace_id           VARCHAR(64)  COMMENT '全链路追踪ID',
    site_code          VARCHAR(32)  COMMENT '站点编码，区分多站点网关',
    customer_id        VARCHAR(64)  COMMENT '客户租户ID',
    api_token          VARCHAR(128) COMMENT '调用方鉴权token',
    model_id           VARCHAR(64)  COMMENT '请求模型ID',
    input_tokens       BIGINT       COMMENT '输入prompt token量',
    output_tokens      BIGINT       COMMENT '输出completion token量',
    total_tokens       BIGINT       COMMENT '总token(input+output)',
    req_start_time     TIMESTAMPTZ  COMMENT '请求发起时间(UTC+8)',
    req_end_time       TIMESTAMPTZ  COMMENT '请求结束时间',
    latency_ms         INT          COMMENT '接口耗时ms',
    http_status        INT          COMMENT 'HTTP状态码',
    err_code           VARCHAR(32)  COMMENT '错误码，0=成功',
    err_msg            TEXT         COMMENT '错误信息',
    stream_flag        BOOLEAN      COMMENT '是否流式输出true/false',
    request_ip         VARCHAR(48)  COMMENT '客户端IP',
    raw_ext_info       TEXT         COMMENT '原始扩展JSON字段',
    dt                 VARCHAR(10)  COMMENT '分区日期 yyyy-MM-dd',
    hour_no            VARCHAR(2)   COMMENT '小时编号 00~23'
)
WITH (
    orientation = column,
    compress = middle
)
DISTRIBUTE BY HASH(request_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='ODS LLM大模型API原始调用请求日志；按天分区；短期留存；不启用PERIOD/TTL；原始数据不做维度关联';

-- 测试插入数据
INSERT INTO ods.ods_llm_api_request_log
(
request_id,trace_id,site_code,customer_id,api_token,model_id,
input_tokens,output_tokens,total_tokens,req_start_time,req_end_time,
latency_ms,http_status,err_code,err_msg,stream_flag,request_ip,raw_ext_info,dt,hour_no
)
VALUES
(
'req_001','trace_991','site_sh','cust_0086','tk_demo1','model_alpha',
120,86,206,'2026-07-25 10:05:23','2026-07-25 10:05:25',
1820,200,'0','',true,'10.0.0.1','{"channel":"api-gw"}','2026-07-25','10'
);
```

---

## 2. DWD 明细清洗层 `dwd.dwd_llm_api_request_detail`

原子请求明细；仅清洗、过滤、标准化；**禁止提前关联维度表**

```sql
CREATE TABLE IF NOT EXISTS dwd.dwd_llm_api_request_detail (
    request_id         VARCHAR(64)  COMMENT '单次请求唯一ID',
    trace_id           VARCHAR(64)  COMMENT '全链路追踪ID',
    site_code          VARCHAR(32)  COMMENT '站点编码',
    customer_id        VARCHAR(64)  COMMENT '客户租户ID',
    api_token          VARCHAR(128) COMMENT '调用鉴权token',
    model_id           VARCHAR(64)  COMMENT '模型ID',
    input_tokens       BIGINT       COMMENT '输入token数',
    output_tokens      BIGINT       COMMENT '输出token数',
    total_tokens       BIGINT       COMMENT '总token',
    req_start_time     TIMESTAMPTZ  COMMENT '请求开始时间',
    req_end_time       TIMESTAMPTZ  COMMENT '请求结束时间',
    latency_ms         INT          COMMENT '耗时ms',
    http_status        INT          COMMENT 'HTTP状态码',
    err_code           VARCHAR(32)  COMMENT '错误码',
    err_msg            TEXT         COMMENT '错误信息',
    stream_flag        BOOLEAN      COMMENT '流式标识',
    request_ip         VARCHAR(48)  COMMENT '客户端IP',
    is_success         BOOLEAN      COMMENT '是否调用成功(err_code=0)',
    dt                 VARCHAR(10)  COMMENT '分区日期 yyyy-MM-dd',
    hour_no            VARCHAR(2)   COMMENT '小时编号00~23',
    min_time           TIMESTAMP    COMMENT '按分钟截断时间，用于DWS分钟聚合'
)
WITH (
    orientation = column,
    compress = middle
)
DISTRIBUTE BY HASH(request_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='DWD LLM API清洗请求明细；原子单请求粒度；仅清洗不关联维度；按天分区，留存30天';
```

### ODS → DWD ETL（小时调度，参数 `${bizdate}`, `${bizhour}`）

```sql
DELETE FROM dwd.dwd_llm_api_request_detail
WHERE dt = '${bizdate}'
AND hour_no = '${bizhour}';

INSERT INTO dwd.dwd_llm_api_request_detail
SELECT
    request_id,
    trace_id,
    site_code,
    customer_id,
    api_token,
    model_id,
    input_tokens,
    output_tokens,
    COALESCE(total_tokens, input_tokens + output_tokens) AS total_tokens,
    req_start_time,
    req_end_time,
    latency_ms,
    http_status,
    err_code,
    err_msg,
    stream_flag,
    request_ip,
    CASE WHEN err_code = '0' THEN true ELSE false END AS is_success,
    dt,
    hour_no,
    DATE_TRUNC('minute', req_start_time) AS min_time
FROM ods.ods_llm_api_request_log
WHERE dt = '${bizdate}'
  AND hour_no = '${bizhour}'
  AND request_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND model_id IS NOT NULL;
```

---

## 3. DIM 维度表 `dim.dim_llm_model_info`

模型基础维表，DWS 聚合层 JOIN 补维；行存复制分布

```sql
CREATE TABLE IF NOT EXISTS dim.dim_llm_model_info (
    model_id            VARCHAR(64) PRIMARY KEY COMMENT '模型唯一ID',
    model_name          VARCHAR(128) COMMENT '模型名称 qwen7b/llama3',
    model_type          VARCHAR(32)  COMMENT '模型类型 chat/embedding/rerank',
    model_version       VARCHAR(32)  COMMENT '模型版本',
    model_provider      VARCHAR(64)  COMMENT '厂商',
    token_price_input   DECIMAL(20,8) COMMENT '输入token单价',
    token_price_output  DECIMAL(20,8) COMMENT '输出token单价',
    max_context_len     INT          COMMENT '最大上下文长度',
    valid_start_time    TIMESTAMPTZ  COMMENT '生效起始时间',
    valid_end_time      TIMESTAMPTZ  COMMENT '失效时间，9999代表永久生效'
)
WITH (orientation = row)
DISTRIBUTE BY REPLICATION
COMMENT='DIM LLM模型配置维度表；行存；主键自带索引；复制分布；DWS层关联补维使用';

INSERT INTO dim.dim_llm_model_info
(model_id,model_name,model_type,model_version,model_provider,token_price_input,token_price_output,max_context_len,valid_start_time,valid_end_time)
VALUES
('model_alpha','Alpha-7B-Chat','chat','v1.0','AI模拟厂商A',0.00015,0.0003,32768,'2025-01-01','9999-12-31'),
('model_beta','Beta-8B-Instruct','chat','v1.0','AI模拟厂商B',0.00012,0.00024,8192,'2025-01-01','9999-12-31');
```

---

## 4. DWS 分钟聚合层 `dws.dws_llm_api_model_minute_stat`

在此处关联维表补维度；客户 + 模型分钟指标；分布键 `customer_id, model_id`，已验证无严重倾斜

```sql
CREATE TABLE IF NOT EXISTS dws.dws_llm_api_model_minute_stat (
    stat_minute         TIMESTAMP    COMMENT '统计分钟（req_start_time截断分钟）',
    dt                  VARCHAR(10)  COMMENT '分区日期 yyyy-MM-dd',
    hour_no             VARCHAR(2)   COMMENT '小时编号00~23',
    site_code           VARCHAR(32)  COMMENT '站点编码',
    customer_id         VARCHAR(64)  COMMENT '客户租户ID',
    model_id            VARCHAR(64)  COMMENT '模型ID',
    model_name          VARCHAR(128) COMMENT '模型名称',
    model_type          VARCHAR(32)  COMMENT '模型类型',
    model_provider      VARCHAR(64)  COMMENT '模型厂商',
    request_cnt         BIGINT       COMMENT '总请求次数',
    success_cnt         BIGINT       COMMENT '成功请求次数',
    fail_cnt            BIGINT       COMMENT '失败请求次数',
    input_tokens_sum    BIGINT       COMMENT '输入token总和',
    output_tokens_sum   BIGINT       COMMENT '输出token总和',
    total_tokens_sum    BIGINT       COMMENT '总token总和',
    avg_latency_ms      DECIMAL(12,2) COMMENT '平均耗时ms',
    p95_latency_ms      DECIMAL(12,2) COMMENT 'P95耗时ms',
    cost_input          DECIMAL(20,6) COMMENT '输入token预估费用',
    cost_output         DECIMAL(20,6) COMMENT '输出token预估费用',
    total_cost          DECIMAL(20,6) COMMENT '合计预估费用'
)
WITH (
    orientation = column,
    compress = middle
)
DISTRIBUTE BY HASH(customer_id, model_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='DWS LLM API 客户+模型 分钟级聚合统计表；DWD JOIN维表补维；按天分区；禁止手动创建B树索引';
```

### DWD → DWS ETL（小时调度）

```sql
DELETE FROM dws.dws_llm_api_model_minute_stat
WHERE dt = '${bizdate}'
AND hour_no = '${bizhour}';

INSERT INTO dws.dws_llm_api_model_minute_stat
SELECT
    t.min_time AS stat_minute,
    t.dt,
    t.hour_no,
    t.site_code,
    t.customer_id,
    t.model_id,
    m.model_name,
    m.model_type,
    m.model_provider,
    COUNT(1) AS request_cnt,
    COUNT(CASE WHEN t.is_success THEN 1 END) AS success_cnt,
    COUNT(CASE WHEN NOT t.is_success THEN 1 END) AS fail_cnt,
    SUM(t.input_tokens) AS input_tokens_sum,
    SUM(t.output_tokens) AS output_tokens_sum,
    SUM(t.total_tokens) AS total_tokens_sum,
    AVG(t.latency_ms) AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY t.latency_ms) AS p95_latency_ms,
    SUM(t.input_tokens) * m.token_price_input AS cost_input,
    SUM(t.output_tokens) * m.token_price_output AS cost_output,
    SUM(t.input_tokens) * m.token_price_input + SUM(t.output_tokens) * m.token_price_output AS total_cost
FROM dwd.dwd_llm_api_request_detail t
LEFT JOIN dim.dim_llm_model_info m
    ON t.model_id = m.model_id
WHERE t.dt = '${bizdate}'
  AND t.hour_no = '${bizhour}'
GROUP BY
    t.min_time,
    t.dt,
    t.hour_no,
    t.site_code,
    t.customer_id,
    t.model_id,
    m.model_name,
    m.model_type,
    m.model_provider;
```

---

## 5. ADS 业务汇总层 `ads.ads_llm_customer_model_daily_stat`

面向账单、BI 报表；日粒度汇总，永久留存，不配置自动清理

```sql
CREATE TABLE IF NOT EXISTS ads.ads_llm_customer_model_daily_stat (
    dt                  VARCHAR(10) COMMENT '统计日期',
    customer_id         VARCHAR(64) COMMENT '客户ID',
    model_id            VARCHAR(64) COMMENT '模型ID',
    model_name          VARCHAR(128) COMMENT '模型名称',
    request_cnt         BIGINT COMMENT '总请求量',
    success_rate        DECIMAL(10,4) COMMENT '成功率',
    input_tokens_sum    BIGINT COMMENT '输入token总量',
    output_tokens_sum   BIGINT COMMENT '输出token总量',
    total_tokens_sum    BIGINT COMMENT '总token',
    total_cost          DECIMAL(20,6) COMMENT '当日预估费用'
)
WITH (
    orientation = column,
    compress = middle
)
DISTRIBUTE BY HASH(customer_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='ADS 客户-模型日汇总账单表；供业务账单、报表；永久留存';
```

### DWS → ADS ETL（每日凌晨离线调度）

```sql
TRUNCATE TABLE ads.ads_llm_customer_model_daily_stat PARTITION FOR(to_date('${bizdate}','yyyy-MM-dd'));

INSERT INTO ads.ads_llm_customer_model_daily_stat
SELECT
    dt,
    customer_id,
    model_id,
    model_name,
    SUM(request_cnt) AS request_cnt,
    CASE WHEN SUM(request_cnt) > 0 THEN ROUND(SUM(success_cnt)::DECIMAL/SUM(request_cnt),4) ELSE 0 END AS success_rate,
    SUM(input_tokens_sum) AS input_tokens_sum,
    SUM(output_tokens_sum) AS output_tokens_sum,
    SUM(total_tokens_sum) AS total_tokens_sum,
    SUM(total_cost) AS total_cost
FROM dws.dws_llm_api_model_minute_stat
WHERE dt = '${bizdate}'
GROUP BY dt,customer_id,model_id,model_name;
```

---

## 附录 1：过期分区清理脚本

替代 TTL，DataArts 定时任务执行。

```sql
-- 清理DWD 30天前分区示例，按需复制修改表名
DO $$
DECLARE
    drop_part_sql text;
BEGIN
    FOR drop_part_sql IN
    SELECT 'DROP TABLE dwd.dwd_llm_api_request_detail PARTITION FOR(to_date('''||dt||''',''yyyy-MM-dd''));'
    FROM pg_partitions
    WHERE schemaname='dwd' AND tablename='dwd_llm_api_request_detail'
    AND to_date(partitionrange, 'yyyy-MM-dd') < current_date - INTERVAL '30 days'
    LOOP
        EXECUTE drop_part_sql;
    END LOOP;
END $$;
```

---

## 附录 2：热点倾斜巡检 SQL

日常运维使用。

```sql
-- DWS层巡检客户+模型热度，监控热点组合
SELECT
    customer_id,
    model_id,
    COUNT(*) AS record_cnt
FROM dws.dws_llm_api_model_minute_stat
WHERE dt = '${bizdate}'
GROUP BY customer_id, model_id
ORDER BY record_cnt DESC
LIMIT 50;
```

---

## 附录 3：架构核心规范摘要

### 分层职责

| 分层 | 职责 |
|------|------|
| ODS | 原始接入，不清洗不关联维度 |
| DWD | 明细清洗标准化，**禁止提前 JOIN 维度** |
| DWS | 聚合层执行维度补维，分钟粒度指标 |
| ADS | 面向业务报表高度汇总 |

### 分区策略

统一按天 RANGE，保留 p_default 兜底脏数据；不启用 PERIOD/TTL 自动分区，使用定时脚本清理过期分区。

### 存储规范

- 列存表 compress=middle
- 列存事实/聚合表不手动新建 B 树索引

### 调度策略

| 阶段 | 策略 |
|------|------|
| ODS→DWD、DWD→DWS | 小时增量调度 |
| DWS→ADS | 凌晨日调度 |

### 分布键策略

| 分层 | 分布键 | 说明 |
|------|--------|------|
| ODS/DWD | `HASH(request_id)` | 明细表，请求粒度均匀分布 |
| DWS | `HASH(customer_id, model_id)` | 聚合层，已验无严重倾斜 |
| ADS | `HASH(customer_id)` | 日汇总，按客户均匀分布 |
| DIM 维表 | `REPLICATION` | 各节点全量副本 |

### ETL 幂等机制

优先 DELETE 当前小时/天分区数据，再 INSERT，支持重跑、补数。
