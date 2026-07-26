from __future__ import annotations

from collections import defaultdict, deque

from fastapi import HTTPException

from ..db.repositories import analysis_repo
from .query_service import latest_import_or_404


def analyze_impact(project_id: int, object_name: str, change_type: str, version: int | None = None) -> dict:
    current = latest_import_or_404(project_id, version)
    tables = analysis_repo.list_tables(current["id"])
    table_edges = analysis_repo.list_table_edges(current["id"])
    column_edges = analysis_repo.list_column_edges(current["id"])
    table_names = {table["name"] for table in tables}
    column_names = {
        f"{table['name']}.{column['name']}"
        for table in tables
        for column in analysis_repo.list_columns(current["id"], table["name"])
    }
    is_column = object_name in column_names
    if object_name not in table_names and not is_column:
        raise HTTPException(404, f"analysis object not found: {object_name}")

    table_graph: dict[str, list[dict]] = defaultdict(list)
    column_graph: dict[str, list[dict]] = defaultdict(list)
    for edge in table_edges:
        table_graph[edge["source"]].append(edge)
    for edge in column_edges:
        if edge.get("source") and edge.get("target"):
            column_graph[edge["source"]].append(edge)
    start = object_name
    graph = column_graph if is_column else table_graph
    queue = deque([(start, 0, [start])])
    seen = {start}
    impacts = []
    paths = []
    evidence = []
    while queue:
        current_node, depth, path = queue.popleft()
        for edge in graph.get(current_node, []):
            target = edge["target"]
            if target in seen:
                continue
            seen.add(target)
            next_path = [*path, target]
            item = {"source": current_node, "target": target, "depth": depth + 1}
            impacts.append(item)
            paths.append({"target": target, "depth": depth + 1, "nodes": next_path})
            evidence.append(
                {
                    "source": current_node,
                    "target": target,
                    "file": edge.get("file"),
                    "line": edge.get("line"),
                    "operation": edge.get("operation"),
                    "confidence": edge.get("confidence"),
                    "parse_source": edge.get("parse_source"),
                }
            )
            queue.append((target, depth + 1, next_path))

    impacted_tables = {
        node.rsplit(".", 1)[0] if is_column else node
        for node in seen
    }
    metrics = [
        metric
        for metric in analysis_repo.list_metrics(current["id"])
        if (metric.get("table") or metric.get("table_name")) in impacted_tables
    ]
    findings = [
        finding
        for finding in analysis_repo.list_findings(current["id"])
        if (finding.get("object") or finding.get("object_name")) in seen | impacted_tables
    ]
    ads_tables = sorted(
        table for table in impacted_tables if table.lower().startswith("ads.")
    )
    scripts = sorted(
        {item["file"] for item in evidence if item.get("file")}
    )
    score = min(
        100,
        len(impacts) * 8
        + len(ads_tables) * 12
        + len(metrics) * 6
        + len(findings) * 5
        + (15 if change_type.lower() in {"drop", "delete", "type_change", "breaking"} else 0),
    )
    severity = "medium"
    if score >= 60:
        severity = "high"
    elif score < 25:
        severity = "low"
    recommendations = []
    if ads_tables:
        recommendations.append("Review and regression-test affected ADS outputs.")
    if metrics:
        recommendations.append("Validate impacted metric definitions and consumers.")
    if scripts:
        recommendations.append("Review the referenced transformation scripts before release.")
    if not recommendations:
        recommendations.append("Run targeted regression checks for the directly affected objects.")
    return {
        "project_id": project_id,
        "object": object_name,
        "change_type": change_type,
        "risk_level": severity,
        "risk": {
            "level": severity,
            "score": score,
            "change_type": change_type,
            "finding_count": len(findings),
            "affected_ads_count": len(ads_tables),
        },
        "transitive_impacts": impacts,
        "paths": paths,
        "scripts": scripts,
        "metrics": metrics,
        "ads_tables": ads_tables,
        "recommendations": recommendations,
        "evidence": evidence,
        "summary": {
            "direct": len([item for item in impacts if item["depth"] == 1]),
            "transitive": len(impacts),
            "metrics": len(metrics),
            "ads_tables": len(ads_tables),
            "scripts": len(scripts),
        },
    }
