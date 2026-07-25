CREATE SCHEMA IF NOT EXISTS dwd;

CREATE TABLE dwd.dwd_token_request (
    request_id       VARCHAR(64),
    tenant_id        VARCHAR(32),
    model_code       VARCHAR(64),
    region_code      VARCHAR(16),
    status_code      VARCHAR(16),
    input_tokens     BIGINT,
    output_tokens    BIGINT,
    total_tokens     BIGINT,
    latency_ms       INTEGER,
    event_time       TIMESTAMP,
    ingestion_time   TIMESTAMP,
    dt               DATE
) WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH(request_id);

CREATE TABLE dwd.dwd_token_request_wide (
    request_id       VARCHAR(64),
    tenant_id        VARCHAR(32),
    tenant_name      VARCHAR(128),
    industry         VARCHAR(64),
    customer_tier    VARCHAR(16),
    model_code       VARCHAR(64),
    model_family     VARCHAR(64),
    provider         VARCHAR(64),
    region_code      VARCHAR(16),
    region_name      VARCHAR(64),
    bureau_code      VARCHAR(16),
    bureau_name      VARCHAR(64),
    status_code      VARCHAR(16),
    input_tokens     BIGINT,
    output_tokens    BIGINT,
    total_tokens     BIGINT,
    latency_ms       INTEGER,
    event_time       TIMESTAMP,
    ingestion_time   TIMESTAMP,
    dt               DATE
) WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH(request_id);
