from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
try:
    import sqlite3
except ModuleNotFoundError:  # Some minimal Python images omit stdlib _sqlite3.
    import pysqlite3 as sqlite3
import tempfile
import time
import traceback
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .parser import analyze as parser_analyze
from .parser import parse_ddl as parser_parse_ddl
from .parser import parse_sql as parser_parse_sql

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DFI_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("DFI_DB_PATH", DATA_DIR / "dataflow.db"))
IMPORT_DIR = Path(os.getenv("DFI_IMPORT_DIR", DATA_DIR / "imports"))
MAX_ZIP = int(os.getenv("DFI_MAX_ZIP_BYTES", 50 * 1024 * 1024))
logger = logging.getLogger("dataflow_inspector")
if not logger.handlers:
    logging.basicConfig(
        level=os.getenv("DFI_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS projects(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          dialect TEXT NOT NULL DEFAULT 'gaussdb_dws', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS imports(
          id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          version INTEGER NOT NULL, sha256 TEXT NOT NULL, filename TEXT NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL, analysis TEXT NOT NULL,
          UNIQUE(project_id, version));
        CREATE TABLE IF NOT EXISTS table_metadata(
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          table_name TEXT NOT NULL,
          display_name TEXT NOT NULL DEFAULT '',
          owner TEXT NOT NULL DEFAULT '',
          update_frequency TEXT NOT NULL DEFAULT '',
          retention TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          modified_at TEXT NOT NULL,
          PRIMARY KEY(project_id, table_name));
        CREATE TABLE IF NOT EXISTS column_metadata(
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          table_name TEXT NOT NULL,
          column_name TEXT NOT NULL,
          display_name TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          business_tag TEXT NOT NULL DEFAULT '',
          modified_at TEXT NOT NULL,
          PRIMARY KEY(project_id, table_name, column_name));
        CREATE TABLE IF NOT EXISTS metadata_revisions(
          id INTEGER PRIMARY KEY,
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision INTEGER NOT NULL,
          import_version INTEGER NOT NULL DEFAULT 0,
          summary_json TEXT NOT NULL DEFAULT '{}',
          source TEXT NOT NULL DEFAULT '',
          operator TEXT NOT NULL DEFAULT '',
          reason TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          UNIQUE(project_id, revision));
        CREATE TABLE IF NOT EXISTS table_metadata_revisions(
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision_id INTEGER NOT NULL REFERENCES metadata_revisions(id) ON DELETE CASCADE,
          table_name TEXT NOT NULL,
          display_name TEXT NOT NULL DEFAULT '',
          owner TEXT NOT NULL DEFAULT '',
          update_frequency TEXT NOT NULL DEFAULT '',
          retention TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(project_id, revision_id, table_name));
        CREATE TABLE IF NOT EXISTS column_metadata_revisions(
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision_id INTEGER NOT NULL REFERENCES metadata_revisions(id) ON DELETE CASCADE,
          table_name TEXT NOT NULL,
          column_name TEXT NOT NULL,
          display_name TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          business_tag TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(project_id, revision_id, table_name, column_name));
        """)
        existing_columns = {
            row["name"]
            for row in c.execute("PRAGMA table_info(metadata_revisions)").fetchall()
        }
        if "source" not in existing_columns:
            c.execute("ALTER TABLE metadata_revisions ADD COLUMN source TEXT NOT NULL DEFAULT ''")
        if "operator" not in existing_columns:
            c.execute("ALTER TABLE metadata_revisions ADD COLUMN operator TEXT NOT NULL DEFAULT ''")
        if "reason" not in existing_columns:
            c.execute("ALTER TABLE metadata_revisions ADD COLUMN reason TEXT NOT NULL DEFAULT ''")


app = FastAPI(title="DataFlow Inspector API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    # Development UI may use any available local port, except Loomi's
    # production backend on 8080.  Do not allow LAN names/IPs or arbitrary
    # web origins.
    allow_origin_regex=r"^https?://(?:127\.0\.0\.1|localhost):(?!8080$)\d{1,5}$",
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.exception(
            "request_failed method=%s path=%s request_id=%s elapsed_ms=%s",
            request.method,
            request.url.path,
            request_id,
            elapsed_ms,
        )
        raise
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = str(elapsed_ms)
    logger.info(
        "request_ok method=%s path=%s status=%s request_id=%s elapsed_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
    logger.warning(
        "http_error method=%s path=%s status=%s request_id=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        request_id,
        detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": detail,
            "detail": detail,
            "status_code": exc.status_code,
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled_error method=%s path=%s request_id=%s",
        request.method,
        request.url.path,
        request_id,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal server error",
            "detail": str(exc),
            "request_id": request_id,
            "trace_hint": traceback.format_exception_only(type(exc), exc)[-1].strip(),
        },
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    dialect: str = "gaussdb_dws"


class ChangeIn(BaseModel):
    object: str
    change_type: str
    before: str | None = None
    after: str | None = None
    compare_scope: str | None = None
    left_version: int | None = None
    right_version: int | None = None
    left_revision: int | None = None
    right_revision: int | None = None


class MetadataRevisionContextIn(BaseModel):
    source: str = ""
    operator: str = ""
    reason: str = ""


class TableMetadataPatch(BaseModel):
    table_name: str
    display_name: str = ""
    owner: str = ""
    update_frequency: str = ""
    retention: str = ""
    note: str = ""


class ColumnMetadataPatch(BaseModel):
    table_name: str
    column_name: str
    display_name: str = ""
    note: str = ""
    business_tag: str = ""


class DictionaryBulkSaveIn(BaseModel):
    tables: list[TableMetadataPatch] = []
    columns: list[ColumnMetadataPatch] = []
    revision_meta: MetadataRevisionContextIn | None = None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def project_or_404(pid: int) -> dict:
    with db() as c:
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not r:
        raise HTTPException(404, "project not found")
    return dict(r)


def import_or_404(iid: int) -> dict:
    with db() as c:
        r = c.execute("SELECT * FROM imports WHERE id=?", (iid,)).fetchone()
    if not r:
        raise HTTPException(404, "import not found")
    d = dict(r)
    d["analysis"] = json.loads(d["analysis"])
    return d


def latest_analysis(pid: int, version: int | None = None) -> tuple[dict, dict]:
    project_or_404(pid)
    sql = "SELECT * FROM imports WHERE project_id=?"
    args: list[Any] = [pid]
    if version is not None:
        sql += " AND version=?"
        args.append(version)
    sql += " ORDER BY version DESC LIMIT 1"
    with db() as c:
        r = c.execute(sql, args).fetchone()
    if not r:
        raise HTTPException(404, "project has no analyzed import")
    meta = dict(r)
    return json.loads(meta.pop("analysis")), meta


def _metric_signature(metric: dict) -> tuple[str, str, str, str]:
    return (
        str(metric.get("table", "")),
        str(metric.get("name", "")),
        str(metric.get("formula", "")),
        str(metric.get("filter", "")),
    )


def _risk_signature(risk: dict) -> tuple[str, str, str]:
    return (
        str(risk.get("code", "")),
        str(risk.get("severity", "")),
        str(risk.get("message", "")),
    )


def _table_snapshot(table: dict) -> dict:
    dws = table.get("dws") or {}
    return {
        "name": table.get("name"),
        "layer": table.get("layer"),
        "column_count": len(table.get("columns", [])),
        "ddl_file": table.get("ddl_file"),
        "partition_columns": dws.get("partition_columns", []),
        "partition_type": dws.get("partition_type"),
        "distribute_columns": dws.get("distribute_columns", []),
    }


def _column_diffs(left_table: dict, right_table: dict) -> dict:
    left_cols = {c["name"]: c for c in left_table.get("columns", [])}
    right_cols = {c["name"]: c for c in right_table.get("columns", [])}
    changed = []
    for name in sorted(set(left_cols) & set(right_cols)):
        before = left_cols[name]
        after = right_cols[name]
        delta = {}
        if before.get("type") != after.get("type"):
            delta["type"] = {"before": before.get("type"), "after": after.get("type")}
        if before.get("role") != after.get("role"):
            delta["role"] = {"before": before.get("role"), "after": after.get("role")}
        if before.get("semantic_type") != after.get("semantic_type"):
            delta["semantic_type"] = {"before": before.get("semantic_type"), "after": after.get("semantic_type")}
        if delta:
            changed.append({"name": name, "changes": delta})
    return {
        "added": [
            {
                "name": name,
                "type": right_cols[name].get("type"),
                "role": right_cols[name].get("role"),
            }
            for name in sorted(set(right_cols) - set(left_cols))
        ],
        "removed": [
            {
                "name": name,
                "type": left_cols[name].get("type"),
                "role": left_cols[name].get("role"),
            }
            for name in sorted(set(left_cols) - set(right_cols))
        ],
        "changed": changed,
    }


def _import_summary_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    analysis = json.loads(item.pop("analysis"))
    diagnostics = analysis.get("diagnostics", [])
    item["summary"] = analysis.get("summary", {})
    item["diagnostics_count"] = len(diagnostics)
    item["error_count"] = sum(1 for d in diagnostics if d.get("severity") == "error")
    item["warning_count"] = sum(1 for d in diagnostics if d.get("severity") == "warning")
    item["risk_count"] = len(analysis.get("risks", []))
    item["job_count"] = len(analysis.get("jobs", []))
    return item


def _find_table_or_404(analysis: dict, table_name: str) -> dict:
    wanted = table_name.lower()
    for table in analysis.get("tables", []):
        if str(table.get("name", "")).lower() == wanted:
            return table
    raise HTTPException(404, f"table {table_name} not found")


def _field_kind(column: dict, metric_names: set[str]) -> str:
    name = str(column.get("name", "")).lower()
    role = str(column.get("role", "")).lower()
    semantic = str(column.get("semantic_type", "")).lower()
    if name in metric_names or role == "measure" or semantic == "metric":
        return "metric"
    if "partition" in role or "partition" in semantic:
        return "partition"
    if "time" in role or "time" in semantic:
        return "time"
    if role == "dimension" or semantic == "dimension":
        return "dimension"
    return "field"


def _table_metadata_map(pid: int) -> dict[str, dict]:
    with db() as c:
        rows = c.execute(
            "SELECT * FROM table_metadata WHERE project_id=?",
            (pid,),
        ).fetchall()
    return {str(row["table_name"]).lower(): dict(row) for row in rows}


def _column_metadata_map(pid: int) -> dict[tuple[str, str], dict]:
    with db() as c:
        rows = c.execute(
            "SELECT * FROM column_metadata WHERE project_id=?",
            (pid,),
        ).fetchall()
    return {
        (str(row["table_name"]).lower(), str(row["column_name"]).lower()): dict(row)
        for row in rows
    }


def _metadata_revision_rows(pid: int) -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT * FROM metadata_revisions WHERE project_id=? ORDER BY revision DESC",
            (pid,),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["summary"] = json.loads(item.pop("summary_json") or "{}")
        items.append(item)
    return items


def _latest_metadata_revision(pid: int) -> dict | None:
    rows = _metadata_revision_rows(pid)
    return rows[0] if rows else None


def _table_metadata_snapshot(pid: int, revision: int | None = None) -> dict[str, dict]:
    if revision is None:
        return _table_metadata_map(pid)
    with db() as c:
        row = c.execute(
            "SELECT id FROM metadata_revisions WHERE project_id=? AND revision=?",
            (pid, revision),
        ).fetchone()
        if not row:
            return {}
        rows = c.execute(
            """SELECT table_name,display_name,owner,update_frequency,retention,note
               FROM table_metadata_revisions WHERE project_id=? AND revision_id=?""",
            (pid, row["id"]),
        ).fetchall()
    return {str(item["table_name"]).lower(): dict(item) for item in rows}


def _column_metadata_snapshot(pid: int, revision: int | None = None) -> dict[tuple[str, str], dict]:
    if revision is None:
        return _column_metadata_map(pid)
    with db() as c:
        row = c.execute(
            "SELECT id FROM metadata_revisions WHERE project_id=? AND revision=?",
            (pid, revision),
        ).fetchone()
        if not row:
            return {}
        rows = c.execute(
            """SELECT table_name,column_name,display_name,note,business_tag
               FROM column_metadata_revisions WHERE project_id=? AND revision_id=?""",
            (pid, row["id"]),
        ).fetchall()
    return {
        (str(item["table_name"]).lower(), str(item["column_name"]).lower()): dict(item)
        for item in rows
    }


def _create_metadata_revision(
    pid: int,
    import_version: int,
    preview: dict,
    revision_meta: MetadataRevisionContextIn | None = None,
) -> dict | None:
    table_map = _table_metadata_map(pid)
    column_map = _column_metadata_map(pid)
    if not table_map and not column_map:
        return None
    previous = _latest_metadata_revision(pid)
    next_revision = int(previous["revision"]) + 1 if previous else 1
    ts = now()
    source = _normalize_text(revision_meta.source if revision_meta else "") or "dictionary_bulk"
    operator_name = _normalize_text(revision_meta.operator if revision_meta else "")
    reason = _normalize_text(revision_meta.reason if revision_meta else "")
    with db() as c:
        cur = c.execute(
            """INSERT INTO metadata_revisions(project_id,revision,import_version,summary_json,source,operator,reason,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                pid,
                next_revision,
                import_version,
                json.dumps(preview.get("summary", {}), ensure_ascii=False),
                source,
                operator_name,
                reason,
                ts,
            ),
        )
        revision_id = cur.lastrowid
        c.executemany(
            """INSERT INTO table_metadata_revisions(
                   project_id,revision_id,table_name,display_name,owner,update_frequency,retention,note
               ) VALUES(?,?,?,?,?,?,?,?)""",
            [
                (
                    pid,
                    revision_id,
                    key,
                    value.get("display_name", ""),
                    value.get("owner", ""),
                    value.get("update_frequency", ""),
                    value.get("retention", ""),
                    value.get("note", ""),
                )
                for key, value in sorted(table_map.items())
            ],
        )
        c.executemany(
            """INSERT INTO column_metadata_revisions(
                   project_id,revision_id,table_name,column_name,display_name,note,business_tag
               ) VALUES(?,?,?,?,?,?,?)""",
            [
                (
                    pid,
                    revision_id,
                    table_name,
                    column_name,
                    value.get("display_name", ""),
                    value.get("note", ""),
                    value.get("business_tag", ""),
                )
                for (table_name, column_name), value in sorted(column_map.items())
            ],
        )
    return {
        "id": revision_id,
        "revision": next_revision,
        "import_version": import_version,
        "source": source,
        "operator": operator_name,
        "reason": reason,
        "created_at": ts,
        "summary": preview.get("summary", {}),
    }


