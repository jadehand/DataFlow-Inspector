-- 故意保留的口径差异：日报排除 TEST 状态，而 DWS 小时指标未排除。
INSERT INTO ads.ads_token_daily
SELECT
    CAST(event_time AS DATE) AS stat_date,
    tenant_id,
    region_code,
    COUNT(*) AS request_cnt,
    SUM(CASE WHEN status_code = 'SUCCESS' THEN 1 ELSE 0 END) AS success_cnt,
    SUM(CASE WHEN status_code = 'SUCCESS' THEN 1 ELSE 0 END)::NUMERIC
        / NULLIF(COUNT(*), 0) AS success_rate,
    SUM(total_tokens) AS total_token_cnt
FROM dwd.dwd_token_request_wide
WHERE dt = CAST('${biz_date}' AS DATE)
  AND status_code <> 'TEST'
GROUP BY CAST(event_time AS DATE), tenant_id, region_code;
