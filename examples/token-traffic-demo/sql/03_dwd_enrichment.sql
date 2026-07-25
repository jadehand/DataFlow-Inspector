INSERT INTO dwd.dwd_token_request_wide
SELECT
    f.request_id, f.tenant_id, t.tenant_name, t.industry, t.customer_tier,
    f.model_code, m.model_family, m.provider,
    f.region_code, r.region_name, r.bureau_code, r.bureau_name,
    f.status_code, f.input_tokens, f.output_tokens, f.total_tokens,
    f.latency_ms, f.event_time, f.ingestion_time, f.dt
FROM dwd.dwd_token_request f
LEFT JOIN dim.dim_tenant t ON f.tenant_id = t.tenant_id
LEFT JOIN dim.dim_model m ON f.model_code = m.model_code
LEFT JOIN dim.dim_region r ON f.region_code = r.region_code
WHERE f.dt = CAST('${biz_date}' AS DATE);
