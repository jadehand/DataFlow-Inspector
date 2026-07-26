from __future__ import annotations

from ..connection import transaction
from ...services.common import as_dict, json_dumps, json_loads, now_iso


def next_version(project_id: int) -> int:
    with transaction() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM imports WHERE project_id=?",
            (project_id,),
        ).fetchone()
    return int(row["version"])


def create_import(project_id: int, filename: str, sha256: str, mode: str) -> dict:
    version = next_version(project_id)
    created_at = now_iso()
    with transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO imports(project_id, version, filename, sha256, status, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            (project_id, version, filename, sha256, "queued", created_at),
        )
        import_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO analysis_runs(project_id, import_id, mode, status, requested_at)
            VALUES(?,?,?,?,?)
            """,
            (project_id, import_id, mode, "queued", created_at),
        )
        row = conn.execute("SELECT * FROM imports WHERE id=?", (import_id,)).fetchone()
    return as_dict(row)


def list_imports(project_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            """
            SELECT i.*, r.id AS run_id, r.status AS run_status, r.error AS run_error
            FROM imports i
            LEFT JOIN analysis_runs r ON r.import_id = i.id
            WHERE i.project_id=?
            ORDER BY i.version DESC
            """,
            (project_id,),
        ).fetchall()
    return [as_dict(row) for row in rows]


def get_import(import_id: int) -> dict | None:
    with transaction() as conn:
        row = conn.execute(
            """
            SELECT i.*, r.id AS run_id, r.status AS run_status, r.error AS run_error
            FROM imports i
            LEFT JOIN analysis_runs r ON r.import_id = i.id
            WHERE i.id=?
            """,
            (import_id,),
        ).fetchone()
    if not row:
        return None
    item = as_dict(row)
    item["summary"] = json_loads(item.get("summary_json"), {})
    item["snapshot"] = json_loads(item.get("snapshot_json"), {})
    return item


def get_import_by_project_version(project_id: int, version: int) -> dict | None:
    with transaction() as conn:
        row = conn.execute(
            """
            SELECT i.*, r.id AS run_id, r.status AS run_status, r.error AS run_error
            FROM imports i
            LEFT JOIN analysis_runs r ON r.import_id = i.id
            WHERE i.project_id=? AND i.version=?
            """,
            (project_id, version),
        ).fetchone()
    if not row:
        return None
    item = as_dict(row)
    item["summary"] = json_loads(item.get("summary_json"), {})
    item["snapshot"] = json_loads(item.get("snapshot_json"), {})
    return item


def latest_completed_import(project_id: int, version: int | None = None) -> dict | None:
    sql = """
        SELECT i.*, r.id AS run_id, r.status AS run_status, r.error AS run_error
        FROM imports i
        LEFT JOIN analysis_runs r ON r.import_id = i.id
        WHERE i.project_id=? AND i.status='completed'
    """
    params: list[object] = [project_id]
    if version is not None:
        sql += " AND i.version=?"
        params.append(version)
    sql += " ORDER BY i.version DESC LIMIT 1"
    with transaction() as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    item = as_dict(row)
    item["summary"] = json_loads(item.get("summary_json"), {})
    item["snapshot"] = json_loads(item.get("snapshot_json"), {})
    return item


def get_run(run_id: int) -> dict | None:
    with transaction() as conn:
        row = conn.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
    return as_dict(row) if row else None


def recoverable_run_ids() -> list[int]:
    """Reset interrupted work and return every run that must be queued."""
    with transaction() as conn:
        conn.execute(
            """
            UPDATE analysis_runs
            SET status='queued', started_at=NULL, completed_at=NULL, error=''
            WHERE status='running'
            """
        )
        conn.execute(
            """
            UPDATE imports SET status='queued', completed_at=NULL
            WHERE id IN (
              SELECT import_id FROM analysis_runs WHERE status='queued'
            )
            """
        )
        rows = conn.execute(
            "SELECT id FROM analysis_runs WHERE status='queued' ORDER BY id"
        ).fetchall()
    return [int(row["id"]) for row in rows]


def claim_run(run_id: int) -> bool:
    """Atomically claim a queued run so duplicate queue entries are harmless."""
    started_at = now_iso()
    with transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE analysis_runs
            SET status='running', started_at=?, completed_at=NULL, error=''
            WHERE id=? AND status='queued'
            """,
            (started_at, run_id),
        )
        if cursor.rowcount != 1:
            return False
        conn.execute(
            """
            UPDATE imports SET status='running', completed_at=NULL
            WHERE id=(SELECT import_id FROM analysis_runs WHERE id=?)
            """,
            (run_id,),
        )
    return True


def latest_run_for_import(import_id: int) -> dict | None:
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_runs WHERE import_id=? ORDER BY id DESC LIMIT 1",
            (import_id,),
        ).fetchone()
    return as_dict(row) if row else None


def mark_run_started(run_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE analysis_runs SET status='running', started_at=? WHERE id=?",
            (now_iso(), run_id),
        )
        conn.execute(
            "UPDATE imports SET status='running' WHERE id=(SELECT import_id FROM analysis_runs WHERE id=?)",
            (run_id,),
        )


def mark_run_failed(run_id: int, error: str) -> None:
    completed_at = now_iso()
    with transaction() as conn:
        conn.execute(
            "UPDATE analysis_runs SET status='failed', error=?, completed_at=? WHERE id=?",
            (error, completed_at, run_id),
        )
        conn.execute(
            "UPDATE imports SET status='failed', completed_at=? WHERE id=(SELECT import_id FROM analysis_runs WHERE id=?)",
            (completed_at, run_id),
        )


def mark_run_completed(run_id: int, snapshot: dict, summary: dict) -> None:
    completed_at = now_iso()
    with transaction() as conn:
        conn.execute(
            "UPDATE analysis_runs SET status='completed', completed_at=? WHERE id=?",
            (completed_at, run_id),
        )
        conn.execute(
            """
            UPDATE imports
            SET status='completed', completed_at=?, snapshot_json=?, summary_json=?
            WHERE id=(SELECT import_id FROM analysis_runs WHERE id=?)
            """,
            (completed_at, json_dumps(snapshot), json_dumps(summary), run_id),
        )


def record_import_files(import_id: int, files: list[dict], source_type: str) -> None:
    ts = now_iso()
    rows = [
        (
            import_id,
            file["category"],
            file["logical_name"],
            file["path"],
            source_type,
            file["sha256"],
            int(file["size"]),
            ts,
        )
        for file in files
    ]
    if not rows:
        return
    with transaction() as conn:
        conn.executemany(
            """
            INSERT INTO import_files(
              import_id, category, logical_name, relative_path,
              source_type, content_sha256, size_bytes, created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(import_id, relative_path) DO UPDATE SET
              category=excluded.category,
              logical_name=excluded.logical_name,
              source_type=excluded.source_type,
              content_sha256=excluded.content_sha256,
              size_bytes=excluded.size_bytes
            """,
            rows,
        )


def list_import_files(import_id: int) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            """
            SELECT * FROM import_files
            WHERE import_id=?
            ORDER BY relative_path
            """,
            (import_id,),
        ).fetchall()
    return [as_dict(row) for row in rows]
