from __future__ import annotations

from ..connection import transaction
from ...services.common import as_dict, json_dumps, json_loads


def replace_import_analysis(project_id: int, import_id: int, version: int, analysis: dict) -> None:
    tables = analysis.get("tables", [])
    columns = [
        (table.get("name"), column)
        for table in tables
        for column in table.get("columns", [])
    ]
    table_edges = analysis.get("table_lineage", [])
    column_edges = analysis.get("column_lineage", [])
    metrics = analysis.get("metrics", [])
    risks = analysis.get("risks", [])
    jobs = analysis.get("jobs", [])
    job_edges = analysis.get("job_lineage", [])
    with transaction() as conn:
        for table_name in [
            "tables",
            "columns",
            "table_lineage_edges",
            "column_lineage_edges",
            "metrics",
            "quality_findings",
            "jobs",
            "job_edges",
        ]:
            conn.execute(f"DELETE FROM {table_name} WHERE import_id=?", (import_id,))
        conn.executemany(
            """
            INSERT INTO tables(
              project_id, import_id, version, name, layer, ddl_file, description,
              inferred, confidence, parse_source, table_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    table.get("name", ""),
                    table.get("layer", "OTHER"),
                    table.get("ddl_file"),
                    table.get("description", "") or table.get("comment", ""),
                    1 if table.get("inferred") else 0,
                    float(table.get("confidence", 0) or 0),
                    table.get("parse_source", ""),
                    json_dumps(table),
                )
                for table in tables
            ],
        )
        conn.executemany(
            """
            INSERT INTO columns(
              project_id, import_id, version, table_name, name, data_type, column_json
            ) VALUES(?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    table_name,
                    column.get("name", ""),
                    column.get("type", ""),
                    json_dumps(column),
                )
                for table_name, column in columns
            ],
        )
        conn.executemany(
            """
            INSERT INTO table_lineage_edges(
              project_id, import_id, version, source, target, file, line,
              operation, confidence, parse_source
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    edge.get("source", ""),
                    edge.get("target", ""),
                    edge.get("file"),
                    edge.get("line"),
                    edge.get("operation", ""),
                    float(edge.get("confidence", 0) or 0),
                    edge.get("parse_source", ""),
                )
                for edge in table_edges
            ],
        )
        conn.executemany(
            """
            INSERT INTO column_lineage_edges(
              project_id, import_id, version, source_table, source_column,
              target_table, target_column, file, line, confidence, parse_source, edge_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    edge.get("source", "").rsplit(".", 1)[0] if "." in edge.get("source", "") else "",
                    edge.get("source", "").rsplit(".", 1)[-1] if "." in edge.get("source", "") else edge.get("source", ""),
                    edge.get("target", "").rsplit(".", 1)[0] if "." in edge.get("target", "") else "",
                    edge.get("target", "").rsplit(".", 1)[-1] if "." in edge.get("target", "") else edge.get("target", ""),
                    edge.get("file"),
                    edge.get("line"),
                    float(edge.get("confidence", 0) or 0),
                    edge.get("parse_source", ""),
                    json_dumps(edge),
                )
                for edge in column_edges
            ],
        )
        conn.executemany(
            """
            INSERT INTO metrics(
              project_id, import_id, version, name, table_name, formula,
              grain_json, filter_expr, file, line, confidence, metric_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    metric.get("name", ""),
                    metric.get("table", ""),
                    metric.get("formula", ""),
                    json_dumps(metric.get("grain", [])),
                    metric.get("filter") or "",
                    metric.get("file"),
                    metric.get("line"),
                    float(metric.get("confidence", 0) or 0),
                    json_dumps(metric),
                )
                for metric in metrics
            ],
        )
        conn.executemany(
            """
            INSERT INTO quality_findings(
              project_id, import_id, version, code, severity, file, object_name, message, finding_json
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    risk.get("code", ""),
                    risk.get("severity", "medium"),
                    risk.get("file"),
                    risk.get("object", ""),
                    risk.get("message", ""),
                    json_dumps(risk),
                )
                for risk in risks
            ],
        )
        conn.executemany(
            """
            INSERT INTO jobs(
              project_id, import_id, version, job_name, output_table,
              schedule, owner, script_path, job_json
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    job.get("job_name", ""),
                    job.get("output_table", "") or job.get("target_table", ""),
                    job.get("schedule", ""),
                    job.get("owner", ""),
                    job.get("script_path", "") or job.get("file", ""),
                    json_dumps(job),
                )
                for job in jobs
            ],
        )
        conn.executemany(
            """
            INSERT INTO job_edges(project_id, import_id, version, source, target, status)
            VALUES(?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    import_id,
                    version,
                    edge.get("source", ""),
                    edge.get("target", ""),
                    edge.get("status", "inferred"),
                )
                for edge in job_edges
            ],
        )


def list_tables(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM tables WHERE import_id=? ORDER BY name",
            (import_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        item.update(json_loads(item.pop("table_json"), {}))
        result.append(item)
    return result


def get_table(import_id: int, table_name: str) -> dict | None:
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM tables WHERE import_id=? AND lower(name)=lower(?)",
            (import_id, table_name),
        ).fetchone()
    if not row:
        return None
    item = as_dict(row)
    item.update(json_loads(item.pop("table_json"), {}))
    return item


def list_columns(import_id: int, table_name: str) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            """
            SELECT * FROM columns
            WHERE import_id=? AND lower(table_name)=lower(?)
            ORDER BY id
            """,
            (import_id, table_name),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        item.update(json_loads(item.pop("column_json"), {}))
        result.append(item)
    return result


def list_table_edges(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM table_lineage_edges WHERE import_id=? ORDER BY id",
            (import_id,),
        ).fetchall()
    return [as_dict(row) for row in rows]


def list_column_edges(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM column_lineage_edges WHERE import_id=? ORDER BY id",
            (import_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        edge = json_loads(item.pop("edge_json"), {})
        if edge:
            result.append(edge)
            continue
        item["source"] = f"{item['source_table']}.{item['source_column']}"
        item["target"] = f"{item['target_table']}.{item['target_column']}"
        result.append(item)
    return result


def list_metrics(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE import_id=? ORDER BY table_name, name",
            (import_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        metric = json_loads(item.pop("metric_json"), {})
        metric.setdefault("grain", json_loads(item.get("grain_json"), []))
        result.append(metric or item)
    return result


def list_findings(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM quality_findings WHERE import_id=? ORDER BY severity DESC, code",
            (import_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        finding = json_loads(item.pop("finding_json"), {})
        result.append(finding or item)
    return result


def list_jobs(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE import_id=? ORDER BY job_name",
            (import_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        job = json_loads(item.pop("job_json"), {})
        result.append(job or item)
    return result


def list_job_edges(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT source, target, status FROM job_edges WHERE import_id=? ORDER BY id",
            (import_id,),
        ).fetchall()
    return [as_dict(row) for row in rows]
