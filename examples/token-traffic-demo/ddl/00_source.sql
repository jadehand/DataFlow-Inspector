CREATE SCHEMA IF NOT EXISTS rds;

CREATE TABLE rds.token_request (
    request_id       VARCHAR(64) NOT NULL,
    tenant_id        VARCHAR(32) NOT NULL,
    model_code       VARCHAR(64) NOT NULL,
    region_code      VARCHAR(16) NOT NULL,
    status_code      VARCHAR(16) NOT NULL,
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    latency_ms       INTEGER,
    request_time     TIMESTAMP NOT NULL,
    created_at       TIMESTAMP NOT NULL,
    updated_at       TIMESTAMP
);
