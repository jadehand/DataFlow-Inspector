from __future__ import annotations

from pathlib import Path

from .connection import transaction


def migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _reject_legacy_schema(conn) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='imports'"
    ).fetchone()
    if not exists:
        return
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(imports)").fetchall()}
    if "analysis" in columns and "snapshot_json" not in columns:
        raise RuntimeError(
            "legacy database schema detected; this release is intentionally incompatible "
            "with the old imports.analysis model. Start with a new DFI_DB_PATH and preserve "
            "the old database as a backup."
        )


def apply_migrations() -> None:
    with transaction() as conn:
        _reject_legacy_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version(
              version TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_version").fetchall()
        }
        for path in sorted(migrations_dir().glob("*.sql")):
            if path.name in applied:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES(?, datetime('now'))",
                (path.name,),
            )
