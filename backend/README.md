# DataFlow Inspector Backend

轻量、只读的 DWS SQL 静态分析 API。它不连接生产数据库，也不会执行用户 SQL。

## 启动

```bash
python3 -m pip install -r requirements.txt
python3 run.py
```

默认监听 `127.0.0.1:18080`。上传接口接收 ZIP 原始请求体：

```bash
curl -X POST 'http://127.0.0.1:18080/api/projects' \
  -H 'Content-Type: application/json' -d '{"name":"Token traffic"}'

curl -X POST 'http://127.0.0.1:18080/api/projects/1/imports?filename=demo.zip' \
  -H 'Content-Type: application/zip' --data-binary @../examples/token-traffic-demo.zip
```

主要接口：`/api/projects`、`/imports`、`/catalog`、`/lineage`、`/workflows`、
`/metrics`、`/impact-analysis`、`/compare`、`/assistant/query`、
`/dictionary/bulk`、`/dictionary/bulk/preview`、
`/metadata/revisions`、`/metadata/compare`。

## Metadata Revision

后端会在字典元数据成功保存后生成 metadata revision 快照。

当前结构：

- `metadata_revisions`
- `table_metadata_revisions`
- `column_metadata_revisions`

用途：

- 审计表级/字段级元数据变更
- 记录修订来源、操作人和变更原因
- 支持 revision 列表查询
- 支持 revision 间结构化差异比较
- 让前端在版本比较页和表详情页展示真实 revision 信息
- 允许影响分析消费 compare / revision diff 证据

静态解析覆盖常见 DDL、INSERT SELECT、CTAS、JOIN、GROUP BY 和字段投影。
动态 SQL、存储过程、复杂宏及 `SELECT *` 的字段级映射会明确降级，不宣称完整。
