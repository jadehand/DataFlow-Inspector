DELETE FROM schema.dwd_dim_service WHERE ts_event = '${data_time}';

INSERT INTO schema.dwd_dim_service
WITH t_service_list AS (
    SELECT DISTINCT service_id, engine_type FROM schema.service_spec_table
), t_platform_service AS (
    SELECT * FROM schema.platform_service_table
), t_template_config AS (
    SELECT service_name,
           json_extract(config_json, '$.param_a') AS param_a,
           json_extract(config_json, '$.param_b') AS param_b
    FROM schema.template_config_table
), t_service_props AS (
    SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY service_id ORDER BY updated_at DESC
        ) AS rn
        FROM schema.service_spec_table
    ) t WHERE rn = 1
), t_pool_detail AS (
    SELECT * FROM schema.pool_detail_daily
    WHERE ts_data >= DATE('${data_time}') - 3
      AND ts_data <= DATE('${data_time}') + 1
), t_engine_status AS (
    SELECT * FROM schema.engine_running_summary
    WHERE ts_data >= '${data_time}'::timestamp - INTERVAL '5' HOUR
      AND ts_data <= '${data_time}'::timestamp + INTERVAL '1' HOUR
)
SELECT t_list.service_id,
       COALESCE(t_platform.service_desc, t_engine.service_desc) AS service_desc,
       COALESCE(t_platform.service_name, t_engine.service_name) AS service_name,
       COALESCE(t_platform.service_status, 'unknown') AS service_status,
       t_template.param_a AS data_type, t_template.param_b AS max_length,
       t_platform.model_name, t_list.engine_type,
       t_platform.flag_moderation, t_platform.flag_dispatcher,
       COALESCE(t_platform.region, t_engine.region) AS region,
       t_platform.created_at, t_platform.updated_at, t_platform.deleted_at,
       '${data_time}' AS ts_event
FROM t_service_list t_list
LEFT JOIN t_platform_service t_platform ON t_list.service_id = t_platform.service_id
LEFT JOIN t_template_config t_template ON t_list.service_id = t_template.service_name
LEFT JOIN t_service_props t_props ON t_list.service_id = t_props.service_id
LEFT JOIN t_pool_detail t_pool ON t_platform.pool_name = t_pool.pool_name
                              AND t_platform.region = t_pool.region
LEFT JOIN t_engine_status t_engine ON t_list.service_id = t_engine.service_id
                                  AND t_platform.region = t_engine.region;
