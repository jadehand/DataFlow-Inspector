from __future__ import annotations

from ..db.repositories import analysis_repo, import_repo


def _stable_value(value):
    if isinstance(value, dict):
        return {
            key: _stable_value(item)
            for key, item in sorted(value.items())
            if key
            not in {
                "id",
                "project_id",
                "import_id",
                "version",
                "created_at",
                "completed_at",
                "table_json",
                "column_json",
            }
        }
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    return value


def _table_semantics(table: dict) -> dict:
    return _stable_value(
        {
            key: value
            for key, value in table.items()
            if key not in {"name", "columns", "ddl_file", "confidence", "parse_source"}
        }
    )


def _column_semantics(column: dict) -> dict:
    return _stable_value(
        {
            key: value
            for key, value in column.items()
            if key
            not in {
                "name",
                "table_name",
                "confidence",
                "parse_source",
                "file",
                "line",
            }
        }
    )


def _metric_index(import_id: int) -> dict[str, dict]:
    result = {}
    for metric in analysis_repo.list_metrics(import_id):
        name = metric.get("name", "")
        table_name = metric.get("table", metric.get("table_name", ""))
        key = f"{table_name}.{name}" if table_name else name
        result[key] = _stable_value(
            {
                field: value
                for field, value in metric.items()
                if field not in {"name", "table", "table_name", "file", "line", "confidence"}
            }
        )
    return result


def _finding_index(import_id: int) -> dict[str, dict]:
    result = {}
    for finding in analysis_repo.list_findings(import_id):
        code = finding.get("code", "")
        object_name = finding.get("object_name", "")
        key = f"{code}:{object_name}" if object_name else code
        result[key] = _stable_value(
            {
                field: value
                for field, value in finding.items()
                if field not in {"code", "file", "line"}
            }
        )
    return result


def _index_tables(import_id: int) -> dict[str, dict]:
    return {
        table["name"]: _table_semantics(table)
        for table in analysis_repo.list_tables(import_id)
    }


def _table_details(import_id: int) -> dict[str, dict]:
    return {table["name"]: _stable_value(table) for table in analysis_repo.list_tables(import_id)}


def _index_columns(import_id: int) -> dict[tuple[str, str], dict]:
    items = {}
    for table in analysis_repo.list_tables(import_id):
        for column in analysis_repo.list_columns(import_id, table["name"]):
            items[(table["name"], column["name"])] = _column_semantics(column)
    return items


def _column_details(import_id: int) -> dict[tuple[str, str], dict]:
    items = {}
    for table in analysis_repo.list_tables(import_id):
        for column in analysis_repo.list_columns(import_id, table["name"]):
            items[(table["name"], column["name"])] = _stable_value(column)
    return items


