CREATE TABLE schema.dws_agg_minute (
    pk_id VARCHAR(36), entity_id VARCHAR(64), service_name VARCHAR(64),
    resource_name VARCHAR(128), tenant_id VARCHAR(64), ts_collect BIGINT,
    rpm BIGINT, tpm BIGINT, metric_a_avg FLOAT8, metric_b_avg FLOAT8,
    cnt_client_err BIGINT, cnt_server_err BIGINT, err_rate FLOAT8,
    val_total FLOAT8, val_input FLOAT8, val_output FLOAT8,
    price_input FLOAT8, price_output FLOAT8, price_total FLOAT8, latency_avg FLOAT8,
    cnt_total BIGINT, cnt_success BIGINT, cnt_error BIGINT,
    val_input_avg FLOAT8, val_input_p50 FLOAT8, val_input_p80 FLOAT8,
    val_input_p90 FLOAT8, val_input_p99 FLOAT8, val_input_max FLOAT8,
    val_output_avg FLOAT8, val_output_p50 FLOAT8, val_output_p80 FLOAT8,
    val_output_p90 FLOAT8, val_output_p99 FLOAT8, val_output_max FLOAT8,
    metric_a_p50 FLOAT8, metric_a_p80 FLOAT8, metric_a_p90 FLOAT8,
    metric_a_p99 FLOAT8, metric_a_max FLOAT8, metric_b_p50 FLOAT8,
    metric_b_p80 FLOAT8, metric_b_p90 FLOAT8, metric_b_p99 FLOAT8, metric_b_max FLOAT8,
    ts_collect_std TIMESTAMP, ts_event TIMESTAMP, ts_data_date VARCHAR(256),
    tpm_input BIGINT, tpm_output BIGINT, service_id VARCHAR(128), region VARCHAR(64),
    engine_type VARCHAR(128), service_full_name VARCHAR(256), service_tag VARCHAR(256),
    tps_input FLOAT8, tps_output FLOAT8, tps_total FLOAT8, is_billing BOOLEAN,
    region_source VARCHAR(64), service_type INTEGER, is_streaming BOOLEAN,
    sub_entities TEXT, ext_cache_token FLOAT8, source_type VARCHAR(64),
    real_cached_tokens FLOAT8, auth_channel VARCHAR(255),
    ext_resolution VARCHAR(255), ext_audio VARCHAR(255)
)
WITH (ORIENTATION = COLUMN, COMPRESSION = 'middle', period = '10 day')
DISTRIBUTE BY HASH (pk_id)
PARTITION BY RANGE (ts_event);
