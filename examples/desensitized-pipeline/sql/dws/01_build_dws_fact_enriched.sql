DELETE FROM schema.dws_fact_enriched WHERE ts_event = '${data_time}';

INSERT INTO schema.dws_fact_enriched
WITH t_fact_data AS (
    SELECT t_fact.*
    FROM (
        SELECT * FROM schema.dwd_fact_request WHERE ts_event = '${data_time}'
    ) t_fact
    LEFT JOIN (
        SELECT tenant_id FROM schema.excluded_tenant_list
    ) t_exclude ON t_fact.tenant_id = t_exclude.tenant_id
    WHERE t_exclude.tenant_id IS NULL
), t_dim_entity AS (
    SELECT * FROM schema.dwd_dim_model WHERE ts_event = '${data_time}'
), t_dim_service AS (
    SELECT * FROM schema.dwd_dim_service WHERE ts_event = '${data_time}'
), t_dim_user AS (
    SELECT DISTINCT user_id, user_name, company_name, dept_name
    FROM schema.user_base_table
)
SELECT
    generate_uuid() AS pk_id,
    t_fact.api_path,
    COALESCE(t_fact.entity_id, t_entity.entity_id) AS entity_id,
    NULL AS platform_service_id,
    COALESCE(t_fact.entity_name, t_entity.entity_name) AS entity_name,
    t_entity.resource_name, t_service.service_desc, t_entity.is_billing,
    t_fact.service_id,
    CASE
        WHEN t_service.service_name IS NOT NULL THEN t_service.service_name
        ELSE CASE WHEN t_service.engine_type = 'special_engine'
                  THEN COALESCE(t_fact.entity_name, t_entity.entity_name) END
    END AS service_name,
    t_service.service_status, t_service.data_type, t_service.max_length,
    t_service.model_name, t_service.engine_type,
    t_service.flag_moderation, t_service.flag_dispatcher,
    t_service.created_at, t_service.updated_at,
    t_fact.tenant_id, t_fact.ts_collect, t_fact.cnt_total, t_fact.cnt_success,
    t_fact.cnt_client_err, t_fact.cnt_server_err,
    CASE
        WHEN t_entity.billing_mode = '7'
         AND t_fact.ext_attr_1 NOT LIKE '%None%'
         AND t_fact.status_code = 200
        THEN SPLIT_PART(REPLACE(t_fact.ext_attr_1, '×', 'x'), 'x', 1)::BIGINT
           * SPLIT_PART(REPLACE(t_fact.ext_attr_1, '×', 'x'), 'x', 2)::BIGINT
           / 64 / 1000 + t_fact.val_output
        ELSE COALESCE(NULLIF(t_fact.val_input + t_fact.val_output, 0), t_fact.val_total)
    END AS val_total,
    CASE
        WHEN t_entity.billing_mode = '7'
         AND t_fact.ext_attr_1 NOT LIKE '%None%'
         AND t_fact.status_code = 200
        THEN SPLIT_PART(REPLACE(t_fact.ext_attr_1, '×', 'x'), 'x', 1)::BIGINT
           * SPLIT_PART(REPLACE(t_fact.ext_attr_1, '×', 'x'), 'x', 2)::BIGINT
           / 64 / 1000
        ELSE t_fact.val_input
    END AS val_input,
    t_fact.val_output, t_fact.val_metric_a, t_fact.val_metric_b, t_fact.val_latency,
    t_fact.ts_collect_std, t_fact.ts_event,
    t_service.service_name AS service_full_name,
    t_service.service_desc AS service_full_desc,
    t_fact.status_code, t_service.region,
    COALESCE(t_entity.parent_entity_id, t_fact.entity_id, t_entity.entity_id)
        AS parent_entity_id,
    COALESCE(t_entity.parent_entity_name, t_fact.entity_name, t_entity.entity_name)
        AS parent_entity_name,
    t_entity.source_type, t_entity.billing_mode, t_entity.entity_type,
    t_entity.business_type, t_fact.ext_attr_1, t_fact.ext_attr_2,
    t_fact.region_source, t_fact.service_type, t_fact.is_streaming
FROM t_fact_data t_fact
LEFT JOIN t_dim_entity t_entity ON t_fact.entity_id = t_entity.entity_id
LEFT JOIN t_dim_service t_service ON t_fact.service_id = t_service.service_id
LEFT JOIN t_dim_user t_user ON t_fact.tenant_id = t_user.user_id
LEFT JOIN schema.meta_customer_table t_meta ON t_fact.tenant_id = t_meta.tenant_id;
