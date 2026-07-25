"""
分析器 — 整合 DDL 解析、SQL 解析、指标识别、风险检测。

对应旧版 main.py 中的 analyze() 函数，输出结构完全兼容。
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from .ddl_parser import parse_ddl
from .sql_parser import parse_sql


def analyze(dest: Path, files: list[dict]) -> dict[str, Any]:
    """
    对解压后的项目包执行完整分析。

    输出结构与旧版完全一致，新增部分字段（如 confidence、parse_source）。
    """
    # 读取所有文本文件
    texts: dict[str, str] = {}
    diagnostics: list[dict] = []

    for f in files:
        suffix = Path(f["path"]).suffix.lower()
        if suffix in {".sql", ".ddl", ".csv", ".yaml", ".yml"}:
            try:
                texts[f["path"]] = (dest / f["path"]).read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                diagnostics.append({
                    "file": f["path"],
                    "severity": "error",
                    "message": "file is not UTF-8",
                })

    # 1. DDL 解析 → 表 catalog
    tables: list[dict] = []
    for path, text in texts.items():
        suffix = Path(path).suffix.lower()
        if suffix in {".sql", ".ddl"}:
            ddl_tables = parse_ddl(text, path)
            tables.extend(ddl_tables)

    # 去重：同名表保留第一个（DDL 文件优先），合并字段
    catalog: dict[str, dict] = {}
    for t in tables:
        name = t["name"]
        if name not in catalog:
            catalog[name] = t
        else:
            # 合并字段（新的补上）
            existing_cols = {c["name"] for c in catalog[name]["columns"]}
            for col in t["columns"]:
                if col["name"] not in existing_cols:
                    catalog[name]["columns"].append(col)

    # 2. SQL 解析 → 操作列表
    operations = []
    for path, text in texts.items():
        if Path(path).suffix.lower() == ".sql":
            ops = parse_sql(text, path, catalog)
            operations.extend(ops)
            # 检查省略号占位符
            if re.search(r"(?<!\.)\.\.\.(?!\.)", text):
                diagnostics.append({
                    "file": path,
                    "severity": "warning",
                    "code": "INCOMPLETE_SQL",
                    "message": "SQL contains an ellipsis placeholder; table lineage is retained, "
                               "but omitted columns are not guessed",
                })

    # 3. 表级血缘边
    table_edges: list[dict] = []
    column_edges: list[dict] = []
    for op in operations:
        for src in op["sources"]:
            edge = {
                "source": src,
                "target": op["target"],
                "file": op["file"],
                "line": op["line"],
                "operation": op["type"],
                "confidence": op.get("confidence", 0.9),
                "parse_source": op.get("parse_source", "regex_fallback"),
            }
            # 去重
            if not any(e["source"] == edge["source"] and e["target"] == edge["target"] for e in table_edges):
                table_edges.append(edge)
        column_edges.extend(op["columns"])

    # 4. 作业 DAG（来自 jobs.csv）
    jobs: list[dict] = []
    job_edges: list[dict] = []
    for path, text in texts.items():
        if path.endswith("jobs.csv"):
            try:
                jobs = list(csv.DictReader(io.StringIO(text)))
                for j in jobs:
                    upstreams = (j.get("upstream_jobs") or "").split("|")
                    for upstream in upstreams:
                        upstream = upstream.strip()
                        if upstream:
                            job_edges.append({
                                "source": upstream,
                                "target": j.get("job_name", ""),
                                "status": j.get("relation_status", "inferred"),
                            })
            except Exception as e:
                diagnostics.append({
                    "file": path,
                    "severity": "error",
                    "message": f"jobs.csv: {e}",
                })

    # 5. 指标识别
    metrics: list[dict] = []
    aggregate_funcs = re.compile(
        r"\b(COUNT|SUM|AVG|MIN|MAX|PERCENTILE_DISC|PERCENTILE_CONT|"
        r"STDDEV|VARIANCE|ARRAY_AGG|STRING_AGG|GROUP_CONCAT)\s*\(",
        re.I,
    )
    for op in operations:
        for i, expr in enumerate(op.get("metric_projections", op["projections"])):
            if aggregate_funcs.search(expr):
                # 提取别名作为指标名
                am = re.search(r"\s+AS\s+([\w$]+)\s*$", expr, re.I)
                name = am.group(1).lower() if am else f"metric_{i+1}"
                metrics.append({
                    "name": name,
                    "table": op["target"],
                    "formula": expr.strip(),
                    "grain": op["group_by"],
                    "filter": op["where"],
                    "file": op["file"],
                    "line": op["line"],
                    "confidence": op.get("confidence", 0.9),
                })

    # 6. 风险检测
    risks: list[dict] = []

    # SELECT *
    for path, text in texts.items():
        if Path(path).suffix.lower() == ".sql" and re.search(r"\bSELECT\s+\*", text, re.I):
            risks.append({
                "code": "SELECT_STAR",
                "severity": "high",
                "file": path,
                "message": "SELECT * may break when upstream columns change",
            })

    # 时间语义漂移（分钟/小时聚合使用不同时间字段）
    time_usage: list[dict] = []
    for op in operations:
        body = " ".join(op["projections"] + op["group_by"])
        fields = sorted(set(re.findall(
            r"\b([\w]*?(?:event|ingestion|stat|request)[\w]*time|stat_(?:minute|hour)|dt)\b",
            body, re.I)))
        if fields:
            time_usage.append({
                "target": op["target"],
                "fields": [x.lower() for x in fields],
                "file": op["file"],
            })

    minute_fields = {x for u in time_usage if "minute" in u["target"] for x in u["fields"]}
    hour_fields = {x for u in time_usage if "hour" in u["target"] for x in u["fields"]}
    if minute_fields and hour_fields and minute_fields != hour_fields:
        risks.append({
            "code": "TIME_SEMANTIC_DRIFT",
            "severity": "high",
            "message": (f"minute/hour aggregations use different time fields: "
                        f"{sorted(minute_fields)} vs {sorted(hour_fields)}"),
        })

    # 指标过滤漂移（同名指标不同过滤条件）
    filters_by_metric: dict[str, set[str]] = {}
    for m in metrics:
        filters_by_metric.setdefault(m["name"], set()).add(m["filter"] or "")
    for name, filters in filters_by_metric.items():
        if len(filters) > 1:
            risks.append({
                "code": "METRIC_FILTER_DRIFT",
                "severity": "medium",
                "message": f"metric {name} has inconsistent filters",
            })

    # 7. 补充推断表（血缘中出现但不在 catalog 中的表）
    known = set(catalog.keys())
    from .regex_fallback import layer_of as _layer_of
    inferred_tables = []
    for e in table_edges:
        for n in (e["source"], e["target"]):
            if n not in known:
                inferred_table = {
                    "name": n,
                    "columns": [],
                    "ddl_file": None,
                    "layer": _layer_of(n),
                    "inferred": True,
                    "confidence": 0.6,
                    "parse_source": "inferred",
                }
                inferred_tables.append(inferred_table)
                known.add(n)

    all_tables = list(catalog.values()) + inferred_tables

    return {
        "summary": {
            "tables": len(all_tables),
            "columns": sum(len(t["columns"]) for t in all_tables),
            "table_edges": len(table_edges),
            "column_edges": len(column_edges),
            "metrics": len(metrics),
            "risks": len(risks),
            "jobs": len(jobs),
        },
        "files": files,
        "tables": all_tables,
        "operations": operations,
        "table_lineage": table_edges,
        "column_lineage": column_edges,
        "jobs": jobs,
        "job_lineage": job_edges,
        "metrics": metrics,
        "time_usage": time_usage,
        "risks": risks,
        "diagnostics": diagnostics,
    }
