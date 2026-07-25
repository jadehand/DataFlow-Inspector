CREATE TABLE schema.dws_fact_enriched (
    pk_id VARCHAR(36), api_path TEXT, entity_id VARCHAR(255),
    platform_service_id VARCHAR(255), entity_name VARCHAR(255), resource_name VARCHAR(255),
    service_desc TEXT, is_billing BOOLEAN, service_id VARCHAR(255),
    service_name VARCHAR(255), service_status VARCHAR(255), data_type VARCHAR(255),
    max_length BIGINT, model_name VARCHAR(255), engine_type VARCHAR(128),
    flag_moderation TINYINT, flag_dispatcher VARCHAR(255), created_at TIMESTAMP,
    updated_at TIMESTAMP, tenant_id VARCHAR(255), ts_collect BIGINT,
    cnt_total BIGINT, cnt_success BIGINT, cnt_client_err BIGINT, cnt_server_err BIGINT,
    val_total FLOAT8, val_input FLOAT8, val_output FLOAT8, val_metric_a FLOAT8,
    val_metric_b FLOAT8, val_latency FLOAT8, ts_collect_std TIMESTAMP, ts_event TIMESTAMP,
    service_full_name VARCHAR(64), service_full_desc TEXT, status_code VARCHAR(64),
    region VARCHAR(64), parent_entity_id VARCHAR(128), parent_entity_name VARCHAR(256),
    source_type VARCHAR(64), billing_mode INTEGER, entity_type VARCHAR(128),
    business_type VARCHAR(64), ext_attr_1 VARCHAR(255), ext_attr_2 FLOAT8,
    region_source VARCHAR(64), service_type INTEGER, is_streaming BOOLEAN
)
WITH (ORIENTATION = COLUMN, COMPRESSION = 'middle', period = '1 day', ttl = '1 month')
DISTRIBUTE BY HASH (pk_id)
PARTITION BY RANGE (ts_event);
