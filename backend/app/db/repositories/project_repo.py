from __future__ import annotations

from ..connection import transaction
from ...services.common import as_dict, now_iso


def list_projects() -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [as_dict(row) for row in rows]


def create_project(name: str, description: str = "", dialect: str = "gaussdb_dws") -> dict:
    created_at = now_iso()
    with transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO projects(name, description, dialect, created_at, updated_at)
            VALUES(?,?,?,?,?)
            """,
            (name, description, dialect, created_at, created_at),
        )
        row = conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()
    return as_dict(row)


def get_project(project_id: int) -> dict | None:
    with transaction() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return as_dict(row) if row else None


def ensure_project(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise LookupError("project not found")
    return project