def _compare_metadata_revisions(pid: int, left: int, right: int) -> dict:
    left_tables = _table_metadata_snapshot(pid, left)
    right_tables = _table_metadata_snapshot(pid, right)
    left_columns = _column_metadata_snapshot(pid, left)
    right_columns = _column_metadata_snapshot(pid, right)
    table_changes = []
    column_changes = []
    diff_items = []

    for table_name in sorted(set(left_tables) | set(right_tables)):
        before = left_tables.get(table_name)
        after = right_tables.get(table_name)
        if before is None:
            table_changes.append({"table_name": table_name, "change_type": "added", "before": None, "after": after, "changes": after})
            diff_items.append({"scope": "table_metadata", "table": table_name, "object": table_name, "change_type": "added", "before": None, "after": after})
            continue
        if after is None:
            table_changes.append({"table_name": table_name, "change_type": "removed", "before": before, "after": None, "changes": before})
            diff_items.append({"scope": "table_metadata", "table": table_name, "object": table_name, "change_type": "removed", "before": before, "after": None})
            continue
        delta = {
            key: {"before": _normalize_text(before.get(key)), "after": _normalize_text(after.get(key))}
            for key in ("display_name", "owner", "update_frequency", "retention", "note")
            if _normalize_text(before.get(key)) != _normalize_text(after.get(key))
        }
        if delta:
            table_changes.append({"table_name": table_name, "change_type": "changed", "before": before, "after": after, "changes": delta})
            diff_items.append({"scope": "table_metadata", "table": table_name, "object": table_name, "change_type": "changed", "before": before, "after": after, "details": delta})

    for key in sorted(set(left_columns) | set(right_columns)):
        before = left_columns.get(key)
        after = right_columns.get(key)
        table_name, column_name = key
        object_name = f"{table_name}.{column_name}"
        if before is None:
            column_changes.append({"table_name": table_name, "column_name": column_name, "change_type": "added", "before": None, "after": after, "changes": after})
            diff_items.append({"scope": "column_metadata", "table": table_name, "object": object_name, "change_type": "added", "before": None, "after": after})
            continue
        if after is None:
            column_changes.append({"table_name": table_name, "column_name": column_name, "change_type": "removed", "before": before, "after": None, "changes": before})
            diff_items.append({"scope": "column_metadata", "table": table_name, "object": object_name, "change_type": "removed", "before": before, "after": None})
            continue
        delta = {
            field: {"before": _normalize_text(before.get(field)), "after": _normalize_text(after.get(field))}
            for field in ("display_name", "note", "business_tag")
            if _normalize_text(before.get(field)) != _normalize_text(after.get(field))
        }
        if delta:
            column_changes.append({"table_name": table_name, "column_name": column_name, "change_type": "changed", "before": before, "after": after, "changes": delta})
            diff_items.append({"scope": "column_metadata", "table": table_name, "object": object_name, "change_type": "changed", "before": before, "after": after, "details": delta})

    return {
        "summary": {
            "table_changes": len(table_changes),
            "column_changes": len(column_changes),
            "diff_items": len(diff_items),
        },
        "tables": table_changes,
        "columns": column_changes,
        "diff_items": diff_items,
    }


def _filter_diff_items_for_object(diff_items: list[dict], object_name: str) -> list[dict]:
    normalized = str(object_name or "").strip().lower()
    if not normalized:
        return []
    table_name = normalized.rsplit(".", 1)[0] if normalized.count(".") >= 2 else normalized
    matched = []
    for item in diff_items:
        item_table = str(item.get("table") or "").lower()
        item_object = str(item.get("object") or "").lower()
        if normalized == item_object or normalized == item_table:
            matched.append(item)
            continue
        if table_name and (table_name == item_table or table_name == item_object):
            matched.append(item)
            continue
        if normalized in item_object or normalized in item_table:
            matched.append(item)
    return matched


def _merge_table_metadata(pid: int, table: dict) -> dict:
    meta = _table_metadata_map(pid).get(str(table.get("name", "")).lower(), {})
    merged = dict(table)
    for key in ("display_name", "owner", "update_frequency", "retention", "note"):
        if meta.get(key):
            merged[key] = meta[key]
    return merged


def _merge_column_metadata(column: dict, meta: dict | None) -> dict:
    merged = dict(column)
    if not meta:
        return merged
    for key in ("display_name", "note", "business_tag"):
        if meta.get(key):
            merged[key] = meta[key]
    return merged


def _compare_table_fields(left_table: dict, right_table: dict) -> list[dict]:
    diffs = []
    name = str(right_table.get("name") or left_table.get("name"))
    columns = _column_diffs(left_table, right_table)
    for added in columns["added"]:
        diffs.append({
            "scope": "column",
            "table": name,
            "object": f"{name}.{added['name']}",
            "change_type": "added",
            "before": None,
            "after": added,
        })
    for removed in columns["removed"]:
        diffs.append({
            "scope": "column",
            "table": name,
            "object": f"{name}.{removed['name']}",
            "change_type": "removed",
            "before": removed,
            "after": None,
        })
    for changed in columns["changed"]:
        diffs.append({
            "scope": "column",
            "table": name,
            "object": f"{name}.{changed['name']}",
            "change_type": "changed",
            "before": changed["changes"],
            "after": changed["changes"],
            "details": changed["changes"],
        })
    return diffs


