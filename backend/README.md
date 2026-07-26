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

如果重构后入口迁移到工厂函数，可直接用：

```bash
cd ..
DATAFLOW_BACKEND_APP=app.factory:create_app:factory make dev
```

`scripts/check.sh` 会自动尝试以下入口：

- `app.factory:create_app`
- `app.main:create_app`
- `app.main:app`

若都不存在，需显式设置 `DATAFLOW_BACKEND_APP`。

主要接口：`/api/projects`、`/imports`、`/catalog`、`/lineage`、`/workflows`、
`/metrics`、`/impact-analysis`、`/compare`、`/assistant/query`、
`/dictionary/bulk`、`/dictionary/bulk/preview`、
`/metadata/revisions`、`/metadata/compare`、
`/imports/{id}/files`、`/imports/{id}/files/content`、`/imports/{id}/files/export`。

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

## 导入文件资产

当前后端会统一记录导入文件资产：

- ZIP 导入：保存原始解压文件并建立文件索引
- 单表导入：把输入的 DDL / ETL 规范化落盘后再建立文件索引

因此后续可以统一支持：

- 查看原始 DDL / ETL
- 导出单个导入文件
- 导出某个分析版本全部导入文件