def compare_project_versions(project_id: int, left: int, right: int) -> dict:
    left_import = import_repo.get_import_by_project_version(project_id, left)
    right_import = import_repo.get_import_by_project_version(project_id, right)
    if not left_import or not right_import:
        raise LookupError("import version not found")
    left_tables = _index_tables(left_import["id"])
    right_tables = _index_tables(right_import["id"])
    left_table_details = _table_details(left_import["id"])
    right_table_details = _table_details(right_import["id"])
    left_columns = _index_columns(left_import["id"])
    right_columns = _index_columns(right_import["id"])
    left_column_details = _column_details(left_import["id"])
    right_column_details = _column_details(right_import["id"])
    left_edges = {(edge["source"], edge["target"]) for edge in analysis_repo.list_table_edges(left_import["id"])}
    right_edges = {(edge["source"], edge["target"]) for edge in analysis_repo.list_table_edges(right_import["id"])}
    left_metrics = _metric_index(left_import["id"])
    right_metrics = _metric_index(right_import["id"])
    left_findings = _finding_index(left_import["id"])
    right_findings = _finding_index(right_import["id"])
    table_changes = {
        "added": sorted(set(right_tables) - set(left_tables)),
        "removed": sorted(set(left_tables) - set(right_tables)),
        "modified": sorted(
            key for key in set(left_tables) & set(right_tables) if left_tables[key] != right_tables[key]
        ),
    }
    column_changes = {
        "added": sorted(".".join(key) for key in set(right_columns) - set(left_columns)),
        "removed": sorted(".".join(key) for key in set(left_columns) - set(right_columns)),
        "modified": sorted(
            ".".join(key)
            for key in set(left_columns) & set(right_columns)
            if left_columns[key] != right_columns[key]
        ),
    }
    column_detail_changes = []
    for key in sorted(set(right_columns) - set(left_columns)):
        column_detail_changes.append(
            {
                "table": key[0],
                "name": key[1],
                "change": "added",
                "before": None,
                "after": right_column_details[key],
            }
        )
    for key in sorted(set(left_columns) - set(right_columns)):
        column_detail_changes.append(
            {
                "table": key[0],
                "name": key[1],
                "change": "removed",
                "before": left_column_details[key],
                "after": None,
            }
        )
    for key in sorted(set(left_columns) & set(right_columns)):
        if left_columns[key] != right_columns[key]:
            column_detail_changes.append(
                {
                    "table": key[0],
                    "name": key[1],
                    "change": "modified",
                    "before": left_column_details[key],
                    "after": right_column_details[key],
                }
            )
    modified_table_names = set(table_changes["modified"]) | {
        item["table"] for item in column_detail_changes if item["change"] == "modified"
    }
    changed_tables = []
    for name, change in [
        *((name, "added") for name in table_changes["added"]),
        *((name, "removed") for name in table_changes["removed"]),
        *((name, "modified") for name in sorted(modified_table_names)),
    ]:
        changed_tables.append(
            {
                "name": name,
                "change": change,
                "before": left_table_details.get(name),
                "after": right_table_details.get(name),
                "columns": [
                    item for item in column_detail_changes if item["table"] == name
                ],
            }
        )
    table_changes["changed"] = changed_tables
    changed_seeds = set(table_changes["added"]) | set(table_changes["modified"])
    changed_seeds.update(item.rsplit(".", 1)[0] for item in column_changes["added"])
    changed_seeds.update(item.rsplit(".", 1)[0] for item in column_changes["modified"])
    graph: dict[str, set[str]] = {}
    for source, target in right_edges:
        graph.setdefault(source, set()).add(target)
    pending = list(changed_seeds)
    reached = set(changed_seeds)
    while pending:
        source = pending.pop()
        for target in graph.get(source, set()):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    impacted_ads = sorted(name for name in reached if name.lower().startswith("ads."))
    metrics_modified = sorted(
        key
        for key in set(left_metrics) & set(right_metrics)
        if left_metrics[key] != right_metrics[key]
    )
    risks_modified = sorted(
        key
        for key in set(left_findings) & set(right_findings)
        if left_findings[key] != right_findings[key]
    )
    return {
        "project_id": project_id,
        "left_version": left,
        "right_version": right,
        "tables": table_changes,
        "columns": column_changes,
        "lineage": {
            "added": [
                {"source": source, "target": target}
                for source, target in sorted(right_edges - left_edges)
            ],
            "removed": [
                {"source": source, "target": target}
                for source, target in sorted(left_edges - right_edges)
            ],
        },
        "metrics": {
            "added": sorted(set(right_metrics) - set(left_metrics)),
            "removed": sorted(set(left_metrics) - set(right_metrics)),
            "modified": metrics_modified,
        },
        "risks": {
            "added": sorted(set(right_findings) - set(left_findings)),
            "removed": sorted(set(left_findings) - set(right_findings)),
            "modified": risks_modified,
        },
        "summary": {
            "added": len(table_changes["added"]) + len(column_changes["added"]),
            "modified": len(table_changes["modified"]) + len(column_changes["modified"]),
            "removed": len(table_changes["removed"]) + len(column_changes["removed"]),
            "affected_ads": len([name for name in right_tables if name.lower().startswith("ads.")]),
            "tables_added": len(table_changes["added"]),
            "tables_changed": len(modified_table_names),
            "tables_removed": len(table_changes["removed"]),
            "columns_added": len(column_changes["added"]),
            "columns_changed": len(column_changes["modified"]),
            "columns_removed": len(column_changes["removed"]),
            "lineage_added": len(right_edges - left_edges),
            "lineage_removed": len(left_edges - right_edges),
            "metrics_added": len(set(right_metrics) - set(left_metrics)),
            "metrics_changed": len(metrics_modified),
            "metrics_removed": len(set(left_metrics) - set(right_metrics)),
            "risks_added": len(set(right_findings) - set(left_findings)),
            "risks_changed": len(risks_modified),
            "risks_removed": len(set(left_findings) - set(right_findings)),
            "impacted_ads": impacted_ads,
        },
    }


def compare_single_table(project_id: int, table_name: str, left: int, right: int) -> dict:
    comparison = compare_project_versions(project_id, left, right)
    fields = [
        item
        for item in comparison["columns"]["added"] + comparison["columns"]["removed"] + comparison["columns"]["modified"]
        if item.startswith(f"{table_name}.")
    ]
    return {
        "project_id": project_id,
        "table_name": table_name,
        "left_version": left,
        "right_version": right,
        "field_changes": fields,
        "changed": bool(fields) or table_name in comparison["tables"]["modified"],
    }
