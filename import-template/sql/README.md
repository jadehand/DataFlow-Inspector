# 加工 SQL 目录

请放入实际加工脚本，推荐一个作业对应一个文件，并通过文件名前缀表达便于阅读的顺序：

```text
01_source_to_ods.sql
02_ods_to_dwd.sql
03_dwd_enrichment.sql
04_dws_aggregation.sql
05_ads_report.sql
```

可以保留 `${biz_date}` 等调度宏，并在 `manifest.yaml` 的 `variables` 中提供示例值。产品只做静态分析，不执行这些 SQL。

`00_example_job.sql` 只有注释，不代表任何真实业务；请替换或删除。
