CREATE SCHEMA IF NOT EXISTS ods;

CREATE TABLE ods.ods_token_request (
    request_id       VARCHAR(64),
    tenant_id        VARCHAR(32),
    model_code       VARCHAR(64),
    region_code      VARCHAR(16),
    status_code      VARCHAR(16),
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    latency_ms       INTEGER,
    request_time     TIMESTAMP,
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    ingestion_time   TIMESTAMP,
    dt               DATE
) WITH (orientation = column, compression = low)
DISTRIBUTE BY HASH(request_id);
