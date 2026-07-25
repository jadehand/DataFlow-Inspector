# DDL 目录

请放入本项目链路涉及的建表和变更语句，推荐按数据层拆分，例如：

```text
01_ods.sql
02_dwd.sql
03_dimensions.sql
04_dws.sql
05_ads.sql
```

建议包含 Schema、字段类型、分区键、分布键和字段注释。外部依赖表没有 DDL 时仍能识别表级依赖，但字段级血缘会不完整。

`00_example.sql` 只有注释，不代表任何真实业务；请替换或删除。
