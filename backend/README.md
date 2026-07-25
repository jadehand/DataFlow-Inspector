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
`/metrics`、`/impact-analysis`、`/compare`、`/assistant/query`。

静态解析覆盖常见 DDL、INSERT SELECT、CTAS、JOIN、GROUP BY 和字段投影。
动态 SQL、存储过程、复杂宏及 `SELECT *` 的字段级映射会明确降级，不宣称完整。
