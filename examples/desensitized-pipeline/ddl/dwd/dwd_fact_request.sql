CREATE TABLE schema.dwd_fact_request (
    pk_id VARCHAR(36), api_path TEXT, entity_id VARCHAR(255),
    entity_name VARCHAR(255), service_id VARCHAR(255), tenant_id VARCHAR(255),
    ts_collect BIGINT, ts_collect_std TIMESTAMP, ts_event TIMESTAMP,
    cnt_total BIGINT, cnt_success BIGINT, cnt_client_err BIGINT, cnt_server_err BIGINT,
    val_total FLOAT8, val_input FLOAT8, val_output FLOAT8,
    val_metric_a FLOAT8, val_metric_b FLOAT8, val_latency FLOAT8,
    status_code VARCHAR(64), ext_attr_1 VARCHAR(255), ext_attr_2 FLOAT8,
    region VARCHAR(64), region_source VARCHAR(64), service_type INTEGER,
    is_streaming BOOLEAN
)
WITH (ORIENTATION = COLUMN, COMPRESSION = 'middle', period = '1 day', ttl = '1 month')
DISTRIBUTE BY HASH (entity_id, service_id)
PARTITION BY RANGE (ts_event);
