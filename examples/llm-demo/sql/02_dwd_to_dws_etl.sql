-- ============================================
-- DWD → DWS ETL（小时调度，幂等 Delete+Insert）
-- 在此处 JOIN 维表补维度 + 分钟聚合
-- 参数: ${bizdate}, ${bizhour}
-- ============================================

DELETE FROM dws.dws_llm_api_model_minute_stat
WHERE dt = '${bizdate}'
AND hour_no = '${bizhour}';

INSERT INTO dws.dws_llm_api_model_minute_stat
SELECT
    t.min_time AS stat_minute,
    t.dt,
    t.hour_no,
    t.site_code,
    t.customer_id,
    t.model_id,
    m.model_name,
    m.model_type,
    m.model_provider,
    COUNT(1) AS request_cnt,
    COUNT(CASE WHEN t.is_success THEN 1 END) AS success_cnt,
    COUNT(CASE WHEN NOT t.is_success THEN 1 END) AS fail_cnt,
    SUM(t.input_tokens) AS input_tokens_sum,
    SUM(t.output_tokens) AS output_tokens_sum,
    SUM(t.total_tokens) AS total_tokens_sum,
    AVG(t.latency_ms) AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY t.latency_ms) AS p95_latency_ms,
    SUM(t.input_tokens) * m.token_price_input AS cost_input,
    SUM(t.output_tokens) * m.token_price_output AS cost_output,
    SUM(t.input_tokens) * m.token_price_input + SUM(t.output_tokens) * m.token_price_output AS total_cost
FROM dwd.dwd_llm_api_request_detail t
LEFT JOIN dim.dim_llm_model_info m
    ON t.model_id = m.model_id
WHERE t.dt = '${bizdate}'
  AND t.hour_no = '${bizhour}'
GROUP BY
    t.min_time,
    t.dt,
    t.hour_no,
    t.site_code,
    t.customer_id,
    t.model_id,
    m.model_name,
    m.model_type,
    m.model_provider;
