INSERT INTO ads.ads_region_report
SELECT
    d.stat_date,
    CAST(d.region_code AS VARCHAR(16)) AS region_code,
    r.region_name,
    r.bureau_code,
    SUM(d.request_cnt) AS request_cnt,
    SUM(d.success_cnt)::NUMERIC / NULLIF(SUM(d.request_cnt), 0) AS success_rate,
    SUM(d.total_token_cnt) AS total_token_cnt
FROM ads.ads_token_daily d
LEFT JOIN dim.dim_region r ON d.region_code = r.region_code
GROUP BY d.stat_date, CAST(d.region_code AS VARCHAR(16)), r.region_name, r.bureau_code;
