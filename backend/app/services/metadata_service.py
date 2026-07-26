from __future__ import annotations

import csv
import io

from fastapi import HTTPException

from ..db.repositories import analysis_repo, import_repo, metadata_repo, project_repo
from .common import now_iso


def preview_bulk_update(project_id: int, payload: dict) -> dict:
    if not project_repo.get_project(project_id):
        raise HTTPException(404, "project not found")
    current = import_repo.latest_completed_import(project_id)
    if not current:
        raise HTTPException(400, "project has no completed import")
    tables = {table["name"].lower() for table in analysis_repo.list_tables(current["id"])}
    columns = {
        (field["table_name"].lower(), field["name"].lower())
        for table in analysis_repo.list_tables(current["id"])
        for field in analysis_repo.list_columns(current["id"], table["name"])
    }
    missing_tables = [
        item["table_name"]
        for item in payload.get("tables", [])
        if item["table_name"].lower() not in tables
    ]
    missing_columns = [
        f"{item['table_name']}.{item['column_name']}"
        for item in payload.get("columns", [])
        if (item["table_name"].lower(), item["column_name"].lower()) not in columns
    ]
    latest = metadata_repo.latest_revision(project_id)
    return {
        "summary": {
            "table_updates": len(payload.get("tables", [])),
            "column_updates": len(payload.get("columns", [])),
        },
        "skipped": {
            "missing_tables": missing_tables,
            "missing_columns": missing_columns,
        },
        "requires_confirmation": True,
        "next_metadata_revision": (latest["revision"] if latest else 0) + 1,
        "generated_at": now_iso(),
    }


def save_bulk_update(project_id: int, payload: dict) -> dict:
    current = import_repo.latest_completed_import(project_id)
    if not current:
        raise HTTPException(400, "project has no completed import")
    preview = preview_bulk_update(project_id, payload)
    valid_tables = [
        item
        for item in payload.get("tables", [])
        if item["table_name"] not in preview["skipped"]["missing_tables"]
    ]
    valid_columns = [
        item
        for item in payload.get("columns", [])
        if f"{item['table_name']}.{item['column_name']}" not in preview["skipped"]["missing_columns"]
    ]
    revision = metadata_repo.save_bulk_metadata(
        project_id,
        current["version"],
        valid_tables,
        valid_columns,
        payload.get("revision_meta", {}),
    )
    return {
        "saved_tables": len(valid_tables),
        "saved_columns": len(valid_columns),
        "metadata_revision": revision,
        "preview": preview,
        "skipped": preview["skipped"],
    }


def list_revisions(project_id: int) -> dict:
    if not project_repo.get_project(project_id):
        raise HTTPException(404, "project not found")
    return {"project_id": project_id, "revisions": metadata_repo.list_revisions(project_id)}


def compare_revisions(project_id: int, left: int, right: int) -> dict:
    if not project_repo.get_project(project_id):
        raise HTTPException(404, "project not found")
    left_snapshot = metadata_repo.revision_snapshot(project_id, left)
    right_snapshot = metadata_repo.revision_snapshot(project_id, right)
    left_tables = {item["table_name"]: item for item in left_snapshot["tables"]}
    right_tables = {item["table_name"]: item for item in right_snapshot["tables"]}
    left_columns = {(item["table_name"], item["column_name"]): item for item in left_snapshot["columns"]}
    right_columns = {(item["table_name"], item["column_name"]): item for item in right_snapshot["columns"]}
    changes = []
    for key in sorted(set(left_tables) | set(right_tables)):
        if key not in left_tables:
            changes.append({"object": key, "change_type": "table_added"})
        elif key not in right_tables:
            changes.append({"object": key, "change_type": "table_removed"})
        elif left_tables[key] != right_tables[key]:
            changes.append({"object": key, "change_type": "table_modified"})
    for key in sorted(set(left_columns) | set(right_columns)):
        if key not in left_columns:
            changes.append({"object": ".".join(key), "change_type": "column_added"})
        elif key not in right_columns:
            changes.append({"object": ".".join(key), "change_type": "column_removed"})
        elif left_columns[key] != right_columns[key]:
            changes.append({"object": ".".join(key), "change_type": "column_modified"})
    return {
        "project_id": project_id,
        "left": left,
        "right": right,
        "compare_scope": "metadata_revision",
        "changes": changes,
        "summary": {"diff_items": len(changes)},
    }


def export_dictionary_csv(project_id: int) -> str:
    if not project_repo.get_project(project_id):
        raise HTTPException(404, "project not found")
    current = import_repo.latest_completed_import(project_id)
    if not current:
        raise HTTPException(404, "completed import not found")
    table_meta = metadata_repo.table_metadata_map(project_id)
    column_meta = metadata_repo.column_metadata_map(project_id)
    output = io.StringIO()
    fieldnames = [
        "table_name",
        "table_display_name",
        "layer",
        "owner",
        "update_frequency",
        "retention",
        "table_note",
        "column_name",
        "column_display_name",
        "data_type",
        "nullable",
        "role",
        "business_tag",
        "column_note",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for table in analysis_repo.list_tables(current["id"]):
        table_name = table["name"]
        table_patch = table_meta.get(table_name.lower(), {})
        columns = analysis_repo.list_columns(current["id"], table_name)
        if not columns:
            columns = [{}]
        for column in columns:
            column_name = column.get("name", "")
            column_patch = column_meta.get(
                (table_name.lower(), column_name.lower()), {}
            )
            writer.writerow(
                {
                    "table_name": table_name,
                    "table_display_name": table_patch.get("display_name", ""),
                    "layer": table.get("layer", ""),
                    "owner": table_patch.get("owner", ""),
                    "update_frequency": table_patch.get("update_frequency", ""),
                    "retention": table_patch.get("retention", ""),
                    "table_note": table_patch.get("note", ""),
                    "column_name": column_name,
                    "column_display_name": column_patch.get("display_name", ""),
                    "data_type": column.get("type", column.get("data_type", "")),
                    "nullable": column.get("nullable", ""),
                    "role": column.get("role", ""),
                    "business_tag": column_patch.get("business_tag", ""),
                    "column_note": column_patch.get("note", ""),
                }
            )
    return output.getvalue()
