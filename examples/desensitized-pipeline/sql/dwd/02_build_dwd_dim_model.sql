DELETE FROM schema.dwd_dim_model WHERE ts_event = '${data_time}';

INSERT INTO schema.dwd_dim_model
WITH t_config_a_all AS (
    SELECT * FROM schema.config_table_a
    UNION ALL SELECT * FROM schema.config_table_a_hk
), t_config_b_all AS (
    SELECT * FROM schema.config_table_b
    UNION ALL SELECT * FROM schema.config_table_b_hk
), t_all_entities AS (
    SELECT t.id AS entity_id, t.entity_name,
           CASE WHEN t.parent_entity_id IS NULL THEN t.id ELSE t.parent_entity_id END AS parent_entity_id,
           t.billing_mode, t.entity_type, t.business_type,
           t.created_at, t.updated_at, t.deleted_at
    FROM t_config_a_all t WHERE t.source_type = 'system'
    UNION ALL
    SELECT t.id, t.endpoint_name, t.parent_entity_id,
           NULL, NULL, NULL, t.created_at, t.updated_at, t.deleted_at
    FROM t_config_b_all t
    WHERE t.source_type IN ('custom_type_1', 'custom_type_2')
), t_parent_info AS (
    SELECT DISTINCT id, entity_name, billing_mode, entity_type, business_type
    FROM t_config_a_all
), t_billing_resource AS (
    SELECT t_all.entity_id, MAX(t_all.resource_name) AS resource_name
    FROM (
        SELECT * FROM schema.dwd_billing_spec
        WHERE ts_data >= DATE('${data_time}') - 2
          AND ts_data <= DATE('${data_time}') + 1
    ) t_all
    JOIN (
        SELECT entity_id, MAX(start_time) AS start_time
        FROM schema.dwd_billing_spec
        WHERE ts_data >= DATE('${data_time}') - 2
          AND ts_data <= DATE('${data_time}') + 1
        GROUP BY entity_id
    ) t_latest ON t_all.entity_id = t_latest.entity_id
              AND t_all.start_time = t_latest.start_time
    GROUP BY t_all.entity_id
)
SELECT t_all.entity_id, t_all.entity_name, t_billing.resource_name,
       CASE WHEN t_all.business_type = 'free' THEN FALSE ELSE TRUE END AS is_billing,
       t_all.parent_entity_id, t_parent.entity_name AS parent_entity_name,
       t_all.source_type, t_all.limit_rpm, t_all.limit_tpm,
       t_parent.billing_mode, t_parent.entity_type, t_parent.business_type,
       t_all.created_at, t_all.updated_at, t_all.deleted_at,
       '${data_time}' AS ts_event
FROM t_all_entities t_all
LEFT JOIN t_parent_info t_parent ON t_all.parent_entity_id = t_parent.id
LEFT JOIN t_billing_resource t_billing ON t_all.entity_id = t_billing.entity_id;

/* SOURCE NOTE:
   The source document references source_type/limit_rpm/limit_tpm from t_all_entities
   although its displayed CTE projection omits them. This inconsistency is preserved. */
