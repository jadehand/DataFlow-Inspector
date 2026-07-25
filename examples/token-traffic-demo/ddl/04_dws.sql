CREATE SCHEMA IF NOT EXISTS dws;

CREATE TABLE dws.dws_token_minute (
    stat_minute      TIMESTAMP,
    tenant_id        VARCHAR(32),
    model_code       VARCHAR(64),
    region_code      VARCHAR(16),
    request_cnt      BIGINT,
    success_cnt      BIGINT,
    failure_cnt      BIGINT,
    input_token_cnt  BIGINT,
    output_token_cnt BIGINT,
    total_token_cnt  BIGINT,
    avg_latency_ms   NUMERIC(18,2),
    dt               DATE
) WITH (orientation = column, compression = high)
DISTRIBUTE BY HASH(tenant_id);

CREATE TABLE dws.dws_token_hour (
    stat_hour        TIMESTAMP,
    tenant_id        VARCHAR(32),
    model_code       VARCHAR(64),
    region_code      VARCHAR(16),
    request_cnt      BIGINT,
    success_cnt      BIGINT,
    failure_cnt      BIGINT,
    total_token_cnt  BIGINT,
    avg_latency_ms   NUMERIC(18,2),
    dt               DATE
) WITH (orientation = column, compression = high)
DISTRIBUTE BY HASH(tenant_id);
