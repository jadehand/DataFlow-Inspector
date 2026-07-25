(function () {
  const tables = [
    {
      id: "rds-token-request",
      name: "token_request",
      qualifiedName: "rds_ai.token_request",
      layer: "RDS",
      domain: "Token 请求",
      description: "线上模型调用请求原始交易表",
      grain: "一次模型请求一行",
      timeField: "request_time",
      owner: "AI 平台",
      rows: "18.4 亿",
      status: "healthy",
      fields: [
        ["request_id", "VARCHAR(64)", "标识", "请求唯一标识"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["request_time", "TIMESTAMP", "事件时间", "请求发起时间"],
        ["status", "VARCHAR(16)", "维度", "请求处理状态"],
        ["input_tokens", "BIGINT", "指标", "输入 Token 数"],
        ["output_tokens", "BIGINT", "指标", "输出 Token 数"],
        ["latency_ms", "BIGINT", "指标", "响应耗时（毫秒）"]
      ]
    },
    {
      id: "ods-token-request",
      name: "ods_token_request",
      qualifiedName: "ods.ods_token_request",
      layer: "ODS",
      domain: "Token 请求",
      description: "CDM 按小时增量搬运的请求明细",
      grain: "一次模型请求一行",
      timeField: "request_time",
      owner: "数据平台",
      rows: "18.4 亿",
      status: "warning",
      fields: [
        ["request_id", "VARCHAR(64)", "标识", "请求唯一标识"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["request_time", "TIMESTAMP", "事件时间", "请求发起时间"],
        ["status", "VARCHAR(16)", "维度", "请求处理状态"],
        ["input_tokens", "BIGINT", "指标", "输入 Token 数"],
        ["output_tokens", "BIGINT", "指标", "输出 Token 数"],
        ["latency_ms", "BIGINT", "指标", "响应耗时"],
        ["cdm_load_time", "TIMESTAMP", "入库时间", "CDM 落库时间"],
        ["dt", "DATE", "分区时间", "业务日期分区"]
      ]
    },
    {
      id: "dwd-token-request",
      name: "dwd_token_request",
      qualifiedName: "dwd.dwd_token_request",
      layer: "DWD",
      domain: "Token 请求",
      description: "去重、状态标准化后的有效请求明细",
      grain: "一次有效请求一行",
      timeField: "event_time",
      owner: "流量数据组",
      rows: "18.1 亿",
      status: "warning",
      fields: [
        ["request_id", "VARCHAR(64)", "标识", "请求唯一标识"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "标准模型编码"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["event_time", "TIMESTAMP", "事件时间", "标准业务事件时间"],
        ["ingestion_time", "TIMESTAMP", "入库时间", "ODS 入库时间"],
        ["status_code", "VARCHAR(16)", "维度", "标准状态码"],
        ["input_token_cnt", "BIGINT", "指标", "输入 Token 数"],
        ["output_token_cnt", "BIGINT", "指标", "输出 Token 数"],
        ["latency_ms", "BIGINT", "指标", "响应耗时"]
      ]
    },
    {
      id: "dim-region",
      name: "dim_region",
      qualifiedName: "dim.dim_region",
      layer: "DIM",
      domain: "公共维度",
      description: "局点、区域及大区层级维度",
      grain: "一个局点一行",
      timeField: "effective_from",
      owner: "基础数据组",
      rows: "126",
      status: "healthy",
      fields: [
        ["region_code", "VARCHAR(16)", "标识", "局点编码"],
        ["region_name", "VARCHAR(64)", "维度", "局点名称"],
        ["region_group", "VARCHAR(32)", "维度", "大区"],
        ["effective_from", "TIMESTAMP", "生效时间", "版本生效时间"]
      ]
    },
    {
      id: "dim-tenant",
      name: "dim_tenant",
      qualifiedName: "dim.dim_tenant",
      layer: "DIM",
      domain: "公共维度",
      description: "租户及行业属性维度",
      grain: "一个租户一行",
      timeField: "updated_at",
      owner: "客户数据组",
      rows: "8.6 万",
      status: "healthy",
      fields: [
        ["tenant_id", "VARCHAR(32)", "标识", "租户编码"],
        ["tenant_name", "VARCHAR(128)", "维度", "租户名称"],
        ["industry_code", "VARCHAR(16)", "维度", "行业编码"],
        ["tenant_level", "VARCHAR(16)", "维度", "客户等级"]
      ]
    },
    {
      id: "dim-model",
      name: "dim_model",
      qualifiedName: "dim.dim_model",
      layer: "DIM",
      domain: "公共维度",
      description: "模型系列、厂商及计费类型维度",
      grain: "一个模型版本一行",
      timeField: "effective_from",
      owner: "模型运营组",
      rows: "384",
      status: "healthy",
      fields: [
        ["model_code", "VARCHAR(64)", "标识", "模型编码"],
        ["model_name", "VARCHAR(128)", "维度", "模型名称"],
        ["model_family", "VARCHAR(64)", "维度", "模型系列"],
        ["billing_type", "VARCHAR(16)", "维度", "计费类型"]
      ]
    },
    {
      id: "dim-status",
      name: "dim_status",
      qualifiedName: "dim.dim_status",
      layer: "DIM",
      domain: "公共维度",
      description: "请求状态及成功失败分类",
      grain: "一个状态码一行",
      timeField: "updated_at",
      owner: "AI 平台",
      rows: "28",
      status: "healthy",
      fields: [
        ["status_code", "VARCHAR(16)", "标识", "状态码"],
        ["status_name", "VARCHAR(64)", "维度", "状态名称"],
        ["success_flag", "SMALLINT", "维度", "是否成功"],
        ["failure_type", "VARCHAR(32)", "维度", "失败分类"]
      ]
    },
    {
      id: "dwd-token-wide",
      name: "dwd_token_request_wide",
      qualifiedName: "dwd.dwd_token_request_wide",
      layer: "DWD",
      domain: "Token 请求",
      description: "关联局点、租户、模型和状态后的请求宽表",
      grain: "一次有效请求一行",
      timeField: "event_time",
      owner: "流量数据组",
      rows: "18.1 亿",
      status: "healthy",
      fields: [
        ["request_id", "VARCHAR(64)", "标识", "请求唯一标识"],
        ["event_time", "TIMESTAMP", "事件时间", "请求事件时间"],
        ["ingestion_time", "TIMESTAMP", "入库时间", "数据入仓时间"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["region_name", "VARCHAR(64)", "维度", "局点名称"],
        ["region_group", "VARCHAR(32)", "维度", "大区"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["industry_code", "VARCHAR(16)", "维度", "行业编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["model_family", "VARCHAR(64)", "维度", "模型系列"],
        ["success_flag", "SMALLINT", "维度", "是否成功"],
        ["input_token_cnt", "BIGINT", "指标", "输入 Token 数"],
        ["output_token_cnt", "BIGINT", "指标", "输出 Token 数"],
        ["latency_ms", "BIGINT", "指标", "响应耗时"]
      ]
    },
    {
      id: "dws-token-minute",
      name: "dws_token_minute",
      qualifiedName: "dws.dws_token_minute",
      layer: "DWS",
      domain: "Token 请求",
      description: "局点、租户、模型粒度的分钟聚合宽表",
      grain: "局点 + 租户 + 模型 + 分钟",
      timeField: "stat_minute",
      owner: "流量数据组",
      rows: "4.28 亿",
      status: "healthy",
      fields: [
        ["stat_minute", "TIMESTAMP", "统计时间", "分钟统计窗口"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["region_group", "VARCHAR(32)", "维度", "大区"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["request_cnt", "BIGINT", "指标", "请求总量"],
        ["success_cnt", "BIGINT", "指标", "成功请求量"],
        ["failure_cnt", "BIGINT", "指标", "失败请求量"],
        ["input_token_cnt", "BIGINT", "指标", "输入 Token 数"],
        ["output_token_cnt", "BIGINT", "指标", "输出 Token 数"],
        ["avg_latency_ms", "NUMERIC(18,2)", "指标", "平均响应耗时"]
      ]
    },
    {
      id: "dws-token-hour",
      name: "dws_token_hour",
      qualifiedName: "dws.dws_token_hour",
      layer: "DWS",
      domain: "Token 请求",
      description: "供经营分析使用的小时聚合表",
      grain: "局点 + 租户 + 模型 + 小时",
      timeField: "stat_hour",
      owner: "流量数据组",
      rows: "7620 万",
      status: "critical",
      fields: [
        ["stat_hour", "TIMESTAMP", "统计时间", "小时统计窗口"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["request_cnt", "BIGINT", "指标", "请求总量"],
        ["success_cnt", "BIGINT", "指标", "成功请求量"],
        ["total_token_cnt", "BIGINT", "指标", "总 Token 数"],
        ["avg_latency_ms", "NUMERIC(18,2)", "指标", "平均响应耗时"]
      ]
    },
    {
      id: "dws-token-day",
      name: "dws_token_day",
      qualifiedName: "dws.dws_token_day",
      layer: "DWS",
      domain: "Token 请求",
      description: "租户、模型、局点日汇总表",
      grain: "局点 + 租户 + 模型 + 日",
      timeField: "stat_date",
      owner: "经营分析组",
      rows: "328 万",
      status: "warning",
      fields: [
        ["stat_date", "DATE", "统计时间", "统计日期"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["request_cnt", "BIGINT", "指标", "请求总量"],
        ["success_cnt", "BIGINT", "指标", "成功请求量"],
        ["total_token_cnt", "BIGINT", "指标", "总 Token 数"]
      ]
    },
    {
      id: "ads-token-realtime",
      name: "ads_token_realtime",
      qualifiedName: "ads.ads_token_realtime",
      layer: "ADS",
      domain: "实时运营",
      description: "运营驾驶舱实时流量报表",
      grain: "局点 + 模型 + 分钟",
      timeField: "stat_minute",
      owner: "运营驾驶舱",
      rows: "2160 万",
      status: "healthy",
      fields: [
        ["stat_minute", "TIMESTAMP", "统计时间", "分钟统计窗口"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["request_cnt", "BIGINT", "指标", "请求总量"],
        ["success_rate", "NUMERIC(8,4)", "指标", "请求成功率"],
        ["total_token_cnt", "BIGINT", "指标", "总 Token 数"]
      ]
    },
    {
      id: "ads-token-daily",
      name: "ads_token_daily",
      qualifiedName: "ads.ads_token_daily",
      layer: "ADS",
      domain: "经营日报",
      description: "Token 经营日报主题表",
      grain: "租户 + 模型 + 日",
      timeField: "stat_date",
      owner: "经营分析组",
      rows: "186 万",
      status: "warning",
      fields: [
        ["stat_date", "DATE", "统计时间", "统计日期"],
        ["tenant_id", "VARCHAR(32)", "维度", "租户编码"],
        ["model_code", "VARCHAR(64)", "维度", "模型编码"],
        ["request_cnt", "BIGINT", "指标", "请求总量"],
        ["success_rate", "NUMERIC(8,4)", "指标", "请求成功率"],
        ["total_token_cnt", "BIGINT", "指标", "总 Token 数"]
      ]
    },
    {
      id: "ads-region-report",
      name: "ads_region_report",
      qualifiedName: "ads.ads_region_report",
      layer: "ADS",
      domain: "局点分析",
      description: "分局点流量与资源利用分析报表",
      grain: "局点 + 日",
      timeField: "stat_date",
      owner: "区域运营组",
      rows: "4.6 万",
      status: "critical",
      fields: [
        ["stat_date", "DATE", "统计时间", "统计日期"],
        ["region_code", "VARCHAR(16)", "维度", "局点编码"],
        ["region_name", "VARCHAR(64)", "维度", "局点名称"],
        ["request_cnt", "BIGINT", "指标", "请求总量"],
        ["total_token_cnt", "BIGINT", "指标", "总 Token 数"],
        ["avg_latency_ms", "NUMERIC(18,2)", "指标", "平均响应耗时"]
      ]
    }
  ].map(function (table) {
    table.fields = table.fields.map(function (field, index) {
      return {
        id: table.id + "-" + field[0],
        name: field[0],
        type: field[1],
        role: field[2],
        description: field[3],
        nullable: index > 0
      };
    });
    return table;
  });

  const lineage = [
    ["rds-token-request", "ods-token-request", "CDM 增量同步", "migration_rds_token_request", "cdm_load_time > ${last_success_time}", "confirmed"],
    ["ods-token-request", "dwd-token-request", "去重与状态标准化", "02_ods_to_dwd.sql", "row_number() over(partition by request_id order by cdm_load_time desc)", "confirmed"],
    ["dwd-token-request", "dwd-token-wide", "请求主数据", "03_dwd_enrichment.sql", "d.request_id, d.event_time, d.input_token_cnt", "confirmed"],
    ["dim-region", "dwd-token-wide", "补充局点维度", "03_dwd_enrichment.sql", "d.region_code = r.region_code", "confirmed"],
    ["dim-tenant", "dwd-token-wide", "补充租户维度", "03_dwd_enrichment.sql", "d.tenant_id = t.tenant_id", "confirmed"],
    ["dim-model", "dwd-token-wide", "补充模型维度", "03_dwd_enrichment.sql", "d.model_code = m.model_code", "confirmed"],
    ["dim-status", "dwd-token-wide", "补充状态分类", "03_dwd_enrichment.sql", "d.status_code = s.status_code", "confirmed"],
    ["dwd-token-wide", "dws-token-minute", "分钟聚合", "04_dws_token_minute.sql", "date_trunc('minute', event_time), count(*), sum(input_token_cnt)", "confirmed"],
    ["dws-token-minute", "dws-token-hour", "小时聚合", "05_dws_token_hour.sql", "date_trunc('hour', ingestion_time)", "confirmed"],
    ["dws-token-hour", "dws-token-day", "日聚合", "06_dws_token_day.sql", "cast(stat_hour as date)", "inferred"],
    ["dws-token-minute", "ads-token-realtime", "实时看板聚合", "07_ads_token_realtime.sql", "sum(success_cnt) / nullif(sum(request_cnt), 0)", "confirmed"],
    ["dws-token-day", "ads-token-daily", "经营日报加工", "08_ads_token_daily.sql", "where status_code <> 'TEST'", "confirmed"],
    ["dws-token-day", "ads-region-report", "局点日报加工", "09_ads_region_report.sql", "cast(region_code as varchar(16))", "confirmed"],
    ["dim-region", "ads-region-report", "补充局点名称", "09_ads_region_report.sql", "d.region_code = r.region_code", "inferred"]
  ].map(function (edge, index) {
    return {
      id: "lineage-" + (index + 1),
      source: edge[0],
      target: edge[1],
      operation: edge[2],
      script: edge[3],
      expression: edge[4],
      evidence: edge[5],
      confidence: edge[5] === "confirmed" ? 0.98 : 0.74
    };
  });

  window.DATAFLOW_MOCK = {
    project: {
      id: "token-traffic",
      name: "Token 业务流",
      description: "模型请求流量从 RDS 搬运至 DWS，并加工为实时、小时和日报指标",
      version: "v2026.07.23",
      previousVersion: "v2026.07.20",
      dialect: "GaussDB(DWS)",
      timezone: "Asia/Shanghai",
      updatedAt: "2026-07-23 14:32",
      coverage: 94,
      stats: {
        tables: tables.length,
        fields: tables.reduce(function (sum, table) { return sum + table.fields.length; }, 0),
        scripts: 9,
        jobs: 9,
        metrics: 8,
        risks: 6
      },
      layerCounts: { RDS: 1, ODS: 1, DWD: 2, DIM: 4, DWS: 3, ADS: 3 }
    },
    tables: tables,
    lineage: lineage,
    jobs: [
      { id: "job-1", order: 1, name: "RDS 请求迁移", layer: "RDS", script: "migration_rds_token_request", reads: ["rds_ai.token_request"], writes: ["ods.ods_token_request"], schedule: "每小时 02 分", status: "confirmed", duration: "4m 18s" },
      { id: "job-2", order: 2, name: "ODS 请求清洗", layer: "ODS", script: "02_ods_to_dwd.sql", reads: ["ods.ods_token_request"], writes: ["dwd.dwd_token_request"], schedule: "每小时 08 分", status: "confirmed", duration: "6m 42s" },
      { id: "job-3", order: 3, name: "DWD 维度补充", layer: "DWD", script: "03_dwd_enrichment.sql", reads: ["dwd.dwd_token_request", "dim.dim_region", "dim.dim_tenant", "dim.dim_model", "dim.dim_status"], writes: ["dwd.dwd_token_request_wide"], schedule: "每小时 16 分", status: "confirmed", duration: "8m 06s" },
      { id: "job-4", order: 4, name: "分钟流量聚合", layer: "DWS", script: "04_dws_token_minute.sql", reads: ["dwd.dwd_token_request_wide"], writes: ["dws.dws_token_minute"], schedule: "每 5 分钟", status: "confirmed", duration: "1m 24s" },
      { id: "job-5", order: 5, name: "小时流量聚合", layer: "DWS", script: "05_dws_token_hour.sql", reads: ["dws.dws_token_minute"], writes: ["dws.dws_token_hour"], schedule: "每小时 28 分", status: "confirmed", duration: "2m 12s" },
      { id: "job-6", order: 6, name: "日流量汇总", layer: "DWS", script: "06_dws_token_day.sql", reads: ["dws.dws_token_hour"], writes: ["dws.dws_token_day"], schedule: "每日 01:10", status: "inferred", duration: "7m 55s" },
      { id: "job-7", order: 5, name: "实时驾驶舱", layer: "ADS", script: "07_ads_token_realtime.sql", reads: ["dws.dws_token_minute"], writes: ["ads.ads_token_realtime"], schedule: "每 5 分钟", status: "confirmed", duration: "38s" },
      { id: "job-8", order: 7, name: "Token 经营日报", layer: "ADS", script: "08_ads_token_daily.sql", reads: ["dws.dws_token_day"], writes: ["ads.ads_token_daily"], schedule: "每日 01:30", status: "confirmed", duration: "3m 20s" },
      { id: "job-9", order: 7, name: "局点经营报告", layer: "ADS", script: "09_ads_region_report.sql", reads: ["dws.dws_token_day", "dim.dim_region"], writes: ["ads.ads_region_report"], schedule: "每日 01:35", status: "inferred", duration: "2m 46s" }
    ],
    metrics: [
      { id: "metric-request", name: "请求总量", code: "request_cnt", formula: "COUNT(*)", grain: "局点 + 租户 + 模型 + 分钟", source: "dwd_token_request_wide.request_id", time: "event_time → stat_minute", filter: "无", status: "confirmed", consumers: 5 },
      { id: "metric-success", name: "成功请求量", code: "success_cnt", formula: "SUM(CASE WHEN success_flag = 1 THEN 1 ELSE 0 END)", grain: "局点 + 租户 + 模型 + 分钟", source: "dwd_token_request_wide.success_flag", time: "event_time → stat_minute", filter: "无", status: "confirmed", consumers: 5 },
      { id: "metric-failure", name: "失败请求量", code: "failure_cnt", formula: "SUM(CASE WHEN success_flag = 0 THEN 1 ELSE 0 END)", grain: "局点 + 租户 + 模型 + 分钟", source: "dwd_token_request_wide.success_flag", time: "event_time → stat_minute", filter: "无", status: "confirmed", consumers: 2 },
      { id: "metric-input", name: "输入 Token 数", code: "input_token_cnt", formula: "SUM(input_token_cnt)", grain: "局点 + 租户 + 模型 + 分钟", source: "dwd_token_request_wide.input_token_cnt", time: "event_time → stat_minute", filter: "无", status: "confirmed", consumers: 4 },
      { id: "metric-output", name: "输出 Token 数", code: "output_token_cnt", formula: "SUM(output_token_cnt)", grain: "局点 + 租户 + 模型 + 分钟", source: "dwd_token_request_wide.output_token_cnt", time: "event_time → stat_minute", filter: "无", status: "confirmed", consumers: 4 },
      { id: "metric-total", name: "总 Token 数", code: "total_token_cnt", formula: "SUM(input_token_cnt) + SUM(output_token_cnt)", grain: "局点 + 租户 + 模型 + 小时", source: "dws_token_minute", time: "stat_minute → stat_hour", filter: "无", status: "confirmed", consumers: 4 },
      { id: "metric-rate", name: "请求成功率", code: "success_rate", formula: "success_cnt / NULLIF(request_cnt, 0)", grain: "随消费报表", source: "dws_token_minute", time: "stat_minute / stat_date", filter: "日报额外过滤 status <> 'TEST'", status: "warning", consumers: 2 },
      { id: "metric-latency", name: "平均响应时长", code: "avg_latency_ms", formula: "AVG(latency_ms)", grain: "局点 + 租户 + 模型 + 分钟", source: "dwd_token_request_wide.latency_ms", time: "event_time → stat_minute", filter: "latency_ms >= 0", status: "confirmed", consumers: 3 }
    ],
    risks: [
      { id: "risk-time", severity: "high", title: "小时表时间口径不一致", object: "dws.dws_token_hour.stat_hour", detail: "分钟表按 event_time 聚合，小时表脚本却引用 ingestion_time，迟到数据可能跨小时偏移。", recommendation: "统一使用 stat_minute，回刷最近 7 天小时及下游日分区。" },
      { id: "risk-star-1", severity: "high", title: "下游存在 SELECT *", object: "05_dws_token_hour.sql", detail: "字段新增或顺序变化可能导致隐式映射错误。", recommendation: "显式列出目标字段和来源字段。" },
      { id: "risk-star-2", severity: "medium", title: "ADS 脚本存在 SELECT *", object: "08_ads_token_daily.sql", detail: "上游 DWS 字段变化将无提示传播至日报。", recommendation: "改为显式字段映射并增加契约测试。" },
      { id: "risk-cast", severity: "high", title: "局点编码长度被固定", object: "09_ads_region_report.sql", detail: "CAST(region_code AS VARCHAR(16)) 会截断计划扩容后的编码。", recommendation: "统一升级到 VARCHAR(32)，并检查 BI 数据集字段。" },
      { id: "risk-filter", severity: "medium", title: "成功率过滤条件分叉", object: "ads.ads_token_daily.success_rate", detail: "日报排除 TEST 状态，实时看板未排除，导致同名指标口径不一致。", recommendation: "拆分指标名称或统一正式业务过滤规则。" },
      { id: "risk-order", severity: "low", title: "两条作业依赖尚未确认", object: "日流量汇总 → ADS 报表", detail: "依赖仅由 SQL 读写关系推断，未获得平台调度配置。", recommendation: "补录 jobs.csv 或在界面人工确认。" }
    ],
    versionDiffs: [
      { type: "added", objectType: "字段", object: "dwd.dwd_token_request.source_type", summary: "新增请求来源类型，尚未传播到宽表。" },
      { type: "changed", objectType: "字段类型", object: "dwd.dwd_token_request.region_code", summary: "VARCHAR(16) → VARCHAR(32)" },
      { type: "changed", objectType: "指标口径", object: "ads.ads_token_daily.success_rate", summary: "新增 status <> 'TEST' 过滤条件。" },
      { type: "changed", objectType: "时间逻辑", object: "dws.dws_token_hour.stat_hour", summary: "聚合时间从 stat_minute 改为 ingestion_time，疑似错误。" },
      { type: "removed", objectType: "表", object: "ads.ads_token_legacy", summary: "旧版 Token 月报表已下线。" },
      { type: "added", objectType: "血缘", object: "dim.dim_region → ads.ads_region_report", summary: "新增局点名称维度补充。" }
    ],
    assistantSuggestions: [
      "request_success_rate 是怎么计算出来的？",
      "event_time 和 stat_hour 的时间关系有什么风险？",
      "修改 region_code 长度会影响哪些表和报表？",
      "哪些下游脚本使用了 SELECT *？",
      "从 RDS 请求到经营日报经历了哪些加工？",
      "分钟表与小时表请求量为什么可能对不上？"
    ],
    assistantAnswers: {
      success_rate: {
        answer: "请求成功率由 success_cnt / NULLIF(request_cnt, 0) 计算。实时看板直接使用分钟聚合结果；经营日报额外排除了 TEST 状态，因此当前存在同名不同口径风险。",
        evidence: ["04_dws_token_minute.sql 第 31 行", "07_ads_token_realtime.sql 第 18 行", "08_ads_token_daily.sql 第 22 行"]
      },
      region_code: {
        answer: "region_code 从 RDS 经 ODS、DWD、分钟/小时/日聚合传播到 3 张 ADS 表。若扩容到 VARCHAR(32)，至少需修改 7 个结构或脚本对象，并重点处理局点报告中的 VARCHAR(16) 强制转换。",
        evidence: ["03_dwd_enrichment.sql 第 16 行", "09_ads_region_report.sql 第 12 行", "完整下游血缘路径共 8 条边"]
      }
    },
    impactPresets: [
      { id: "impact-region", label: "扩展局点编码长度", object: "dwd.dwd_token_request.region_code", type: "字段类型变化", before: "VARCHAR(16)", after: "VARCHAR(32)", risk: "高", direct: 3, transitive: 11, metrics: 4, ads: 3 },
      { id: "impact-source", label: "新增请求来源字段", object: "dwd.dwd_token_request.source_type", type: "新增字段", before: "不存在", after: "VARCHAR(16)", risk: "中", direct: 2, transitive: 7, metrics: 0, ads: 3 },
      { id: "impact-rate", label: "统一成功率过滤", object: "ads.ads_token_daily.success_rate", type: "过滤条件变化", before: "status <> 'TEST'", after: "统一使用 success_flag = 1", risk: "中", direct: 1, transitive: 0, metrics: 1, ads: 1 }
    ]
  };
})();
