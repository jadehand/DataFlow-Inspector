CREATE TABLE schema.dwd_dim_model (
    entity_id VARCHAR(255), entity_name VARCHAR(255), resource_name VARCHAR(255),
    is_billing BOOLEAN, parent_entity_id VARCHAR(128), parent_entity_name VARCHAR(256),
    source_type VARCHAR(64), limit_rpm BIGINT, limit_tpm BIGINT,
    billing_mode INTEGER, entity_type VARCHAR(128), business_type VARCHAR(64),
    created_at TIMESTAMP, updated_at TIMESTAMP, deleted_at TIMESTAMP, ts_event TIMESTAMP
)
WITH (ORIENTATION = 'row', period = '3 months')
PARTITION BY RANGE (ts_event);
