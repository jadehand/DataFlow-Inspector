from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException

from ..db.repositories import analysis_repo, import_repo, metadata_repo, project_repo


def latest_import_or_404(project_id: int, version: int | None = None) -> dict:
    project = project_repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "project not found")
    item = import_repo.latest_completed_import(project_id, version)
    if not item:
        raise HTTPException(404, "completed import not found")
    return item


def _merge_table_meta(project_id: int, table: dict) -> dict:
    meta = metadata_repo.table_metadata_map(project_id).get(table["name"].lower(), {})
    merged = dict(table)
    merged.update(
        {
            "display_name": meta.get("display_name", merged.get("display_name", "")),
            "owner": meta.get("owner", merged.get("owner", "")),
            "update_frequency": meta.get("update_frequency", merged.get("update_frequency", "")),
            "retention": meta.get("retention", merged.get("retention", "")),
            "note": meta.get("note", merged.get("note", "")),
        }
    )
    return merged


def catalog(project_id: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    item = latest_import_or_404(project_id, version)
    tables = [_merge_table_meta(project_id, table) for table in analysis_repo.list_tables(item["id"])]
    if layer:
        layer_upper = layer.upper()
        tables = [table for table in tables if str(table.get("layer", "")).upper() == layer_upper]
    if search:
        needle = search.lower()
        tables = [
            table
            for table in tables
            if needle in table.get("name", "").lower()
            or needle in table.get("display_name", "").lower()
            or needle in table.get("description", "").lower()
        ]
    edges = analysis_repo.list_table_edges(item["id"])
    upstream_count = defaultdict(int)
    downstream_count = defaultdict(int)
    for edge in edges:
        upstream_count[edge["target"].lower()] += 1
        downstream_count[edge["source"].lower()] += 1
    for table in tables:
        columns = analysis_repo.list_columns(item["id"], table["name"])
        table["column_count"] = len(columns)
        table["upstream_count"] = upstream_count[table["name"].lower()]
        table["downstream_count"] = downstream_count[table["name"].lower()]
    return {
        "project_id": project_id,
        "version": item["version"],
        "tables": tables,
        "summary": item.get("summary", {}),
    }


def workflows(project_id: int, version: int | None = None) -> dict:
    item = latest_import_or_404(project_id, version)
    return {
        "project_id": project_id,
        "version": item["version"],
        "jobs": analysis_repo.list_jobs(item["id"]),
        "edges": analysis_repo.list_job_edges(item["id"]),
    }


def quality_findings(project_id: int, version: int | None = None) -> dict:
    item = latest_import_or_404(project_id, version)
    return {
        "project_id": project_id,
        "version": item["version"],
        "findings": analysis_repo.list_findings(item["id"]),
    }


def metrics(project_id: int, version: int | None = None) -> dict:
    item = latest_import_or_404(project_id, version)
    return {
        "project_id": project_id,
        "version": item["version"],
        "metrics": analysis_repo.list_metrics(item["id"]),
    }


def lineage(project_id: int, version: int | None = None, level: str = "table") -> dict:
    item = latest_import_or_404(project_id, version)
    if level == "column":
        edges = analysis_repo.list_column_edges(item["id"])
    else:
        edges = analysis_repo.list_table_edges(item["id"])
    return {
        "project_id": project_id,
        "version": item["version"],
        "level": level,
        "edges": edges,
    }


def table_detail(project_id: int, table_name: str, version: int | None = None) -> dict:
    item = latest_import_or_404(project_id, version)
    table = analysis_repo.get_table(item["id"], table_name)
    if not table:
        raise HTTPException(404, "table not found")
    table = _merge_table_meta(project_id, table)
    fields = analysis_repo.list_columns(item["id"], table["name"])
    field_meta = metadata_repo.column_metadata_map(project_id)
    for field in fields:
        meta = field_meta.get((table["name"].lower(), field["name"].lower()), {})
        field["display_name"] = meta.get("display_name", field.get("display_name", ""))
        field["note"] = meta.get("note", field.get("note", ""))
        field["business_tag"] = meta.get("business_tag", field.get("business_tag", ""))
    table_edges = analysis_repo.list_table_edges(item["id"])
    column_edges = analysis_repo.list_column_edges(item["id"])
    metrics = [metric for metric in analysis_repo.list_metrics(item["id"]) if metric.get("table") == table["name"]]
    findings = [
        finding
        for finding in analysis_repo.list_findings(item["id"])
        if not finding.get("file") or finding.get("file") == table.get("ddl_file") or table["name"] in finding.get("message", "")
    ]
    upstream_tables = sorted({edge["source"] for edge in table_edges if edge["target"].lower() == table["name"].lower()})
    downstream_tables = sorted({edge["target"] for edge in table_edges if edge["source"].lower() == table["name"].lower()})
    related_operations = [
        edge
        for edge in table_edges
        if edge["source"].lower() == table["name"].lower() or edge["target"].lower() == table["name"].lower()
    ]
    evidence = []
    if table.get("ddl_file"):
        evidence.append(
            {
                "type": "ddl",
                "file": table["ddl_file"],
                "summary": "DDL 定义",
                "file_available": True,
                "content_url": f"/api/imports/{item['id']}/files/content?path={table['ddl_file']}",
                "export_url": f"/api/imports/{item['id']}/files/export?path={table['ddl_file']}",
            }
        )
    for op in related_operations[:6]:
        if op.get("file"):
            evidence.append(
                {
                    "type": "etl",
                    "file": op["file"],
                    "line": op.get("line"),
                    "summary": op.get("operation", "transformation"),
                    "sources": [op.get("source")] if op.get("source") else [],
                    "file_available": True,
                    "content_url": f"/api/imports/{item['id']}/files/content?path={op['file']}",
                    "export_url": f"/api/imports/{item['id']}/files/export?path={op['file']}",
                }
            )
    latest_revision = metadata_repo.latest_revision(project_id)
    return {
        "project_id": project_id,
        "version": item["version"],
        "table": {
            **table,
            "upstream_tables": upstream_tables,
            "downstream_tables": downstream_tables,
            "metric_count": len(metrics),
        },
        "fields": fields,
        "metrics": metrics,
        "operations": related_operations[:10],
        "risks": findings,
        "evidence": evidence,
        "import_meta": {
            "id": item["id"],
            "version": item["version"],
            "filename": item["filename"],
            "status": item["status"],
            "created_at": item["created_at"],
        },
        "metadata_revision": latest_revision,
        "column_lineage": [edge for edge in column_edges if edge.get("target", "").startswith(f"{table['name']}.")],
    }
