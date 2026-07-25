-- ============================================
-- ODS → DWD ETL（小时调度，幂等 Delete+Insert）
-- 参数: ${bizdate}, ${bizhour}
-- ============================================

DELETE FROM dwd.dwd_llm_api_request_detail
WHERE dt = '${bizdate}'
AND hour_no = '${bizhour}';

INSERT INTO dwd.dwd_llm_api_request_detail
SELECT
    request_id,
    trace_id,
    site_code,
    customer_id,
    api_token,
    model_id,
    input_tokens,
    output_tokens,
    COALESCE(total_tokens, input_tokens + output_tokens) AS total_tokens,
    req_start_time,
    req_end_time,
    latency_ms,
    http_status,
    err_code,
    err_msg,
    stream_flag,
    request_ip,
    CASE WHEN err_code = '0' THEN true ELSE false END AS is_success,
    dt,
    hour_no,
    DATE_TRUNC('minute', req_start_time) AS min_time
FROM ods.ods_llm_api_request_log
WHERE dt = '${bizdate}'
  AND hour_no = '${bizhour}'
  AND request_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND model_id IS NOT NULL;
