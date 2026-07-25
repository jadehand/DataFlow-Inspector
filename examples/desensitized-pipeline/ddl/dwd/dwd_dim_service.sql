CREATE TABLE schema.dwd_dim_service (
    service_id VARCHAR(255), service_desc TEXT, service_name VARCHAR(255),
    service_status VARCHAR(255), data_type VARCHAR(255), max_length BIGINT,
    model_name VARCHAR(255), engine_type VARCHAR(128), flag_moderation TINYINT,
    flag_dispatcher VARCHAR(255), created_at TIMESTAMP, updated_at TIMESTAMP,
    deleted_at TIMESTAMP, ts_event TIMESTAMP, region VARCHAR(64)
)
WITH (ORIENTATION = 'row', period = '3 months')
PARTITION BY RANGE (ts_event);