def _dictionary_rows(pid: int, analysis: dict) -> list[dict]:
    table_meta = _table_metadata_map(pid)
    column_meta = _column_metadata_map(pid)
    rows = []
    for raw_table in analysis.get("tables", []):
        table = _merge_table_metadata(pid, raw_table)
        for raw_column in table.get("columns", []):
            meta = column_meta.get((str(table.get("name", "")).lower(), str(raw_column.get("name", "")).lower()))
            column = _merge_column_metadata(raw_column, meta)
            rows.append({
                "table_name": table.get("name"),
                "table_display_name": table.get("display_name", ""),
                "layer": table.get("layer"),
                "owner": table.get("owner", ""),
                "update_frequency": table.get("update_frequency", ""),
                "retention": table.get("retention", ""),
                "table_note": table.get("note", ""),
                "column_name": column.get("name"),
                "column_display_name": column.get("display_name", ""),
                "column_type": column.get("type"),
                "role": column.get("role"),
                "semantic_type": column.get("semantic_type"),
                "business_tag": column.get("business_tag", ""),
                "column_note": column.get("note", ""),
            })
    return rows


def _build_dictionary_bulk_preview(
    pid: int,
    payload: DictionaryBulkSaveIn,
    analysis: dict,
    version: int,
) -> dict:
    known_tables = {
        str(table.get("name", "")).lower(): {
            str(column.get("name", "")).lower() for column in table.get("columns", [])
        }
        for table in analysis.get("tables", [])
    }
    table_meta = _table_metadata_map(pid)
    column_meta = _column_metadata_map(pid)
    missing_tables = sorted({
        item.table_name.strip().lower()
        for item in payload.tables + payload.columns
        if item.table_name.strip() and item.table_name.strip().lower() not in known_tables
    })
    missing_columns = sorted({
        f"{item.table_name.strip().lower()}.{item.column_name.strip().lower()}"
        for item in payload.columns
        if item.table_name.strip().lower() in known_tables
        and item.column_name.strip()
        and item.column_name.strip().lower() not in known_tables[item.table_name.strip().lower()]
    })
    table_changes = []
    column_changes = []
    unchanged_tables = []
    unchanged_columns = []
    touched_tables: set[str] = set()
    table_compare_urls: dict[str, str] = {}

    for item in payload.tables:
        table_name = item.table_name.strip().lower()
        if not table_name or table_name in missing_tables:
            continue
        current = table_meta.get(table_name, {})
        proposed = {
            "display_name": _normalize_text(item.display_name),
            "owner": _normalize_text(item.owner),
            "update_frequency": _normalize_text(item.update_frequency),
            "retention": _normalize_text(item.retention),
            "note": _normalize_text(item.note),
        }
        delta = {
            key: {"before": _normalize_text(current.get(key)), "after": value}
            for key, value in proposed.items()
            if _normalize_text(current.get(key)) != value
        }
        if not delta:
            unchanged_tables.append(table_name)
            continue
        touched_tables.add(table_name)
        table_compare_urls.setdefault(
            table_name,
            f"/api/projects/{pid}/tables/{table_name}/detail?version={version}",
        )
        table_changes.append({
            "table_name": table_name,
            "current": {key: _normalize_text(current.get(key)) for key in proposed},
            "proposed": proposed,
            "changes": delta,
        })

    for item in payload.columns:
        table_name = item.table_name.strip().lower()
        column_name = item.column_name.strip().lower()
        if not table_name or not column_name:
            continue
        if table_name in missing_tables or f"{table_name}.{column_name}" in missing_columns:
            continue
        current = column_meta.get((table_name, column_name), {})
        proposed = {
            "display_name": _normalize_text(item.display_name),
            "note": _normalize_text(item.note),
            "business_tag": _normalize_text(item.business_tag),
        }
        delta = {
            key: {"before": _normalize_text(current.get(key)), "after": value}
            for key, value in proposed.items()
            if _normalize_text(current.get(key)) != value
        }
        if not delta:
            unchanged_columns.append(f"{table_name}.{column_name}")
            continue
        touched_tables.add(table_name)
        table_compare_urls.setdefault(
            table_name,
            f"/api/projects/{pid}/tables/{table_name}/detail?version={version}",
        )
        column_changes.append({
            "table_name": table_name,
            "column_name": column_name,
            "current": {key: _normalize_text(current.get(key)) for key in proposed},
            "proposed": proposed,
            "changes": delta,
        })

    latest_revision = _latest_metadata_revision(pid)
    next_revision = int(latest_revision["revision"]) + 1 if latest_revision else 1
    return {
        "project_id": pid,
        "version": version,
        "metadata_revision": latest_revision,
        "next_metadata_revision": next_revision,
        "summary": {
            "table_updates": len(table_changes),
            "column_updates": len(column_changes),
            "table_field_changes": sum(len(item["changes"]) for item in table_changes),
            "column_field_changes": sum(len(item["changes"]) for item in column_changes),
            "unchanged_tables": len(unchanged_tables),
            "unchanged_columns": len(unchanged_columns),
            "missing_tables": len(missing_tables),
            "missing_columns": len(missing_columns),
        },
        "changes": {
            "tables": table_changes,
            "columns": column_changes,
        },
        "touched_tables": sorted(touched_tables),
        "skipped": {
            "missing_tables": missing_tables,
            "missing_columns": missing_columns,
            "unchanged_tables": sorted(unchanged_tables),
            "unchanged_columns": sorted(unchanged_columns),
        },
        "compare_hints": {
            "project_compare_url": f"/api/projects/{pid}/compare?left={version}&right={version}",
            "table_detail_urls": table_compare_urls,
        },
    }


@app.get("/api/health")
def health() -> dict:
    with db() as c:
        c.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "ok", "version": app.version}


