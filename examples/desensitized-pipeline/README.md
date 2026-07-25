# 脱敏数据加工链路项目包

本项目包由 `uploads/desensitized_data_pipeline.md` 拆分，供 DataFlow Inspector 上传分析。

## 覆盖链路

```text
ods_source_a ─┐
              ├─> dwd_fact_request ─┐
ods_source_b ─┘                     │
dwd_dim_model ──────────────────────┼─> dws_fact_enriched ─> dws_agg_minute
dwd_dim_service ────────────────────┘
```

## 重要边界

- 原文中的 `...` 表示脱敏后省略。包内将其保留为 `/* OMITTED... */` 注释，不推测字段。
- `ods_source_b` 的完整 DDL 未给出，只能确认 `pk_id`、`trace_id`，并确认其缺少 `err_detail`；因此该表字段级血缘为低置信度。
- `dwd_fact_request` 两个源 CTE 的完整投影被省略，ODS→DWD 字段级血缘不完整。
- `dws_agg_minute` 的“其他分组维度”和部分 JOIN 条件被省略，分位数回连边只能作为低置信度结果。
- SQL 中引用了一些未提供 DDL 的外部配置、计费、用户和价格表。这些对象应被识别为外部资产，而不是解析错误。
- `jobs.csv` 的顺序依据文档章节和显式读写关系推断，并非来自真实调度平台。
- 原文 DDL 与 SELECT 投影存在若干字段不一致（例如分钟聚合中引用的扩展字段未完整出现在富化表 DDL）；产品应报告而不自动补齐。

## 上传

可直接上传本目录的 ZIP。变量 `${data_time}` 是小时批次时间，示例值见 `manifest.yaml`。
