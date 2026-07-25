DELETE FROM schema.dwd_fact_request WHERE ts_event = '${data_time}';

INSERT INTO schema.dwd_fact_request
WITH t_source_a AS (
    SELECT DISTINCT
        'source_a' AS region_source,
        api_path, entity_id, entity_name, service_id
        /* OMITTED BY SOURCE DOCUMENT: remaining projected source columns */
    FROM schema.ods_source_a
    WHERE mq_timestamp >= '${data_time}'
      AND mq_timestamp < DATE_ADD('${data_time}', INTERVAL '1' HOUR)
), t_source_b AS (
    SELECT DISTINCT
        'source_b' AS region_source,
        api_path, entity_id, entity_name, service_id
        /* OMITTED BY SOURCE DOCUMENT: remaining projected source columns */
    FROM schema.ods_source_b
    WHERE mq_timestamp >= '${data_time}'
      AND mq_timestamp < DATE_ADD('${data_time}', INTERVAL '1' HOUR)
)
SELECT
    generate_uuid() AS pk_id,
    api_path, entity_id, entity_name, service_id, tenant_id, ts_collect,
    cnt_total, cnt_success, cnt_client_err, cnt_server_err,
    val_total, val_input, val_output, val_metric_a, val_metric_b, val_latency,
    TO_TIMESTAMP(ts_collect / 1000) AS ts_collect_std,
    DATE_FORMAT('${data_time}', '%Y-%m-%d %H:00:00') AS ts_event,
    status_code,
    REPLACE(ext_attr_1, '*', 'x') AS ext_attr_1,
    ext_attr_2, region_source, service_type,
    CASE WHEN (val_metric_a = 0 OR val_metric_b = 0) THEN FALSE ELSE TRUE END AS is_streaming
FROM (
    SELECT * FROM t_source_a
    UNION ALL
    SELECT * FROM t_source_b
) t_sources;
