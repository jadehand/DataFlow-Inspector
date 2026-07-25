-- CDM 搬运的等价 SQL；ingestion_time 表示进入 DWS 的时间。
INSERT INTO ods.ods_token_request
SELECT
    request_id, tenant_id, model_code, region_code, status_code,
    input_tokens, output_tokens, latency_ms, request_time,
    created_at, updated_at, CURRENT_TIMESTAMP, CAST(request_time AS DATE)
FROM rds.token_request
WHERE updated_at >= CAST('${biz_date}' AS TIMESTAMP)
  AND updated_at <  CAST('${biz_date}' AS TIMESTAMP) + INTERVAL '1 day';
