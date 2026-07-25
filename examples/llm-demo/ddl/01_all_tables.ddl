-- ============================================
-- 0. Schema 创建
-- ============================================
CREATE SCHEMA IF NOT EXISTS ods;
CREATE SCHEMA IF NOT EXISTS dwd;
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS dws;
CREATE SCHEMA IF NOT EXISTS ads;

-- ============================================
-- 1. ODS 原始贴源层
-- ============================================
CREATE TABLE IF NOT EXISTS ods.ods_llm_api_request_log (
    request_id         VARCHAR(64)  COMMENT '单次请求唯一ID(UUID)',
    trace_id           VARCHAR(64)  COMMENT '全链路追踪ID',
    site_code          VARCHAR(32)  COMMENT '站点编码',
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
WITH (orientation=column, compress=middle)
DISTRIBUTE BY HASH(request_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='ODS LLM大模型API原始调用请求日志';

-- ============================================
-- 2. DWD 明细清洗层
-- ============================================
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
    min_time           TIMESTAMP    COMMENT '按分钟截断时间'
)
WITH (orientation=column, compress=middle)
DISTRIBUTE BY HASH(request_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='DWD LLM API清洗请求明细；原子单请求粒度；仅清洗不关联维度';

-- ============================================
-- 3. DIM 维度表（行存 + 复制分布）
-- ============================================
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
    valid_end_time      TIMESTAMPTZ  COMMENT '失效时间'
)
WITH (orientation=row)
DISTRIBUTE BY REPLICATION
COMMENT='DIM LLM模型配置维度表；行存；复制分布';

-- ============================================
-- 4. DWS 分钟聚合层
-- ============================================
CREATE TABLE IF NOT EXISTS dws.dws_llm_api_model_minute_stat (
    stat_minute         TIMESTAMP    COMMENT '统计分钟',
    dt                  VARCHAR(10)  COMMENT '分区日期',
    hour_no             VARCHAR(2)   COMMENT '小时编号',
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
WITH (orientation=column, compress=middle)
DISTRIBUTE BY HASH(customer_id, model_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='DWS LLM API 客户+模型 分钟级聚合统计表';

-- ============================================
-- 5. ADS 业务汇总层
-- ============================================
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
WITH (orientation=column, compress=middle)
DISTRIBUTE BY HASH(customer_id)
PARTITION BY RANGE(to_date(dt, 'yyyy-MM-dd'))
(
    PARTITION p_default VALUES LESS THAN (MAXVALUE)
)
COMMENT='ADS 客户-模型日汇总账单表';
