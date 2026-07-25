DELETE FROM schema.dws_agg_minute WHERE ts_event = '${data_time}';

INSERT INTO schema.dws_agg_minute
WITH t_minute_summary AS (
    SELECT
        DATE_FORMAT(ts_collect_std, '%Y-%m-%d %H:%i:00') AS ts_minute,
        parent_entity_id, entity_id, service_name, resource_name, tenant_id,
        service_id, region, engine_type, service_full_name, service_tag,
        is_billing, region_source, service_type, is_streaming,
        SUM(cnt_total) AS rpm,
        SUM(val_total) * 1000 AS tpm,
        SUM(val_input) * 1000 AS tpm_input,
        SUM(val_output) * 1000 AS tpm_output,
        AVG(CASE WHEN val_metric_a > 0 THEN val_metric_a END) AS metric_a_avg,
        AVG(CASE WHEN val_metric_b > 0 THEN val_metric_b END) AS metric_b_avg,
        AVG(CASE WHEN val_latency > 0 THEN val_latency END) AS latency_avg,
        SUM(val_total) AS val_total, SUM(val_input) AS val_input,
        SUM(val_output) AS val_output, SUM(cnt_total) AS cnt_total,
        SUM(cnt_success) AS cnt_success, SUM(cnt_client_err) AS cnt_client_err,
        SUM(cnt_server_err) AS cnt_server_err,
        SUM(ext_cache_token) AS ext_cache_token,
        SUM(real_cached_tokens) AS real_cached_tokens
    FROM schema.dws_fact_enriched
    WHERE ts_event = '${data_time}'
      AND tenant_id != 'excluded_tenant_id_placeholder'
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
), t_percentile_input AS (
    SELECT ts_minute, parent_entity_id,
           /* OMITTED BY SOURCE DOCUMENT: other grouping dimensions */
           PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY val_input) AS val_input_p50,
           PERCENTILE_DISC(0.8) WITHIN GROUP (ORDER BY val_input) AS val_input_p80,
           PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY val_input) AS val_input_p90,
           PERCENTILE_DISC(0.99) WITHIN GROUP (ORDER BY val_input) AS val_input_p99,
           MAX(val_input) AS val_input_max
    FROM schema.dws_fact_enriched
    WHERE ts_event = '${data_time}' AND val_input > 0
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
), t_percentile_output AS (
    SELECT ts_minute, parent_entity_id,
           /* OMITTED BY SOURCE DOCUMENT: other grouping dimensions */
           PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY val_output) AS val_output_p50,
           PERCENTILE_DISC(0.8) WITHIN GROUP (ORDER BY val_output) AS val_output_p80,
           PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY val_output) AS val_output_p90,
           PERCENTILE_DISC(0.99) WITHIN GROUP (ORDER BY val_output) AS val_output_p99,
           MAX(val_output) AS val_output_max
    FROM schema.dws_fact_enriched
    WHERE ts_event = '${data_time}' AND val_output > 0
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
), t_percentile_a AS (
    SELECT ts_minute, parent_entity_id,
           /* OMITTED BY SOURCE DOCUMENT: other grouping dimensions */
           PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY val_metric_a) AS metric_a_p50,
           PERCENTILE_DISC(0.8) WITHIN GROUP (ORDER BY val_metric_a) AS metric_a_p80,
           PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY val_metric_a) AS metric_a_p90,
           PERCENTILE_DISC(0.99) WITHIN GROUP (ORDER BY val_metric_a) AS metric_a_p99,
           MAX(val_metric_a) AS metric_a_max
    FROM schema.dws_fact_enriched
    WHERE ts_event = '${data_time}' AND val_metric_a > 0
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
), t_percentile_b AS (
    SELECT ts_minute, parent_entity_id,
           /* OMITTED BY SOURCE DOCUMENT: other grouping dimensions */
           PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY val_metric_b) AS metric_b_p50,
           PERCENTILE_DISC(0.8) WITHIN GROUP (ORDER BY val_metric_b) AS metric_b_p80,
           PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY val_metric_b) AS metric_b_p90,
           PERCENTILE_DISC(0.99) WITHIN GROUP (ORDER BY val_metric_b) AS metric_b_p99,
           MAX(val_metric_b) AS metric_b_max
    FROM schema.dws_fact_enriched
    WHERE ts_event = '${data_time}' AND val_metric_b > 0
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
)
SELECT
    generate_uuid() AS pk_id,
    t_summary.entity_id, t_summary.service_name, t_summary.resource_name,
    t_summary.tenant_id, t_summary.ts_collect, t_summary.rpm, t_summary.tpm,
    t_summary.metric_a_avg, t_summary.metric_b_avg,
    t_summary.cnt_client_err, t_summary.cnt_server_err,
    (t_summary.cnt_client_err + t_summary.cnt_server_err)
        / NULLIF(t_summary.cnt_total, 0) AS err_rate,
    t_summary.val_total, t_summary.val_input, t_summary.val_output,
    t_summary.val_input * t_price.price_input AS price_input,
    t_summary.val_output * t_price.price_output AS price_output,
    (t_summary.val_input * t_price.price_input)
      + (t_summary.val_output * t_price.price_output) AS price_total,
    t_summary.latency_avg, t_summary.cnt_total, t_summary.cnt_success,
    t_summary.cnt_client_err + t_summary.cnt_server_err AS cnt_error,
    t_summary.val_input AS val_input_avg,
    t_pctl_input.val_input_p50, t_pctl_input.val_input_p80,
    t_pctl_input.val_input_p90, t_pctl_input.val_input_p99,
    t_pctl_input.val_input_max,
    t_summary.val_output AS val_output_avg,
    t_pctl_output.val_output_p50, t_pctl_output.val_output_p80,
    t_pctl_output.val_output_p90, t_pctl_output.val_output_p99,
    t_pctl_output.val_output_max,
    t_pctl_a.metric_a_p50, t_pctl_a.metric_a_p80, t_pctl_a.metric_a_p90,
    t_pctl_a.metric_a_p99, t_pctl_a.metric_a_max,
    t_pctl_b.metric_b_p50, t_pctl_b.metric_b_p80, t_pctl_b.metric_b_p90,
    t_pctl_b.metric_b_p99, t_pctl_b.metric_b_max,
    t_summary.ts_collect_std, t_summary.ts_event,
    DATE_FORMAT(t_summary.ts_event, '%Y-%m-%d') AS ts_data_date,
    t_summary.tpm_input, t_summary.tpm_output, t_summary.service_id,
    t_summary.region, t_summary.engine_type, t_summary.service_full_name,
    t_summary.service_tag, t_summary.tpm_input / 60.0 AS tps_input,
    t_summary.tpm_output / 60.0 AS tps_output,
    t_summary.tpm / 60.0 AS tps_total, t_summary.is_billing,
    t_summary.region_source, t_summary.service_type, t_summary.is_streaming,
    NULL AS sub_entities, t_summary.ext_cache_token, t_summary.source_type,
    t_summary.real_cached_tokens, t_summary.auth_channel,
    t_summary.ext_resolution, t_summary.ext_audio
FROM t_minute_summary t_summary
LEFT JOIN t_percentile_input t_pctl_input
  ON t_summary.ts_minute = t_pctl_input.ts_minute
 AND t_summary.parent_entity_id = t_pctl_input.parent_entity_id
 /* OMITTED BY SOURCE DOCUMENT: other join conditions */
LEFT JOIN t_percentile_output t_pctl_output
  ON t_summary.ts_minute = t_pctl_output.ts_minute
 AND t_summary.parent_entity_id = t_pctl_output.parent_entity_id
LEFT JOIN t_percentile_a t_pctl_a
  ON t_summary.ts_minute = t_pctl_a.ts_minute
 AND t_summary.parent_entity_id = t_pctl_a.parent_entity_id
LEFT JOIN t_percentile_b t_pctl_b
  ON t_summary.ts_minute = t_pctl_b.ts_minute
 AND t_summary.parent_entity_id = t_pctl_b.parent_entity_id
LEFT JOIN schema.sku_price_dict t_price
  ON t_summary.service_id = t_price.service_id;