@app.post("/api/projects", status_code=201)
def create_project(p: ProjectIn) -> dict:
    if not p.name.strip():
        raise HTTPException(422, "name is required")
    ts = now()
    with db() as c:
        cur = c.execute("INSERT INTO projects(name,description,dialect,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (p.name.strip(), p.description, p.dialect, ts, ts))
        pid = cur.lastrowid
    return project_or_404(pid)


@app.get("/api/projects")
def list_projects() -> list[dict]:
    with db() as c:
        rows = c.execute("""SELECT p.*,COUNT(i.id) import_count,MAX(i.version) latest_version
                           FROM projects p LEFT JOIN imports i ON i.project_id=p.id
                           GROUP BY p.id ORDER BY p.id""").fetchall()
    return [dict(x) for x in rows]


@app.get("/api/projects/{pid}")
def get_project(pid: int) -> dict:
    return project_or_404(pid)


@app.patch("/api/projects/{pid}")
def update_project(pid: int, p: ProjectIn) -> dict:
    project_or_404(pid)
    with db() as c:
        c.execute("UPDATE projects SET name=?,description=?,dialect=?,updated_at=? WHERE id=?",
                  (p.name, p.description, p.dialect, now(), pid))
    return project_or_404(pid)


@app.delete("/api/projects/{pid}", status_code=204)
def delete_project(pid: int) -> Response:
    project_or_404(pid)
    with db() as c:
        c.execute("DELETE FROM projects WHERE id=?", (pid,))
    shutil.rmtree(IMPORT_DIR / str(pid), ignore_errors=True)
    return Response(status_code=204)


IDENT = r'(?:"[^"]+"|[A-Za-z_][\w$]*)(?:\.(?:"[^"]+"|[A-Za-z_][\w$]*)){0,2}'


def clean_ident(s: str) -> str:
    return ".".join(x.strip('"').lower() for x in s.strip().split("."))


def split_top(text: str) -> list[str]:
    out, start, depth, quote = [], 0, 0, None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            out.append(text[start:i].strip()); start = i + 1
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


def parse_ddl(text: str, path: str) -> list[dict]:
    return parser_parse_ddl(text, path)


def layer_of(name: str) -> str:
    base = name.split(".")[-1].lower()
    for layer in ("ods", "dwd", "dws", "ads"):
        if base.startswith(layer + "_") or name.startswith(layer + "."):
            return layer.upper()
    return "SOURCE" if name.startswith("rds.") else "DIM" if name.startswith("dim.") else "OTHER"


def classify_column(name: str, typ: str) -> dict:
    n = name.lower()
    if n in {"dt", "biz_date", "partition_date"}:
        return {"role": "partition_time", "semantic_type": "partition_time", "confidence": .95}
    if any(x in n for x in ("event_time", "request_time")):
        return {"role": "event_time", "semantic_type": "event_time", "confidence": .9}
    if any(x in n for x in ("ingestion_time", "load_time", "create_time")):
        return {"role": "ingestion_time", "semantic_type": "ingestion_time", "confidence": .85}
    if any(x in n for x in ("stat_", "_hour", "_minute")) and ("TIME" in typ or "DATE" in typ):
        return {"role": "stat_time", "semantic_type": "statistical_time", "confidence": .9}
    if n.endswith(("_cnt", "_count", "_amount", "_rate", "_ms", "_tokens")):
        return {"role": "measure", "semantic_type": "metric", "confidence": .85}
    if n.endswith(("_id", "_code", "_name", "_type", "_status", "_tier")):
        return {"role": "dimension", "semantic_type": "dimension", "confidence": .8}
    return {"role": "unknown", "semantic_type": "unknown", "confidence": .35}


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def matching_paren(text: str, opening: int) -> int | None:
    """Return the matching ')' while respecting SQL strings."""
    depth, quote, i = 0, None, opening
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def cte_definitions(stmt: str) -> dict[str, str]:
    """Extract balanced CTE bodies; regex cannot handle nested subqueries."""
    match = re.search(r"\bWITH\b", stmt, re.I)
    if not match:
        return {}
    out: dict[str, str] = {}
    pos = match.end()
    while pos < len(stmt):
        name_match = re.match(r'\s*,?\s*"?([A-Za-z_]\w*)"?\s+AS\s*\(', stmt[pos:], re.I)
        if not name_match:
            break
        name = name_match.group(1).lower()
        opening = pos + name_match.end() - 1
        closing = matching_paren(stmt, opening)
        if closing is None:
            break
        out[name] = stmt[opening + 1:closing]
        pos = closing + 1
        if not re.match(r"\s*,", stmt[pos:]):
            break
    return out


def top_level_select(text: str) -> re.Match | None:
    """Find SELECT outside parentheses, used to avoid selecting inside a CTE."""
    depth, quote, i = 0, None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            match = re.match(r"\bSELECT\b", text[i:], re.I)
            if match:
                return re.match(r"\bSELECT\b", text[i:], re.I)
        i += 1
    return None


def parse_sql(text: str, path: str, catalog: dict[str, dict]) -> list[dict]:
    return parser_parse_sql(text, path, catalog)


def safe_extract(blob: bytes, dest: Path) -> list[dict]:
    if not blob or len(blob) > MAX_ZIP:
        raise HTTPException(413, "empty or oversized zip")
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        raise HTTPException(400, "invalid zip archive")
    files = []
    total = 0
    seen_paths: set[str] = set()
    for info in zf.infolist():
        # ZIP names are specified with '/', but reject backslash paths too so
        # an archive cannot become unsafe when moved between operating systems.
        portable_name = info.filename.replace("\\", "/")
        rel = Path(portable_name)
        if info.is_dir():
            continue
        normalized = rel.as_posix()
        if ("\x00" in info.filename or rel.is_absolute() or ".." in rel.parts
                or re.match(r"^[A-Za-z]:", portable_name)
                or info.external_attr >> 16 & 0o170000 == 0o120000):
            raise HTTPException(400, f"unsafe zip entry: {info.filename}")
        if normalized in seen_paths:
            raise HTTPException(400, f"duplicate zip entry: {info.filename}")
        seen_paths.add(normalized)
        total += info.file_size
        if total > MAX_ZIP * 5:
            raise HTTPException(413, "expanded archive too large")
        raw = zf.read(info)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append({"path": rel.as_posix(), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    if not files:
        raise HTTPException(400, "zip contains no files")
    return files


def classify_import_files(dest: Path, files: list[dict]) -> dict:
    """Classify an extracted package without persisting or analyzing a project."""
    classified: dict[str, list[str]] = {
        "sql": [], "ddl": [], "manifest": [], "jobs": [], "samples": [], "other": [],
    }
    errors: list[str] = []
    warnings: list[str] = []
    text_suffixes = {".sql", ".ddl", ".csv", ".yaml", ".yml", ".json"}
    for item in files:
        path = item["path"]
        rel = Path(path)
        suffix = rel.suffix.lower()
        lowered = path.lower()
        # Teams commonly use the .sql suffix for DDL. Directory placement is
        # the clearest signal in an import package and keeps the wizard counts
        # intuitive without treating DDL-only files as processing jobs.
        if suffix == ".sql" and "ddl" in {part.lower() for part in rel.parts[:-1]}:
            classified["ddl"].append(path)
        elif suffix == ".sql":
            classified["sql"].append(path)
        elif suffix == ".ddl":
            classified["ddl"].append(path)
        elif rel.name.lower() in {"manifest.yaml", "manifest.yml"}:
            classified["manifest"].append(path)
        elif rel.name.lower() == "jobs.csv":
            classified["jobs"].append(path)
        elif suffix == ".csv" and ("samples/" in f"/{lowered}" or "sample" in rel.stem.lower()):
            classified["samples"].append(path)
        else:
            classified["other"].append(path)
        if suffix in text_suffixes:
            try:
                (dest / rel).read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                errors.append(f"{path}: file is not UTF-8")

    # Some teams keep CREATE TABLE statements in .sql files. Count those as
    # both processing SQL and DDL evidence while preserving the file category.
    ddl_evidence = list(classified["ddl"])
    for path in classified["sql"]:
        try:
            text = (dest / path).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        if re.search(r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\b|\bALTER\s+TABLE\b", text, re.I):
            ddl_evidence.append(path)

    has_sql = bool(classified["sql"])
    has_ddl = bool(ddl_evidence)
    if not has_sql:
        errors.append("加工 SQL 是必需的；请在 ZIP 中加入至少一个 .sql 文件")
    if not has_ddl:
        warnings.append("未发现 DDL；仍可导入，但字段级血缘、SELECT * 展开和类型影响分析会不完整")
    if not classified["manifest"]:
        warnings.append("未提供 manifest.yaml（可选）；将使用默认 DWS 方言、时区和分层规则")
    if not classified["jobs"]:
        warnings.append("未提供 metadata/jobs.csv（可选）；作业顺序将根据 SQL 读写依赖推断")
    if not classified["samples"]:
        warnings.append("未提供 samples/*.csv（可选）；不会进行样例数据辅助分析")
    return {
        "files": classified,
        "counts": {key: len(value) for key, value in classified.items()},
        "has_sql": has_sql,
        "has_ddl": has_ddl,
        "has_manifest": bool(classified["manifest"]),
        "has_jobs": bool(classified["jobs"]),
        "has_samples": bool(classified["samples"]),
        "warnings": warnings,
        "errors": errors,
        "ready": not errors,
    }


def zip_response(blob: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(blob),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def blank_template_zip() -> bytes:
    buf = io.BytesIO()
    manifest = """project: my_data_pipeline
sql_dialect: gaussdb_dws
timezone: Asia/Shanghai
layer_rules:
  ods: "^ods_"
  dwd: "^dwd_"
  dws: "^dws_"
  ads: "^ads_"
"""
    jobs = "job_name,script_path,schedule,upstream_jobs,relation_status\n"
    readme = """DataFlow Inspector 导入模板

必需：sql/ 下至少一个加工 SQL。
强烈推荐：ddl/ 下提供涉及表的完整 DDL。
可选：manifest.yaml、metadata/jobs.csv、samples/*.csv。
请替换示例内容后，将整个目录重新压缩为 ZIP 上传。
"""
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dataflow-template/README.txt", readme)
        zf.writestr("dataflow-template/manifest.yaml", manifest)
        zf.writestr("dataflow-template/ddl/01_tables.ddl",
                    "CREATE TABLE ods.example_source (id BIGINT, event_time TIMESTAMP);\n")
        zf.writestr("dataflow-template/sql/01_example_job.sql",
                    "INSERT INTO dwd.example_target (id, event_time)\n"
                    "SELECT id, event_time FROM ods.example_source;\n")
        zf.writestr("dataflow-template/metadata/jobs.csv", jobs)
        zf.writestr("dataflow-template/samples/example_source.csv", "id,event_time\n")
    return buf.getvalue()


def analyze(dest: Path, files: list[dict]) -> dict:
    return parser_analyze(dest, files)


@app.post("/api/imports/preflight")
async def preflight_import(request: Request) -> dict:
    if "application/zip" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "send ZIP bytes with Content-Type: application/zip")
    blob = await request.body()
    with tempfile.TemporaryDirectory(prefix="dfi-preflight-") as temp:
        dest = Path(temp)
        files = safe_extract(blob, dest)
        return classify_import_files(dest, files)


@app.get("/api/templates/blank")
def download_blank_template() -> StreamingResponse:
    return zip_response(blank_template_zip(), "dataflow-inspector-blank-template.zip")


@app.get("/api/templates/demo")
def download_demo_template() -> StreamingResponse:
    # Resolve relative to this module, never the server's current directory.
    candidates = [
        ROOT.parent / "examples" / "token-traffic-demo.zip",
        ROOT.parent / "examples" / "desensitized-pipeline-project.zip",
    ]
    demo = next((path for path in candidates if path.is_file() and path.stat().st_size), None)
    if demo is None:
        # A deployable backend package may intentionally omit repository
        # examples. Return the safe built-in package instead of a cwd-dependent
        # 404 so the import wizard remains useful.
        return zip_response(blank_template_zip(), "dataflow-inspector-demo.zip")
    return zip_response(demo.read_bytes(), "dataflow-inspector-demo.zip")


@app.post("/api/projects/{pid}/imports", status_code=201)
async def upload_import(pid: int, request: Request, filename: str = Query("project.zip")) -> dict:
    project_or_404(pid)
    if "application/zip" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "send ZIP bytes with Content-Type: application/zip")
    blob = await request.body()
    digest = hashlib.sha256(blob).hexdigest()
    with db() as c:
        version = c.execute("SELECT COALESCE(MAX(version),0)+1 FROM imports WHERE project_id=?", (pid,)).fetchone()[0]
    dest = IMPORT_DIR / str(pid) / str(version)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    try:
        files = safe_extract(blob, dest)
        result = analyze(dest, files)
        with db() as c:
            cur = c.execute("""INSERT INTO imports(project_id,version,sha256,filename,status,created_at,analysis)
                             VALUES(?,?,?,?,?,?,?)""",
                            (pid, version, digest, filename, "completed", now(), json.dumps(result, ensure_ascii=False)))
            iid = cur.lastrowid
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return {"id": iid, "project_id": pid, "version": version, "status": "completed",
            "sha256": digest, "summary": result["summary"]}


@app.get("/api/projects/{pid}/imports")
def list_imports(pid: int) -> list[dict]:
    project_or_404(pid)
    with db() as c:
        rows = c.execute(
            "SELECT id,project_id,version,sha256,filename,status,created_at,analysis "
            "FROM imports WHERE project_id=? ORDER BY version DESC",
            (pid,),
        ).fetchall()
    return [_import_summary_row(r) for r in rows]


@app.get("/api/imports/{iid}")
def get_import(iid: int) -> dict:
    r = import_or_404(iid)
    a = r.pop("analysis")
    r["summary"] = a.get("summary", {})
    r["diagnostics"] = a.get("diagnostics", [])
    r["risks"] = a.get("risks", [])
    r["jobs"] = a.get("jobs", [])
    r["files"] = a.get("files", [])
    return r


@app.get("/api/projects/{pid}/catalog")
def catalog(pid: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    tables = [_merge_table_metadata(pid, t) for t in a["tables"]]
    if layer:
        tables = [t for t in tables if t["layer"].lower() == layer.lower()]
    if search:
        q = search.lower()
        tables = [t for t in tables if q in t["name"] or any(q in c["name"] for c in t["columns"])]
    return {"version": meta["version"], "tables": tables}


@app.get("/api/projects/{pid}/tables")
def tables_alias(pid: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    """Frontend-friendly alias for the catalog endpoint."""
    return catalog(pid, version, layer, search)


@app.get("/api/projects/{pid}/tables/{table_name:path}/detail")
def table_detail(pid: int, table_name: str, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    table = _merge_table_metadata(pid, _find_table_or_404(a, table_name))
    latest_meta_revision = _latest_metadata_revision(pid)
    canonical_name = table["name"]
    metric_names = {m["name"].lower() for m in a.get("metrics", []) if m.get("table") == canonical_name}
    column_meta = _column_metadata_map(pid)
    upstream = sorted({e["source"] for e in a.get("table_lineage", []) if e["target"] == canonical_name})
    downstream = sorted({e["target"] for e in a.get("table_lineage", []) if e["source"] == canonical_name})
    operation_list = [op for op in a.get("operations", []) if op.get("target") == canonical_name]
    related_metrics = [m for m in a.get("metrics", []) if m.get("table") == canonical_name]
    operation_files = sorted({op.get("file") for op in operation_list if op.get("file")})
    related_risks = [
        risk for risk in a.get("risks", [])
        if risk.get("file") in operation_files or risk.get("file") == table.get("ddl_file")
    ]
    incoming_columns = {}
    for edge in a.get("column_lineage", []):
        target = str(edge.get("target", ""))
        prefix = canonical_name + "."
        if target.startswith(prefix):
            field_name = target[len(prefix):]
            incoming_columns.setdefault(field_name, []).append(edge)
    fields = []
    for column in table.get("columns", []):
        field_name = column["name"]
        meta_patch = column_meta.get((canonical_name.lower(), field_name.lower()), {})
        lineage_rows = incoming_columns.get(field_name, [])
        source_tables = sorted({row["source"].rsplit(".", 1)[0] for row in lineage_rows if "." in row["source"]})
        source_fields = sorted({row["source"] for row in lineage_rows})
        expressions = [row.get("expression") for row in lineage_rows if row.get("expression")]
        fields.append({
            "name": field_name,
            "type": column.get("type"),
            "role": column.get("role"),
            "semantic_type": column.get("semantic_type"),
            "nullable": column.get("nullable"),
            "kind": _field_kind(column, metric_names),
            "display_name": meta_patch.get("display_name", ""),
            "note": meta_patch.get("note", ""),
            "business_tag": meta_patch.get("business_tag", ""),
            "source_tables": source_tables,
            "source_fields": source_fields,
            "expression": expressions[0] if expressions else None,
            "lineage_count": len(lineage_rows),
        })
    dws = table.get("dws") or {}
    grain_candidates = []
    time_candidates = []
    for metric in related_metrics:
        grain_candidates.extend(metric.get("grain") or [])
    for field in fields:
        if field["kind"] == "time":
            time_candidates.append(field["name"])
    evidence = []
    if table.get("ddl_file"):
        evidence.append({
            "type": "ddl",
            "file": table["ddl_file"],
            "line": None,
            "summary": "DDL 定义",
        })
    for op in operation_list[:5]:
        evidence.append({
            "type": "etl",
            "file": op.get("file"),
            "line": op.get("line"),
            "summary": f"{op.get('type', 'write')} {op.get('target')}",
            "sources": op.get("sources", []),
            "group_by": op.get("group_by", []),
            "where": op.get("where"),
        })
    return {
        "version": meta["version"],
        "metadata_revision": latest_meta_revision,
        "import_meta": {
            "version": meta["version"],
            "created_at": meta.get("created_at"),
            "status": meta.get("status"),
            "filename": meta.get("filename"),
        },
        "table": {
            "name": canonical_name,
            "layer": table.get("layer"),
            "description": table.get("comment") or table.get("description") or "",
            "display_name": table.get("display_name", ""),
            "owner": table.get("owner", ""),
            "update_frequency": table.get("update_frequency", ""),
            "retention": table.get("retention", ""),
            "note": table.get("note", ""),
            "ddl_file": table.get("ddl_file"),
            "parse_source": table.get("parse_source"),
            "confidence": table.get("confidence"),
            "partition_type": dws.get("partition_type"),
            "partition_columns": dws.get("partition_columns", []),
            "distribute_columns": dws.get("distribute_columns", []),
            "grain": sorted({str(x) for x in grain_candidates if x}),
            "time_fields": sorted(set(time_candidates)),
            "upstream_count": len(upstream),
            "downstream_count": len(downstream),
            "upstream_tables": upstream,
            "downstream_tables": downstream,
            "column_count": len(table.get("columns", [])),
            "metric_count": len(related_metrics),
            "risk_count": len(related_risks),
        },
        "fields": fields,
        "metrics": related_metrics,
        "risks": related_risks,
        "evidence": evidence,
        "operations": [
            {
                "type": op.get("type"),
                "file": op.get("file"),
                "line": op.get("line"),
                "sources": op.get("sources", []),
                "group_by": op.get("group_by", []),
                "where": op.get("where"),
                "projection_count": len(op.get("projections", [])),
            }
            for op in operation_list
        ],
    }


@app.put("/api/projects/{pid}/dictionary/bulk")
def save_dictionary_bulk(pid: int, payload: DictionaryBulkSaveIn) -> dict:
    project_or_404(pid)
    analysis, meta = latest_analysis(pid)
    preview = _build_dictionary_bulk_preview(pid, payload, analysis, meta["version"])
    known_tables = {
        str(table.get("name", "")).lower(): {
            str(column.get("name", "")).lower() for column in table.get("columns", [])
        }
        for table in analysis.get("tables", [])
    }
    missing_tables = preview["skipped"]["missing_tables"]
    missing_columns = preview["skipped"]["missing_columns"]
    ts = now()
    saved_tables = 0
    saved_columns = 0
    touched_tables: set[str] = set()
    with db() as c:
        for item in payload.tables:
            table_name = item.table_name.strip().lower()
            if not table_name or table_name in missing_tables:
                continue
            touched_tables.add(table_name)
            c.execute(
                """INSERT INTO table_metadata(project_id,table_name,display_name,owner,update_frequency,retention,note,modified_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(project_id,table_name) DO UPDATE SET
                     display_name=excluded.display_name,
                     owner=excluded.owner,
                     update_frequency=excluded.update_frequency,
                     retention=excluded.retention,
                     note=excluded.note,
                     modified_at=excluded.modified_at""",
                (
                    pid,
                    table_name,
                    item.display_name.strip(),
                    item.owner.strip(),
                    item.update_frequency.strip(),
                    item.retention.strip(),
                    item.note.strip(),
                    ts,
                ),
            )
            saved_tables += 1
        for item in payload.columns:
            table_name = item.table_name.strip().lower()
            column_name = item.column_name.strip().lower()
            if not table_name or not column_name:
                continue
            if table_name in missing_tables or f"{table_name}.{column_name}" in missing_columns:
                continue
            touched_tables.add(table_name)
            c.execute(
                """INSERT INTO column_metadata(project_id,table_name,column_name,display_name,note,business_tag,modified_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(project_id,table_name,column_name) DO UPDATE SET
                     display_name=excluded.display_name,
                     note=excluded.note,
                     business_tag=excluded.business_tag,
                     modified_at=excluded.modified_at""",
                (
                    pid,
                    table_name,
                    column_name,
                    item.display_name.strip(),
                    item.note.strip(),
                    item.business_tag.strip(),
                    ts,
                ),
            )
            saved_columns += 1
    revision_meta = None
    if saved_tables or saved_columns:
        revision_meta = _create_metadata_revision(pid, meta["version"], preview, payload.revision_meta)
    return {
        "project_id": pid,
        "version": meta["version"],
        "saved_tables": saved_tables,
        "saved_columns": saved_columns,
        "touched_tables": sorted(touched_tables),
        "metadata_revision": revision_meta,
        "preview": preview,
        "skipped": {
            "missing_tables": missing_tables,
            "missing_columns": missing_columns,
        },
        "modified_at": ts,
    }


@app.post("/api/projects/{pid}/dictionary/bulk/preview")
def preview_dictionary_bulk(pid: int, payload: DictionaryBulkSaveIn) -> dict:
    project_or_404(pid)
    analysis, meta = latest_analysis(pid)
    preview = _build_dictionary_bulk_preview(pid, payload, analysis, meta["version"])
    preview["requires_confirmation"] = bool(
        preview["changes"]["tables"] or preview["changes"]["columns"]
    )
    return preview


@app.get("/api/projects/{pid}/metadata/revisions")
def list_metadata_revisions(pid: int) -> dict:
    project_or_404(pid)
    return {
        "project_id": pid,
        "revisions": _metadata_revision_rows(pid),
    }


@app.get("/api/projects/{pid}/metadata/compare")
def compare_metadata_revisions(pid: int, left: int, right: int) -> dict:
    project_or_404(pid)
    revisions = {item["revision"]: item for item in _metadata_revision_rows(pid)}
    if left not in revisions or right not in revisions:
        raise HTTPException(404, "metadata revision not found")
    compared = _compare_metadata_revisions(pid, left, right)
    return {
        "project_id": pid,
        "left_revision": revisions[left],
        "right_revision": revisions[right],
        **compared,
        "compare_scope": "metadata_revision",
    }


@app.get("/api/projects/{pid}/tables/{table_name:path}/compare")
def compare_single_table(pid: int, table_name: str, left: int, right: int) -> dict:
    left_analysis, left_meta = latest_analysis(pid, left)
    right_analysis, right_meta = latest_analysis(pid, right)
    left_table = _find_table_or_404(left_analysis, table_name)
    right_table = _find_table_or_404(right_analysis, table_name)
    column_diff = _column_diffs(left_table, right_table)
    left_metrics = [m for m in left_analysis.get("metrics", []) if m.get("table") == left_table["name"]]
    right_metrics = [m for m in right_analysis.get("metrics", []) if m.get("table") == right_table["name"]]
    left_metric_map = {m["name"]: m for m in left_metrics}
    right_metric_map = {m["name"]: m for m in right_metrics}
    metric_changes = []
    for key in sorted(set(left_metric_map) & set(right_metric_map)):
        before = left_metric_map[key]
        after = right_metric_map[key]
        delta = {}
        for field in ("formula", "filter", "grain"):
            if before.get(field) != after.get(field):
                delta[field] = {"before": before.get(field), "after": after.get(field)}
        if delta:
            metric_changes.append({"name": key, "changes": delta})
    diff_items = _compare_table_fields(left_table, right_table)
    for name in sorted(set(right_metric_map) - set(left_metric_map)):
        diff_items.append({
            "scope": "metric",
            "table": right_table["name"],
            "object": f"{right_table['name']}::{name}",
            "change_type": "added",
            "before": None,
            "after": right_metric_map[name],
        })
    for name in sorted(set(left_metric_map) - set(right_metric_map)):
        diff_items.append({
            "scope": "metric",
            "table": left_table["name"],
            "object": f"{left_table['name']}::{name}",
            "change_type": "removed",
            "before": left_metric_map[name],
            "after": None,
        })
    for changed in metric_changes:
        diff_items.append({
            "scope": "metric",
            "table": right_table["name"],
            "object": f"{right_table['name']}::{changed['name']}",
            "change_type": "changed",
            "before": changed["changes"],
            "after": changed["changes"],
            "details": changed["changes"],
        })
    table_meta = _table_metadata_map(pid).get(table_name.lower(), {})
    latest_meta_revision = _latest_metadata_revision(pid)
    return {
        "table_name": table_name,
        "left": left_meta["version"],
        "right": right_meta["version"],
        "summary": {
            "column_added": len(column_diff["added"]),
            "column_removed": len(column_diff["removed"]),
            "column_changed": len(column_diff["changed"]),
            "metric_added": len(set(right_metric_map) - set(left_metric_map)),
            "metric_removed": len(set(left_metric_map) - set(right_metric_map)),
            "metric_changed": len(metric_changes),
            "diff_items": len(diff_items),
        },
        "table_metadata": {
            "display_name": table_meta.get("display_name", ""),
            "owner": table_meta.get("owner", ""),
            "update_frequency": table_meta.get("update_frequency", ""),
            "retention": table_meta.get("retention", ""),
            "note": table_meta.get("note", ""),
        },
        "metadata_revision": latest_meta_revision,
        "columns": column_diff,
        "metrics": {
            "added": sorted(set(right_metric_map) - set(left_metric_map)),
            "removed": sorted(set(left_metric_map) - set(right_metric_map)),
            "changed": metric_changes,
        },
        "diff_items": diff_items,
        "compare_scope": "table",
    }


@app.get("/api/projects/{pid}/dictionary/export")
def export_dictionary(pid: int, version: int | None = None, format: str = "csv"):
    a, meta = latest_analysis(pid, version)
    rows = _dictionary_rows(pid, a)
    latest_meta_revision = _latest_metadata_revision(pid)
    fmt = format.strip().lower()
    if fmt == "json":
        return {
            "project_id": pid,
            "version": meta["version"],
            "metadata_revision": latest_meta_revision,
            "row_count": len(rows),
            "rows": rows,
        }
    if fmt != "csv":
        raise HTTPException(422, "format must be csv or json")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else [
        "table_name", "table_display_name", "layer", "owner", "update_frequency", "retention",
        "table_note", "column_name", "column_display_name", "column_type", "role",
        "semantic_type", "business_tag", "column_note"
    ])
    writer.writeheader()
    writer.writerows(rows)
    blob = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(blob),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="data-dictionary-project-{pid}-v{meta["version"]}.csv"'},
    )


@app.get("/api/projects/{pid}/lineage")
def lineage(pid: int, version: int | None = None, level: str = "table") -> dict:
    a, meta = latest_analysis(pid, version)
    if level not in {"table", "column"}:
        raise HTTPException(422, "level must be table or column")
    return {"version": meta["version"], "level": level,
            "edges": a["table_lineage" if level == "table" else "column_lineage"]}


@app.get("/api/projects/{pid}/workflows")
def workflows(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "jobs": a["jobs"], "edges": a["job_lineage"]}


@app.get("/api/projects/{pid}/metrics")
def metrics(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "metrics": a["metrics"], "time_usage": a["time_usage"],
            "risks": a["risks"]}


@app.get("/api/projects/{pid}/quality-findings")
def quality_findings(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "findings": a["risks"], "risks": a["risks"]}


@app.post("/api/projects/{pid}/impact-analysis")
def impact(pid: int, change: ChangeIn, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    obj = change.object.lower()
    table = obj.rsplit(".", 1)[0] if obj.count(".") >= 2 else obj
    adjacency: dict[str, list[str]] = {}
    for e in a["table_lineage"]:
        adjacency.setdefault(e["source"], []).append(e["target"])
    queue, seen, paths = [table], {table}, []
    while queue:
        cur = queue.pop(0)
        for nxt in adjacency.get(cur, []):
            paths.append({"source": cur, "target": nxt})
            if nxt not in seen:
                seen.add(nxt); queue.append(nxt)
    direct = adjacency.get(table, [])
    scripts = sorted({e["file"] for e in a["table_lineage"] if e["source"] in seen or e["target"] in seen})
    metric_names = sorted({m["name"] for m in a["metrics"] if m["table"] in seen})
    ads = sorted(x for x in seen if layer_of(x) == "ADS")
    severity = "high" if change.change_type in {"delete_column", "rename_column", "group_by_change", "filter_change"} or len(seen) > 5 else "medium" if direct else "low"
    warnings = [r for r in a["risks"] if not r.get("file") or r.get("file") in scripts]
    diff_evidence = []
    evidence_scope = None
    if change.compare_scope == "metadata_revision" and change.left_revision and change.right_revision:
        evidence_scope = "metadata_revision"
        diff_evidence = _filter_diff_items_for_object(
            _compare_metadata_revisions(pid, change.left_revision, change.right_revision)["diff_items"],
            change.object,
        )
    elif change.compare_scope == "project" and change.left_version and change.right_version:
        evidence_scope = "project"
        compared = compare(pid, change.left_version, change.right_version)
        diff_evidence = _filter_diff_items_for_object(compared.get("diff_items", []), change.object)
    latest_meta_revision = _latest_metadata_revision(pid)
    return {"version": meta["version"], "change": change.model_dump(), "risk": severity,
            "direct_impacts": direct, "transitive_impacts": sorted(seen - {table}),
            "paths": paths, "scripts": scripts, "metrics": metric_names, "ads_tables": ads,
            "warnings": warnings, "diff_evidence": diff_evidence, "evidence_scope": evidence_scope,
            "metadata_revision": latest_meta_revision,
            "recommendations": [
                "update target DDL and writer SQL first", "update downstream transformations in topological order",
                "run schema and metric regression checks", "backfill affected partitions when historical semantics change"]}


@app.get("/api/projects/{pid}/compare")
def compare(pid: int, left: int, right: int) -> dict:
    a, lm = latest_analysis(pid, left)
    b, rm = latest_analysis(pid, right)
    latest_meta_revision = _latest_metadata_revision(pid)
    at, bt = {x["name"]: x for x in a["tables"]}, {x["name"]: x for x in b["tables"]}
    changed = []
    diff_items = []
    for n in sorted(set(bt) - set(at)):
        diff_items.append({
            "scope": "table",
            "table": n,
            "object": n,
            "change_type": "added",
            "before": None,
            "after": _table_snapshot(bt[n]),
        })
    for n in sorted(set(at) - set(bt)):
        diff_items.append({
            "scope": "table",
            "table": n,
            "object": n,
            "change_type": "removed",
            "before": _table_snapshot(at[n]),
            "after": None,
        })
    for n in sorted(set(at) & set(bt)):
        column_changes = _column_diffs(at[n], bt[n])
        structural_delta = {}
        for key in ("ddl_file", "layer"):
            if at[n].get(key) != bt[n].get(key):
                structural_delta[key] = {"before": at[n].get(key), "after": bt[n].get(key)}
        left_dws, right_dws = at[n].get("dws") or {}, bt[n].get("dws") or {}
        if left_dws.get("partition_columns") != right_dws.get("partition_columns"):
            structural_delta["partition_columns"] = {
                "before": left_dws.get("partition_columns", []),
                "after": right_dws.get("partition_columns", []),
            }
        if left_dws.get("partition_type") != right_dws.get("partition_type"):
            structural_delta["partition_type"] = {
                "before": left_dws.get("partition_type"),
                "after": right_dws.get("partition_type"),
            }
        if column_changes["added"] or column_changes["removed"] or column_changes["changed"] or structural_delta:
            changed.append({
                "table": n,
                "before": _table_snapshot(at[n]),
                "after": _table_snapshot(bt[n]),
                "columns": column_changes,
                "structure": structural_delta,
            })
            diff_items.append({
                "scope": "table",
                "table": n,
                "object": n,
                "change_type": "changed",
                "before": _table_snapshot(at[n]),
                "after": _table_snapshot(bt[n]),
                "details": {
                    "structure": structural_delta,
                    "columns": column_changes,
                },
            })
            diff_items.extend(_compare_table_fields(at[n], bt[n]))
    edgekey = lambda x: (x["source"], x["target"])
    ae, be = {edgekey(x) for x in a["table_lineage"]}, {edgekey(x) for x in b["table_lineage"]}
    left_metrics = {_metric_signature(m): m for m in a.get("metrics", [])}
    right_metrics = {_metric_signature(m): m for m in b.get("metrics", [])}
    left_metric_names = {m["table"] + "::" + m["name"]: m for m in a.get("metrics", [])}
    right_metric_names = {m["table"] + "::" + m["name"]: m for m in b.get("metrics", [])}
    metric_changed = []
    for key in sorted(set(left_metric_names) & set(right_metric_names)):
        before = left_metric_names[key]
        after = right_metric_names[key]
        delta = {}
        for field in ("formula", "filter", "grain"):
            if before.get(field) != after.get(field):
                delta[field] = {"before": before.get(field), "after": after.get(field)}
        if delta:
            metric_changed.append({
                "metric": key,
                "table": after.get("table"),
                "name": after.get("name"),
                "changes": delta,
            })
            diff_items.append({
                "scope": "metric",
                "table": after.get("table"),
                "object": key,
                "change_type": "changed",
                "before": delta,
                "after": delta,
                "details": delta,
            })
    left_risks = {_risk_signature(r): r for r in a.get("risks", [])}
    right_risks = {_risk_signature(r): r for r in b.get("risks", [])}
    left_ops = {(op.get("target"), op.get("file"), op.get("type")): op for op in a.get("operations", [])}
    right_ops = {(op.get("target"), op.get("file"), op.get("type")): op for op in b.get("operations", [])}
    for key in sorted(set(right_metrics) - set(left_metrics)):
        metric = right_metrics[key]
        diff_items.append({
            "scope": "metric",
            "table": metric.get("table"),
            "object": f"{metric.get('table')}::{metric.get('name')}",
            "change_type": "added",
            "before": None,
            "after": metric,
        })
    for key in sorted(set(left_metrics) - set(right_metrics)):
        metric = left_metrics[key]
        diff_items.append({
            "scope": "metric",
            "table": metric.get("table"),
            "object": f"{metric.get('table')}::{metric.get('name')}",
            "change_type": "removed",
            "before": metric,
            "after": None,
        })
    for source, target in sorted(be - ae):
        diff_items.append({
            "scope": "lineage",
            "table": target,
            "object": f"{source}->{target}",
            "change_type": "added",
            "before": None,
            "after": {"source": source, "target": target},
        })
    for source, target in sorted(ae - be):
        diff_items.append({
            "scope": "lineage",
            "table": target,
            "object": f"{source}->{target}",
            "change_type": "removed",
            "before": {"source": source, "target": target},
            "after": None,
        })
    impacted_ads = sorted({
        edge[1]
        for edge in (be - ae)
        if layer_of(edge[1]) == "ADS"
    })
    table_scope = sorted({item["table"] for item in diff_items if item.get("table")})
    return {
        "left": lm["version"],
        "right": rm["version"],
        "summary": {
            "tables_added": len(set(bt) - set(at)),
            "tables_removed": len(set(at) - set(bt)),
            "tables_changed": len(changed),
            "lineage_added": len(be - ae),
            "lineage_removed": len(ae - be),
            "metrics_added": len(set(right_metrics) - set(left_metrics)),
            "metrics_removed": len(set(left_metrics) - set(right_metrics)),
            "metrics_changed": len(metric_changed),
            "risks_added": len(set(right_risks) - set(left_risks)),
            "risks_removed": len(set(left_risks) - set(right_risks)),
            "ops_added": len(set(right_ops) - set(left_ops)),
            "ops_removed": len(set(left_ops) - set(right_ops)),
            "impacted_ads": len(impacted_ads),
            "diff_items": len(diff_items),
            "changed_tables_scope": len(table_scope),
        },
        "tables": {
            "added": [_table_snapshot(bt[n]) for n in sorted(set(bt) - set(at))],
            "removed": [_table_snapshot(at[n]) for n in sorted(set(at) - set(bt))],
            "changed": changed,
        },
        "lineage": {
            "added": [{"source": s, "target": t} for s, t in sorted(be - ae)],
            "removed": [{"source": s, "target": t} for s, t in sorted(ae - be)],
        },
        "metrics": {
            "added": [right_metrics[k] for k in sorted(set(right_metrics) - set(left_metrics))],
            "removed": [left_metrics[k] for k in sorted(set(left_metrics) - set(right_metrics))],
            "changed": metric_changed,
        },
        "risks": {
            "added": [right_risks[k] for k in sorted(set(right_risks) - set(left_risks))],
            "removed": [left_risks[k] for k in sorted(set(left_risks) - set(right_risks))],
        },
        "operations": {
            "added": [right_ops[k] for k in sorted(set(right_ops) - set(left_ops))],
            "removed": [left_ops[k] for k in sorted(set(left_ops) - set(right_ops))],
        },
        "impacted_ads": impacted_ads,
        "diff_items": diff_items,
        "table_names_in_scope": table_scope,
        "metadata_revision": latest_meta_revision,
        "compare_scope": "project",
    }


@app.post("/api/projects/{pid}/assistant/query")
def assistant(pid: int, payload: dict = Body(...), version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(422, "question is required")
    q = question.lower()
    evidence, lines = [], []
    for m in a["metrics"]:
        if m["name"].lower() in q:
            lines.append(f"{m['name']} 在 {m['table']} 中计算，公式为 {m['formula']}。")
            lines.append(f"聚合粒度：{', '.join(m['grain']) or '未识别'}；过滤：{m['filter'] or '无'}。")
            evidence.append({"file": m["file"], "line": m["line"], "object": f"{m['table']}.{m['name']}"})
    for t in a["tables"]:
        if t["name"] in q:
            ups = [e["source"] for e in a["table_lineage"] if e["target"] == t["name"]]
            downs = [e["target"] for e in a["table_lineage"] if e["source"] == t["name"]]
            lines.append(f"{t['name']} 属于 {t['layer']} 层；直接上游：{', '.join(ups) or '无'}；直接下游：{', '.join(downs) or '无'}。")
            evidence.extend({"file": e["file"], "line": e["line"], "object": t["name"]}
                            for e in a["table_lineage"] if e["target"] == t["name"] or e["source"] == t["name"])
    if any(x in q for x in ("风险", "问题", "异常")):
        lines.extend(f"[{r['severity']}] {r['message']}" for r in a["risks"])
        evidence.extend({"file": r.get("file"), "line": None, "object": r["code"]} for r in a["risks"])
    if not lines:
        lines.append("未找到足够的结构化证据。可询问具体表名、指标名或“有哪些风险”。")
    return {"version": meta["version"], "question": question, "answer": "\n".join(lines),
            "evidence": evidence[:20], "confidence": "high" if evidence else "low"}


# ============================================================
#  单表导入 + 冲突检测 + 自动融合
# ============================================================

from app.parser.single_table import (
    import_single_table,
    merge_table_into_analysis,
    infer_relationships,
    SingleTableImportResult,
)


class SingleTableImportRequest(BaseModel):
    ddl: str
    etl_sql: str = ""                  # 可选：加工 SQL，提供时精准解析血缘
    conflict_strategy: str = "check"   # "check" | "replace" | "keep" | "merge" | "merge_inferred" | "accept_orphan" | "confirm_precise"
    confirmed_relation_index: int | None = None


@app.post("/api/projects/{pid}/tables/import")
def import_single_table_endpoint(pid: int, req: SingleTableImportRequest) -> dict:
    """
    导入单条 CREATE TABLE DDL + 可选 ETL SQL。

    三级模式：
    - DDL + ETL  → 精准解析入库 (action: imported_precise)
    - 仅 DDL      → 返回推断供用户判断 (action: orphan_pending)，或直接作为孤立表入库 (conflict_strategy != "check")
    - 冲突        → 返回冲突详情让用户选择策略 (action: conflict)
    """
    project_or_404(pid)

    # 获取最新分析数据
    existing = None
    latest_version = 0
    with db() as c:
        row = c.execute(
            "SELECT * FROM imports WHERE project_id=? ORDER BY version DESC LIMIT 1",
            (pid,),
        ).fetchone()
    if row:
        existing = json.loads(dict(row)["analysis"])
        latest_version = row["version"]

    raw_strategy = (req.conflict_strategy or "check").strip().lower()
    strategy = {"accept_orphan": "keep", "confirm_precise": "merge"}.get(raw_strategy, raw_strategy)

    result = import_single_table(
        ddl_text=req.ddl,
        project_id=pid,
        existing_analysis=existing,
        conflict_strategy=strategy,
        etl_sql=req.etl_sql if req.etl_sql else None,
    )

    if (
        strategy == "merge_inferred"
        and req.confirmed_relation_index is not None
        and 0 <= req.confirmed_relation_index < len(result.inferred_relations)
    ):
        result.inferred_relations = [result.inferred_relations[req.confirmed_relation_index]]

    # 推断结果格式化
    def _relations_out():
        return [
            {
                "index": i,
                "source_table": r.source_table,
                "target_table": r.target_table,
                "matched_columns_count": len(r.matched_columns),
                "matched_columns": r.matched_columns[:20],
                "confidence": r.confidence,
                "inference_method": r.inference_method,
                "selected": req.confirmed_relation_index == i,
            }
            for i, r in enumerate(result.inferred_relations)
        ]

    def _table_out():
        return {
            "name": result.table_name,
            "layer": result.table_info["layer"] if result.table_info else "?",
            "columns": [{"name": c["name"], "type": c["type"]} for c in (result.table_info["columns"] if result.table_info else [])],
            "column_count": len(result.table_info["columns"]) if result.table_info else 0,
        }

    def _missing_upstream_tables() -> list[str]:
        if not existing:
            existing_cat = {}
        else:
            existing_cat = {t["name"]: t for t in existing.get("tables", [])}
        etl_sources = {e["source"] for e in result.table_lineage}
        return sorted(s for s in etl_sources if s not in existing_cat and s != result.table_name)

    def _navigation_out(default_page: str) -> dict:
        return {"project_id": pid, "page": default_page, "table_name": result.table_name}

    def _decision_out() -> dict:
        action = result.action
        if action == "conflict":
            return {
                "stage": "conflict_resolution",
                "available_strategies": ["replace", "keep", "merge"],
                "recommended_strategy": "merge",
                "hint": "请先查看共同列、新增列、删除列和类型变化，再选择冲突策略。",
            }
        if action == "ready_to_import_precise":
            return {
                "stage": "precise_import_confirmation",
                "available_strategies": ["confirm_precise"],
                "recommended_strategy": "confirm_precise",
                "hint": "已完成精确解析；确认后会落一个新版本并刷新项目血缘。",
            }
        if action == "orphan_pending":
            available = ["accept_orphan"]
            if result.inferred_relations:
                available.insert(0, "merge_inferred")
            return {
                "stage": "orphan_or_inferred_confirmation",
                "available_strategies": available,
                "recommended_strategy": available[0],
                "hint": "如果推断关系可信，建议确认一条推断关系导入；否则可作为孤立表先入库。",
            }
        return {}

    # ↓ 三种不需要写库的返回场景 ↓

    # A. 冲突
    if result.action == "conflict":
        return {
            "table_name": result.table_name,
            "action": result.action,
            "table": _table_out(),
            "conflict": result.conflict.__dict__ if result.conflict else None,
            "table_lineage": result.table_lineage,
            "column_lineage": result.column_lineage,
            "inferred_relations": _relations_out(),
            "message": result.message,
            "requires_decision": True,
            **_decision_out(),
            "navigation": _navigation_out("assets"),
        }

    # B. 仅 DDL、check 模式 → 返回推断给用户判断
    if result.action == "orphan_pending":
        return {
            "table_name": result.table_name,
            "action": result.action,
            "table": _table_out(),
            "inferred_relations": _relations_out(),
            "message": result.message,
            "requires_decision": True,
            **_decision_out(),
            "navigation": _navigation_out("assets"),
        }

    # C. DDL + ETL check 模式 → 解析完成预览，等用户确认
    if result.action == "ready_to_import_precise":
        return {
            "table_name": result.table_name,
            "action": result.action,
            "table": _table_out(),
            "table_lineage": result.table_lineage,
            "column_lineage_count": len(result.column_lineage),
            "column_lineage": result.column_lineage[:20],
            "missing_upstream_tables": _missing_upstream_tables(),
            "message": result.message,
            "requires_decision": True,
            **_decision_out(),
            "navigation": _navigation_out("lineage"),
        }

    # ↓ 入库场景 ↓

    # 构建或更新分析数据
    if existing is None:
        new_analysis = {
            "summary": {
                "tables": 1,
                "columns": len(result.table_info["columns"]) if result.table_info else 0,
                "table_edges": len(result.table_lineage),
                "column_edges": len(result.column_lineage),
                "metrics": 0, "risks": 0, "jobs": 0,
            },
            "files": [],
            "tables": [result.table_info] if result.table_info else [],
            "operations": result.operations,
            "table_lineage": result.table_lineage,
            "column_lineage": result.column_lineage,
            "jobs": [], "job_lineage": [],
            "metrics": [], "time_usage": [], "risks": [], "diagnostics": [],
        }
    else:
        new_analysis = merge_table_into_analysis(
            existing, result.table_info,
            result.table_lineage, result.column_lineage,
            result.inferred_relations, result.operations)

    # 写回
    seed = (req.ddl + (req.etl_sql or "")).encode()
    digest = hashlib.sha256(seed).hexdigest()
    new_version = latest_version + 1
    ts = now()
    with db() as c:
        c.execute(
            """INSERT INTO imports(project_id,version,sha256,filename,status,created_at,analysis)
               VALUES(?,?,?,?,?,?,?)""",
            (pid, new_version, digest, f"single-import:{result.table_name}", "completed",
             ts, json.dumps(new_analysis, ensure_ascii=False)),
        )

    lineage_sources = {e.get("parse_source", "?") for e in
                      (result.table_lineage + result.column_lineage)}
    return {
        "table_name": result.table_name,
        "action": result.action,
        "table": _table_out(),
        "conflict": result.conflict.__dict__ if result.conflict else None,
        "lineage_source": "parsed_from_sql" if lineage_sources & {"sqlglot_ast", "regex_fallback"} else
                         "inferred" if "inferred" in lineage_sources else
                         "none",
        "table_lineage": result.table_lineage,
        "column_lineage": result.column_lineage,
        "inferred_relations": _relations_out(),
        "missing_upstream_tables": _missing_upstream_tables(),
        "version": new_version,
        "summary": new_analysis["summary"],
        "message": result.message,
        "requires_decision": False,
        "navigation": _navigation_out("assets"),
    }


@app.get("/api/projects/{pid}/tables/{table_name:path}/relationships")
def get_table_relationships(pid: int, table_name: str, version: int | None = None) -> dict:
    """查询指定表在现有数据字典中的上游/下游关系和同名字段匹配。"""
    a, meta = latest_analysis(pid, version)

    # 找到目标表
    target_table = None
    for t in a["tables"]:
        if t["name"].lower() == table_name.lower():
            target_table = t
            break

    if not target_table:
        raise HTTPException(404, f"table {table_name} not found in project {pid}")

    # 上游表
    upstream = [e["source"] for e in a["table_lineage"] if e["target"].lower() == table_name.lower()]

    # 下游表
    downstream = [e["target"] for e in a["table_lineage"] if e["source"].lower() == table_name.lower()]

    # 同名字段匹配（JOIN 键）
    target_cols = {c["name"].lower(): c for c in target_table.get("columns", [])}
    join_matches = []
    for t in a["tables"]:
        if t["name"] == table_name:
            continue
        for c in t.get("columns", []):
            cname = c["name"].lower()
            if cname in target_cols and cname.endswith("_id"):
                join_matches.append({
                    "table": t["name"],
                    "column": cname,
                    "type": c.get("type", ""),
                })

    return {
        "version": meta["version"],
        "table": table_name,
        "layer": target_table.get("layer"),
        "columns": len(target_table.get("columns", [])),
        "upstream_tables": upstream,
        "downstream_tables": downstream,
        "join_key_matches": join_matches,
    }


@app.post("/api/projects/{pid}/tables/preview")
def preview_table_ddl(pid: int, payload: dict = Body(...)) -> dict:
    """预处理单条 DDL/可选 ETL，返回解析结果和冲突/关系预览（不写库）。"""
    ddl_text = str(payload.get("ddl", "")).strip()
    etl_sql = str(payload.get("etl_sql", "")).strip()
    if not ddl_text:
        raise HTTPException(422, "ddl is required")

    # 获取现有 catalog
    existing_catalog = {}
    existing_analysis = None
    with db() as c:
        row = c.execute(
            "SELECT * FROM imports WHERE project_id=? ORDER BY version DESC LIMIT 1",
            (pid,),
        ).fetchone()
    if row:
        existing_analysis = json.loads(dict(row)["analysis"])
        for t in existing_analysis.get("tables", []):
            existing_catalog[t["name"]] = t

    result = import_single_table(
        ddl_text=ddl_text,
        project_id=pid,
        existing_analysis=existing_analysis,
        conflict_strategy="check",
        etl_sql=etl_sql or None,
    )

    def _table_out() -> dict:
        table_info = result.table_info or {}
        return {
            "name": result.table_name,
            "layer": table_info.get("layer", "?"),
            "columns": [
                {
                    "name": c["name"],
                    "type": c["type"],
                    "role": c.get("role", "unknown"),
                }
                for c in table_info.get("columns", [])
            ],
            "column_count": len(table_info.get("columns", [])),
        }

    def _relations_out() -> list[dict]:
        return [
            {
                "index": i,
                "source_table": r.source_table,
                "target_table": r.target_table,
                "matched_columns_count": len(r.matched_columns),
                "matched_columns": r.matched_columns[:20],
                "confidence": r.confidence,
                "inference_method": r.inference_method,
            }
            for i, r in enumerate(result.inferred_relations)
        ]

    def _missing_upstream_tables() -> list[str]:
        etl_sources = {e["source"] for e in result.table_lineage}
        return sorted(
            s for s in etl_sources if s not in existing_catalog and s != result.table_name
        )

    def _decision_out() -> dict:
        if result.action == "conflict":
            return {
                "stage": "conflict_resolution",
                "available_strategies": ["replace", "keep", "merge"],
                "recommended_strategy": "merge",
                "hint": "请先查看共同列、新增列、删除列和类型变化，再选择冲突策略。",
            }
        if result.action == "ready_to_import_precise":
            return {
                "stage": "precise_import_confirmation",
                "available_strategies": ["confirm_precise"],
                "recommended_strategy": "confirm_precise",
                "hint": "已完成精确解析；确认后会落一个新版本并刷新项目血缘。",
            }
        available = ["accept_orphan"]
        if result.inferred_relations:
            available.insert(0, "merge_inferred")
        return {
            "stage": "orphan_or_inferred_confirmation",
            "available_strategies": available,
            "recommended_strategy": available[0],
            "hint": "如果推断关系可信，建议确认一条推断关系导入；否则可作为孤立表先入库。",
        }

    return {
        "table_name": result.table_name,
        "action": result.action,
        "table": _table_out(),
        "conflict": result.conflict.__dict__ if result.conflict else None,
        "table_lineage": result.table_lineage,
        "column_lineage_count": len(result.column_lineage),
        "column_lineage": result.column_lineage[:20],
        "missing_upstream_tables": _missing_upstream_tables(),
        "inferred_relations": _relations_out(),
        "total_relations_found": len(result.inferred_relations),
        "requires_decision": result.action in {"conflict", "orphan_pending", "ready_to_import_precise"},
        "message": result.message,
        **_decision_out(),
    }
