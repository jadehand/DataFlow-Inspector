CREATE SCHEMA IF NOT EXISTS ads;

CREATE TABLE ads.ads_token_realtime (
    stat_minute      TIMESTAMP,
    tenant_id        VARCHAR(32),
    model_code       VARCHAR(64),
    region_code      VARCHAR(16),
    request_cnt      BIGINT,
    success_cnt      BIGINT,
    success_rate     NUMERIC(12,6),
    total_token_cnt  BIGINT,
    avg_latency_ms   NUMERIC(18,2),
    dt               DATE
);

CREATE TABLE ads.ads_token_daily (
    stat_date        DATE,
    tenant_id        VARCHAR(32),
    region_code      VARCHAR(16),
    request_cnt      BIGINT,
    success_cnt      BIGINT,
    success_rate     NUMERIC(12,6),
    total_token_cnt  BIGINT
);

CREATE TABLE ads.ads_region_report (
    stat_date        DATE,
    region_code      VARCHAR(16),
    region_name      VARCHAR(64),
    bureau_code      VARCHAR(16),
    request_cnt      BIGINT,
    success_rate     NUMERIC(12,6),
    total_token_cnt  BIGINT
);
