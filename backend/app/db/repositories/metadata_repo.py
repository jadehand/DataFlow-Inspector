from __future__ import annotations

from ..connection import transaction
from ...services.common import as_dict, json_dumps, json_loads, now_iso


def table_metadata_map(project_id: int) -> dict[str, dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM table_metadata WHERE project_id=?",
            (project_id,),
        ).fetchall()
    return {row["table_name"].lower(): as_dict(row) for row in rows}


def column_metadata_map(project_id: int) -> dict[tuple[str, str], dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM column_metadata WHERE project_id=?",
            (project_id,),
        ).fetchall()
    return {
        (row["table_name"].lower(), row["column_name"].lower()): as_dict(row)
        for row in rows
    }


def latest_revision(project_id: int) -> dict | None:
    with transaction() as conn:
        row = conn.execute(
            """
            SELECT * FROM metadata_revisions
            WHERE project_id=?
            ORDER BY revision DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    return as_dict(row) if row else None


def list_revisions(project_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            """
            SELECT * FROM metadata_revisions
            WHERE project_id=?
            ORDER BY revision DESC
            """,
            (project_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = as_dict(row)
        item["summary"] = json_loads(item.get("summary_json"), {})
        result.append(item)
    return result


def revision_snapshot(project_id: int, revision: int) -> dict:
    with transaction() as conn:
        revision_row = conn.execute(
            "SELECT * FROM metadata_revisions WHERE project_id=? AND revision=?",
            (project_id, revision),
        ).fetchone()
        if not revision_row:
            raise LookupError("metadata revision not found")
        table_rows = conn.execute(
            """
            SELECT table_name, display_name, owner, update_frequency, retention, note
            FROM table_metadata_revisions
            WHERE project_id=? AND revision_id=?
            ORDER BY table_name
            """,
            (project_id, revision_row["id"]),
        ).fetchall()
        column_rows = conn.execute(
            """
            SELECT table_name, column_name, display_name, note, business_tag
            FROM column_metadata_revisions
            WHERE project_id=? AND revision_id=?
            ORDER BY table_name, column_name
            """,
            (project_id, revision_row["id"]),
        ).fetchall()
    return {
        "revision": as_dict(revision_row),
        "tables": [as_dict(row) for row in table_rows],
        "columns": [as_dict(row) for row in column_rows],
    }


def save_bulk_metadata(
    project_id: int,
    import_version: int,
    tables: list[dict],
    columns: list[dict],
    revision_meta: dict,
) -> dict:
    latest = latest_revision(project_id)
    next_revision = (latest["revision"] if latest else 0) + 1
    summary = {
        "table_updates": len(tables),
        "column_updates": len(columns),
        "diff_items": len(tables) + len(columns),
    }
    created_at = now_iso()
    with transaction() as conn:
        for table in tables:
            conn.execute(
                """
                INSERT INTO table_metadata(
                  project_id, table_name, display_name, owner, update_frequency, retention, note, modified_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(project_id, table_name) DO UPDATE SET
                  display_name=excluded.display_name,
                  owner=excluded.owner,
                  update_frequency=excluded.update_frequency,
                  retention=excluded.retention,
                  note=excluded.note,
                  modified_at=excluded.modified_at
                """,
                (
                    project_id,
                    table["table_name"],
                    table.get("display_name", ""),
                    table.get("owner", ""),
                    table.get("update_frequency", ""),
                    table.get("retention", ""),
                    table.get("note", ""),
                    created_at,
                ),
            )
        for column in columns:
            conn.execute(
                """
                INSERT INTO column_metadata(
                  project_id, table_name, column_name, display_name, note, business_tag, modified_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(project_id, table_name, column_name) DO UPDATE SET
                  display_name=excluded.display_name,
                  note=excluded.note,
                  business_tag=excluded.business_tag,
                  modified_at=excluded.modified_at
                """,
                (
                    project_id,
                    column["table_name"],
                    column["column_name"],
                    column.get("display_name", ""),
                    column.get("note", ""),
                    column.get("business_tag", ""),
                    created_at,
                ),
            )
        cur = conn.execute(
            """
            INSERT INTO metadata_revisions(
              project_id, revision, import_version, summary_json, source, operator, reason, created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                project_id,
                next_revision,
                import_version,
                json_dumps(summary),
                revision_meta.get("source", ""),
                revision_meta.get("operator", ""),
                revision_meta.get("reason", ""),
                created_at,
            ),
        )
        revision_id = cur.lastrowid
        latest_tables = conn.execute(
            "SELECT * FROM table_metadata WHERE project_id=? ORDER BY table_name",
            (project_id,),
        ).fetchall()
        latest_columns = conn.execute(
            "SELECT * FROM column_metadata WHERE project_id=? ORDER BY table_name, column_name",
            (project_id,),
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO table_metadata_revisions(
              project_id, revision_id, table_name, display_name, owner, update_frequency, retention, note
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    revision_id,
                    row["table_name"],
                    row["display_name"],
                    row["owner"],
                    row["update_frequency"],
                    row["retention"],
                    row["note"],
                )
                for row in latest_tables
            ],
        )
        conn.executemany(
            """
            INSERT INTO column_metadata_revisions(
              project_id, revision_id, table_name, column_name, display_name, note, business_tag
            ) VALUES(?,?,?,?,?,?,?)
            """,
            [
                (
                    project_id,
                    revision_id,
                    row["table_name"],
                    row["column_name"],
                    row["display_name"],
                    row["note"],
                    row["business_tag"],
                )
                for row in latest_columns
            ],
        )
        row = conn.execute("SELECT * FROM metadata_revisions WHERE id=?", (revision_id,)).fetchone()
    item = as_dict(row)
    item["summary"] = summary
    return item
