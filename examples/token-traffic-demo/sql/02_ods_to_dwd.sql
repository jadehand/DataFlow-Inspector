INSERT INTO dwd.dwd_token_request
SELECT
    request_id,
    tenant_id,
    model_code,
    UPPER(TRIM(region_code)) AS region_code,
    UPPER(TRIM(status_code)) AS status_code,
    COALESCE(input_tokens, 0)::BIGINT AS input_tokens,
    COALESCE(output_tokens, 0)::BIGINT AS output_tokens,
    (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0))::BIGINT AS total_tokens,
    latency_ms,
    request_time AS event_time,
    ingestion_time,
    dt
FROM (
    SELECT o.*,
           ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY source_updated_at DESC) AS rn
    FROM ods.ods_token_request o
    WHERE dt = CAST('${biz_date}' AS DATE)
) s
WHERE rn = 1
  AND request_id IS NOT NULL;
