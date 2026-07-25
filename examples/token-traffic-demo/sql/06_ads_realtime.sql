-- 故意保留的验收风险：SELECT * 对上游列顺序和新增字段敏感。
INSERT INTO ads.ads_token_realtime
SELECT * FROM (
    SELECT
        stat_minute, tenant_id, model_code, region_code,
        request_cnt, success_cnt,
        success_cnt::NUMERIC / NULLIF(request_cnt, 0) AS success_rate,
        total_token_cnt, avg_latency_ms, dt
    FROM dws.dws_token_minute
    WHERE dt = CAST('${biz_date}' AS DATE)
) realtime_view;
