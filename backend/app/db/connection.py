from __future__ import annotations

try:
    import sqlite3
except ModuleNotFoundError:  # pragma: no cover
    import pysqlite3 as sqlite3

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..core.config import get_settings


def ensure_data_dirs() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.imports_dir.mkdir(parents=True, exist_ok=True)


def db_path() -> Path:
    return get_settings().db_path


def connect() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
