-- 故意保留的验收风险：小时聚合使用 ingestion_time，而分钟表使用 event_time。
INSERT INTO dws.dws_token_hour
SELECT
    DATE_TRUNC('hour', ingestion_time) AS stat_hour,
    tenant_id, model_code, region_code,
    COUNT(*) AS request_cnt,
    SUM(CASE WHEN status_code = 'SUCCESS' THEN 1 ELSE 0 END) AS success_cnt,
    SUM(CASE WHEN status_code = 'FAILED' THEN 1 ELSE 0 END) AS failure_cnt,
    SUM(total_tokens) AS total_token_cnt,
    AVG(latency_ms)::NUMERIC(18,2) AS avg_latency_ms,
    dt
FROM dwd.dwd_token_request_wide
WHERE dt = CAST('${biz_date}' AS DATE)
GROUP BY DATE_TRUNC('hour', ingestion_time), tenant_id, model_code, region_code, dt;
