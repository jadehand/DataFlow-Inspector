-- ============================================
-- DWS → ADS ETL（每日凌晨离线调度）
-- 参数: ${bizdate}
-- ============================================

TRUNCATE TABLE ads.ads_llm_customer_model_daily_stat
PARTITION FOR(to_date('${bizdate}','yyyy-MM-dd'));

INSERT INTO ads.ads_llm_customer_model_daily_stat
SELECT
    dt,
    customer_id,
    model_id,
    model_name,
    SUM(request_cnt) AS request_cnt,
    CASE
        WHEN SUM(request_cnt) > 0
        THEN ROUND(SUM(success_cnt)::DECIMAL / SUM(request_cnt), 4)
        ELSE 0
    END AS success_rate,
    SUM(input_tokens_sum) AS input_tokens_sum,
    SUM(output_tokens_sum) AS output_tokens_sum,
    SUM(total_tokens_sum) AS total_tokens_sum,
    SUM(total_cost) AS total_cost
FROM dws.dws_llm_api_model_minute_stat
WHERE dt = '${bizdate}'
GROUP BY dt, customer_id, model_id, model_name;
